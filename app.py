import streamlit as st
import pandas as pd
import datetime
import requests
import io

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (純淨資安版)")
st.markdown("---")

# 💡 鎖定核心需求 1：將搜尋框的值存在記憶體 (Session State) 中，切換分頁絕對不被清空
if "search_input_val" not in st.session_state:
    st.session_state.search_input_val = ""

# ==================== 2. 安全讀取您的公開 Google Sheet ====================
sheet_id = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"

# 模擬標準網頁表頭，避開公司網路可能產生的域名請求卡頓
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

@st.cache_data(ttl=2) # 💡 每 2 秒自動清除快取，同仁在 Sheet 改了什麼，網頁 2 秒內自動同步！
def fetch_cloud_data():
    route_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=route_template"
    status_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=wafer_status"
    
    # 建立空的預設結構，防止讀取失敗時網頁死當
    r_df = pd.DataFrame(columns=["Wafer ID", "Step No.", "Step Description", "Process Tool", "Stage Owner"])
    s_df = pd.DataFrame(columns=["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"])
    
    try:
        # 讀取 92 步全路由模板
        res_r = requests.get(route_url, headers=headers, timeout=5)
        if res_r.status_code == 200:
            r_df = pd.read_csv(io.StringIO(res_r.text))
            rename_map = {
                "Step": "Step No.", "Step_No": "Step No.", 
                "Step description": "Step Description", "Step_Description": "Step Description", 
                "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", 
                "Owner": "Stage Owner", "Stage_Owner": "Stage Owner", 
                "Wafer ID": "Wafer ID", "Wafer_ID": "Wafer ID"
            }
            r_df = r_df.rename(columns=rename_map)
            if "Step No." in r_df.columns:
                r_df["Step No."] = pd.to_numeric(r_df["Step No."], errors='coerce').fillna(1).astype(int)
                
        # 讀取最新晶圓過站歷史
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

# ==================== 3. 側邊欄導覽 ====================
menu = st.sidebar.radio("🧭 系統功能切換", [
    "📋 頁面一：Full Route & 即時狀態", 
    "📜 頁面二：Wafer History",
    "📤 頁面三：上傳新路由檔案"
])

# 輔助功能：秒級即時動態計算 Hold Time
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
    
    # 💡 鎖定核心需求 2：文字輸入框，讀取記憶體內的值，且切換分頁完內容原封不動保留
    search_wafer = st.text_input(
        "請輸入 晶圓/批次/機台/負責人 關鍵字：", 
        value=st.session_state.search_input_val,
        placeholder="輸入後 Enter 即可啟動模糊搜尋與過站高亮..."
    ).strip()
    st.session_state.search_input_val = search_wafer # 存回記憶體

    # 定義預設底層指標
    current_step, shuttle_name, status_val, customer_val, hold_start = 1, "T18-C14A", "INPR", "蔡作敏/張振豪團隊", ""

    # 💡 只有當「精準匹配」到過站資料庫中的 Wafer_ID 時，下方指標卡片才調取它的最新狀態
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
        
        # 💡 核心修正：如果 CSV 原始讀出來就有「Wafer ID」或「Shuttle Name」，直接保留它！
        # 徹底解決上一版「打字導致下面 Wafer ID 欄位整排被改掉」的錯誤 Bug。
        if "Wafer ID" not in full_route_df.columns:
            full_route_df["Wafer ID"] = "LOT4-11F0"
        if "Shuttle Name" not in full_route_df.columns:
            full_route_df["Shuttle Name"] = shuttle_name
            
        # 調整顯示順序與排版
        available_cols = ["Wafer ID", "Shuttle Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"]
        display_cols = [col for col in available_cols if col in full_route_df.columns]
        full_route_df = full_route_df[display_cols].sort_values("Step No.")
        
        # 💡 核心需求 3：採用模糊搜尋過濾表格
        # 如果打字，只要任一欄位（如機台 DISCO、負責人 Bill）有關鍵字，就列出該行；不打字則預設全秀
        if search_wafer:
            mask = full_route_df.astype(str).apply(lambda x: x.str.contains(search_wafer, case=False)).any(axis=1)
            filtered_route_df = full_route_df[mask]
        else:
            filtered_route_df = full_route_df.copy()

        # 表格高亮渲染邏輯（當前站別變色反白、已完成變灰色）
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
    
    # 呈現四大指標卡片
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("當前狀態 (Status)", status_val)
    c2.metric("客戶名稱 (Customer)", customer_val)
    c3.metric("雪梭名稱 (Shuttle Name)", shuttle_name)
    c4.metric("暫停計時 (Hold Time)", computed_hold_time)
    
    st.info("🔒 廠內資安合規提示：本網頁為『即時大螢幕看板』。若需要讓晶圓過站、Hold 或修改狀態，請直接前往您的 Google Sheet 試算表的 `wafer_status` 工作表最下方填入最新數據，本網頁將在 2 秒內動態自動重新載入並反白呈現！")

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產變更紀錄總覽 (Wafer History)")
    
    # 同步第一頁打的關鍵字，在歷史紀錄頁籤進行同步模糊篩選
    if st.session_state.search_input_val:
        st.info(f"💡 目前正依據您的記憶體關鍵字 『{st.session_state.search_input_val}』 進行同步篩選。")
        
    if not cloud_status.empty:
        display_df = cloud_status.sort_values(by="Timestamp", ascending=False) if "Timestamp" in cloud_status.columns else cloud_status
        if st.session_state.search_input_val:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(st.session_state.search_input_val, case=False)).any(axis=1)]
        st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("目前雲端尚無任何過站歷史紀錄。")

# ==================== 📤 頁面三：上傳新路由檔案 ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案")
    st.info("💡 提示：本區塊供本地預覽。若需永久儲存您全新的 92 步製程範本，請將此處轉換後的表格內容複製，並貼上至您 Google Sheet 的 `route_template` 工作表中。")
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"])
    if uploaded_file is not None:
        try:
            raw_df = pd.read_csv(uploaded_file)
            rename_map = {"Step": "Step No.", "Step description": "Step Description", "Tool name/mask": "Process Tool", "Owner": "Stage Owner"}
            processed = raw_df.rename(columns=rename_map)
            st.dataframe(processed, use_container_width=True)
            st.success("🎉 檔案解析與欄位轉換成功！")
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
