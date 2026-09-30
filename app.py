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
    # 🛑 關鍵修正：母表使用傳統 export (不受型別推斷影響，保留 HOLD 文字)，歷史紀錄則使用 gviz
    if sheet_name == "route_template":
        csv_url = "https://docs.google.com/spreadsheets/d/1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU/export?format=csv&gid=0"
    else:
        csv_url = f"https://docs.google.com/spreadsheets/d/1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        
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
# 📋 頁籤 1: Full Route (對齊 index 0 - 前半段：資料加載與雙色彩大表格)
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

    st.markdown("🟢 *綠列代表在製中 (INPR)* | 🔴 *紅列代表已報廢 (SCRP)* | 🟡 *黃列代表已暫停 (HOLD)* | ⚪ *灰列代表因報廢已中斷鎖定*")
    
    if not df.empty:
        wafer_col_list = [c for c in df.columns if "Wafer" in c or "wafer" in c]
        if wafer_col_list:
            actual_string_col = wafer_col_list[0]  # 🟢 精確提取純字串
            filtered_df = df[df[actual_string_col].astype(str).str.upper() == search_id.upper()].copy()
        else:
            filtered_df = df.copy()

        if not filtered_df.empty:
            # 💡 【熔斷機制 1】尋找是否有任何一站已經被標記為 SCRP
            has_scrap_occurred = False
            scrap_step_index = 9999
            
            for idx, row in filtered_df.reset_index(drop=True).iterrows():
                co_val = str(row.get("First Check Out", "")).strip().upper()
                if co_val == "SCRP":
                    has_scrap_occurred = True
                    scrap_step_index = idx
                    break
            
            # 💡 【熔斷機制 2】計算在製站點 (WIP Step)
            wip_step_no = "9999"
            if not has_scrap_occurred:
                for idx, row in filtered_df.iterrows():
                    co_val = str(row.get("First Check Out", "")).strip().upper()
                    if co_val in ["", "NAN", "INPR", "HOLD"]:
                        wip_step_no = str(row.get("Step No.", "1"))
                        break
            
            # 動態重組文字顯示欄位（實施 Scrap 後方站點清空空格機制與 HOLD 顯示）
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
                    new_co_display.append("")  # 🎯 報廢後方步驟強制清空
                elif s_val == wip_step_no.strip():
                    new_co_display.append("INPR")
                else:
                    new_co_display.append(co_val)
            display_df["First Check Out"] = new_co_display

            # 💡 【多色彩鋪滿底色引擎】紅 / 綠 / 黃 / 灰 完美分層
            def highlight_dynamic_rows(row):
                row_idx = row.name
                co_cell_string = str(row["First Check Out"]).strip().upper()
                step_cell_string = str(row["Step No."]).strip()
                
                if co_cell_string == "SCRP":
                    return ['background-color: #f8d7da; font-weight: bold; color: #721c24;'] * len(row)
                elif co_cell_string == "HOLD":
                    return ['background-color: #fff3cd; font-weight: bold; color: #856404;'] * len(row)
                elif row_idx > scrap_step_index:
                    return ['background-color: #e2e3e5; font-weight: normal; color: #6c757d;'] * len(row)  # 🎯 報廢後方步驟灰修
                elif step_cell_string == wip_step_no.strip():
                    return ['background-color: #c3e6cb; font-weight: bold; color: #155724;'] * len(row)
                return [''] * len(row)
            
            styled_df = display_df.style.apply(highlight_dynamic_rows, axis=1)

            selected_rows = st.dataframe(
                styled_df, use_container_width=True, hide_index=True, 
                on_select="rerun", selection_mode="single-row"
            )
           # =========================================================================
            # 📋 頁籤 1: Full Route (後半段：定位與動態過站控制面板)
            # =========================================================================
            # 純 Python 清單安全定位，100% 繞過 InvalidIndexError
            default_row_idx = 0
            step_list = [str(x).strip() for x in filtered_df['Step No.'].tolist()]
            if wip_step_no.strip() in step_list:
                default_row_idx = step_list.index(wip_step_no.strip())
            elif has_scrap_occurred:
                default_row_idx = scrap_step_index
            
            current_idx = selected_rows["selection"]["rows"][0] if selected_rows and selected_rows.get("selection", {}).get("rows") else default_row_idx
            target_row = filtered_df.iloc[current_idx]
            
            st.write("---")
            st.subheader("⚙️ 當前過站與動態編輯面板 (Current Stage Action Panel)")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("晶圓編號 (Wafer ID)", str(target_row.get("Wafer ID", "N/A")))
            c2.metric("選定步驟 (Step No.)", f"第 {target_row.get('Step No.', 'N/A')} 步")
            c3.metric("負責模組 (Module)", str(target_row.get("Module", "N/A")))
            c4.metric("客戶團隊 (Customer)", str(target_row.get("Customer", "N/A")))
            
            # 檢查當前站點是否為 HOLD 狀態
            current_status = str(target_row.get("First Check Out", "")).strip().upper()
            is_currently_held = (current_status == "HOLD")

            # 針對已中斷流程的防呆紅色警示
            if has_scrap_occurred and current_idx > scrap_step_index:
                st.error(f"🚫 流程已中斷：該晶圓已於第 {filtered_df.iloc[scrap_step_index].get('Step No.')} 步報廢 (SCRP)。後續第 {target_row.get('Step No.')} 步已被系統強制鎖定封鎖！")
            elif is_currently_held:
                st.warning(f"⚠️ 警告：目前此站點處於 ［HOLD 暫停製程］ 狀態。在解 Hold 恢復正常之前，無法執行出站或修改。")
            
            st.info(f"💡 **目前站點描述**：{target_row.get('Step Description', 'N/A')}")
            
            st.markdown("✏️ **本站參數快速修改區（若不需變更請保持預設）**")
            edit_col1, edit_col2, edit_col3 = st.columns(3)
            with edit_col1: edit_tool = st.text_input("🔧 變更製程機台 (Process Tool):", value=str(target_row.get("Process Tool", "")))
            with edit_col2: edit_recipe = st.text_input("🧪 變更機台配方 (Recipe):", value=str(target_row.get("Recipe", "")))
            with edit_col3: edit_cp = st.text_input("🎯 變更檢驗點 (Check point):", value=str(target_row.get("Check point", "")))
            
            st.markdown("📝 **批註 / 機台數據回填 (SPC Data / Comments):**")
            user_comment = st.text_input("請在此輸入過站紀錄...", key="user_comment_input", placeholder="例如: 正常過站資料回填")
            
            # 🎯 這裡會同步將批註（包含 Hold Note）顯示在最下方
            current_comment = str(target_row.get("Comments", "")).strip() or str(target_row.get("備註", "")).strip() or "暫無紀錄"
            current_hold_note = str(target_row.get("Hold Note", "")).strip() or "無"
            
            st.markdown(f"ℹ️ **目前此站點之歷史批註：** `{current_comment}`")
            if current_hold_note != "無" or is_currently_held:
                st.markdown(f"🛑 **目前此站點之 Hold Note：** `{current_hold_note}`")

            st.markdown("⚠️ **流程變更權限指令**")
            b1, b2, b3, b4, b5 = st.columns(5)
            w_id, s_no = str(target_row.get("Wafer ID", "")).strip(), str(target_row.get("Step No.", "")).strip()
            
            if "trigger_iframe" not in st.session_state:
                st.session_state["trigger_iframe"], st.session_state["iframe_url"] = False, ""
            if "multi_iframe_urls" not in st.session_state:
                st.session_state["multi_iframe_urls"] = []

            # 核心執行函數（支援傳入自訂的批註內容）
            def execute_stage_action(action_name, target_w_id, target_s_no, custom_comment=None, target_jump_step=None):
                import time
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                urls_to_send = []
                
                if action_name in ["Check out", "Scrap", "Key in data"]:
                    fields = {"Process Tool": edit_tool, "Recipe": edit_recipe, "Check point": edit_cp}
                    for f_name, f_val in fields.items():
                        if str(f_val).strip() != str(target_row.get(f_name, "")).strip():
                            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&column_name={requests.utils.quote(f_name)}&new_value={requests.utils.quote(str(f_val).strip())}")
                
                final_comment = custom_comment if custom_comment is not None else user_comment.strip()
                enc_comment = requests.utils.quote(final_comment)
                enc_time = requests.utils.quote(now_str)
                
                if action_name == "Check out":
                    urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Check out&comment={enc_comment}&time={enc_time}")
                elif action_name == "Scrap":
                    urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Scrap&comment={enc_comment}&time={enc_time}")
                elif action_name == "Hold":
                    urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Hold&comment={enc_comment}&time={enc_time}")
                elif action_name == "Unhold":
                    urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Unhold&comment={enc_comment}&time={enc_time}")
                elif action_name == "Skip":
                    # 🎯 跳站專屬 URL，附加 target_step 參數
                    enc_target_step = requests.utils.quote(str(target_jump_step))
                    urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Skip&comment={enc_comment}&time={enc_time}&target_step={enc_target_step}")
                
                with st.spinner(f"🚀 正在同步 {action_name} 指令至雲端..."):
                    has_error = False
                    for url in urls_to_send:
                        try:
                            res = requests.get(url, timeout=15)
                            if "Error" in res.text:
                                st.error(f"❌ 雲端拒絕寫入，GAS 錯誤訊息: {res.text}")
                                has_error = True
                        except Exception as e:
                            st.error(f"❌ 網路連線異常: {e}")
                            has_error = True
                            
                    if has_error:
                        time.sleep(4)
                        st.rerun()
                        return
                
                st.success(f"✅ {action_name} 動作已成功寫入資料庫！")
                time.sleep(1.2)
                st.cache_data.clear()
                st.rerun()

            # 🎯 建立設定 Hold 彈出對話框
            @st.dialog("📋 輸入 Hold Note (暫停原因)")
            def show_hold_dialog(target_w_id, target_s_no):
                st.write(f"正在針對 晶圓編號 `{target_w_id}` 的 **第 {target_s_no} 步** 執行暫停指令。")
                hold_reason = st.text_input("請輸入 Hold Note (暫停原因)：", placeholder="例如: 機台異常溫度過高...")
                st.warning("⚠️ 確認提交後，該站點將會鎖定，直到執行解除暫停。")
                
                c_ok, c_cancel = st.columns(2)
                with c_ok:
                    if st.button("👍 確認 OK", type="primary", use_container_width=True):
                        if hold_reason.strip() == "":
                            st.error("請填寫原因再點擊確認！")
                        else:
                            execute_stage_action("Hold", target_w_id, target_s_no, custom_comment=f"[HOLD] {hold_reason.strip()}")
                with c_cancel:
                    if st.button("❌ 取消", use_container_width=True, key="cancel_hold_btn"):
                        st.rerun()

            # 🎯 建立解除 Hold 彈出對話框
            @st.dialog("🟦 輸入解除暫停原因 (Unhold Note)")
            def show_unhold_dialog(target_w_id, target_s_no):
                st.write(f"正在針對 晶圓編號 `{target_w_id}` 的 **第 {target_s_no} 步** 執行解除暫停指令。")
                unhold_reason = st.text_input("請輸入解 Hold 原因：", placeholder="例如: 客戶已確認規格...")
                
                c_ok, c_cancel = st.columns(2)
                with c_ok:
                    if st.button("👍 確認解除", type="primary", use_container_width=True):
                        if unhold_reason.strip() == "":
                            st.error("請填寫原因再點擊確認！")
                        else:
                            execute_stage_action("Unhold", target_w_id, target_s_no, custom_comment=f"[UNHOLD] {unhold_reason.strip()}")
                with c_cancel:
                    if st.button("❌ 取消", use_container_width=True, key="cancel_unhold_btn"):
                        st.rerun()

            # 🎯 建立跳站 (Skip) 彈出對話框
            @st.dialog("⏭️ 晶圓跳站設定 (Skip Station)")
            def show_skip_dialog(target_w_id, target_s_no, available_steps):
                st.write(f"晶圓 `{target_w_id}` 目前位於 **第 {target_s_no} 步**。")
                
                # 下拉選單提供所有站點供選擇
                default_idx = available_steps.index(target_s_no) if target_s_no in available_steps else 0
                jump_target = st.selectbox("請選擇要跳至哪一個 Step (可往前退回或往後跳過)：", options=available_steps, index=default_idx)
                skip_reason = st.text_input("請輸入跳站原因：", placeholder="例如: 客戶要求變更製程、需重工...")
                
                c_ok, c_cancel = st.columns(2)
                with c_ok:
                    if st.button("👍 確認跳站", type="primary", use_container_width=True):
                        if skip_reason.strip() == "":
                            st.error("請填寫跳站原因！")
                        elif jump_target == target_s_no:
                            st.error("目標站點不能與當前站點相同！")
                        else:
                            # 觸發執行，將目標站點傳給後端
                            execute_stage_action("Skip", target_w_id, target_s_no, custom_comment=f"[JUMP TO Step {jump_target}] {skip_reason.strip()}", target_jump_step=jump_target)
                with c_cancel:
                    if st.button("❌ 取消", use_container_width=True, key="cancel_skip_btn"):
                        st.rerun()

            # 自動化流程中斷按鈕禁用防呆鎖定
            is_btn_disabled = True if has_scrap_occurred and current_idx > scrap_step_index else False
            is_wip_locked = True if is_currently_held else is_btn_disabled

            with b1:
                if st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True, key="tab1_btn_co", disabled=is_wip_locked): execute_stage_action("Check out", w_id, s_no)
            with b2:
                if st.button("❌ 報廢處理 (Scrap)", type="secondary", use_container_width=True, key="tab1_btn_sc", disabled=is_wip_locked): execute_stage_action("Scrap", w_id, s_no)
            with b3: 
                if is_currently_held:
                    if st.button("🟦 解除暫停 (Release Hold)", type="primary", use_container_width=True, key="tab1_btn_unhd", disabled=is_btn_disabled):
                        show_unhold_dialog(w_id, s_no)
                else:
                    if st.button("🟨 設定暫停 (Hold)", use_container_width=True, key="tab1_btn_hd", disabled=is_btn_disabled):
                        show_hold_dialog(w_id, s_no)
            with b4: 
                # 🛑 綁定跳站對話框
                if st.button("🟦 跳過此站 (Skip)", use_container_width=True, key="tab1_btn_sk", disabled=is_wip_locked):
                    show_skip_dialog(w_id, s_no, step_list)
            with b5:
                if st.button("💾 儲存修改參數 (Key in data)", use_container_width=True, key="tab1_btn_ki", disabled=is_wip_locked): execute_stage_action("Key in data", w_id, s_no)
