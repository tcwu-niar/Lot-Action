import streamlit as st
import pandas as pd
import datetime

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統")
st.markdown("---")

# ==================== 2. 自動串接您的 Google Sheet 公開網址 ====================
PUBLIC_GSHEET_BASE_URL = "https://google.com"

ROUTE_URL = f"{PUBLIC_GSHEET_BASE_URL}/gviz/tq?tqx=out:csv&sheet=route_template"
STATUS_URL = f"{PUBLIC_GSHEET_BASE_URL}/gviz/tq?tqx=out:csv&sheet=wafer_status"

@st.cache_data(ttl=2) # 2秒快取
def load_data():
    try:
        route_df = pd.read_csv(ROUTE_URL)
        status_df = pd.read_csv(STATUS_URL)
        
        # 強制轉換關鍵欄位型態，避免比對因字串或浮點數出錯
        if not status_df.empty and "Step_No" in status_df.columns:
            status_df["Step_No"] = pd.to_numeric(status_df["Step_No"], errors='coerce').fillna(1).astype(int)
        if not route_df.empty and "Step_No" in route_df.columns:
            route_df["Step_No"] = pd.to_numeric(route_df["Step_No"], errors='coerce').fillna(1).astype(int)
        return route_df, status_df
    except Exception as e:
        st.error(f"❌ 讀取失敗。請確認您的 Google Sheet 開啟權限（任何人皆可編輯），且工作表名稱是否為 'route_template' 與 'wafer_status'。錯誤訊息: {e}")
        return pd.DataFrame(), pd.DataFrame()

route_template, wafer_status = load_data()

# ==================== 3. 側邊欄功能導覽（新增第三頁） ====================
menu = st.sidebar.radio("🧭 系統功能切換", [
    "📋 頁面一：Full Route & 即時狀態", 
    "📜 頁面二：Wafer History",
    "📤 頁面三：上傳新路由檔案"
])

# 輔助功能：動態秒級計算 Hold Time (hh:mm:ss)
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

        # ---- (中) 呈現 Full Route 項目 ----
        st.markdown("---")
        st.subheader("🛤️ (中) 完整製程路由監控 (Full Route - 共 92 步)")
        
        if not route_template.empty:
            full_route_df = route_template.copy()
            full_route_df["Wafer_ID"] = search_wafer
            full_route_df["Shuttle_Name"] = shuttle_name
            
            # 對應您上傳的真實 CSV 檔案欄位
            full_route_df = full_route_df.rename(columns={
                "Step_No": "Step No.",
                "Step_Description": "Step Description",
                "Process_Tool": "Process Tool",
                "Stage_Owner": "Stage Owner"
            })
            
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
        else:
            st.error("⚠️ 無法載入路由範本，請至『頁面三』上傳製程路由 CSV 檔案。")

        # ---- (下) 呈現 Status 區塊 ----
        st.markdown("---")
        st.subheader("📊 (下) 當前即時狀態指標")
        computed_hold_time = calculate_hold_time(hold_start) if status_val == "Hold" else "00:00:00"
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("當前狀態 (Status)", status_val)
        c2.metric("客戶名稱 (Customer)", customer_val)
        c3.metric("雪梭名稱 (Shuttle Name)", shuttle_name)
        c4.metric("暫停計時 (Hold Time)", computed_hold_time)
        
        st.info("💡 提示：若要更新目前晶圓過站，請直接在試算表的 'wafer_status' 表最下方填入最新站別紀錄。")
    else:
        st.info("💡 請在上方空格中輸入 Wafer ID，系統將自動調取 92 步全路由與實時狀態看板。")

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產變更紀錄總覽 (Wafer History)")
    if not wafer_status.empty:
        display_history = wafer_status.copy()
        if "Timestamp" in display_history.columns:
            display_history = display_history.sort_values(by="Timestamp", ascending=False)
            
        search_query = st.text_input("🔍 輸入關鍵字篩選歷史清單 (如特定 Wafer ID、Status)：")
        if search_query:
            display_history = display_history[display_history.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
        st.dataframe(display_history, use_container_width=True)
    else:
        st.warning("🗄️ 目前雲端試算表中尚無任何歷史生產紀錄資料。")

# ==================== 📤 頁面三：上傳新路由檔案 (NEW) ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案")
    st.markdown("您可以在此上傳包含 92 步流程的廠內原始 CSV 報表。系統會自動過濾並對應欄位後，提示您更新至 Google Sheets 中。")
    
    # 建立上傳檔案小工具
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"])
    
    if uploaded_file is not None:
        try:
            # 讀取使用者上傳的檔案
            raw_df = pd.read_csv(uploaded_file)
            st.success("🎉 檔案上傳讀取成功！")
            
            st.write("📋 原始上傳資料預覽：")
            st.dataframe(raw_df.head(5), use_container_width=True)
            
            # 欄位自動對應轉換
            # 將上傳的「Step」對應為系統的「Step_No」
            # 將「Step description」對應為「Step_Description」
            # 將「Tool name/mask」對應為「Process_Tool」
            # 將「Owner」對應為「Stage_Owner」
            rename_dict = {
                "Step": "Step_No",
                "Step description": "Step_Description",
                "Tool name/mask": "Process_Tool",
                "Owner": "Stage_Owner"
            }
            
            # 檢查必要欄位是否存在
            missing_cols = [key for key in rename_dict.keys() if key not in raw_df.columns]
            
            if len(missing_cols) == 0:
                # 擷取對應欄位並清理
                processed_df = raw_df[list(rename_dict.keys())].rename(columns=rename_dict)
                processed_df = processed_df.drop_duplicates(subset=["Step_No"]).sort_values("Step_No")
                
                st.markdown("---")
                st.markdown("### ⚙️ 轉換為系統標準結構：")
                st.dataframe(processed_df, use_container_width=True)
                
                st.info("💡 提示：因為目前的系統架構使用公開讀取網址，若要把這份新路由格式永久儲存，請直接將此轉換後的表格內容「複製並貼上」到您 Google Sheet 的 **`route_template`** 工作表中，這樣第一頁的 92 步清單就會立刻全面更新！")
            else:
                st.error(f"❌ 上傳失敗。檔案中缺少必要的欄位：{missing_cols}，請確認是否與原始格式相符。")
                
        except Exception as e:
            st.error(f"❌ 解析檔案時發生異常: {e}")
