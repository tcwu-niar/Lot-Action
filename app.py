import streamlit as st
import pandas as pd
import datetime
from streamlit_filesconnection import FilesConnection

# 網頁基礎設定
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統")
st.markdown("---")

# 讀取加密的 Google Sheet 網址
BASE_URL = st.secrets.get("gsheet_url", "")

if not BASE_URL:
    st.warning("⚠️ 請至 Streamlit Secrets 設定 `gsheet_url`（需移除末尾的 /edit...）")
    st.stop()

# 轉換讀取特定工作表的網址
ROUTE_URL = f"{BASE_URL}/gviz/tq?tqx=out:csv&sheet=route_template"
STATUS_URL = f"{BASE_URL}/gviz/tq?tqx=out:csv&sheet=wafer_status"

@st.cache_data(ttl=5) # 5秒快取，方便即時重新整理
def load_data():
    conn = st.connection("gcs", type=FilesConnection)
    try:
        route_df = conn.read(ROUTE_URL, input_format="csv")
        status_df = conn.read(STATUS_URL, input_format="csv")
        # 確保型態
        status_df["Step_No"] = pd.to_numeric(status_df["Step_No"], errors='coerce').fillna(1).astype(int)
        route_df["Step_No"] = pd.to_numeric(route_df["Step_No"], errors='coerce').fillna(1).astype(int)
        return route_df, status_df
    except Exception as e:
        st.error(f"資料庫讀取失敗: {e}")
        return pd.DataFrame(), pd.DataFrame()

route_template, wafer_status = load_data()

# 側邊欄導覽
menu = st.sidebar.radio("🧭 系統功能切換", ["📋 頁面一：Full Route & 即時狀態", "📜 頁面二：Wafer History"])

# 輔助函式：計算 Hold Time (hh:mm:ss)
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
        # 抓取該 Wafer 的最新一筆狀態紀錄
        current_wafer_info = wafer_status[wafer_status["Wafer_ID"] == search_wafer]
        
        if not current_wafer_info.empty:
            latest_info = current_wafer_info.sort_values(by="Timestamp").iloc[-1]
            current_step = int(latest_info["Step_No"])
            shuttle_name = latest_info["Shuttle_Name"]
            status_val = latest_info["Status"]
            customer_val = latest_info["Customer"]
            hold_start = latest_info["Hold_Start_Time"]
        else:
            # 若無歷史紀錄，給予初始預設值
            current_step = 1
            shuttle_name = "Unknown_Shuttle"
            status_val = "INPR"
            customer_val = "Unknown_Cust"
            hold_start = ""

        # ---- (中) 呈現 Full Route 項目 ----
        st.markdown("---")
        st.subheader("🛤️ (中) 完整製程路由監控 (Full Route - 共 92 步)")
        
        # 複製路由範本並整合該 Wafer 資訊
        full_route_df = route_template.copy()
        full_route_df["Wafer_ID"] = search_wafer
        full_route_df["Shuttle_Name"] = shuttle_name
        
        # 調整欄位順序以符合需求
        full_route_df = full_route_df[[
            "Wafer_ID", "Shuttle_Name", "Step_No", 
            "Step_Description", "Process_Tool", "Stage_Owner"
        ]].sort_values("Step_No")
        
        # 標示出當前在哪一步驟 (Highlight)
        def highlight_current_step(row):
            if row["Step_No"] == current_step:
                return ['background-color: #ffe6e6; font-weight: bold; color: black'] * len(row)
            elif row["Step_No"] < current_step:
                return ['background-color: #f2f2f2; color: #888888'] * len(row) # 已完成
            return [''] * len(row)
            
        st.dataframe(
            full_route_df.style.apply(highlight_current_step, axis=1), 
            use_container_width=True, 
            height=400
        )

        # ---- (下) 呈現 Status 區塊與更新機制 ----
        st.markdown("---")
        st.subheader("📊 (下) 當前即時狀態指標")
        
        # 計算 Hold Time
        computed_hold_time = calculate_hold_time(hold_start) if status_val == "Hold" else "00:00:00"
        
        # 使用指標卡片排版
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("當前狀態 (Status)", status_val)
        c2.metric("客戶名稱 (Customer)", customer_val)
        c3.metric("雪梭名稱 (Shuttle Name)", shuttle_name)
        c4.metric("暫停計時 (Hold Time)", computed_hold_time, help="狀態為 Hold 時開始累計時間")
        
        # 加值功能：允許操作員直接在網頁更新此 Wafer 的下一步製程狀態
        with st.expander("🛠️ 操作面板：過站或更新此 Wafer 狀態"):
            with st.form("update_status_form"):
                col_a, col_b = st.columns(2)
                with col_a:
                    next_status = st.selectbox("變更狀態", ["INPR", "Hold", "Pass", "Scrap"], index=["INPR", "Hold", "Pass", "Scrap"].index(status_val) if status_val in ["INPR", "Hold", "Pass", "Scrap"] else 0)
                    next_step = st.number_input("前進製程步數 (Step No.)", min_value=1, max_value=92, value=current_step)
                with col_b:
                    input_cust = st.text_input("更新客戶名稱", value=customer_val)
                    input_shuttle = st.text_input("更新 Shuttle Name", value=shuttle_name)
                
                btn = st.form_submit_button("💾 提交過站紀錄並同步至 Google Sheets")
                
                if btn:
                    conn = st.connection("gcs", type=FilesConnection)
                    # 如果變成 Hold，紀錄當下時間；如果不是則清空
                    new_hold_start = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if next_status == "Hold" else ""
                    
                    new_log = pd.DataFrame([{
                        "Wafer_ID": search_wafer,
                        "Lot_ID": latest_info["Lot_ID"] if 'latest_info' in locals() else "LOT-UNKNOWN",
                        "Shuttle_Name": input_shuttle,
                        "Step_No": int(next_step),
                        "Status": next_status,
                        "Customer": input_cust,
                        "Hold_Start_Time": new_hold_start,
                        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    
                    updated_status_df = pd.concat([wafer_status, new_log], ignore_index=True)
                    conn.write(STATUS_URL, updated_status_df, index=False)
                    st.success(f"🎉 晶圓 {search_wafer} 已成功更新至第 {next_step} 步 ({next_status})！")
                    st.cache_data.clear()
                    st.rerun()
    else:
        st.info("💡 請在上方輸入 Wafer ID（例如：W01），系統將自動調取 92 步全路由與實時 Hold Time。")

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產變更紀錄總覽 (Wafer History)")
    st.markdown("本頁面展示資料庫中所有晶圓過站、Hold 紀錄、報廢 (Scrap) 的完整流水帳，方便進行生產追溯。")
    
    if not wafer_status.empty:
        # 按時間最新到最舊排序
        display_history = wafer_status.sort_values(by="Timestamp", ascending=False)
        
        # 提供全局關鍵字搜尋 (可以搜特定的 Wafer, Customer 或 Status)
        search_query = st.text_input("🔍 輸入關鍵字篩選歷史清單 (如特定 Wafer ID 或 Status)：")
        if search_query:
            display_history = display_history[
                display_history.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
            ]
            
        st.dataframe(display_history, use_container_width=True)
    else:
        st.warning("🗄️ 目前雲端資料庫中尚無任何歷史生產紀錄。")
