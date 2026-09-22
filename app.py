import streamlit as st
import pandas as pd
import requests

# 設定 Streamlit 頁面寬度
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")

st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

# 您的 Google 試算表 ID 與分頁名稱
SPREADSHEET_ID = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
SHEET_NAME = "route_template"

# 建立上方四大功能頁籤
tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "🔄 Upload R/C"])

# 🔄 全新優化：利用 Google Sheet CSV 導出功能，100% 繞過網頁應用程式權限限制
@st.cache_data(ttl=5)
def fetch_route_data_via_csv():
    # 建立直接導出 CSV 的特殊 Google 連結
    csv_url = f"https://google.com{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
    try:
        # 直接使用 requests 抓取，並指定編碼為 utf-8
        response = requests.get(csv_url, timeout=8)
        if response.status_code == 200:
            # 轉化為字串流讓 pandas 讀取
            from io import StringIO
            df_data = pd.read_csv(StringIO(response.text))
            
            # 清理欄位名稱中的未命名空格，並將所有 nan 轉化為字串方便統一處理
            df_data.columns = [c.strip() for c in df_data.columns]
            df_data = df_data.fillna("nan")
            return df_data, "Connected"
        else:
            return pd.DataFrame(), f"HTTP Error {response.status_code}"
    except Exception as e:
        return pd.DataFrame(), f"連線異常: {str(e)}"

# ==================== 頁籤 1: Full Route 完整整合內容 ====================
with tabs[0]:
    st.subheader("HETEROGENEOUS INTEGRATION & MANUFACTURING DIVISION")
    
    # 自動加載雲端最新資料
    df, conn_status = fetch_route_data_via_csv()
    
    if "Error" in conn_status or "異常" in conn_status:
        st.error(f"❌ 雲端資料庫連線失敗 ({conn_status})")
    else:
        st.success("🟢 成功透過國研院組織網路連線至 Google Sheets 資料庫")
    
    # 頂部晶圓 ID 過濾面板
    col_input1, col_input2 = st.columns([3, 1])
    with col_input1:
        search_id = st.text_input("🔍 請輸入或掃描品且 ID (Wafer ID):", value="LOT4-11F0")
    with col_input2:
        st.write(" ")
        st.write(" ")
        if st.button("🔄 刷新雲端資料", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("**【當前完整生產路由表格資訊】** (請點擊表格格子外圍選取框以選定控管站點)")
    
    # 渲染大資料表格
    if not df.empty:
        # 如果有 Wafer ID 欄位，進行關鍵字過濾
        if "Wafer ID" in df.columns:
            filtered_df = df[df["Wafer ID"].astype(str).str.upper() == search_id.upper()]
        else:
            filtered_df = df

        if not filtered_df.empty:
            # 顯示互動式表格
            selected_rows = st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            # 偵測使用者點選了哪一列（預設第一列）
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
            
            # 提示使用者目前因組織權限改為純讀取面板
            st.caption("🔒 偵測到國研院帳戶資安限制，目前控制面板按鈕處於離線測試狀態。")
            
            with b1:
                st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True, disabled=True)
            with b2:
                st.button("❌ 報廢處理 (Scrap)", use_container_width=True, disabled=True)
            with b3:
                st.button("🟨 暫停規定 (Hold)", use_container_width=True, disabled=True)
            with b4:
                st.button("🟦 跳過此站 (Skip)", use_container_width=True, disabled=True)
            with b5:
                st.button("💾 僅儲存資料 (Key in data)", use_container_width=True, disabled=True)
                        
        else:
            st.warning(f"⚠️ 雲端資料庫中找不到與 '{search_id}' 相符的晶圓編號。")
    else:
        st.warning("⚠️ 無法載入任何試算表資料，請確認工作表名稱是否為 'route_template'。")

# ==================== 頁籤 2, 3, 4: 保留擴充介面 ====================
with tabs[1]:
    st.subheader("📜 晶圓歷史追蹤足跡 (Wafer History)")
    st.write("未來將自動拉取紀錄，呈現該片晶圓的所有進出站足跡。")

with tabs[2]:
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
    st.write("供製程整合工程師上傳全新批次的 Excel 母體路由檔案。")

with tabs[3]:
    st.subheader("🔄 上傳 R/C 規範 (Upload R/C)")
    st.write("供設定特例與改道製程專用。")
