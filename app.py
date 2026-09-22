import streamlit as st
import pandas as pd
import requests
import json

# 設定 Streamlit 頁面寬度
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")

# =========================================================================
# 🔴 請在此更換為您在 Google Sheets 部署「新部署」後取得的 Web App URL
# =========================================================================
GAS_API_URL = "https://script.google.com/macros/s/AKfycbxSpHeSlbCyMgn0cH60fh62eM_nYoaCwkSCZF1UJMTeC-3z1wQJ1RVLXge1kvzadmKM/exec"

st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

# 建立上方四大功能頁籤
tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "🔄 Upload R/C"])

# 獲取遠端資料的函數
@st.cache_data(ttl=10)  # 每10秒允許重新抓取，保持即時性
def fetch_route_data():
    if not GAS_API_URL or "請在此替換" in GAS_API_URL:
        # 如果尚未配置 GAS 網址，自動降級載入 PPT 中的模擬預設資料進行防呆
        mock_data = [
            {"Wafer ID": "LOT4-11F0", "Step No.": "1", "Module": "Lot Owner", "Step Description": 'Wafer check (TSMC片8")', "Process Tool": "SE-023", "Recipe": "nan", "Check point": "Chipping or not", "Stage Owner": "Bill/yd", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "nan", "First Check Out": "nan", "Shuttle Name": "T18-C14A"},
            {"Wafer ID": "LOT4-11F0", "Step No.": "2", "Module": "Package", "Step Description": "Edge trim (x:500um/y:50um)", "Process Tool": "DISCO", "Recipe": "nan", "Check point": "nan", "Stage Owner": "Laif", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "nan", "First Check Out": "nan", "Shuttle Name": "T18-C14A"},
            {"Wafer ID": "LOT4-11F0", "Step No.": "3", "Module": "Package", "Step Description": "Wafer check", "Process Tool": "KLA Profilemeter", "Recipe": "nan", "Check point": "Depth bias", "Stage Owner": "Laif", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "nan", "First Check Out": "nan", "Shuttle Name": "T18-C14A"},
            {"Wafer ID": "LOT4-11F0", "Step No.": "4", "Module": "LIT", "Step Description": "Surface clean by developer", "Process Tool": "SE-009-02", "Recipe": "No.1", "Check point": "nan", "Stage Owner": "Bill/Jane", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "2hr", "First Check Out": "nan", "Shuttle Name": "T18-C14A"},
            {"Wafer ID": "LOT4-11F0", "Step No.": "5", "Module": "PVD", "Step Description": "Ti/Cu seedlayer 50/300nm", "Process Tool": "SE-003", "Recipe": "165.Ti_500_Cu_3000", "Check point": "nan", "Stage Owner": "Bill/Jane", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "2hr", "First Check Out": "nan", "Shuttle Name": "T18-C14A"},
            {"Wafer ID": "LOT4-11F0", "Step No.": "6", "Module": "LIT", "Step Description": "Litho. AZ4620 10um(EBR)", "Process Tool": "SE-009-01", "Recipe": "nan", "Check point": "nan", "Stage Owner": "Bill/Jane", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "2hr", "First Check Out": "nan", "Shuttle Name": "T18-C14A"}
        ]
        return pd.DataFrame(mock_data), "Offline Mode"
    
    try:
        response = requests.get(GAS_API_URL, timeout=8)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "success":
                return pd.DataFrame(res_json.get("data")), "Connected"
            else:
                return pd.DataFrame(), f"GAS Error: {res_json.get('message')}"
        else:
            return pd.DataFrame(), f"HTTP Error {response.status_code}"
    except Exception as e:
        return pd.DataFrame(), f"Connection Failed: {str(e)}"

# 提交變更動作給後端 GAS
def send_action(wafer_id, step_no, action, comment):
    if not GAS_API_URL or "請在此替換" in GAS_API_URL:
        st.sidebar.warning("離線模式：動作不會同步到雲端")
        return True
    
    payload = {
        "wafer_id": wafer_id,
        "step_no": str(step_no),
        "action": action,
        "comment": comment
    }
    try:
        response = requests.post(GAS_API_URL, data=json.dumps(payload), timeout=8)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("status") == "success":
                st.balloons()
                st.success(res_json.get("message"))
                return True
            else:
                st.error(f"後端寫入失敗: {res_json.get('message')}")
        else:
            st.error(f"連線異常 HTTP 代碼: {response.status_code}")
    except Exception as e:
        st.error(f"無法發送數據: {str(e)}")
    return False

