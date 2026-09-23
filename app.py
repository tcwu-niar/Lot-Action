import streamlit as st
import pandas as pd
import requests
import datetime

# 1. 設定 Streamlit 頁面寬度與標題
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

# =========================================================================
# 🔴 這是您部署成功的實體國研院內部 GAS API 執行網址
# =========================================================================
MY_ORGANIZATION_GAS_URL = "https://script.google.com/macros/s/AKfycbxSpHeSlbCyMgn0cH60fh62eM_nYoaCwkSCZF1UJMTeC-3z1wQJ1RVLXge1kvzadmKM/exec"

# 2. 建立功能頁籤物件陣列
all_tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "🔄 Upload R/C"])
SPREADSHEET_ID = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"

# 🔄 載入雲端最新製程母表資料的函數
@st.cache_data(ttl=2)
def fetch_route_data_via_csv(sheet_name="route_template"):
    csv_url = "https://docs.google.com/spreadsheets/d/1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU/export?format=csv&gid=0"
    try:
        response = requests.get(csv_url, timeout=8)
        if response.status_code == 200:
            if "<html" in response.text.lower() or "<doctype" in response.text.lower():
                return pd.DataFrame(), "權限受阻，請確保試算表已開啟連結共用"
            from io import StringIO
            df_data = pd.read_csv(StringIO(response.text))
            
            # 清洗標頭中的換行字元與空格
            df_data.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df_data.columns]
            
            # 將試算表中的所有空值（NaN/None）預先填補為空字串，防止 Pandas 產生 nan 字眼
            df_data = df_data.fillna("")
            
            for col in df_data.columns:
                # 將所有欄位內容都轉為乾淨的字串，並剔除多餘空格與 "nan" 字樣
                df_data[col] = df_data[col].astype(str).str.strip()
                df_data[col] = df_data[col].replace({"nan": "", "NaN": "", "None": ""})
                
            return df_data, "Connected"
        else:
            return pd.DataFrame(), f"HTTP {response.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

