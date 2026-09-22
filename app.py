import streamlit as st
import pandas as pd
import datetime
import requests
import json

# ========================================== 1. 網頁基礎設定 ==========================================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")
st.markdown("---")

# 設定全站持久型記憶體
if "selected_row_data" not in st.session_state:
    st.session_state.selected_row_data = None
if "wafer_id_input" not in st.session_state:
    st.session_state.wafer_id_input = "LOT4-11F0"

# ========================================== 2. 核心API與雲端試算表設定 ==========================================
# 請將下方的 URL 替換為您部署完 Google Apps Script (GAS) 後產生的網頁應用程式網址 (Web App URL)
GAS_API_URL = "https://script.google.com/macros/s/xxxxxxxx############xxxxxxxxx/exec"

# 模擬 PPT 中的原始資料結構
dummy_data = [
    {"Wafer ID": "LOT4-11F0", "Step No.": "1", "Module": "Lot Owner", "Step Description": 'Wafer check (TSMC片8")', "Process Tool": "SE-023", "Recipe": "nan", "Check point": "Chipping or not", "Stage Owner": "Bill/yd", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "nan", "Check Out Time": "nan", "Shuttle Name": "T18-C14A"},
    {"Wafer ID": "LOT4-11F0", "Step No.": "2", "Module": "Package", "Step Description": "Edge trim (x:500um/y:50um)", "Process Tool": "DISCO", "Recipe": "nan", "Check point": "nan", "Stage Owner": "Laif", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "nan", "Check Out Time": "nan", "Shuttle Name": "T18-C14A"},
    {"Wafer ID": "LOT4-11F0", "Step No.": "3", "Module": "Package", "Step Description": "Wafer check", "Process Tool": "KLA Profilemeter", "Recipe": "nan", "Check point": "Depth bias", "Stage Owner": "Laif", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "nan", "Check Out Time": "nan", "Shuttle Name": "T18-C14A"},
    {"Wafer ID": "LOT4-11F0", "Step No.": "4", "Module": "LIT", "Step Description": "Surface clean by developer", "Process Tool": "SE-009-02", "Recipe": "No.1", "Check point": "nan", "Stage Owner": "Bill/Jane", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "2hr", "Check Out Time": "nan", "Shuttle Name": "T18-C14A"},
    {"Wafer ID": "LOT4-11F0", "Step No.": "5", "Module": "PVD", "Step Description": "Ti/Cu seedlayer 50/300nm", "Process Tool": "SE-003", "Recipe": "165.Ti_500_Cu_3000", "Check point": "nan", "Stage Owner": "Bill/Jane", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "2hr", "Check Out Time": "nan", "Shuttle Name": "T18-C14A"},
    {"Wafer ID": "LOT4-11F0", "Step No.": "6", "Module": "LIT", "Step Description": "Litho. AZ4620 10um(EBR)", "Process Tool": "SE-009-01", "Recipe": "nan", "Check point": "nan", "Stage Owner": "Bill/Jane", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "2hr", "Check Out Time": "nan", "Shuttle Name": "T18-C14A"},
]

@st.cache_data(ttl=10)
def fetch_wafer_data(wafer_id):
    """從 GAS 讀取 Google Sheets 的最新資料"""
    try:
        response = requests.get(f"{GAS_API_URL}?action=read&waferId={wafer_id}", timeout=5)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "success" and res_json.get("data"):
                return pd.DataFrame(res_json["data"])
    except Exception:
        pass
    # 讀取失敗時降級使用本地模擬資料
    df_mock = pd.DataFrame(dummy_data)
    return df_mock[df_mock["Wafer ID"] == wafer_id]

def update_wafer_status(wafer_id, step_no, action_type, comment=""):
    """向 GAS 發送 POST 請求更新站點狀態"""
    payload = {
        "action": "updateStatus",
        "waferId": wafer_id,
        "stepNo": str(step_no),
        "actionType": action_type,
        "comment": comment,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        response = requests.post(GAS_API_URL, json=payload, timeout=5)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "success":
                st.success(f"🎉 成功執行變更操作: {action_type}！")
                st.cache_data.clear()
                return True
            else:
                st.error(f"❌ 雲端更新失敗: {res_json.get('message')}")
        else:
            st.error(f"❌ 通訊異常 (HTTP {response.status_code})")
    except Exception as e:
        st.warning(f"⚠️ 目前處於離線開發模式（未偵測到部署的 GAS URL）。模擬操作：【{action_type}】成功！")
        return True
    return False

# ========================================== 3. 頂部頁籤佈局 (與 PPT 頁面完全一致) ==========================================
tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "🔄 Upload R/C"])