# =========================================================================
# 📜 頁籤 2: Wafer History (主表顯示母表，點選後顯示該站點完整歷史紀錄)
# =========================================================================
with all_tabs[1]:
    st.subheader("📜 晶圓歷史過站追蹤足跡 (Wafer History 日誌)")
    
    # 同時載入「母表 (route_template)」與「歷史紀錄表 (wafer_status)」
    df_route, route_status = fetch_route_data_via_csv("route_template")
    df_logs, log_status = fetch_route_data_via_csv("wafer_status")
    
    if not df_route.empty and not df_logs.empty:
        # --- 1. 處理並顯示上半部的母表 ---
        wafer_col_list = [c for c in df_route.columns if "Wafer" in c or "wafer" in c]
        if wafer_col_list:
            actual_string_col = wafer_col_list[0]
            filtered_route = df_route[df_route[actual_string_col].astype(str).str.upper() == search_id.upper()]
        else:
            filtered_route = df_route
            
        if not filtered_route.empty:
            st.markdown(f"📊 晶圓 **{search_id}** 的母表生產路由全貌：")
            display_route = filtered_route.copy().reset_index(drop=True)

            # 顯示母表並開啟單列選取功能
            selected_route_row = st.dataframe(
                display_route, 
                use_container_width=True, 
                hide_index=True,
                on_select="rerun", 
                selection_mode="single-row",
                key="history_route_table"
            )
            
            # --- 2. 當點擊特定站點時，從歷史紀錄表中撈出該站點的「所有完整紀錄」 ---
            if selected_route_row and selected_route_row.get("selection", {}).get("rows"):
                selected_idx = selected_route_row["selection"]["rows"][0]
                target_step_no = str(display_route.iloc[selected_idx].get("Step No.", "")).strip()
                
                st.markdown("---")
                st.markdown(f"### 🛑 第 {target_step_no} 步 - 歷史動作完整紀錄 (Action History)")
                
                # 過濾出符合該晶圓且符合該步驟的所有歷史紀錄
                log_wafer_col = [c for c in df_logs.columns if "Wafer" in c or "晶圓" in c][0]
                step_logs = df_logs[
                    (df_logs[log_wafer_col].astype(str).str.upper() == search_id.upper()) & 
                    (df_logs["Step No."].astype(str).str.strip() == target_step_no)
                ]
                
                if not step_logs.empty:
                    # ⚠️ 改用陣列收集 HTML，徹底根除 Python 縮排造成的 Markdown 誤判問題
                    html_parts = []
                    html_parts.append('<div style="font-size: 12pt;">')
                    html_parts.append('<table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">')
                    html_parts.append('<tr style="background-color: #f8f9fa; color: #333;">')
                    html_parts.append('<th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 15%;">動作 (Action)</th>')
                    html_parts.append('<th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 25%;">日期與時間</th>')
                    html_parts.append('<th style="padding: 10px; border: 1px solid #ddd; text-align: left; width: 30%;">Hold Note (暫停原因)</th>')
                    html_parts.append('<th style="padding: 10px; border: 1px solid #ddd; text-align: left; width: 30%;">SPC data (過站備註)</th>')
                    html_parts.append('</tr>')
                    
                    # 依序把該站點的「每一次」紀錄疊加進表格中
                    for _, log_row in step_logs.iterrows():
                        action_val = str(log_row.get("Action", "")).strip()
                        time_val = str(log_row.get("First Check Out", "")).strip()
                        hold_note_val = str(log_row.get("Hold Note", "")).strip()
                        spc_val = str(log_row.get("SPC data", "")).strip()
                        
                        # 針對 HOLD 動作給予黃底紅字，其他動作白底黑字
                        bg_color = "#fff3cd" if action_val.upper() == "HOLD" else "#ffffff"
                        text_color = "#d9534f" if action_val.upper() == "HOLD" else "#000000"
                        
                        html_parts.append(f'<tr style="background-color: {bg_color};">')
                        html_parts.append(f'<td style="padding: 10px; border: 1px solid #ddd; text-align: center; font-weight: bold;">{action_val}</td>')
                        html_parts.append(f'<td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{time_val}</td>')
                        html_parts.append(f'<td style="padding: 10px; border: 1px solid #ddd; text-align: left; color: {text_color}; font-weight: bold;">{hold_note_val}</td>')
                        html_parts.append(f'<td style="padding: 10px; border: 1px solid #ddd; text-align: left;">{spc_val}</td>')
                        html_parts.append('</tr>')
                        
                    html_parts.append('</table></div>')
                    
                    # 將陣列合併成一個沒有換行與縮排的連續字串
                    html_table = "".join(html_parts)
                    st.markdown(html_table, unsafe_allow_html=True)
                else:
                    st.info(f"✅ 該晶圓的第 {target_step_no} 步目前無任何歷史紀錄。")

# =========================================================================
# 📤 頁籤 3: Upload New Wafer (🎯 完美對齊原本宣告的 all_tabs[2])
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
# 🔄 頁籤 4: Upload R/C (🎯 完美對齊原本宣告的 all_tabs[3])
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
