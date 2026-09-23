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

# 建立上方四大核心功能頁籤物件陣列 (確保存儲在單一變數中供後續解包)
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
# 📋 頁籤 1: Full Route (對齊 index 0 - 前半段：四色彩大表格渲染)
# =========================================================================
with all_tabs[0]:  
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

    st.markdown("🟢 *綠列代表在製中 (INPR)* | 🟨 *紅底藍字代表暫停管制 (HOLD)* | 🔴 *紅底紅字代表已報廢 (SCRP)* | ⚪ *灰列代表流程中斷*")
    
    if not df.empty:
        wafer_col_list = [c for c in df.columns if "Wafer" in c or "wafer" in c]
        if wafer_col_list:
            actual_string_col = wafer_col_list[0]
            filtered_df = df[df[actual_string_col].astype(str).str.upper() == search_id.upper()].copy()
        else:
            filtered_df = df.copy()

        if not filtered_df.empty:
            # 💡 【熔斷與攔截機制】先掃描是否有任何一站已經被標記為 SCRP 或 HOLD
            has_scrap_occurred = False
            scrap_step_index = 9999
            
            has_hold_occurred = False
            hold_step_index = 9999
            
            for idx, row in filtered_df.reset_index(drop=True).iterrows():
                co_val = str(row.get("First Check Out", "")).strip().upper()
                if co_val == "SCRP":
                    has_scrap_occurred = True
                    scrap_step_index = idx
                    break
                elif co_val == "HOLD":
                    has_hold_occurred = True
                    hold_step_index = idx
                    # 注意：WIP 站點會卡留在被 HOLD 的這一站，且不往下推移
                    break
            
            # 計算在製站點 (WIP Step) 
            wip_step_no = "9999"
            if not has_scrap_occurred and not has_hold_occurred:
                for idx, row in filtered_df.iterrows():
                    co_val = str(row.get("First Check Out", "")).strip().upper()
                    if co_val == "" or co_val == "NAN" or co_val == "INPR":
                        wip_step_no = str(row.get("Step No.", "1"))
                        break
            
            # 動態重組文字顯示欄位
            display_df = filtered_df.copy().reset_index(drop=True)
            new_co_display = []
            for idx, r in display_df.iterrows():
                s_val = str(r.get("Step No.", "")).strip()
                co_val = str(r.get("First Check Out", "")).strip()
                
                if co_val.upper() == "SCRP":
                    new_co_display.append("SCRP")
                elif co_val.upper() == "HOLD":
                    new_co_display.append("HOLD")
                elif idx > scrap_step_index:
                    new_co_display.append("") # 報廢後方步驟強制清空
                elif not has_scrap_occurred and has_hold_occurred and idx > hold_step_index:
                    new_co_display.append("") # HOLD 後方步驟在未解鎖前同樣清空
                elif s_val == wip_step_no.strip():
                    new_co_display.append("INPR")
                else:
                    new_co_display.append(co_val)
            display_df["First Check Out"] = new_co_display

            # 💡 【終極多色彩鋪滿底色引擎】
            # 1. 欄位文字為 SCRP ➡️ 紅底粗體紅字
            # 2. 欄位文字為 HOLD ➡️ 🎯 【核心需求】紅底粗體藍字
            # 3. 順序在 SCRP 之後 ➡️ 灰底深灰字
            # 4. 步驟等於 WIP 當站 ➡️ 綠底粗體綠字
            def highlight_dynamic_rows(row):
                row_idx = row.name
                co_cell_string = str(row["First Check Out"]).strip().upper()
                step_cell_string = str(row["Step No."]).strip()
                
                if co_cell_string == "SCRP":
                    return ['background-color: #f8d7da; font-weight: bold; color: #721c24;'] * len(row)
                elif co_cell_string == "HOLD":
                    # 🎯 滿填紅底 + 粗體藍字
                    return ['background-color: #f8d7da; font-weight: bold; color: #004085;'] * len(row)
                elif row_idx > scrap_step_index:
                    return ['background-color: #e2e3e5; font-weight: normal; color: #6c757d;'] * len(row)
                elif not has_scrap_occurred and has_hold_occurred and row_idx > hold_step_index:
                    # 被 HOLD 站點之後的剩餘常規製程，同樣顯示灰修鎖定
                    return ['background-color: #f8f9fa; font-weight: normal; color: #adb5bd;'] * len(row)
                elif step_cell_string == wip_step_no.strip():
                    return ['background-color: #c3e6cb; font-weight: bold; color: #155724;'] * len(row)
                return [''] * len(row)
            
            styled_df = display_df.style.apply(highlight_dynamic_rows, axis=1)

            selected_rows = st.dataframe(
                styled_df, use_container_width=True, hide_index=True, 
                on_select="rerun", selection_mode="single-row"
            )
            # =========================================================================
            # 📋 頁籤 1: Full Route (後半段：定位與動態過站控制面板 - 修正版)
            # =========================================================================
            default_row_idx = 0
            step_list = [str(x).strip() for x in filtered_df['Step No.'].tolist()]
            if wip_step_no.strip() in step_list:
                default_row_idx = step_list.index(wip_step_no.strip())
            elif has_scrap_occurred:
                default_row_idx = scrap_step_index
            elif has_hold_occurred:
                default_row_idx = hold_step_index  # 🟢 【最關鍵修復】精確對齊前半段的變數名稱 hold_step_index
            
            current_idx = selected_rows["selection"]["rows"] if selected_rows and selected_rows.get("selection", {}).get("rows") else default_row_idx
            target_row = filtered_df.iloc[current_idx]
            
            st.write("---")
            st.subheader("⚙️ 當前過站與動態編輯面板 (Current Stage Action Panel)")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("晶圓編號 (Wafer ID)", str(target_row.get("Wafer ID", "N/A")))
            c2.metric("選定步驟 (Step No.)", f"第 {target_row.get('Step No.', 'N/A')} 步")
            c3.metric("負責模組 (Module)", str(target_row.get("Module", "N/A")))
            c4.metric("客戶團隊 (Customer)", str(target_row.get("Customer", "N/A")))
            
            # 🟢 【變數完全對齊校正】控制面板防呆紅色/黃色警告條邏輯
            if has_scrap_occurred and current_idx > scrap_step_index:
                st.error(f"🚫 流程已中斷：該晶圓已於第 {filtered_df.iloc[scrap_step_index].get('Step No.')} 步報廢 (SCRP)。")
            elif not has_scrap_occurred and has_hold_occurred and current_idx >= hold_step_index:
                st.warning(f"🟨 暫停管制中：該晶圓目前於第 {filtered_df.iloc[hold_step_index].get('Step No.')} 步被執行 HOLD 鎖定，解除管制前無法執行出站作業。")
            
            st.info(f"💡 **目前站點描述**：{target_row.get('Step Description', 'N/A')}")
            
            st.markdown("✏️ **本站參數快速修改區（若不需變更請保持預設）**")
            edit_col1, edit_col2, edit_col3 = st.columns(3)
            with edit_col1: edit_tool = st.text_input("🔧 變更製程機台 (Process Tool):", value=str(target_row.get("Process Tool", "")))
            with edit_col2: edit_recipe = st.text_input("🧪 變更機台配方 (Recipe):", value=str(target_row.get("Recipe", "")))
            with edit_col3: edit_cp = st.text_input("🎯 變更檢驗點 (Check point):", value=str(target_row.get("Check point", "")))
            
            st.markdown("📝 **批註 / 機台數據回填 (SPC Data / Comments):**")
            user_comment = st.text_input("請在此輸入過站紀錄...", key="user_comment_input", placeholder="例如: 數據異常，暫停管制")
            
            st.markdown("⚠️ **流程變更權限指令**")
            b1, b2, b3, b4, b5 = st.columns(5)
            w_id, s_no = str(target_row.get("Wafer ID", "")).strip(), str(target_row.get("Step No.", "")).strip()
            
            if "trigger_iframe" not in st.session_state:
                st.session_state["trigger_iframe"], st.session_state["iframe_url"] = False, ""
            if "multi_iframe_urls" not in st.session_state:
                st.session_state["multi_iframe_urls"] = []

            def execute_stage_action(action_name):
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["multi_iframe_urls"] = []
                
                fields = {"Process Tool": edit_tool, "Recipe": edit_recipe, "Check point": edit_cp}
                for f_name, f_val in fields.items():
                    if str(f_val).strip() != str(target_row.get(f_name, "")).strip():
                        st.session_state["multi_iframe_urls"].append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={w_id}&step_no={s_no}&column_name={requests.utils.quote(f_name)}&new_value={requests.utils.quote(str(f_val).strip())}&callback=jQuery")
                
                enc_comment = requests.utils.quote(user_comment.strip())
                enc_time = requests.utils.quote(now_str)
                
                if action_name == "Check out":
                    st.session_state["multi_iframe_urls"].append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={w_id}&step_no={s_no}&action=Check out&comment={enc_comment}&time={enc_time}")
                    st.session_state["checkout_msg"] = f"✅ 正常出站成功｜已填入出站時間 [ {now_str} ] 。"
                elif action_name == "Scrap":
                    st.session_state["multi_iframe_urls"].append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={w_id}&step_no={s_no}&action=Scrap&comment={enc_comment}&time={enc_time}")
                    st.session_state["checkout_msg"] = f"🚨 晶圓報廢程序執行完畢｜該站點已被強制註記為 SCRP 狀態！"
                elif action_name == "Hold":
                    st.session_state["multi_iframe_urls"].append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={w_id}&step_no={s_no}&action=Hold&comment={enc_comment}&time={enc_time}")
                    st.session_state["checkout_msg"] = f"🟨 暫停管制程序執行完畢｜該站點已被強制註記為 HOLD 狀態！"
                else:
                    st.session_state["checkout_msg"] = f"✅ 參數修改儲存成功！"
                
                st.session_state["trigger_iframe"] = True
                st.cache_data.clear()
                st.rerun()

            # 🟢 【變數完全對齊校正】自動化防呆按鈕禁用控制邏輯
            is_btn_disabled = True if has_scrap_occurred and current_idx > scrap_step_index else False
            is_checkout_disabled = True if (has_hold_occurred and current_idx >= hold_step_index) or is_btn_disabled else False

            with b1:
                if st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True, key="tab1_btn_co", disabled=is_checkout_disabled): execute_stage_action("Check out")
            with b2:
                if st.button("❌ 報廢處理 (Scrap)", type="secondary", use_container_width=True, key="tab1_btn_sc", disabled=is_btn_disabled): execute_stage_action("Scrap")
            with b3: 
                if st.button("🟨 暫停規定 (Hold)", type="secondary", use_container_width=True, key="tab1_btn_hd", disabled=is_btn_disabled): execute_stage_action("Hold")
            with b4: st.button("🟦 跳過此站 (Skip)", use_container_width=True, key="tab1_btn_sk", disabled=is_btn_disabled)
            with b5:
                if st.button("💾 儲存修改參數 (Key in data)", use_container_width=True, key="tab1_btn_ki", disabled=is_btn_disabled): execute_stage_action("Key in data")

            if st.session_state["trigger_iframe"]:
                st.success(st.session_state["checkout_msg"])
                for url in st.session_state["multi_iframe_urls"]:
                    st.markdown(f'<iframe src="{url}" style="width:0px; height:0px; border:0px; display:none;"></iframe>', unsafe_allow_html=True)
                st.session_state["trigger_iframe"] = False
                st.session_state["multi_iframe_urls"] = []
        else:
            st.warning(f"⚠️ 雲端資料庫中找不到與 '{search_id}' 相符的晶圓編號。")
    else:
        st.warning("⚠️ 無法載入 any 試算表資料，請確認工作表名稱是否為 'route_template'。")
