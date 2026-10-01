import streamlit as st
import pandas as pd
import requests
import datetime
import time      # 👈 請確保最上方有加上這一行
import re

# =========================================================================
# 1. 系統全域基礎配置與資料載入
# =========================================================================
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

# 🔴 這是您部署成功的實體國研院內部 GAS API 執行網址
MY_ORGANIZATION_GAS_URL = "https://script.google.com/macros/s/AKfycbxSpHeSlbCyMgn0cH60fh62eM_nYoaCwkSCZF1UJMTeC-3z1wQJ1RVLXge1kvzadmKM/exec"
SPREADSHEET_ID = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"

# 建立上方四大核心功能頁籤物件陣列 (確保存儲在單一變數中供後續解包)
all_tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "📊 Wafer Overview", "📦 Bank Wafers"])

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
# 📋 頁籤 1: Full Route (過站與操作核心)
# =========================================================================
with all_tabs[0]:
    target_w_id = st.text_input("🔍 請輸入或掃描晶圓 ID (Wafer ID):", key="search_w_id")
    
    if target_w_id and not df_route.empty:
        # 動態尋找真實欄位名稱 (防呆)
        wafer_col = next((c for c in df_route.columns if str(c).strip().lower() in ["wafer id", "id", "wafer"]), "Wafer ID")
        filtered_df = df_route[df_route[wafer_col].astype(str).str.strip().str.upper() == target_w_id.strip().upper()]
        
        if not filtered_df.empty:
            st.markdown("🟢 *綠列代表在製中 (INPR)* | 🔴 *紅列代表已報廢 (SCRP)* | 🟡 *黃列代表已暫停 (HOLD)* | 🧊 *藍列代表已入庫 (BANK)* | ⚪ *灰列代表因報廢已中斷鎖定*")
            
            # 動態抓取 Check out 欄位名稱 (防呆，相容 Check out Time)
            fco_col = next((c for c in filtered_df.columns if "check out" in str(c).lower()), "First Check Out")
            
            # 💡 【熔斷機制 1】尋找是否有任何一站已經被標記為 SCRP
            has_scrap_occurred = False
            scrap_step_index = 9999
            
            for idx, row in filtered_df.reset_index(drop=True).iterrows():
                co_val = str(row.get(fco_col, "")).strip().upper()
                if co_val == "SCRP":
                    has_scrap_occurred = True
                    scrap_step_index = idx
                    break
            
            # 💡 【熔斷機制 2】計算在製站點 (WIP Step)
            wip_step_no = "9999"
            wip_row_idx = 9999
            if not has_scrap_occurred:
                for idx, row in filtered_df.reset_index(drop=True).iterrows():
                    co_val = str(row.get(fco_col, "")).strip().upper()
                    # 🎯 將 BANK 納入停站判斷，讓它停在當站反藍
                    if co_val in ["", "NAN", "INPR", "HOLD", "BANK"]:
                        wip_row_idx = idx
                        wip_step_no = str(row.get("Step No.", "1"))
                        break
            
            # 動態重組文字顯示欄位
            display_df = filtered_df.copy().reset_index(drop=True)
            new_co_display = []
            for idx, r in display_df.iterrows():
                co_val = str(r.get(fco_col, "")).strip().upper()
                if co_val == "SCRP": new_co_display.append("SCRP")
                elif co_val == "HOLD": new_co_display.append("HOLD")
                elif co_val == "BANK": new_co_display.append("BANK")
                elif idx > scrap_step_index: new_co_display.append("") 
                elif idx == wip_row_idx: new_co_display.append("INPR")
                else: new_co_display.append(str(r.get(fco_col, "")))
            display_df[fco_col] = new_co_display

            # 💡 多色彩鋪滿底色引擎
            def highlight_dynamic_rows(row):
                row_idx = row.name
                co_cell_string = str(row[fco_col]).strip().upper()
                
                if co_cell_string == "SCRP": return ['background-color: #f8d7da; font-weight: bold; color: #721c24;'] * len(row)
                elif co_cell_string == "HOLD": return ['background-color: #fff3cd; font-weight: bold; color: #856404;'] * len(row)
                elif co_cell_string == "BANK": return ['background-color: #d1ecf1; font-weight: bold; color: #0c5460;'] * len(row)
                elif row_idx > scrap_step_index: return ['background-color: #e2e3e5; font-weight: normal; color: #6c757d;'] * len(row)
                elif row_idx == wip_row_idx: return ['background-color: #c3e6cb; font-weight: bold; color: #155724;'] * len(row)
                return [''] * len(row)
            
            styled_df = display_df.style.apply(highlight_dynamic_rows, axis=1)

            selected_rows = st.dataframe(
                styled_df, use_container_width=True, hide_index=True, 
                on_select="rerun", selection_mode="single-row"
            )

            # --- 下方操作面板區塊 ---
            if len(selected_rows.selection.rows) > 0:
                current_idx = selected_rows.selection.rows[0]
                target_row = display_df.iloc[current_idx]
                w_id = str(target_row.get(wafer_col, ""))
                s_no = str(target_row.get("Step No.", ""))
                
                st.markdown(f"### ⚙️ 針對 `{w_id}` - 第 {s_no} 步進行操作")
                
                c_edit1, c_edit2, c_edit3 = st.columns(3)
                with c_edit1: edit_tool = st.text_input("Process Tool", value=str(target_row.get("Process Tool", "")))
                with c_edit2: edit_recipe = st.text_input("Recipe", value=str(target_row.get("Recipe", "")))
                with c_edit3: edit_cp = st.text_input("Check point", value=str(target_row.get("Check point", "")))
                
                user_comment = st.text_input("📝 填寫備註 (選填，將記錄於雲端母表):")
                step_list = display_df["Step No."].astype(str).tolist()

                # --- API 執行核心函式 ---
                def execute_stage_action(action_name, target_w_id, target_s_no, custom_comment=None, target_jump_step=None):
                    # 🎯 強制指定為台灣時間 (UTC+8)
                    tw_tz = datetime.timezone(datetime.timedelta(hours=8))
                    now_str = datetime.datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
                    
                    urls_to_send = []
                    
                    if action_name in ["Check out", "Scrap", "Key in data"]:
                        fields = {"Process Tool": edit_tool, "Recipe": edit_recipe, "Check point": edit_cp}
                        for f_name, f_val in fields.items():
                            if str(f_val).strip() != str(target_row.get(f_name, "")).strip():
                                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&column_name={requests.utils.quote(f_name)}&new_value={requests.utils.quote(str(f_val).strip())}")
                    
                    final_comment = custom_comment if custom_comment is not None else user_comment.strip()
                    enc_comment = requests.utils.quote(final_comment)
                    enc_time = requests.utils.quote(now_str)
                    
                    if action_name == "Check out": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Check out&comment={enc_comment}&time={enc_time}")
                    elif action_name == "Scrap": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Scrap&comment={enc_comment}&time={enc_time}")
                    elif action_name == "Unscrap": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Unscrap&comment={enc_comment}&time={enc_time}")
                    elif action_name == "Hold": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Hold&comment={enc_comment}&time={enc_time}")
                    elif action_name == "Unhold": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Unhold&comment={enc_comment}&time={enc_time}")
                    elif action_name == "Bank": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Bank&comment={enc_comment}&time={enc_time}")
                    elif action_name == "Kick off": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Kick off&comment={enc_comment}&time={enc_time}")
                    elif action_name == "Skip":
                        enc_target_step = requests.utils.quote(str(target_jump_step))
                        urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={target_w_id}&step_no={target_s_no}&action=Skip&comment={enc_comment}&time={enc_time}&target_step={enc_target_step}")
                    
                    with st.spinner(f"🚀 正在同步 {action_name} 指令至雲端..."):
                        has_error = False
                        for url in urls_to_send:
                            try:
                                res = requests.get(url, timeout=15)
                                if "Error" in res.text:
                                    st.error(f"❌ GAS 錯誤訊息: {res.text}")
                                    has_error = True
                            except Exception as e:
                                st.error(f"❌ 網路異常: {e}")
                                has_error = True
                        if has_error:
                            time.sleep(4)
                            st.rerun()
                            return
                    st.success(f"✅ {action_name} 動作成功寫入！")
                    time.sleep(1.2)
                    st.cache_data.clear()
                    st.rerun()

                # --- 彈出對話框定義 ---
                @st.dialog("📋 輸入 Hold Note")
                def show_hold_dialog(tw_id, ts_no):
                    r = st.text_input("暫停原因：")
                    c_ok, c_cancel = st.columns(2)
                    if c_ok.button("👍 確認", type="primary", use_container_width=True): execute_stage_action("Hold", tw_id, ts_no, f"[HOLD] {r.strip()}")
                    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

                @st.dialog("🟦 輸入解 Hold 原因")
                def show_unhold_dialog(tw_id, ts_no):
                    r = st.text_input("解 Hold 原因：")
                    c_ok, c_cancel = st.columns(2)
                    if c_ok.button("👍 確認", type="primary", use_container_width=True): execute_stage_action("Unhold", tw_id, ts_no, f"[UNHOLD] {r.strip()}")
                    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

                @st.dialog("❌ 輸入報廢原因")
                def show_scrap_dialog(tw_id, ts_no):
                    r = st.text_input("報廢原因：")
                    c_ok, c_cancel = st.columns(2)
                    if c_ok.button("👍 確認報廢", type="primary", use_container_width=True): execute_stage_action("Scrap", tw_id, ts_no, f"[SCRAP] {r.strip()}")
                    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

                @st.dialog("🔄 輸入解除報廢原因")
                def show_unscrap_dialog(tw_id, ts_no):
                    r = st.text_input("復原原因：")
                    c_ok, c_cancel = st.columns(2)
                    if c_ok.button("👍 確認復原", type="primary", use_container_width=True): execute_stage_action("Unscrap", tw_id, ts_no, f"[UNSCRAP] {r.strip()}")
                    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

                @st.dialog("📦 晶圓入庫 (Bank)")
                def show_bank_dialog(tw_id, ts_no):
                    st.info("💡 入庫後，晶圓將暫時從 Wafer Overview 中隱藏。")
                    r = st.text_input("Bank 原因：")
                    c_ok, c_cancel = st.columns(2)
                    if c_ok.button("👍 確認入庫", type="primary", use_container_width=True): execute_stage_action("Bank", tw_id, ts_no, f"[BANK] {r.strip()}")
                    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

                @st.dialog("🚀 晶圓出庫 (Kick off)")
                def show_bankout_dialog(tw_id, ts_no):
                    st.info("💡 恢復後，晶圓將重新出現於 Wafer Overview 中。")
                    r = st.text_input("Kick off 原因：")
                    c_ok, c_cancel = st.columns(2)
                    if c_ok.button("👍 確認開始", type="primary", use_container_width=True): execute_stage_action("Kick off", tw_id, ts_no, f"[KICK OFF] {r.strip()}")
                    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

                @st.dialog("⏭️ 晶圓跳站")
                def show_skip_dialog(tw_id, ts_no, avail_steps):
                    default_idx = avail_steps.index(ts_no) if ts_no in avail_steps else 0
                    j_target = st.selectbox("跳至：", options=avail_steps, index=default_idx)
                    r = st.text_input("跳站原因：")
                    c_ok, c_cancel = st.columns(2)
                    if c_ok.button("👍 確認跳站", type="primary", use_container_width=True):
                        execute_stage_action("Skip", tw_id, ts_no, f"[JUMP TO Step {j_target}] {r.strip()}", j_target)
                    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

                # --- 狀態按鈕判定 ---
                fco_status = str(target_row.get(fco_col, "")).strip().upper()
                is_currently_scrapped = (fco_status == "SCRP")
                is_currently_held = (fco_status == "HOLD")
                is_currently_banked = (fco_status == "BANK")

                is_btn_disabled = True if has_scrap_occurred and current_idx > scrap_step_index else False
                is_wip_locked = True if is_currently_held or is_currently_banked else is_btn_disabled

                st.markdown("---")
                b1, b2, b3, b4, b5, b6 = st.columns(6)
                with b1:
                    if st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True, disabled=is_wip_locked): execute_stage_action("Check out", w_id, s_no)
                with b2:
                    if is_currently_scrapped:
                        if st.button("🔄 復原報廢", type="primary", use_container_width=True, disabled=is_btn_disabled): show_unscrap_dialog(w_id, s_no)
                    else:
                        if st.button("❌ 報廢處理 (Scrap)", type="secondary", use_container_width=True, disabled=is_wip_locked): show_scrap_dialog(w_id, s_no)
                with b3: 
                    if is_currently_held:
                        if st.button("🟦 解除暫停", type="primary", use_container_width=True, disabled=is_btn_disabled): show_unhold_dialog(w_id, s_no)
                    else:
                        if st.button("🟨 設定暫停", use_container_width=True, disabled=is_wip_locked): show_hold_dialog(w_id, s_no)
                with b4: 
                    if st.button("🟦 跳過此站", use_container_width=True, disabled=is_wip_locked): show_skip_dialog(w_id, s_no, step_list)
                with b5:
                    if st.button("💾 儲存修改參數", use_container_width=True, disabled=is_wip_locked): execute_stage_action("Key in data", w_id, s_no)
                with b6:
                    if is_currently_banked:
                        if st.button("🚀 Kick off (出庫)", type="primary", use_container_width=True, disabled=is_btn_disabled): show_bankout_dialog(w_id, s_no)
                    else:
                        if st.button("📦 Bank (入庫隱藏)", use_container_width=True, disabled=is_wip_locked): show_bank_dialog(w_id, s_no)
        else:
            st.warning("查無此 Wafer ID，請重新確認。")
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
                target_step_no = str(display_route.iloc[selected_idx].get("Step", "")).strip()
                
                st.markdown("---")
                st.markdown(f"### 🛑 第 {target_step_no} 步 - 歷史動作完整紀錄 (Action History)")
                
                # 過濾出符合該晶圓且符合該步驟的所有歷史紀錄
                log_wafer_col = [c for c in df_logs.columns if "Wafer" in c or "晶圓" in c][0]
                step_logs = df_logs[
                    (df_logs[log_wafer_col].astype(str).str.upper() == search_id.upper()) & 
                    (df_logs["Step"].astype(str).str.strip() == target_step_no)
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
                        time_val = str(log_row.get("Check out Time", "")).strip()
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
# 📤 頁籤 3: Upload New Wafer (批次上傳 & 自動帶入 BANK)
# =========================================================================
with all_tabs[2]:
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
    st.markdown("供製程整合工程師導入全新批次的生產路由檔案。上傳時系統會自動將每一片晶圓的第 1 站預設為 `BANK` (入庫) 狀態。")
    
    uploaded_file = st.file_uploader("選擇全新批次生產路由檔案 (.csv 或 .xlsx)", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            df_upload = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            df_upload = df_upload.fillna("")
            
            # 🎯 智慧欄位尋找：確保能找到 Wafer ID 與 Check out Time 欄位
            upload_wafer_col = next((c for c in df_upload.columns if str(c).strip().lower() in ["wafer id", "id", "wafer"]), "Wafer ID")
            upload_fco_col = next((c for c in df_upload.columns if "check out" in str(c).lower()), "Check out Time")
            
            if upload_wafer_col in df_upload.columns:
                if upload_fco_col not in df_upload.columns:
                    df_upload["Check out Time"] = ""
                    upload_fco_col = "Check out Time"
                
                # 🎯 自動化邏輯：將每一片 Wafer 的第一站強制作為 BANK
                for wid, group in df_upload.groupby(upload_wafer_col, sort=False):
                    if not group.empty:
                        first_idx = group.index[0]
                        df_upload.at[first_idx, upload_fco_col] = "BANK"
            
            st.info("💡 **資料預覽與編輯**：第 1 站已自動設定為 BANK。您可直接點擊儲存格修改，確認無誤後再上傳。")
            edited_df = st.data_editor(df_upload, use_container_width=True, num_rows="dynamic", key="wafer_upload_editor")
            
            st.markdown("---")
            if st.button("🚀 確認資料無誤，開始批量寫入雲端母表", type="primary", use_container_width=True):
                with st.spinner("⏳ 正在將資料打包發送至 Google Sheets，請稍候..."):
                    payload = {"action": "bulk_upload", "data": edited_df.to_dict(orient="records")}
                    try:
                        res = requests.post(MY_ORGANIZATION_GAS_URL, json=payload, timeout=30)
                        if res.status_code == 200 and "Success" in res.text:
                            st.success("✅ 批量寫入成功！全新晶圓已入庫。")
                            time.sleep(2)
                            st.cache_data.clear()
                            st.rerun()
                        else: st.error(f"❌ 寫入失敗：{res.text}")
                    except Exception as e: st.error(f"❌ 網路發送失敗: {e}")
        except Exception as e:
            st.error(f"❌ 檔案解析失敗: {str(e)}")
            
# =========================================================================
# 📊 頁籤 4: Wafer Overview (自動隱藏 Bank 晶圓)
# =========================================================================
with all_tabs[3]:
    st.subheader("📊 晶圓生產總表與進度追蹤 (Wafer Overview)")
    st.markdown("即時彙整線上所有晶圓的生產進度。尚未 Kick off 或已入庫 (Bank) 的晶圓將暫時隱藏。")

    df_route, conn_status = fetch_route_data_via_csv("route_template")
    
    if not df_route.empty:
        wafer_col = next((c for c in df_route.columns if str(c).strip().lower() in ["wafer id", "id", "wafer"]), "Wafer ID")
        step_col = next((c for c in df_route.columns if str(c).strip().lower() in ["step", "step no.", "step no"]), "Step")
        shuttle_col = next((c for c in df_route.columns if "shuttle" in str(c).lower()), "Shuttle Name")
        owner_col = next((c for c in df_route.columns if "owner" in str(c).lower()), "Stage Owner")
        team_col = next((c for c in df_route.columns if "customer" in str(c).lower()), "Customer")
        fco_col = next((c for c in df_route.columns if "check out" in str(c).lower()), "Check out Time")
        desc_col = next((c for c in df_route.columns if "description" in str(c).lower()), "Step description")
        
        if wafer_col in df_route.columns:
            html_table = """<style>
.overview-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; margin-top: 10px; }
.overview-table th { background-color: #f8f9fa; padding: 12px 10px; border: 1px solid #dee2e6; text-align: left; font-weight: bold; color: #495057; }
.overview-table td { padding: 10px; border: 1px solid #dee2e6; text-align: left; vertical-align: middle; color: #212529; }
.overview-table .merged-cell { text-align: center; vertical-align: middle; font-weight: bold; background-color: #ffffff; color: #0d6efd; }
.overview-table .owner-team-cell { text-align: center; vertical-align: middle; background-color: #ffffff; }
.prog-wrapper { display: flex; align-items: center; width: 100%; }
.prog-container { background-color: #e9ecef; border-radius: 4px; flex-grow: 1; height: 16px; overflow: hidden; }
.prog-bar { background-color: #28a745; height: 100%; border-radius: 4px; transition: width 0.4s ease; }
.prog-text { margin-left: 10px; font-size: 13px; font-weight: 500; min-width: 35px; text-align: right; }
.status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
</style>
<table class="overview-table">
  <tr>
    <th>Shuttle Name</th>
    <th>Owner</th>
    <th>團隊 (or split test)</th>
    <th style="width: 90px; text-align: center;">已出貨片數</th>
    <th>ID (Wafer)</th>
    <th>Step</th>
    <th>Status</th>
    <th style="width: 200px;">目前龍頭Wafer進度條</th>
  </tr>"""
            
            df_route[shuttle_col] = df_route[shuttle_col].fillna("")
            df_route[team_col] = df_route[team_col].fillna("")
            
            # 建立有效晶圓資料庫 (排除 Bank 晶圓)
            valid_shuttles = {}

            for (shuttle, rep_team), s_group in df_route.groupby([shuttle_col, team_col], sort=False):
                if str(shuttle).strip() == "": continue
                rep_owner = str(s_group.iloc[0].get(owner_col, ""))
                
                team_wafer_list = s_group[wafer_col].unique()
                team_valid_wafers = []
                
                for wid in team_wafer_list:
                    w_group = s_group[s_group[wafer_col] == wid].reset_index(drop=True)
                    total_steps = len(w_group)
                    
                    has_scrap = False
                    is_banked = False
                    wip_idx = total_steps  
                    
                    raw_last_step = str(w_group.iloc[-1].get(step_col, "")).replace(".0", "").strip()
                    wip_step_no = str(total_steps) if raw_last_step in ["", "nan", "NaN", "None"] else raw_last_step
                    status_html = '<span class="status-dot" style="background-color: #0d6efd;"></span> Shipped (已出貨)'
                    
                    for idx, row in w_group.iterrows():
                        fco = str(row.get(fco_col, "")).strip().upper()
                        if fco == "SCRP":
                            has_scrap = True
                            wip_idx = idx
                            raw_step = str(row.get(step_col, "")).replace(".0", "").strip()
                            wip_step_no = str(idx + 1) if raw_step in ["", "nan", "NaN", "None"] else raw_step
                            status_html = f'<span class="status-dot" style="background-color: #dc3545;"></span> SCRAPPED: {row.get(desc_col, "")}'
                            break
                            
                    if not has_scrap:
                        for idx, row in w_group.iterrows():
                            fco = str(row.get(fco_col, "")).strip().upper()
                            if fco in ["", "NAN", "INPR", "HOLD", "BANK"]:
                                wip_idx = idx
                                raw_step = str(row.get(step_col, "")).replace(".0", "").strip()
                                wip_step_no = str(idx + 1) if raw_step in ["", "nan", "NaN", "None"] else raw_step
                                if fco == "HOLD":
                                    status_html = f'<span class="status-dot" style="background-color: #ffc107;"></span> HOLD: {row.get(desc_col, "")}'
                                elif fco == "BANK":
                                    is_banked = True # 🎯 偵測到 Bank 狀態
                                else:
                                    status_html = f'<span class="status-dot" style="background-color: #198754;"></span> INPR: {row.get(desc_col, "")}'
                                break
                    
                    if is_banked:
                        continue # 🎯 如果是 Bank，直接跳過不加入渲染清單
                        
                    is_shipped = False
                    if wip_idx == total_steps and not has_scrap:
                        is_shipped = True
                        
                    import re
                    nums = re.findall(r'\d+', str(wip_step_no))
                    step_num = int(nums[0]) if nums else 0
                    progress_pct = int((step_num / 92) * 100)
                    if progress_pct > 100: progress_pct = 100  
                    
                    team_valid_wafers.append({
                        "id": wid,
                        "step": f"{wip_step_no}/92",
                        "status": status_html,
                        "is_shipped": is_shipped,
                        "progress_pct": progress_pct
                    })
                
                # 將未被隱藏的有效資料加入字典，以利計算雙層合併列數
                if team_valid_wafers:
                    if shuttle not in valid_shuttles:
                        valid_shuttles[shuttle] = {"owner": rep_owner, "teams": []}
                    valid_shuttles[shuttle]["teams"].append({
                        "team_name": rep_team,
                        "wafers": team_valid_wafers
                    })
            
            # 開始將結構化資料組合為 HTML
            for shuttle, s_data in valid_shuttles.items():
                shuttle_rowspan = sum(len(t["wafers"]) for t in s_data["teams"])
                is_first_in_shuttle = True
                
                for t_data in s_data["teams"]:
                    team_rowspan = len(t_data["wafers"])
                    is_first_in_team = True
                    
                    shipped_count = sum(1 for w in t_data["wafers"] if w["is_shipped"])
                    max_progress_pct = max([w["progress_pct"] for w in t_data["wafers"] if not w["is_shipped"]] + [0])
                    if shipped_count > 0 and shipped_count == team_rowspan:
                        max_progress_pct = 100

                    for w_data in t_data["wafers"]:
                        html_table += "<tr>"
                        
                        if is_first_in_shuttle:
                            html_table += f'<td class="merged-cell" rowspan="{shuttle_rowspan}">{shuttle}</td>'
                            html_table += f'<td class="owner-team-cell" rowspan="{shuttle_rowspan}">{s_data["owner"]}</td>'
                            is_first_in_shuttle = False
                            
                        if is_first_in_team:
                            html_table += f'<td class="owner-team-cell" rowspan="{team_rowspan}">{t_data["team_name"]}</td>'
                            html_table += f'<td class="merged-cell" rowspan="{team_rowspan}">{shipped_count}</td>'
                            
                        html_table += f"<td>{w_data['id']}</td>"
                        html_table += f"<td>{w_data['step']}</td>"
                        html_table += f"<td>{w_data['status']}</td>"
                        
                        if is_first_in_team:
                            html_table += f"""
                            <td rowspan="{team_rowspan}">
                              <div class="prog-wrapper">
                                <div class="prog-container">
                                  <div class="prog-bar" style="width: {max_progress_pct}%;"></div>
                                </div>
                                <div class="prog-text">{max_progress_pct}%</div>
                              </div>
                            </td>
                            """
                            is_first_in_team = False
                            
                        html_table += "</tr>"
            
            html_table += "</table>"
            st.markdown(html_table, unsafe_allow_html=True)
            
        else:
            st.warning("⚠️ 母表中找不到 Wafer ID 欄位，無法計算總表。")
    else:
        st.info("💡 目前雲端母表尚無資料可供計算。")
# =========================================================================
# 📦 頁籤 5: Bank Wafers (入庫晶圓清單 & 批次 Kick off)
# =========================================================================
with all_tabs[4]:
    st.subheader("📦 入庫晶圓清單 (Banked Wafers)")
    st.markdown("集中顯示目前被標記為 Bank (暫停執行/未下線) 的所有晶圓。**勾選左側框框並點擊下方按鈕，即可批次 Kick off (下貨出庫)**。")

    df_route_bank, conn_status_bank = fetch_route_data_via_csv("route_template")
    
    if not df_route_bank.empty:
        wafer_col = next((c for c in df_route_bank.columns if str(c).strip().lower() in ["wafer id", "id", "wafer"]), "Wafer ID")
        step_col = next((c for c in df_route_bank.columns if str(c).strip().lower() in ["step", "step no.", "step no"]), "Step")
        shuttle_col = next((c for c in df_route_bank.columns if "shuttle" in str(c).lower()), "Shuttle Name")
        owner_col = next((c for c in df_route_bank.columns if "owner" in str(c).lower()), "Stage Owner")
        team_col = next((c for c in df_route_bank.columns if "customer" in str(c).lower()), "Customer")
        fco_col = next((c for c in df_route_bank.columns if "check out" in str(c).lower()), "Check out Time")
        comment_col = next((c for c in df_route_bank.columns if str(c).strip().lower() in ["comments", "備註", "comment"]), "Comments")
        
        if wafer_col in df_route_bank.columns:
            banked_wafers = []
            
            for wid, w_group in df_route_bank.groupby(wafer_col, sort=False):
                w_group = w_group.reset_index(drop=True)
                has_scrap = False
                is_banked = False
                bank_step_no = ""
                bank_comment = ""
                
                for idx, row in w_group.iterrows():
                    fco = str(row.get(fco_col, "")).strip().upper()
                    if fco == "SCRP":
                        has_scrap = True
                        break
                        
                if not has_scrap:
                    for idx, row in w_group.iterrows():
                        fco = str(row.get(fco_col, "")).strip().upper()
                        if fco in ["", "NAN", "INPR", "HOLD", "BANK"]:
                            if fco == "BANK":
                                is_banked = True
                                bank_step_no = str(row.get(step_col, "")).replace(".0", "")
                                bank_comment = str(row.get(comment_col, ""))
                            break
                            
                if is_banked:
                    first_row = w_group.iloc[0]
                    banked_wafers.append({
                        "🚀 選取 (Kick off)": False,  # 🎯 新增布林值供使用者勾選
                        "Shuttle Name": str(first_row.get(shuttle_col, "")),
                        "Owner": str(first_row.get(owner_col, "")),
                        "團隊 (or split test)": str(first_row.get(team_col, "")),
                        "ID (Wafer)": str(wid),
                        "Bank 停留站點": f"第 {bank_step_no} 步",
                        "_Raw_Step": bank_step_no, # 隱藏欄位，傳 API 用
                        "備註 (Bank Note)": bank_comment
                    })
                    
            if banked_wafers:
                df_bank = pd.DataFrame(banked_wafers)
                
                # 🎯 使用 st.data_editor 讓使用者可以勾選
                edited_bank_df = st.data_editor(
                    df_bank.drop(columns=["_Raw_Step"]), # 畫面上隱藏原始 Step 數字
                    hide_index=True,
                    use_container_width=True,
                    disabled=["Shuttle Name", "Owner", "團隊 (or split test)", "ID (Wafer)", "Bank 停留站點", "備註 (Bank Note)"]
                )
                
                # 抓出被選取的 Wafer
                selected_flags = edited_bank_df["🚀 選取 (Kick off)"].tolist()
                selected_wids = [banked_wafers[i]["ID (Wafer)"] for i, flag in enumerate(selected_flags) if flag]
                selected_steps = [banked_wafers[i]["_Raw_Step"] for i, flag in enumerate(selected_flags) if flag]
                
                if selected_wids:
                    st.markdown("---")
                    if st.button(f"🚀 將選取的 {len(selected_wids)} 片晶圓執行 Kick off (下線出庫)", type="primary"):
                        urls_to_send = []
                        
                        # 🎯 強制指定為台灣時間 (UTC+8)
                        tw_tz = datetime.timezone(datetime.timedelta(hours=8))
                        now_str = datetime.datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
                        
                        enc_time = requests.utils.quote(now_str)
                        enc_comment = requests.utils.quote("[KICK OFF] 從 Bank Wafers 批次出庫下線")
                        
                        # 準備所有 API 網址
                        for w, s in zip(selected_wids, selected_steps):
                            url = f"{MY_ORGANIZATION_GAS_URL}?wafer_id={requests.utils.quote(str(w))}&step_no={requests.utils.quote(str(s))}&action=Kick%20off&comment={enc_comment}&time={enc_time}"
                            urls_to_send.append(url)
                            
                        # 執行批次發送
                        with st.spinner(f"⏳ 正在為 {len(selected_wids)} 片晶圓執行 Kick off，請稍候..."):
                            has_err = False
                            for url in urls_to_send:
                                try:
                                    res = requests.get(url, timeout=15)
                                    if "Error" in res.text:
                                        st.error(f"❌ 寫入失敗: {res.text}")
                                        has_err = True
                                except Exception as e:
                                    st.error(f"❌ 網路連線異常: {e}")
                                    has_err = True
                                    
                            if has_err:
                                time.sleep(3)
                            else:
                                st.success("✅ 批次 Kick off 成功！已重返產線。")
                                time.sleep(1.5)
                            st.cache_data.clear()
                            st.rerun()
            else:
                st.success("🎉 目前產線上沒有任何晶圓處於 Bank (入庫) 狀態。")
        else:
            st.warning("⚠️ 母表中找不到 Wafer ID 欄位。")
    else:
        st.info("💡 目前雲端母表尚無資料。")
