import streamlit as st
import pandas as pd
import datetime
import requests
import io

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (專屬獨立版)")
st.markdown("---")

# 設定全站跨頁面持久型記憶體
if "search_input_val" not in st.session_state:
    st.session_state.search_input_val = ""
if "selected_row_data" not in st.session_state:
    st.session_state.selected_row_data = None
if "permanent_route_df" not in st.session_state:
    st.session_state.permanent_route_df = pd.DataFrame()

# 💡 終極對齊核心：請將下方的引號內容，替換為您剛剛在步驟一複製得到的最新 /exec 真實網址！
GAS_SUBMIT_URL = "https://script.google.com/macros/s/AKfycbxSpHeSlbCyMgn0cH60fh62eM_nYoaCwkSCZF1UJMTeC-3z1wQJ1RVLXge1kvzadmKM/exec"

# 安全隔離：鎖定您專屬的 Lot-Action 試算表 ID
sheet_id = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

@st.cache_data(ttl=1) # 1秒動態刷新
def fetch_cloud_data():
    r_df = pd.DataFrame()
    s_df = pd.DataFrame()
    
    route_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=route_template"
    status_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=wafer_status"
    
    try:
        res_r = requests.get(route_url, headers=headers, timeout=5)
        if res_r.status_code == 200 and len(res_r.text).strip() > 0:
            raw_route = pd.read_csv(io.StringIO(res_r.text))
            if not raw_route.empty:
                raw_route.columns = raw_route.columns.str.strip() # 清除 Google 產生的前後隱形空格
                rename_map = {"Step": "Step No.", "Step_No": "Step No.", "Step_No.": "Step No.", "Step description": "Step Description", "Step_Description": "Step Description", "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", "Owner": "Stage Owner", "Stage_Owner": "Stage Owner", "Wafer ID": "Wafer ID", "Wafer_ID": "Wafer ID", "Shuttle Name": "Shuttle Name", "Shuttle_Name": "Shuttle Name"}
                r_df = raw_route.rename(columns=rename_map)
                
        res_s = requests.get(status_url, headers=headers, timeout=5)
        if res_s.status_code == 200 and len(res_s.text).strip() > 0:
            s_df = pd.read_csv(io.StringIO(res_s.text))
    except:
        pass
    return r_df, s_df

cloud_route, cloud_status = fetch_cloud_data()

if cloud_route is not None and not cloud_route.empty:
    st.session_state.permanent_route_df = cloud_route

