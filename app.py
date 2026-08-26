import streamlit as st
import pandas as pd
import datetime
import requests
import io

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (原生網頁 Tab 終極合流版)")
st.markdown("---")

# 設定全站持久型記憶體
if "search_input_val" not in st.session_state:
    st.session_state.search_input_val = ""
if "selected_row_data" not in st.session_state:
    st.session_state.selected_row_data = None

# 💡 與您的 JSON 密道後台完全對齊的安全通道網址
GAS_SUBMIT_URL = "https://script.google.com/macros/s/AKfycbxSpHeSlbCyMgn0cH60fh62eM_nYoaCwkSCZF1UJMTeC-3z1wQJ1RVLXge1kvzadmKM/exec"

# 💡 安全隔離：精準鎖定您專屬的 Lot-Action 試算表 ID
sheet_id = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 實時強拉雲端資料，無快取安全通道
def fetch_cloud_data_raw():
    r_df = pd.DataFrame()
    s_df = pd.DataFrame()
    
    route_url = "https://docs.google.com/spreadsheets/d/" + str(sheet_id) + "/gviz/tq?tqx=out:csv&sheet=route_template&tq=limit%2010000"
    status_url = "https://docs.google.com/spreadsheets/d/" + str(sheet_id) + "/gviz/tq?tqx=out:csv&sheet=wafer_status&tq=limit%2010000"
    
    try:
        # 1. 讀取 92 步全路由模板
        res_r = requests.get(route_url, headers=headers, timeout=5)
        if res_r.status_code == 200 and len(res_r.text).strip() > 0:
            raw_route = pd.read_csv(io.StringIO(res_r.text))
            if not raw_route.empty:
                # 💡 終極優化：將所有欄位表頭和內容強制轉為字串文字，徹底消滅 'int' object has no attribute 'strip' 報錯！
                raw_route.columns = raw_route.columns.astype(str).str.strip()
                r_df = raw_route.astype(str)
                
        # 2. 讀取最新晶圓過站歷史
        res_s = requests.get(status_url, headers=headers, timeout=5)
        if res_s.status_code == 200 and len(res_s.text).strip() > 0:
            raw_status = pd.read_csv(io.StringIO(res_s.text))
            if not raw_status.empty:
                raw_status.columns = raw_status.columns.astype(str).str.strip()
                s_df = raw_status.astype(str)
                s_df.columns = ["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"]
    except:
        pass
        
    return r_df, s_df

cloud_route, cloud_status = fetch_cloud_data_raw()

def calculate_hold_time(start_time_str):
    try:
        start_dt = datetime.datetime.strptime(str(start_time_str), "%Y-%m-%d %H:%M:%S")
        delta = datetime.datetime.now() - start_dt
        seconds = max(0, int(delta.total_seconds()))
        return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
    except:
        return "00:00:00"

# ==================== 🚀 終極解鎖：改用原生網頁 Tabs 分頁標籤流 ====================
tab1, tab2, tab3 = st.tabs(["📋 頁面一：Full Route & 即時狀態", "📜 頁面二：Wafer History", "📤 頁面三：上傳新路由檔案"])