# ==================== 頁籤 1: Full Route 完整整合內容 ====================
with tabs[0]:
    st.subheader("HETEROGENEOUS INTEGRATION & MANUFACTURING DIVISION")
    
    # 資料狀態與載入
    df, conn_status = fetch_route_data()
    
    # 側邊欄或頂部狀態條
    if "Error" in conn_status or "Failed" in conn_status:
        st.error(f"❌ 通訊異常 ({conn_status})")
    elif conn_status == "Offline Mode":
        st.info("💡 目前處於離線展示模式。請將正確的 GAS Web App URL 填入 `app.py` 第 15 行以對接實體試算表。")
    
    # 頂部晶圓 ID 過濾面板
    col_input1, col_input2 = st.columns([4, 1])
    with col_input1:
        search_id = st.text_input("🔍 請輸入或掃描品且 ID (Wafer ID):", value="LOT4-11F0")
    with col_input2:
        st.write(" ")
        st.write(" ")
        if st.button("🔄 刷新資料", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # 過濾資料
    if not df.empty and "Wafer ID" in df.columns:
        filtered_df = df[df["Wafer ID"].str.upper() == search_id.upper()]
    else:
        filtered_df = df

    st.markdown("**【當前完整生產路由表格資訊】** (請點擊表格格子外圍選取框以選定控管站點)")
    
    # 渲染大資料表格
    if not filtered_df.empty:
        # 允許使用者在前端點擊多選框來選擇目前要處理哪一站
        selected_rows = st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # 預設選取第一站，若使用者有手動點選表格，則切換到點選的站點
        current_idx = 0
        if selected_rows and len(selected_rows.get("selection", {}).get("rows", [])) > 0:
            current_idx = selected_rows["selection"]["rows"][0]
            
        target_row = filtered_df.iloc[current_idx]
        
        st.write("---")
        st.subheader("⚙️ 當前過站控制面板 (Current Stage Action Panel)")
        
        # 面板第一排資訊
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("品且編號 (Wafer ID)", str(target_row.get("Wafer ID", "N/A")))
        c2.metric("目前步驟 (Step No.)", f"第 {str(target_row.get('Step No.', 'N/A'))} 步")
        c3.metric("負責模組 (Module)", str(target_row.get("Module", "N/A")))
        c4.metric("客戶團隊 (Customer)", str(target_row.get("Customer", "N/A")))
        
        # 面板第二排：提示操作站點細節
        st.info(
            f"💡 **正在操作的站點描述**：{target_row.get('Step Description', 'N/A')} | "
            f"**製程機台**：{target_row.get('Process Tool', 'N/A')} | "
            f"**𠵱檔配方 (Recipe)**：{target_row.get('Recipe', 'N/A')}"
        )
        
        # 面板第三排：數據與備註回填區
        st.markdown("📝 **批註 / 機台數據回填 (Key in data / SPC Data):**")
        user_comment = st.text_input(
            "請在此輸入過站紀錄、檢驗量測結果（如厚度、偏置）或異常原因...",
            key="user_comment_input",
            placeholder="例如: PR height record = 10um / 無外觀碎裂(Chipping)"
        )
        
        # 面板第四排：功能功能變更指令按鈕群
        st.markdown("⚠️ **流程變更權限指令**")
        b1, b2, b3, b4, b5 = st.columns(5)
        
        with b1:
            if st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True):
                if send_action(target_row.get("Wafer ID"), target_row.get("Step No."), "Check out", user_comment):
                    st.cache_data.clear()
        with b2:
            if st.button("❌ 報廢處理 (Scrap)", use_container_width=True):
                if send_action(target_row.get("Wafer ID"), target_row.get("Step No."), "Scrap", user_comment):
                    st.cache_data.clear()
        with b3:
            if st.button("🟨 暫停規定 (Hold)", use_container_width=True):
                if send_action(target_row.get("Wafer ID"), target_row.get("Step No."), "Hold", user_comment):
                    st.cache_data.clear()
        with b4:
            if st.button("🟦 跳過此站 (Skip)", use_container_width=True):
                if send_action(target_row.get("Wafer ID"), target_row.get("Step No."), "Skip", user_comment):
                    st.cache_data.clear()
        with b5:
            if st.button("💾 僅儲存資料 (Key in data)", use_container_width=True):
                if send_action(target_row.get("Wafer ID"), target_row.get("Step No."), "Key in data", user_comment):
                    st.cache_data.clear()
                    
    else:
        st.warning("⚠️ 沒有找到相關的晶圓路由資料，請確認輸入的 Wafer ID 或是檢查後端資料庫。")

# ==================== 頁籤 2, 3, 4: 保留擴充介面 ====================
with tabs[1]:
    st.subheader("📜 晶圓歷史追蹤足跡 (Wafer History)")
    st.write("此處功能擴充中... 未來將自動拉取 `wafer_status` 內的紀錄，轉化為時間軸（Timeline）呈現該片晶圓的所有進出站足跡。")

with tabs[2]:
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
    st.write("此處功能擴充中... 未來可供製程整合工程師上傳全新批次的 Excel 母體路由檔案。")

with tabs[3]:
    st.subheader("🔄 上傳 R/C 規範 (Upload R/C)")
    st.write("此處功能擴充中... 供設定特例與改道製程專用。")