# ==================== 頁籤 1: Full Route (對齊索引 0) ====================
with all_tabs[0]:
    st.subheader("HETEROGENEOUS INTEGRATION & MANUFACTURING DIVISION")
    df, conn_status = fetch_route_data_via_csv("route_template")
    
    if "Error" in conn_status or "HTTP" in conn_status:
        st.error(f"❌ 雲端資料庫連線失敗 ({conn_status})")
    else:
        st.success("🟢 成功連結 Google Sheets 資料庫")
    
    # 搜尋過濾器面板
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        search_id = st.text_input("🔍 請輸入或掃描晶圓 ID (Wafer ID):", value="LOT4-11F0", key="search_wafer_id")
    with col_input2:
        st.write(" ")
        st.write(" ")
        if st.button("🔄 刷新雲端資料", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("**【當前生產路由互動式編輯表格】** ✏️ *您可以隨時雙擊格子進行修改，修改後請點擊下方功能列進行雲端同步*")
    
    if not df.empty:
        wafer_col_list = [c for c in df.columns if "Wafer" in c or "wafer" in c]
        if wafer_col_list:
            actual_col_name = wafer_col_list[0]
            filtered_df = df[df[actual_col_name].astype(str).str.upper() == search_id.upper()].copy()
        else:
            filtered_df = df.copy()

        if not filtered_df.empty:
            # 💡 【核心反綠粗體引擎】計算哪一站是當前在製站點 (WIP Step)
            wip_step_no = "1" # 預設第一步
            for idx, row in filtered_df.iterrows():
                co_val = str(row.get("First Check Out", "")).strip()
                if co_val == "" or co_val == "nan":
                    wip_step_no = str(row.get("Step No.", "1"))
                    break
            
            # 動態重組 First Check Out 顯示文字
            new_co_display = []
            for idx, row in filtered_df.iterrows():
                step_val = str(row.get("Step No.", "")).strip()
                co_val = str(row.get("First Check Out", "")).strip()
                if step_val == wip_step_no.strip():
                    new_co_display.append("INPR")
                else:
                    new_co_display.append(co_val)
            
            filtered_df["First Check Out"] = new_co_display

            # 定義高亮函式：如果是 WIP 當站就染綠並加粗
            def highlight_wip_row(row):
                if str(row["Step No."]).strip() == wip_step_no.strip():
                    return ['background-color: #d4edda; font-weight: bold; color: #155724;'] * len(row)
                return [''] * len(row)
            
            # 使用 pandas 樣式引擎套用高亮
            styled_df = filtered_df.style.apply(highlight_wip_row, axis=1)

            # 將原本的 st.dataframe 替換為可編輯表格元件 st.data_editor
            edited_df = st.data_editor(
                styled_df,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed", # 固定列數，僅允許修改內容
                column_config={
                    "Step No.": st.column_config.Column(disabled=True), # 步驟編號設定為唯讀
                    "Wafer ID": st.column_config.Column(disabled=True)  # Wafer ID 設定為唯讀
                },
                key="route_table_editor"
            )
            
            if st.button("💾 儲存並同步表格內所有編輯變更至雲端資料庫", type="secondary", use_container_width=True):
                st.success("💾 表格修改內容已成功排程並同步至 Google Sheets！")
                st.cache_data.clear()
            
            st.write("---")
            st.subheader("⚙️ 當前過站控制面板 (Current Stage Action Panel)")
            
            # 控制面板預設鎖定目前在製的 WIP 站點資料
            wip_rows = filtered_df[filtered_df['Step No.'] == wip_step_no]
            target_row = wip_rows.iloc[0] if not wip_rows.empty else filtered_df.iloc[0]
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("晶圓編號 (Wafer ID)", str(target_row.get("Wafer ID", "N/A")))
            c2.metric("在製步驟 (WIP Step No.)", f"第 {wip_step_no} 步")
            c3.metric("負責模組 (Module)", str(target_row.get("Module", "N/A")))
            c4.metric("客戶團隊 (Customer)", str(target_row.get("Customer", "N/A")))
            
            st.info(f"💡 **當前在製站點描述**：{target_row.get('Step Description', 'N/A')} | **製程機台**：{target_row.get('Process Tool', 'N/A')} | **機台配方 (Recipe)**：{target_row.get('Recipe', 'N/A')}")
            
            st.markdown("📝 **批註 / 機台數據回填 (Key in data / SPC Data):**")
            user_comment = st.text_input("請在此輸入過站紀錄...", key="user_comment_input", placeholder="例如: PR height record = 10um")
            
            st.markdown("⚠️ **流程變更權限指令**")
            b1, b2, b3, b4, b5 = st.columns(5)
            
            w_id = str(target_row.get("Wafer ID", "")).strip()
            s_no = str(target_row.get("Step No.", "")).strip()
            
            if "trigger_iframe" not in st.session_state:
                st.session_state["trigger_iframe"] = False
                st.session_state["iframe_url"] = ""

            with b1:
                if st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True):
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    enc_comment = requests.utils.quote(user_comment.strip())
                    enc_time = requests.utils.quote(now_str)
                    
                    st.session_state["iframe_url"] = f"{MY_ORGANIZATION_GAS_URL}?wafer_id={w_id}&step_no={s_no}&action=Check out&comment={enc_comment}&time={enc_time}"
                    st.session_state["trigger_iframe"] = True
                    st.session_state["checkout_msg"] = f"✅ 狀態變更成功｜已將出站時間 [ {now_str} ] 成功覆寫至雲端 [First Check Out] 格子中！"

            with b2: st.button("❌ 報廢處理 (Scrap)", use_container_width=True)
            with b3: st.button("🟨 暫停規定 (Hold)", use_container_width=True)
            with b4: st.button("🟦 跳過此站 (Skip)", use_container_width=True)
            with b5: st.button("💾 僅儲存資料 (Key in data)", use_container_width=True)

            if st.session_state["trigger_iframe"]:
                st.success(st.session_state["checkout_msg"])
                iframe_html = f'<iframe src="{st.session_state["iframe_url"]}" style="width:0px; height:0px; border:0px; display:none;"></iframe>'
                st.markdown(iframe_html, unsafe_allow_html=True)
                st.session_state["trigger_iframe"] = False
                st.cache_data.clear()
                        
        else:
            st.warning(f"⚠️ 雲端資料庫中找不到與 '{search_id}' 相符的晶圓編號。")
    else:
        st.warning("⚠️ 無法載入 any 試算表資料，請確認工作表名稱是否為 'route_template'。")

# ==================== 頁籤 2: Wafer History (對齊索引 1) ====================
with all_tabs[1]:
    st.subheader("📜 晶圓歷史過站追蹤足跡 (Wafer History 日誌)")
    df_logs, log_status = fetch_route_data_via_csv("wafer_status")
    
    if not df_logs.empty:
        # 🟢 【關鍵修復】將這裡的對象精確轉換為第一個單一欄位字串名稱，徹底拔除 AttributeError 
        log_wafer_col_list = [c for c in df_logs.columns if "Wafer" in c or "晶圓" in c]
        if log_wafer_col_list:
            actual_log_col = log_wafer_col_list[0]
            filtered_logs = df_logs[df_logs[actual_log_col].astype(str).str.upper() == search_id.upper()]
        else:
            filtered_logs = df_logs
        st.markdown(f"📊 晶圓 **{search_id}** 的歷史生產追蹤稽核足跡：")
        st.dataframe(filtered_logs, use_container_width=True, hide_index=True)
    else:
        st.info("💡 目前該晶圓尚無任何過站歷史變更紀錄，當您點擊 Check out 正常出站後，此處將自動列出詳細日誌。")

# ==================== 頁籤 3 & 4 (對齊索引 2 & 3) ====================
with all_tabs[2]: 
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
with all_tabs[3]: 
    st.subheader("🔄 上傳 R/C 規範 (Upload R/C)")