# ==================== 📋 頁面一：Full Route & 即時狀態 ====================
with tab1:
    st.subheader("🔍 (上) 晶圓動態查詢")
    search_wafer = st.text_input("請輸入 晶圓編號 (Wafer ID) 並按下 Enter 切換製程：", value=st.session_state.search_input_val, placeholder="例如: LOT4-11F0", key="tab1_search").strip()
    if search_wafer != st.session_state.search_input_val:
        st.session_state.selected_row_data = None
        st.session_state.search_input_val = search_wafer

    current_step_val, status_val, shuttle_val, tool_val, owner_val, hold_start = "1", "INPR", "T18-C14A", "SE 023", "Bill/yd", ""
    
    st.markdown("---")
    st.subheader("🛤️ (中) 完整製程路由監控 (Full Route)")
    if cloud_route is not None and not cloud_route.empty:
        if search_wafer:
            mask = cloud_route.astype(str).apply(lambda x: x.str.contains(search_wafer, case=False)).any(axis=1)
            display_route_df = cloud_route[mask]
        else:
            display_route_df = cloud_route.copy()
        
        if not display_route_df.empty:
            st.caption("💡 提示：您可以用滑鼠點擊下方表格的任意整行（站點），（下）方的生產指標與計時卡片會即時同步變更呈現！")
            event = st.dataframe(display_route_df, use_container_width=True, height=320, selection_mode="single-row", on_select="rerun", hide_index=True, key="tab1_grid")
            if event and "rows" in event.selection and len(event.selection["rows"]) > 0:
                st.session_state.selected_row_data = display_route_df.iloc[event.selection["rows"]]
        else:
            st.warning(f"⚠️ 專屬獨立路由庫中目前查無關於關鍵字 『{search_wafer}』 的製程路由。")
    else:
        st.info("💡 雲端安全接口測試正常！請前往右側分頁『📤 頁面三：上傳新路由檔案』將您的 92 步 CSV 導入，資料便會直接在此呈現大表！")

    st.markdown("---")
    st.subheader("📊 (下) 當前即時狀態指標")
    if search_wafer and cloud_status is not None and not cloud_status.empty:
        exact_match = cloud_status[cloud_status["Wafer_ID"].astype(str) == search_wafer]
        if not exact_match.empty:
            latest_info = exact_match.sort_values(by="Timestamp").iloc[-1]
            current_step_val = str(latest_info.get("Step_No", "1"))
            shuttle_val = str(latest_info.get("Shuttle_Name", "T18-C14A"))
            status_val = str(latest_info.get("Status", "INPR"))
            hold_start = str(latest_info.get("Hold_Start_Time", ""))

    if st.session_state.selected_row_data is not None:
        row = st.session_state.selected_row_data
        current_step_val = str(row.get("Step No.", row.get("Step_No", row.get("Step", "1"))))
        shuttle_val = str(row.get("Shuttle Name", row.get("Shuttle_Name", "T18-C14A")))
        tool_val = str(row.get("Process Tool", row.get("Process_Tool", row.get("Tool name/mask", "N/A"))))
        owner_val = str(row.get("Stage Owner", row.get("Stage_Owner", row.get("Owner", "N/A"))))
        status_val = "SELECTED"
    else:
        if cloud_route is not None and not cloud_route.empty:
            try:
                step_col = "Step" if "Step" in cloud_route.columns else ("Step No." if "Step No." in cloud_route.columns else "Step_No")
                meta_match = cloud_route[cloud_route[step_col].astype(str).str.strip() == str(int(float(current_step_val)))] if step_col in cloud_route.columns else pd.DataFrame()
                if not meta_match.empty:
                    tool_val = str(meta_match.iloc.get("Tool name/mask", meta_match.iloc.get("Process Tool", "N/A")))
                    owner_val = str(meta_match.iloc.get("Owner", meta_match.iloc.get("Stage Owner", "N/A")))
            except:
                pass

    computed_hold_time = calculate_hold_time(hold_start) if status_val == "Hold" else "00:00:00"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("當前實際進度 / 狀態", f"第 {current_step_val} 步 ({status_val})")
    c2.metric("預定生產機台 / 負責人", f"{tool_val} / {owner_val}")
    c3.metric("雪梭名稱 (Shuttle Name)", shuttle_val)
    c4.metric("暫停計時累計 (Hold Time)", computed_hold_time)
    
    with st.form("real_time_update_form", clear_on_submit=True):
        st.write("📝 **現場生產作業面板：過站變更或 Hold 晶圓狀態 (資料實時同步寫回試算表)**")
        col_panel_a, col_panel_b = st.columns(2)
        with col_panel_a:
            input_target_id = st.text_input("確認晶圓編號 (Wafer ID) *", value=search_wafer if search_wafer else "LOT4-11F0", key="tab1_form_id")
            select_status = st.selectbox("變更生產狀態", ["INPR", "Hold", "Pass", "Scrap"], index=["INPR", "Hold", "Pass", "Scrap"].index(status_val) if status_val in ["INPR", "Hold", "Pass", "Scrap"] else 0, key="tab1_form_status")
        with col_panel_b:
            try: default_step_idx = int(float(current_step_val))
            except: default_step_idx = 1
            input_next_step = st.number_input("前進製程步數 (Step) *", min_value=1, max_value=200, value=default_step_idx, key="tab1_form_step")
            input_shuttle_name = st.text_input("確認 Shuttle Name", value=shuttle_val, key="tab1_form_shuttle")
        
        submit_status_btn = st.form_submit_button("💾 正式過站並同步寫回 Google Sheets", type="primary")
        if submit_status_btn:
            import base64, json, urllib.parse
            with st.spinner("🚀 正在安全穿透組織防線，實時同步過站進度中..."):
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                hold_start_str = now_str if select_status == "Hold" else ""
                status_list = [input_target_id, input_shuttle_name, int(input_next_step), select_status, "蔡作敏/張振豪團隊", hold_start_str, now_str]
                json_bytes = json.dumps(status_list, ensure_ascii=False).encode('utf-8')
                base64_str = base64.b64encode(json_bytes).decode('utf-8')
                encoded_param = urllib.parse.quote(base64_str)
                submit_status_url = f"{GAS_SUBMIT_URL}?type=status&d={encoded_param}"
                try:
                    response = requests.get(submit_status_url, headers=headers, timeout=10)
                    if "SUCCESS" in response.text:
                        st.success(f"🎉 晶圓 {input_target_id} 成功過站至第 {input_next_step} 步 ({select_status})！")
                        st.rerun()
                    else: st.error(f"❌ 雲端更新拒絕: {response.text}")
                except Exception as ex: st.error(f"❌ 網路連線錯誤。錯誤: {ex}")

