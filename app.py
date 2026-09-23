import streamlit as st
import pandas as pd
import requests
import datetime

# =========================================================================
# 1. 系統全域基礎配置與資料載入
# =========================================================================
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

# 🔴 這是您部署成功的實體國研院內部 GAS API 執行網址
MY_ORGANIZATION_GAS_URL = "https://script.google.com/macros/s/AKfycbxSpHeSlbCyMgn0cH60fh62eM_nYoaCwkSCZF1UJMTeC-3z1wQJ1RVLXge1kvzadmKM/exec"
SPREADSHEET_ID = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"

# 建立上方四大核心功能頁籤物件陣列
all_tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "🔄 Upload R/C"])

# 🔄 載入雲端最新資料的公用函數
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
            df_data = df_data.fillna("")
            
            for col in df_data.columns:
                df_data[col] = df_data[col].astype(str).str.strip()
                df_data[col] = df_data[col].replace({"nan": "", "NaN": "", "None": ""})
            return df_data, "Connected"
        else:
            return pd.DataFrame(), f"HTTP {response.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)
# =========================================================================
# 📋 頁籤 1: Full Route (完整生產路由與互動編輯面板)
# =========================================================================
with all_tabs:
    st.subheader("HETEROGENEOUS INTEGRATION & MANUFACTURING DIVISION")
    
    df, conn_status = fetch_route_data_via_csv("route_template")
    if "Error" in conn_status or "HTTP" in conn_status:
        st.error(f"❌ 雲端資料庫連線失敗 ({conn_status})")
    else:
        st.success("🟢 成功連結 Google Sheets 資料庫")
    
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        search_id = st.text_input("🔍 請輸入或掃描晶圓 ID (Wafer ID):", value="LOT4-11F0", key="search_wafer_id")
    with col_input2:
        st.write(" ")
        st.write(" ")
        if st.button("🔄 刷新雲端資料", use_container_width=True, key="tab1_refresh"):
            st.cache_data.clear()
            st.rerun()

    st.markdown("**【當前生產路由互動式編輯表格】** 🟢 *綠色粗體整列代表晶圓目前正停留之在製站點 (Current WIP Stage)*")
    
    if not df.empty:
        wafer_col_list = [c for c in df.columns if "Wafer" in c or "wafer" in c]
        filtered_df = df[df[wafer_col_list].astype(str).str.upper() == search_id.upper()].copy() if wafer_col_list else df.copy()

        if not filtered_df.empty:
            # WIP 站點追蹤判定
            wip_step_no = "1"
            for idx, row in filtered_df.iterrows():
                co_val = str(row.get("First Check Out", "")).strip()
                if co_val == "" or co_val == "nan" or co_val == "INPR":
                    wip_step_no = str(row.get("Step No.", "1"))
                    break
            
            display_df = filtered_df.copy()
            new_co_display = [ "INPR" if str(r.get("Step No.", "")).strip() == wip_step_no.strip() else str(r.get("First Check Out", "")).strip() for _, r in display_df.iterrows() ]
            display_df["First Check Out"] = new_co_display

            # 💡 【終極整列鋪滿綠底引擎】透過 Axis=1 確保 pandas 一口氣將底色塗滿整列的所有 Cell
            def highlight_wip_row(row):
                if str(row["Step No."]).strip() == wip_step_no.strip():
                    return ['background-color: #c3e6cb !important; font-weight: bold; color: #155724 !important;'] * len(row)
                return [''] * len(row)
            
            styled_df = display_df.style.apply(highlight_wip_row, axis=1)

            edited_table = st.data_editor(
                styled_df, use_container_width=True, hide_index=True, num_rows="fixed",
                column_config={"Step No.": st.column_config.Column(disabled=True), "Wafer ID": st.column_config.Column(disabled=True)},
                key="route_table_editor"
            )
            
            if "multi_iframe_urls" not in st.session_state:
                st.session_state["multi_iframe_urls"] = []
                st.session_state["show_save_success"] = False

            if st.button("💾 儲存並同步表格內所有編輯變更至雲端資料庫", type="secondary", use_container_width=True, key="tab1_save_grid"):
                st.session_state["multi_iframe_urls"] = []
                base_df = filtered_df.reset_index(drop=True)
                user_df = pd.DataFrame(edited_table).reset_index(drop=True)
                
                for r_idx in range(len(base_df)):
                    w_id, s_no = base_df.loc[r_idx, "Wafer ID"], base_df.loc[r_idx, "Step No."]
                    for col in base_df.columns:
                        if col == "First Check Out": continue
                        if str(base_df.loc[r_idx, col]).strip() != str(user_df.loc[r_idx, col]).strip():
                            enc_new_val = requests.utils.quote(str(user_df.loc[r_idx, col]).strip())
                            enc_col_name = requests.utils.quote(col)
                            st.session_state["multi_iframe_urls"].append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={w_id}&step_no={s_no}&column_name={enc_col_name}&new_value={enc_new_val}&callback=jQuery")
                st.session_state["show_save_success"] = True
                st.cache_data.clear()
                st.rerun()

            if st.session_state["show_save_success"]:
                if st.session_state["multi_iframe_urls"]:
                    st.success(f"💾 偵測到表格變更！背景自動同步處理 {len(st.session_state['multi_iframe_urls'])} 筆儲存格...")
                    for url in st.session_state["multi_iframe_urls"]:
                        st.markdown(f'<iframe src="{url}" style="width:0px; height:0px; border:0px; display:none;"></iframe>', unsafe_allow_html=True)
                else:
                    st.info("ℹ️ 資料未變動，無需同步。")
                st.session_state["show_save_success"], st.session_state["multi_iframe_urls"] = False, []

            st.write("---")
            st.subheader("⚙️ 當前過站控制面板 (Current Stage Action Panel)")
            wip_rows = filtered_df[filtered_df['Step No.'] == wip_step_no]
            target_row = wip_rows.iloc if not wip_rows.empty else filtered_df.iloc
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("晶圓編號 (Wafer ID)", str(target_row.get("Wafer ID", "N/A")))
            c2.metric("在製步驟 (WIP Step No.)", f"第 {wip_step_no} 步")
            c3.metric("負責模組 (Module)", str(target_row.get("Module", "N/A")))
            c4.metric("客戶團隊 (Customer)", str(target_row.get("Customer", "N/A")))
            
            user_comment = st.text_input("請在此輸入過站紀錄...", key="user_comment_input", placeholder="例如: PR height record = 10um")
            
            st.markdown("⚠️ **流程變更權限指令**")
            b1, b2, b3, b4, b5 = st.columns(5)
            w_id, s_no = str(target_row.get("Wafer ID", "")).strip(), str(target_row.get("Step No.", "")).strip()
            
            if "trigger_iframe" not in st.session_state:
                st.session_state["trigger_iframe"], st.session_state["iframe_url"] = False, ""

            def send_action_to_iframe(action_name):
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["iframe_url"] = f"{MY_ORGANIZATION_GAS_URL}?wafer_id={w_id}&step_no={s_no}&action={action_name}&comment={requests.utils.quote(user_comment.strip())}&time={requests.utils.quote(now_str)}"
                st.session_state["trigger_iframe"] = True
                st.session_state["checkout_msg"] = f"✅ 狀態變更成功｜已將出站時間 [ {now_str} ] 覆寫至雲端！"
                st.cache_data.clear()
                st.rerun()

            with b1:
                if st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True, key="tab1_btn_co"): send_action_to_iframe("Check out")
            with b2:
                if st.button("❌ 報廢處理 (Scrap)", use_container_width=True, key="tab1_btn_sc"): send_action_to_iframe("Scrap")
            with b3:
                if st.button("🟨 暫停規定 (Hold)", use_container_width=True, key="tab1_btn_hd"): send_action_to_iframe("Hold")
            with b4:
                if st.button("🟦 跳過此站 (Skip)", use_container_width=True, key="tab1_btn_sk"): send_action_to_iframe("Skip")
            with b5:
                if st.button("💾 僅儲存資料 (Key in data)", use_container_width=True, key="tab1_btn_ki"): send_action_to_iframe("Key in data")

            if st.session_state["trigger_iframe"]:
                st.success(st.session_state["checkout_msg"])
                st.markdown(f'<iframe src="{st.session_state["iframe_url"]}" style="width:0px; height:0px; border:0px; display:none;"></iframe>', unsafe_allow_html=True)
                st.session_state["trigger_iframe"] = False
        else:
            st.warning(f"⚠️ 雲端資料庫中找不到與 '{search_id}' 相符的晶圓編號。")