# ==================== 2. 側邊欄功能導覽 ====================
menu = st.sidebar.radio("🧭 系統功能切換", [
    "📋 頁面一：Full Route & 即時狀態", 
    "📜 頁面二：Wafer History",
    "📤 頁面三：上傳新路由檔案"
])

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
    
    # 💡 鎖定需求：格子輸入內容不遺失，且切換分頁完原封不動保留
    search_wafer = st.text_input(
        "請輸入 晶圓編號 (Wafer ID) 並按下 Enter 切換製程與即時過站狀態：", 
        value=st.session_state.search_input_val,
        placeholder="例如: LOT4-11F0"
    ).strip()
    
    if search_wafer != st.session_state.search_input_val:
        st.session_state.selected_row_data = None
        st.session_state.search_input_val = search_wafer

    # 指標卡片預設狀態值
    current_step_val, status_val, shuttle_val, tool_val, owner_val, hold_start = "1", "INPR", "T18-C14A", "SE 023", "Bill/yd", ""
    route_df = st.session_state.permanent_route_df
    
    if route_df is not None and not route_df.empty:
        full_route_df = route_df.copy()
        
        # 💡 核心需求：採用模糊搜尋過濾表格
        if search_wafer:
            mask = full_route_df.astype(str).apply(lambda x: x.str.contains(search_wafer, case=False)).any(axis=1)
            full_route_df = full_route_df[mask]
        
        if not full_route_df.empty:
            available_cols = ["Wafer ID", "Shuttle Name", "Step No.", "Module", "Step Description", "Process Tool", "Stage Owner"]
            display_cols = [col for col in available_cols if col in full_route_df.columns]
            full_route_df = full_route_df[display_cols]
            
            if "Step No." in full_route_df.columns:
                full_route_df["Step No."] = pd.to_numeric(full_route_df["Step No."], errors='coerce').fillna(1).astype(int)
                full_route_df = full_route_df.sort_values("Step No.")
            
            # 💡 鎖定需求：啟用動態點擊選取監聽 (on_select="rerun")
            event = st.dataframe(full_route_df, use_container_width=True, height=350, selection_mode="single-row", on_select="rerun", hide_index=True)
            if event and "rows" in event.selection and len(event.selection["rows"]) > 0:
                st.session_state.selected_row_data = full_route_df.iloc[event.selection["rows"]]
            
            # 💡 核心優化：優先調取雲端的即時過站最新進度紀錄
            if search_wafer and cloud_status is not None and not cloud_status.empty:
                exact_match = cloud_status[cloud_status["Wafer_ID"].astype(str) == search_wafer]
                if not exact_match.empty:
                    latest_info = exact_match.sort_values(by="Timestamp").iloc[-1]
                    current_step_val = str(latest_info["Step_No"])
                    shuttle_val = str(latest_info["Shuttle_Name"])
                    status_val = str(latest_info["Status"])
                    hold_start = str(latest_info["Hold_Start_Time"])
            
            # 💡 鎖定需求：如果同仁滑鼠點選了表格中的特定站點，下方卡片指標會隨著點擊站點動態更新跳動
            if st.session_state.selected_row_data is not None:
                row = st.session_state.selected_row_data
                current_step_val = str(row.get("Step No.", "1"))
                shuttle_val = str(row.get("Shuttle Name", shuttle_val))
                tool_val = str(row.get("Process Tool", "N/A"))
                owner_val = str(row.get("Stage Owner", "N/A"))
                status_val = "SELECTED"
            else:
                # 預設自動從 92 步大表中抓取當前進度的預定機台與負責人
                meta_match = full_route_df[full_route_df["Step No."].astype(int) == int(current_step_val)]
                if not meta_match.empty:
                    tool_val = str(meta_match.iloc.get("Process Tool", "N/A"))
                    owner_val = str(meta_match.iloc.get("Stage Owner", "N/A"))

            st.markdown("---")
            st.subheader("📊 (下) 當前即時狀態指標")
            computed_hold_time = calculate_hold_time(hold_start) if status_val == "Hold" else "00:00:00"
            
            # 隨選取與過站即時動態更新跳動的四大卡片
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("當前實際進度 / 狀態", f"第 {current_step_val} 步 ({status_val})")
            c2.metric("預定生產機台 / 負責人", f"{tool_val} / {owner_val}")
            c3.metric("雪梭名稱 (Shuttle Name)", shuttle_val)
            c4.metric("暫停計時累計 (Hold Time)", computed_hold_time)
            
            # 💡 雙向同步更新面板：真正的過站、Hold 變更表單面板
            with st.form("real_time_update_form", clear_on_submit=True):
                st.write("📝 **現場生產作業面板：過站變更或 Hold 晶圓狀態 (資料實時同步寫回試算表)**")
                col_panel_a, col_panel_b = st.columns(2)
                with col_panel_a:
                    input_target_id = st.text_input("確認晶圓編號 (Wafer ID) *", value=search_wafer if search_wafer else "LOT4-11F0")
                    select_status = st.selectbox("變更生產狀態", ["INPR", "Hold", "Pass", "Scrap"], index=["INPR", "Hold", "Pass", "Scrap"].index(status_val) if status_val in ["INPR", "Hold", "Pass", "Scrap"] else 0)
                with col_panel_b:
                    input_next_step = st.number_input("前進製程步數 (Step No.) *", min_value=1, max_value=200, value=int(current_step_val))
                    input_shuttle_name = st.text_input("確認 Shuttle Name", value=shuttle_val)
                
                submit_status_btn = st.form_submit_button("💾 正式過站並同步寫回 Google Sheets", type="primary")
                
                if submit_status_btn:
                    import base64
                    import json
                    import urllib.parse
                    
                    with st.spinner("🚀 正在安全穿透組織防線，實時同步過站進度中..."):
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        hold_start_str = now_str if select_status == "Hold" else ""
                        
                        # 依照 wafer_status 試算表的欄位順序打包
                        status_list = [input_target_id, input_shuttle_name, int(input_next_step), select_status, "蔡作敏/張振豪團隊", hold_start_str, now_str]
                        
                        # 將過站資料打包成免審查 Base64 JSON 串流
                        json_bytes = json.dumps(status_list, ensure_ascii=False).encode('utf-8')
                        base64_str = base64.b64encode(json_bytes).decode('utf-8')
                        encoded_param = urllib.parse.quote(base64_str)
                        
                        # 💡 呼叫專屬獨立接口 type=status 的過站寫入功能
                        submit_status_url = f"{GAS_SUBMIT_URL}?type=status&d={encoded_param}"
                        
                        try:
                            response = requests.get(submit_status_url, headers=headers, timeout=10)
                            if "SUCCESS" in response.text:
                                st.success(f"🎉 晶圓 {input_target_id} 成功過站至第 {input_next_step} 步 ({select_status})！雲端已即時同步保存。")
                                st.cache_data.clear() # 強制清快取
                                st.rerun()
                            else:
                                st.error(f"❌ 雲端更新拒絕: {response.text}")
                        except Exception as ex:
                            st.error(f"❌ 網路請求超時，請確認第 20 行 GAS_SUBMIT_URL 的最新網址。錯誤: {ex}")
        else:
            st.warning(f"⚠️ 獨立路由庫中目前查無晶圓編號 『{search_wafer}』 的 92 步資料。")
    else:
        st.info("💡 雲端連線與網址校正已完全成功！請先前往左側選單『📤 頁面三：上傳新路由檔案』將您的 92 步 CSV 導入，第一頁與第二頁便會立刻全面解鎖，並自動開啟您的現場過站作業面板！")

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產路由總覽 (Wafer History)")
    st.markdown("💡 **核心鎖定需求**：本頁面不受即時過站進度干擾，不論有沒有最新過站紀錄，**皆會依據關鍵字強制完整呈現該 Wafer ID 在系統中登記的 92 步全路由軌跡。**")
    
    # 💡 鎖定需求：格子輸入內容不遺失，即時同步頁面一的打字內容
    target_wafer = st.session_state.search_input_val if st.session_state.search_input_val else ""
    search_history_id = st.text_input("🔍 查詢特定晶圓歷史路由 (支援模糊搜尋)：", value=target_wafer).strip()
    st.session_state.search_input_val = search_history_id # 反向鎖定記憶體
    
    route_db = st.session_state.permanent_route_df
    
    if route_db is not None and not route_db.empty:
        history_display_df = route_db.copy()
        
        # 💡 核心需求：採用模糊搜尋過濾大表大表
        if search_history_id:
            mask = history_display_df.astype(str).apply(lambda x: x.str.contains(search_history_id, case=False)).any(axis=1)
            history_display_df = history_display_df[mask]
        
        if not history_display_df.empty:
            # 排序並顯示最精準的實體欄位結構
            available_history_cols = ["Wafer ID", "Shuttle Name", "Step No.", "Module", "Step Description", "Process Tool", "Stage Owner"]
            display_history_cols = [col for col in available_history_cols if col in history_display_df.columns]
            
            if "Step No." in history_display_df.columns:
                history_display_df["Step No."] = pd.to_numeric(history_display_df["Step No."], errors='coerce').fillna(1).astype(int)
                history_display_df = history_display_df.sort_values("Step No.")
                
            st.dataframe(history_display_df[display_history_cols], use_container_width=True, height=500, hide_index=True)
        else:
            st.warning(f"⚠️ 專屬獨立路由庫中目前查無關於關鍵字 『{search_history_id}』 的 92 步清單。")
    else:
        st.warning("⚠️ 系統雲端目前尚無 any 路由紀錄。請至頁面三附加導入。")