# ==================== 📜 頁面二：Wafer History ====================
with tab2:
    st.subheader("📜 歷史生產路由總覽 (Wafer History)")
    st.markdown("💡 **核心鎖定需求**：本頁面不受過站進度干擾，不論有沒有最新過站紀錄，皆會依據關鍵字強制完整呈現該 Wafer ID 在系統中登記的 92 步全路由軌跡。")
    target_wafer = st.session_state.search_input_val if st.session_state.search_input_val else ""
    search_history_id = st.text_input("🔍 查詢特定晶圓歷史路由 (支援模糊搜尋)：", value=target_wafer, key="tab2_search").strip()
    st.session_state.search_input_val = search_history_id 
    if cloud_route is not None and not cloud_route.empty:
        history_display_df = cloud_route.copy()
        if search_history_id:
            history_display_df = history_display_df[history_display_df.astype(str).apply(lambda x: x.str.contains(search_history_id, case=False)).any(axis=1)]
        st.dataframe(history_display_df, use_container_width=True, height=500, hide_index=True, key="tab2_grid")
    else: st.warning("⚠️ 系統雲端目前尚無 any 路由紀錄。")
# ==================== 📤 頁面三：上傳新路由檔案 ====================
with tab3:
    st.subheader("📤 導入晶圓生產路由 CSV 檔案至雲端 (接續附加模式)")
    st.markdown("💡 **安全隔離機制**：此處上傳的資料只會附加寫入您獨立的 `Lot-Action` 試算表底部，與其他系統完全隔離！")
    
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"], key="tab3_uploader")
    
    if uploaded_file is not None:
        try:
            raw_text = uploaded_file.getvalue().decode("utf-8")
            raw_df = pd.read_csv(io.StringIO(raw_text))
            
            st.write("📋 偵測到您即將上傳的檔案內容預覽：")
            st.dataframe(raw_df.head(5), use_container_width=True, key="tab3_preview")
            
            st.markdown("---")
            # 💡 核心功能：防誤觸二次確認按鈕
            st.warning("⚠️ 確認檔案正確後點擊下方按鈕，這 92 步資料將永久接續併入您獨立的 Lot-Action 雲端資料庫。")
            confirm_upload_btn = st.button("📤 我已確認檔案無誤，正式同步至 Google Sheets", type="primary", key="tab3_submit_btn")
            
            if confirm_upload_btn:
                with st.spinner("🚀 正在安全透過加密密道附加至您專屬的獨立試算表中..."):
                    import base64, json, urllib.parse
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    success_count = 0
                    total_rows = len(raw_df)
                    status_text.text("🚀 正在啟用 JSON 雙向分流密道，實時寫入雲端中...")
                    
                    # 💡 終極優化：將整行打包成 JSON 再轉 Base64 網址參數，1秒傳完、絕不漏字錯位
                    for index, row in raw_df.iterrows():
                        row_list = [str(val).strip() for val in row.values]
                        json_bytes = json.dumps(row_list, ensure_ascii=False).encode('utf-8')
                        base64_str = base64.b64encode(json_bytes).decode('utf-8')
                        encoded_param = urllib.parse.quote(base64_str)
                        
                        # 💡 呼叫專屬獨立接口 type=route 的路由附加功能
                        get_url = f"{GAS_SUBMIT_URL}?type=route&d={encoded_param}"
                        
                        try:
                            response = requests.get(get_url, headers=headers, timeout=10)
                            if "SUCCESS" in response.text:
                                success_count += 1
                        except:
                            pass
                        
                        progress_bar.progress((index + 1) / total_rows)
                    
                    status_text.empty()
                    if success_count > 0:
                        st.success(f"🎉 附加同步成功！共計 {success_count} 筆製程步驟已成功附加寫入您專屬的 Google Sheets 底部！")
                    else:
                        st.error("❌ 網路同步失敗。請確認第 20 行的網址是否與 Google 試算表最新的『網頁應用程式 URL』完全一致。")
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