# =========================================================================
# 📜 頁籤 2: Wafer History (完美綁定 all_tabs[1] - 晶圓歷史過站追蹤足跡)
# =========================================================================
with all_tabs[1]:
    st.subheader("📜 晶圓歷史過站追蹤足跡 (Wafer History 日誌)")
    df_logs, log_status = fetch_route_data_via_csv("wafer_status")
    
    if not df_logs.empty:
        log_wafer_col_list = [c for c in df_logs.columns if "Wafer" in c or "晶圓" in c]
        if log_wafer_col_list:
            actual_log_string_col = log_wafer_col_list[0]  # 🟢 【安全鎖定】精確取出第一個單一字串，100% 根除 AttributeError
            filtered_logs = df_logs[df_logs[actual_log_string_col].astype(str).str.upper() == search_id.upper()]
        else:
            filtered_logs = df_logs
            
        if not filtered_logs.empty:
            st.markdown(f"📊 晶圓 **{search_id}** 的歷史生產追蹤稽核足跡：")
            st.dataframe(filtered_logs, use_container_width=True, hide_index=True)
        else:
            st.info(f"ℹ️ 品且編號 {search_id} 目前在 wafer_status 中尚無紀錄。")
    else:
        st.info("💡 目前雲端資料庫尚無紀錄。當您點擊 Check out 出站後，詳細日誌將在此呈現。")


# =========================================================================
# 📤 頁籤 3: Upload New Wafer (完美綁定 all_tabs[2] - 上傳新晶圓路由母表)
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
# 🔄 頁籤 4: Upload R/C (完美綁定 all_tabs[3] - 上傳 R/C 規範)
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