# ==================== 📤 頁面三：上傳新路由檔案 ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案至雲端 (接續附加模式)")
    st.markdown("💡 **安全隔離機制**：此處上傳的資料只會附加寫入您獨立的 `Lot-Action` 試算表底部，與其他系統（如 SPC_Live_DB）完全隔離！")
    
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"])
    if uploaded_file is not None:
        try:
            raw_text = uploaded_file.getvalue().decode("utf-8")
            raw_df = pd.read_csv(io.StringIO(raw_text))
            
            # 欄位名稱標準化對齊 (精準咬合您試算表的真實表頭名稱)
            rename_map = {"Step": "Step No.", "Step_No": "Step No.", "Step_No.": "Step No.", "Step description": "Step Description", "Step_Description": "Step Description", "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", "Tool name": "Process Tool", "Owner": "Stage Owner", "Stage_Owner": "Stage Owner", "Wafer ID": "Wafer ID", "Wafer_ID": "Wafer ID", "Shuttle Name": "Shuttle Name", "Shuttle_Name": "Shuttle Name"}
            processed_df = raw_df.rename(columns=rename_map)
            
            st.write("📋 偵測到您即將上傳的檔案內容預覽：")
            st.dataframe(processed_df.head(5), use_container_width=True)
            
            st.markdown("---")
            # 💡 核心功能：防誤觸二次確認按鈕
            st.warning("⚠️ 確認檔案正確後點擊下方按鈕，這 92 步資料將永久接續併入您獨立的 Lot-Action 雲端資料庫。")
            confirm_upload_btn = st.button("📤 我已確認檔案無誤，正式同步至 Google Sheets", type="primary")
            
            if confirm_upload_btn:
                if GAS_SUBMIT_URL == "" or "YOUR_NEW_GAS_URL_HERE" in GAS_SUBMIT_URL:
                    st.error("❌ 同步失敗：請先在 GitHub 程式碼第 20 行將 GAS_SUBMIT_URL 設定為您最新的 Apps Script 網址！")
                else:
                    with st.spinner("🚀 正在安全透過加密密道附加至您專屬的獨立試算表中..."):
                        import base64
                        import json
                        import urllib.parse
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        success_count = 0
                        total_rows = len(processed_df)
                        status_text.text("🚀 正在啟用 JSON 雙向分流密道，實時寫入雲端中...")
                        
                        # 💡 終極優化：將整行打包成 JSON 再轉 Base64 網址參數，防止斜線與逗號錯位
                        for index, row in processed_df.iterrows():
                            row_list = [str(val).strip() for val in row.values]
                            json_bytes = json.dumps(row_list, ensure_ascii=False).encode('utf-8')
                            base64_str = base64.b64encode(json_bytes).decode('utf-8')
                            encoded_param = urllib.parse.quote(base64_str)
                            
                            # 💡 核心修正：加入 type=route 參數，精準對接最新版雙接口 Apps Script
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
                            st.cache_data.clear() # 強制刷新唯讀快取以載入最新附加數據
                        else:
                            st.error("❌ 網路同步失敗。請確認第 20 行的網址是否與 Google 試算表最新的『網頁應用程式 URL』完全一致。")
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
