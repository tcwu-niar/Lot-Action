import streamlit as st
import pandas as pd
import datetime
import requests
import io

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (自動同步版)")
st.markdown("---")

# 💡 請在此處貼上您剛剛在 Google Sheet 產生的 Apps Script 網址
# 系統將會在您上傳 CSV 時，免金鑰自動透過此接口強制更新試算表！
GAS_SUBMIT_URL = "https://script.google.com/macros/s/AKfycbwEEZf5MjfIuLjQa_uyAr4olDIKh7k_E2cCAqqC5mfgZR1bekwcxoOnVp8M1SNG32t6/exec"

if "search_input_val" not in st.session_state:
    st.session_state.search_input_val = ""

# 您的試算表 ID
sheet_id = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

@st.cache_data(ttl=2) # 2秒快取
def fetch_cloud_data():
    route_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=route_template"
    status_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=wafer_status"
    
    r_df = pd.DataFrame(columns=["Wafer ID", "Step No.", "Step Description", "Process Tool", "Stage Owner"])
    s_df = pd.DataFrame(columns=["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"])
    
    try:
        res_r = requests.get(route_url, headers=headers, timeout=5)
        if res_r.status_code == 200:
            r_df = pd.read_csv(io.StringIO(res_r.text))
            rename_map = {"Step": "Step No.", "Step_No": "Step No.", "Step description": "Step Description", "Step_Description": "Step Description", "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", "Owner": "Stage Owner", "Stage_Owner": "Stage Owner", "Wafer ID": "Wafer ID", "Wafer_ID": "Wafer ID"}
            r_df = r_df.rename(columns=rename_map)
            if "Step No." in r_df.columns:
                r_df["Step No."] = pd.to_numeric(r_df["Step No."], errors='coerce').fillna(1).astype(int)
                
        res_s = requests.get(status_url, headers=headers, timeout=5)
        if res_s.status_code == 200:
            s_df = pd.read_csv(io.StringIO(res_s.text))
            if not s_df.empty:
                s_df.columns = ["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"]
                s_df["Step_No"] = pd.to_numeric(s_df["Step_No"], errors='coerce').fillna(1).astype(int)
    except:
        pass
    return r_df, s_df

cloud_route, cloud_status = fetch_cloud_data()

# ==================== 2. 側邊欄導覽 ====================
menu = st.sidebar.radio("🧭 系統功能切換", [
    "📋 頁面一：Full Route & 即時狀態", 
    "📜 頁面二：Wafer History",
    "📤 頁面三：上傳新路由檔案"
])

def calculate_hold_time(start_time_str):
    try:
        start_dt = datetime.datetime.strptime(str(start_time_str), "%Y-%m-%d %H:%M:%S")
        delta = datetime.datetime.now() - start_dt
        seconds = max(0, int(delta.total_seconds()))
        return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
    except:
        return "00:00:00"