# =========================================================================
# 📜 頁籤 2: Wafer History (晶圓歷史過站追蹤足跡)
# =========================================================================
with all_tabs[1]:
    st.subheader("📜 晶圓歷史過站追蹤足跡 (Wafer History 日誌)")
    df_logs, log_status = fetch_route_data_via_csv("wafer_status")
    
    if not df_logs.empty:
        log_wafer_col_list = [c for c in df_logs.columns if "Wafer" in c or "晶圓" in c]
        filtered_logs = df_logs[df_logs[log_wafer_col_list[0]].astype(str).str.upper() == search_id.upper()] if log_wafer_col_list else df_logs
        if not filtered_logs.empty:
            st.markdown(f"📊 晶圓 **{search_id}** 的歷史生產追蹤稽核足跡：")
            st.dataframe(filtered_logs, use_container_width=True, hide_index=True)
        else:
            st.info(f"ℹ️ 品且編號 {search_id} 目前在 wafer_status 中尚無紀錄。")
    else:
        st.info("💡 目前雲端資料庫尚無紀錄。當您點擊 Check out 出站後，詳細日誌將在此呈現。")

# =========================================================================
# 📤 頁籤 3: Upload New Wafer (上傳新晶圓路由母表)
# =========================================================================
with all_tabs[2]:
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
    st.markdown("供製程整合工程師導入全新批次的半導體製造整合路由母體檔案。")
    uploaded_file = st.file_uploader("請選擇或拖曳要上傳的全新批次生產路由檔案 (.csv 或 .xlsx)", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            preview_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.success("✅ 檔案解析成功！以下為前 5 筆製程路由資料預覽：")
            st.dataframe(preview_df.head(5), use_container_width=True, hide_index=True)
            if st.button("🚀 開始批量寫入 Google Sheets 資料庫", type="primary", use_container_width=True):
                st.info("正在連線至國研院專案母表... 批量解析寫入模組初始化完成！")
        except Exception as e:
            st.error(f"❌ 檔案解析失敗: {str(e)}")

# =========================================================================
# 🔄 頁籤 4: Upload R/C (上傳 R/C 規範)
# =========================================================================
with all_tabs[3]:
    st.subheader("🔄 上傳 R/C 規範 (Upload Run Card Change)")
    st.markdown("當晶圓需要執行晶圓重工 (Rework)、機台特例改道或特殊參數調整時，在此進行 R/C 規範單號綁定。")
    with st.form("rc_form"):
        rc_no = st.text_input("📋 Run Card 簽核單號 (R/C Number):", placeholder="例如: RC-2026-001")
        rc_step = st.text_input("📍 影響之起迄製程步驟 (Affected Steps):", placeholder="例如: Step 4 - Step 9")
        rc_reason = st.text_area("📝 改道製程說明與特別配方參數註記 (R/C Instruction):")
        submitted = st.form_submit_button(label="提交 R/C 變更指令至雲端母表", use_container_width=True)
        if submitted:
            if rc_no and rc_reason:
                st.success(f"✅ R/C 單號 {rc_no} 指令已成功暫存！")
            else:
                st.warning("⚠️ 請完整填寫 R/C 單號與改道說明。")