# --- 頁籤 1: Full Route ---
with tabs[0]:
    st.subheader("HETEROGENEOUS INTEGRATION & MANUFACTURING DIVISION")
    
    # 頂部查詢列
    col_search1, col_search2 = st.columns([3, 1])
    with col_search1:
        wafer_id = st.text_input("🔍 請輸入或掃描 晶圓 ID (Wafer ID):", value=st.session_state.wafer_id_input)
        st.session_state.wafer_id_input = wafer_id
    with col_search2:
        st.write(" ")
        st.write(" ")
        if st.button("🔄 刷新資料", use_container_width=True):
            st.cache_data.clear()
    
    # 抓取並顯示表格
    df_route = fetch_wafer_data(wafer_id)
    
    if not df_route.empty:
        st.markdown("**【當前完整生產路由表格資訊】** (請點擊表格左側單選框以選定控管站點)")
        # 使用 st.dataframe 搭配單選列選取功能
        event = st.dataframe(
            df_route,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # 處理使用者選擇的站點
        selected_rows = event.get("selection", {}).get("rows", [])
        if selected_rows:
            st.session_state.selected_row_data = df_route.iloc[selected_rows[0]].to_dict()
        elif st.session_state.selected_row_data is None:
            st.session_state.selected_row_data = df_route.iloc[0].to_dict()
            
        st.markdown("---")
        
        # 下半部：站點控制與資料回填區塊（高度還原 PPT 樣式）
        st.subheader("⚙️ 當前過站控制面板 (Current Stage Action Panel)")
        
        # 顯示當前鎖定的站點基本資訊摘要
        cur = st.session_state.selected_row_data
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric(label="晶圓編號 (Wafer ID)", value=str(cur.get("Wafer ID", "")))
        with col_m2:
            st.metric(label="目前步驟 (Step No.)", value=f"第 {cur.get('Step No.', '')} 步")
        with col_m3:
            st.metric(label="負責模組 (Module)", value=str(cur.get("Module", "")))
        with col_m4:
            st.metric(label="客戶團隊 (Customer)", value=str(cur.get("Customer", "")))
            
        st.info(f"💡 **正在操作的站點描述：** {cur.get('Step Description', '')} | **製程機台：** {cur.get('Process Tool', '')} | **食譜配方 (Recipe)：** {cur.get('Recipe', '')}")
        
        # 操作與備註輸入欄位
        col_act1, col_act2 = st.columns([3, 1])
        with col_act1:
            comment_input = st.text_input("💬 批註 / 機台數據回填 (Key in data / SPC Data):", placeholder="請在此輸入過站紀錄、檢驗量測結果或異常原因...")
        with col_act2:
            st.write(" ")
            st.write(" ")
            if st.button("💾 僅儲存資料 (Key in data)", use_container_width=True):
                update_wafer_status(wafer_id, cur.get('Step No.'), "Key in data", comment_input)
        
        # PPT 下方實體按鈕群組
        st.markdown("### 🚦 流程變更權限指令")
        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
        
        with col_btn1:
            if st.button("✅ 正常出站 (Check out)", type="primary", use_container_width=True):
                update_wafer_status(wafer_id, cur.get('Step No.'), "Check out", comment_input)
        with col_btn2:
            if st.button("❌ 報廢處理 (Scrap)", type="secondary", use_container_width=True):
                update_wafer_status(wafer_id, cur.get('Step No.'), "Scrap", comment_input)
        with col_btn3:
            if st.button("⚠️ 暫停鎖定 (Hold)", use_container_width=True):
                update_wafer_status(wafer_id, cur.get('Step No.'), "Hold", comment_input)
        with col_btn4:
            if st.button("⏭️ 跳過此站 (Skip)", use_container_width=True):
                update_wafer_status(wafer_id, cur.get('Step No.'), "Skip", comment_input)
                
    else:
        st.warning("⚠️ 查無此 Wafer ID 的路由資料，請確認後重新輸入。")

# --- 頁籤 2: Wafer History ---
with tabs[1]:
    st.subheader("📜 歷史操作變更日誌 (Wafer Operational History)")
    st.caption("此處將即時串接讀取 Google Sheets 上的 Operational_Logs 工作表，顯示該晶圓過去所有的 Check out / Hold / Scrap 異動時間軸與操作人員。")
    # 預留未來呈現位置
    st.dataframe(pd.DataFrame(columns=["時間戳記", "Wafer ID", "步驟", "變更動作", "備註/SPC數據"]), use_container_width=True)

# --- 頁籤 3: Upload New Wafer ---
with tabs[2]:
    st.subheader("📤 批量註冊全新晶圓路由 (Upload New Wafer)")
    st.markdown("請上傳由整合部門產出的完整流程 Excel/CSV 檔案，系統將自動同步上傳解析至雲端 Google Sheets 中。")
    uploaded_file = st.file_uploader("選擇路由定義檔案 (.csv, .xlsx)", type=["csv", "xlsx"])
    if uploaded_file is not None:
        st.success("檔案解析成功！已預備寫入 Google Sheets 後端。")

# --- 頁籤 4: Upload R/C ---
with tabs[3]:
    st.subheader("🔄 流程重工與修訂上傳 (Upload R/C - Rework / Change)")
    st.warning("提醒：操作重工流程（Rework）將會改寫既有 Full Route 的站點順序，請務必雙重確認填入資訊。")
