import streamlit as st
import pandas as pd
import datetime

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統")
st.markdown("---")

# ==================== 2. 自動串接您的 Google Sheet 公開網址 ====================
# 已直接填入您的試算表 ID
PUBLIC_GSHEET_BASE_URL = "https://docs.google.com/spreadsheets/d/1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"

# 利用 Pandas 直接將公開試算表轉為 CSV 格式讀取
ROUTE_URL = f"{PUBLIC_GSHEET_BASE_URL}/gviz/tq?tqx=out:csv&sheet=route_template"
STATUS_URL = f"{PUBLIC_GSHEET_BASE_URL}/gviz/tq?tqx=out:csv&sheet=wafer_status"

@st.cache_data(ttl=2) # 2秒快取，兼顧更新即時性與讀取效能
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

# ==================== 3. 側邊欄功能導覽 ====================
menu = st.sidebar.radio("🧭 系統功能切換", ["📋 頁面一：Full Route & 即時狀態", "📜 頁面二：Wafer History"])

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
    
    # 建立輸入 Wafer ID 的空格
    search_wafer = st.text_input("請輸入 晶圓編號 (Wafer ID) 並按下 Enter：", placeholder="例如: W01").strip()
    
    if search_wafer:
        # 撈取該 Wafer 在狀態資料庫中的最新一筆進度
        current_wafer_info = wafer_status[wafer_status["Wafer_ID"] == search_wafer] if not wafer_status.empty else pd.DataFrame()
        
        if not current_wafer_info.empty:
            latest_info = current_wafer_info.sort_values(by="Timestamp").iloc[-1]
            current_step = int(latest_info["Step_No"]) if "Step_No" in latest_info else 1
            shuttle_name = latest_info["Shuttle_Name"] if "Shuttle_Name" in latest_info else "Unknown"
            status_val = latest_info["Status"] if "Status" in latest_info else "INPR"
            customer_val = latest_info["Customer"] if "Customer" in latest_info else "Unknown"
            hold_start = latest_info["Hold_Start_Time"] if "Hold_Start_Time" in latest_info else ""
        else:
            # 查無紀錄時的全新晶圓預設初始狀態
            current_step = 1
            shuttle_name = "New_Shuttle"
            status_val = "INPR"
            customer_val = "New_Customer"
            hold_start = ""

        # ---- (中) 呈現 Full Route 項目 ----
        st.markdown("---")
        st.subheader("🛤️ (中) 完整製程路由監控 (Full Route - 共 92 步)")
        
        if not route_template.empty:
            full_route_df = route_template.copy()
            full_route_df["Wafer_ID"] = search_wafer
            full_route_df["Shuttle_Name"] = shuttle_name
            
            # 配合使用者要求的欄位結構與排版順序
            available_cols = ["Wafer_ID", "Shuttle_Name", "Step_No", "Step_Description", "Process_Tool", "Stage_Owner"]
            display_cols = [col for col in available_cols if col in full_route_df.columns]
            full_route_df = full_route_df[display_cols].sort_values("Step_No")
            
            # CSS 樣式：高亮標示當前製程站別 (淡粉色背景)
            def highlight_current_step(row):
                if "Step_No" in row and row["Step_No"] == current_step:
                    return ['background-color: #ffe6e6; font-weight: bold; color: black'] * len(row)
                elif "Step_No" in row and row["Step_No"] < current_step:
                    return ['background-color: #f2f2f2; color: #888888'] * len(row)
                return [''] * len(row)
                
            st.dataframe(full_route_df.style.apply(highlight_current_step, axis=1), use_container_width=True, height=400)
        else:
            st.error("⚠️ 無法載入路由範本，請確認您的 Google Sheet 中 'route_template' 工作表第一行是否有對應欄位資料。")

        # ---- (下) 呈現 Status 區塊 ----
        st.markdown("---")
        st.subheader("📊 (下) 當前即時狀態指標")
        
        # 即時計算 Hold Time
        computed_hold_time = calculate_hold_time(hold_start) if status_val == "Hold" else "00:00:00"
        
        # 使用精美指標卡片呈現資訊
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("當前狀態 (Status)", status_val)
        c2.metric("客戶名稱 (Customer)", customer_val)
        c3.metric("雪梭名稱 (Shuttle Name)", shuttle_name)
        c4.metric("暫停計時 (Hold Time)", computed_hold_time)
        
        st.info("💡 系統運作方式：當前網頁已與您的 Google Sheet 自動同步。若要變更過站進度或 Hold 晶圓，請直接在試算表的 'wafer_status' 頁籤下方填入新資料，網頁會在 2 秒內動態重新載入呈現！")
    else:
        st.info("💡 請在上方空格中輸入 Wafer ID，系統將自動調取 92 步全路由與實時狀態看板。")

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產變更紀錄總覽 (Wafer History)")
    st.markdown("此頁面完整同步 Google 表單中 'wafer_status' 的所有過站事件軌跡。")
    
    if not wafer_status.empty:
        # 按時間戳記由新到舊排序
        display_history = wafer_status.copy()
        if "Timestamp" in display_history.columns:
            display_history = display_history.sort_values(by="Timestamp", ascending=False)
            
        search_query = st.text_input("🔍 輸入關鍵字篩選歷史清單 (如特定 Wafer ID、Status 或 Customer)：")
        if search_query:
            display_history = display_history[display_history.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
        st.dataframe(display_history, use_container_width=True)
    else:
        st.warning("🗄️ 目前雲端試算表中尚無任何歷史生產紀錄資料。")
