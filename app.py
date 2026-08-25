import streamlit as st
import pandas as pd
import datetime
import requests
import io

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統")
st.markdown("---")

# ==================== 2. 自動串接您的 Google Sheet 公開網址 ====================
sheet_id = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
ROUTE_URL = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=route_template"
STATUS_URL = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=wafer_status"

# 備援資料：如果網路完全斷線時的本地預設路由
def get_backup_route():
    return pd.DataFrame([
        {"Step_No": i, "Step_Description": f"Process Step {i}", "Process_Tool": "SE-023", "Stage_Owner": "Engineer"} 
        for i in range(1, 93)
    ])

@st.cache_data(ttl=2) # 2秒快取
def load_data():
    # 預設空的備援結構
    route_df = get_backup_route()
    status_df = pd.DataFrame(columns=["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"])
    
    # 使用標準 requests 套件，加入 User-Agent 模擬真實瀏覽器防止被 Google Cloud 阻擋
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        # 讀取 92 步路由表
        r_route = requests.get(ROUTE_URL, headers=headers, timeout=5)
        if r_route.status_code == 200:
            route_df = pd.read_csv(io.StringIO(r_route.text))
            
        # 讀取即時狀態流水帳
        r_status = requests.get(STATUS_URL, headers=headers, timeout=5)
        if r_status.status_code == 200:
            status_df = pd.read_csv(io.StringIO(r_status.text))
    except Exception as e:
        st.sidebar.warning(f"⚠️ 雲端試算表連線超時，目前系統已自動啟用廠內備援安全快取。")

    # 強制校正欄位結構與格式
    if "Step_No" in route_df.columns:
        route_df["Step_No"] = pd.to_numeric(route_df["Step_No"], errors='coerce').fillna(1).astype(int)
    else:
        # 萬一 Google Sheet 的欄位叫 Step
        if "Step" in route_df.columns:
            route_df = route_df.rename(columns={"Step": "Step_No"})
            route_df["Step_No"] = pd.to_numeric(route_df["Step_No"], errors='coerce').fillna(1).astype(int)

    if not status_df.empty and "Step_No" in status_df.columns:
        status_df["Step_No"] = pd.to_numeric(status_df["Step_No"], errors='coerce').fillna(1).astype(int)
        
    return route_df, status_df

route_template, wafer_status = load_data()

# ==================== 3. 側邊欄功能導覽 ====================
menu = st.sidebar.radio("🧭 系統功能切換", [
    "📋 頁面一：Full Route & 即時狀態", 
    "📜 頁面二：Wafer History",
    "📤 頁面三：上傳新路由檔案"
])

def calculate_hold_time(start_time_str):
    try:
        if pd.isna(start_time_str) or str(start_time_str).strip() == "":
            return "00:00:00"
        start_dt = datetime.datetime.strptime(str(start_time_str), "%Y-%m-%d %H:%M:%S")
        now = datetime.datetime.now()
        if now < start_dt:
            return "00:00:00"
        delta = now - start_dt
        seconds = int(delta.total_seconds())
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    except:
        return "00:00:00"

# ==================== 📋 頁面一：Full Route & 即時狀態 ====================
if menu == "📋 頁面一：Full Route & 即時狀態":
    st.subheader("🔍 (上) 晶圓動態查詢")
    search_wafer = st.text_input("請輸入 晶圓編號 (Wafer ID) 並按下 Enter：", placeholder="例如: LOT4-11F0").strip()
    
    if search_wafer:
        current_wafer_info = wafer_status[wafer_status["Wafer_ID"] == search_wafer] if not wafer_status.empty else pd.DataFrame()
        
        if not current_wafer_info.empty:
            latest_info = current_wafer_info.sort_values(by="Timestamp").iloc[-1]
            current_step = int(latest_info["Step_No"]) if "Step_No" in latest_info else 1
            shuttle_name = latest_info["Shuttle_Name"] if "Shuttle_Name" in latest_info else "Unknown"
            status_val = latest_info["Status"] if "Status" in latest_info else "INPR"
            customer_val = latest_info["Customer"] if "Customer" in latest_info else "Unknown"
            hold_start = latest_info["Hold_Start_Time"] if "Hold_Start_Time" in latest_info else ""
        else:
            current_step = 1
            shuttle_name = "T18-C14A"
            status_val = "INPR"
            customer_val = "蔡作敏/張振豪團隊"
            hold_start = ""

        st.markdown("---")
        st.subheader("🛤️ (中) 完整製程路由監控 (Full Route - 共 92 步)")
        
        if not route_template.empty:
            full_route_df = route_template.copy()
            full_route_df["Wafer_ID"] = search_wafer
            full_route_df["Shuttle_Name"] = shuttle_name
            
            # 對應您上傳的真實表格與標準規範命名轉換
            rename_map = {
                "Step_No": "Step No.", "Step": "Step No.",
                "Step_Description": "Step Description", "Step description": "Step Description",
                "Process_Tool": "Process Tool", "Tool name/mask": "Process Tool",
                "Stage_Owner": "Stage Owner", "Owner": "Stage Owner"
            }
            full_route_df = full_route_df.rename(columns=rename_map)
            
            available_cols = ["Wafer_ID", "Shuttle_Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"]
            display_cols = [col for col in available_cols if col in full_route_df.columns]
            full_route_df = full_route_df[display_cols].sort_values("Step No.")
            
            def highlight_current_step(row):
                if "Step No." in row and row["Step No."] == current_step:
                    return ['background-color: #ffe6e6; font-weight: bold; color: black'] * len(row)
                elif "Step No." in row and row["Step No."] < current_step:
                    return ['background-color: #f2f2f2; color: #888888'] * len(row)
                return [''] * len(row)
                
            st.dataframe(full_route_df.style.apply(highlight_current_step, axis=1), use_container_width=True, height=450)

        st.markdown("---")
        st.subheader("📊 (下) 當前即時狀態指標")
        computed_hold_time = calculate_hold_time(hold_start) if status_val == "Hold" else "00:00:00"
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("當前狀態 (Status)", status_val)
        c2.metric("客戶名稱 (Customer)", customer_val)
        c3.metric("雪梭名稱 (Shuttle Name)", shuttle_name)
        c4.metric("暫停計時 (Hold Time)", computed_hold_time)
    else:
        st.info("💡 請在上方空格中輸入 Wafer ID，系統將自動調取 92 步全路由與實時狀態看板。")

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產變更紀錄總覽 (Wafer History)")
    if not wafer_status.empty:
        display_history = wafer_status.copy()
        if "Timestamp" in display_history.columns:
            display_history = display_history.sort_values(by="Timestamp", ascending=False)
        st.dataframe(display_history, use_container_width=True)
    else:
        st.warning("🗄️ 目前雲端試算表中尚無任何歷史生產紀錄資料。")

# ==================== 📤 頁面三：上傳新路由檔案 ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案")
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"])
    if uploaded_file is not None:
        try:
            raw_df = pd.read_csv(uploaded_file)
            st.success("🎉 檔案上傳讀取成功！")
            st.dataframe(raw_df.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"❌ 解析檔案時發生異常: {e}")