# ==================== 📋 頁面一：Full Route & 即時狀態 ====================
if menu == "📋 頁面一：Full Route & 即時狀態":
    st.subheader("🔍 (上) 晶圓動態查詢")
    
    search_wafer = st.text_input("請輸入 晶圓/批次/機台/負責人 關鍵字：", value=st.session_state.search_input_val).strip()
    st.session_state.search_input_val = search_wafer

    current_step, shuttle_name, status_val, customer_val, hold_start = 1, "T18-C14A", "INPR", "蔡作敏/張振豪團隊", ""

    if search_wafer and not cloud_status.empty:
        exact_wafer_match = cloud_status[cloud_status["Wafer_ID"].astype(str) == search_wafer]
        if not exact_wafer_match.empty:
            latest_info = exact_wafer_match.sort_values(by="Timestamp").iloc[-1]
            current_step = int(latest_info["Step_No"])
            shuttle_name = latest_info["Shuttle_Name"]
            status_val = latest_info["Status"]
            customer_val = latest_info["Customer"]
            hold_start = latest_info["Hold_Start_Time"]

    st.markdown("---")
    st.subheader("🛤️ (中) 完整製程路由監控 (Full Route)")
    
    if not cloud_route.empty:
        full_route_df = cloud_route.copy()
        
        # 💡 修正 BUG：如果第一欄本來就叫 Wafer ID，就絕對不要覆寫它，維持檔案原汁原味的資料
        if "Wafer ID" not in full_route_df.columns:
            full_route_df["Wafer ID"] = "LOT4-11F0"
        if "Shuttle Name" not in full_route_df.columns:
            full_route_df["Shuttle Name"] = shuttle_name
            
        available_cols = ["Wafer ID", "Shuttle Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"]
        display_cols = [col for col in available_cols if col in full_route_df.columns]
        full_route_df = full_route_df[display_cols].sort_values("Step No.")
        
        if search_wafer:
            mask = full_route_df.astype(str).apply(lambda x: x.str.contains(search_wafer, case=False)).any(axis=1)
            filtered_route_df = full_route_df[mask]
        else:
            filtered_route_df = full_route_df.copy()

        def highlight_current_step(row):
            if "Step No." in row and row["Step No."] == current_step:
                return ['background-color: #ffe6e6; font-weight: bold; color: black'] * len(row)
            elif "Step No." in row and row["Step No."] < current_step:
                return ['background-color: #f2f2f2; color: #888888'] * len(row)
            return [''] * len(row)
            
        st.dataframe(filtered_route_df.style.apply(highlight_current_step, axis=1), use_container_width=True, height=450)
    else:
        st.warning("⚠️ 雲端目前的 route_template 工作表內尚無路由範本資料。")

    st.markdown("---")
    st.subheader("📊 (下) 當前即時狀態指標")
    computed_hold_time = calculate_hold_time(hold_start) if status_val == "Hold" else "00:00:00"
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("當前狀態 (Status)", status_val)
    c2.metric("客戶名稱 (Customer)", customer_val)
    c3.metric("雪梭名稱 (Shuttle Name)", shuttle_name)
    c4.metric("暫停計時 (Hold Time)", computed_hold_time)

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產變更紀錄總覽 (Wafer History)")
    if not cloud_status.empty:
        display_df = cloud_status.sort_values(by="Timestamp", ascending=False) if "Timestamp" in cloud_status.columns else cloud_status
        if st.session_state.search_input_val:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(st.session_state.search_input_val, case=False)).any(axis=1)]
        st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("目前雲端尚無任何過站歷史紀錄。")

# ==================== 📤 頁面三：上傳新路由檔案 ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案至雲端 (免金鑰硬核更新)")
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"])
    
    if uploaded_file is not None:
        try:
            # 讀取上傳資料
            raw_text = uploaded_file.getvalue().decode("utf-8")
            raw_df = pd.read_csv(io.StringIO(raw_text))
            
            st.write("📋 準備同步至 Google Sheets 的檔案內容預覽：")
            st.dataframe(raw_df.head(5), use_container_width=True)
            
            # 💡 核心修改：利用 requests 將整個 CSV 文字丟給您的 Google Apps Script 後台！
            if GAS_SUBMIT_URL == "YOUR_GAS_WEB_APP_URL_HERE":
                st.error("❌ 請先在程式碼第 14 行填入您的 Google Apps Script 網頁應用程式網址！")
            else:
                with st.spinner("🚀 正在繞過資安封鎖，實時覆寫更新 Google Sheets 雲端資料庫..."):
                    response = requests.post(GAS_SUBMIT_URL, data=raw_text.encode('utf-8'), headers={"Content-Type": "text/plain"})
                    
                    if response.text == "SUCCESS":
                        st.success("🎉 自動更新成功！92 步製程數據已成功同步覆寫至 Google Sheet 中！")
                        st.cache_data.clear() # 清除快取讓第一頁立刻拿到最新資料
                    else:
                        st.error(f"❌ 雲端更新拒絕。錯誤回報: {response.text}")
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
