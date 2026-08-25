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

# 💡 串聯核心：已直接填入與您最新 JSON 密道後台對齊的 GET 網址
GAS_SUBMIT_URL = "https://google.com"

# 💡 安全隔離：精準鎖定您專屬的 Lot-Action 試算表 ID
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
                raw_route.columns = raw_route.columns.str.strip() # 清除 Google 產生的前後空格
                rename_map = {"Step": "Step No.", "Step_No": "Step No.", "Step_No.": "Step No.", "Step description": "Step Description", "Step_Description": "Step Description", "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", "Owner": "Stage Owner", "Stage_Owner": "Stage Owner", "Wafer ID": "Wafer ID", "Wafer_ID": "Wafer ID", "Shuttle Name": "Shuttle Name", "Shuttle_Name": "Shuttle Name"}
                r_df = raw_route.rename(columns=rename_map)
                
        res_s = requests.get(status_url, headers=headers, timeout=5)
        if res_s.status_code == 200 and len(res_s.text).strip() > 0:
            s_df = pd.read_csv(io.StringIO(res_s.text))
    except:
        pass
    return r_df, s_df

cloud_route, cloud_status = fetch_cloud_data()

# 只要雲端有成功下載到資料，一律無條件灌入記憶體，解鎖呈現
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
    search_wafer = st.text_input("請輸入 晶圓編號 (Wafer ID) 並按下 Enter 切換製程：", value=st.session_state.search_input_val).strip()
    
    if search_wafer != st.session_state.search_input_val:
        st.session_state.selected_row_data = None
        st.session_state.search_input_val = search_wafer

    current_step_val, status_val, shuttle_val, tool_val, owner_val, hold_start = "1", "INPR", "T18-C14A", "SE 023", "Bill/yd", ""
    route_df = st.session_state.permanent_route_df
    
    if route_df is not None and not route_df.empty:
        full_route_df = route_df.copy()
        
        # 進行模糊搜尋過濾
        if search_wafer:
            full_route_df = full_route_df[full_route_df.astype(str).apply(lambda x: x.str.contains(search_wafer, case=False)).any(axis=1)]
        
        if not full_route_df.empty:
            # 💡 核心優化 1：直接執行數值校正與排序，完全拔除原本 103 行導致當機的 # 號判斷
            if "Step No." in full_route_df.columns:
                full_route_df["Step No."] = pd.to_numeric(full_route_df["Step No."], errors='coerce').fillna(1).astype(int)
                full_route_df = full_route_df.sort_values("Step No.")
                
            # 🚀 重新喚醒中段 Full Route 表格呈現！
            event = st.dataframe(full_route_df, use_container_width=True, height=400, selection_mode="single-row", on_select="rerun", hide_index=True)
            if event and "rows" in event.selection and len(event.selection["rows"]) > 0:
                st.session_state.selected_row_data = full_route_df.iloc[event.selection["rows"]]
            
            # (下)方指標卡片隨著點擊動態同步跳動
            if st.session_state.selected_row_data is not None:
                row = st.session_state.selected_row_data
                current_step_val = str(row.get("Step No.", "1"))
                shuttle_val = str(row.get("Shuttle Name", "T18-C14A"))
                tool_val = str(row.get("Process Tool", "N/A"))
                owner_val = str(row.get("Stage Owner", "N/A"))
                status_val = "SELECTED"
            else:
                if search_wafer and not cloud_status.empty:
                    exact_match = cloud_status[cloud_status["Wafer_ID"].astype(str) == search_wafer]
                    if not exact_match.empty:
                        latest_info = exact_match.sort_values(by="Timestamp").iloc[-1]
                        current_step_val = str(latest_info["Step_No"])
                        shuttle_val = latest_info["Shuttle_Name"]
                        status_val = latest_info["Status"]
                        hold_start = latest_info["Hold_Start_Time"]
                        if "Step No." in full_route_df.columns:
                            meta_match = full_route_df[full_route_df["Step No."].astype(int) == int(current_step_val)]
                            if not meta_match.empty:
                                tool_val = str(meta_match.iloc.get("Process Tool", "N/A"))
                                owner_val = str(meta_match.iloc.get("Stage Owner", "N/A"))
        else:
            st.warning(f"⚠️ 專屬獨立路由庫中目前查無關鍵字 『{search_wafer}』 的 92 步資料。")
    else:
        st.info("💡 歡迎回到獨立隔離系統！請前往『📤 頁面三：上傳新路由檔案』引入新製程，數據將安全附加至您獨立的 Lot-Action 底部。")

    st.markdown("---")
    st.subheader("📊 (下) 當前即時狀態指標")
    computed_hold_time = calculate_hold_time(hold_start) if status_val == "Hold" else "00:00:00"
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("當前選定站點 (Step No.)", f"第 {current_step_val} 步 ({status_val})")
    c2.metric("製程機台 / 負責人", f"{tool_val} / {owner_val}")
    c3.metric("雪梭名稱 (Shuttle Name)", shuttle_val)
    c4.metric("暫停計時 (Hold Time)", computed_hold_time)

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產路由總覽 (Wafer History)")
    target_wafer = st.session_state.search_input_val if st.session_state.search_input_val else ""
    search_history_id = st.text_input("🔍 查詢特定晶圓歷史路由：", value=target_wafer).strip()
    st.session_state.search_input_val = search_history_id
    
    route_db = st.session_state.permanent_route_df
    if route_db is not None and not route_db.empty:
        history_display_df = route_db.copy()
        if search_history_id:
            history_display_df = history_display_df[history_display_df.astype(str).apply(lambda x: x.str.contains(search_history_id, case=False)).any(axis=1)]
        st.dataframe(history_display_df, use_container_width=True, height=500, hide_index=True)
    else:
        st.warning("⚠️ 系統雲端目前尚無 any 路由紀錄。")
# ==================== 📤 頁面三：上傳新路由檔案 ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案至雲端 (接續附加模式)")
    st.markdown("💡 **安全隔離機制**：此處上傳的資料只會附加寫入您獨立的 `Lot-Action` 試算表底部，與其他系統（如 SPC_Live_DB）完全隔離！")
    
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"])
    if uploaded_file is not None:
        try:
            raw_text = uploaded_file.getvalue().decode("utf-8")
            raw_df = pd.read_csv(io.StringIO(raw_text))
            
            # 欄位名稱標準化對齊
            rename_map = {"Step": "Step No.", "Step_No": "Step No.", "Step_No.": "Step No.", "Step description": "Step Description", "Step_Description": "Step Description", "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", "Tool name": "Process Tool", "Owner": "Stage Owner", "Stage_Owner": "Stage Owner", "Wafer ID": "Wafer ID", "Wafer_ID": "Wafer ID", "Shuttle Name": "Shuttle Name", "Shuttle_Name": "Shuttle Name"}
            processed_df = raw_df.rename(columns=rename_map)
            
            st.write("📋 偵測到您即將上傳的檔案內容預覽：")
            st.dataframe(processed_df.head(5), use_container_width=True)
            
            st.markdown("---")
            # 💡 核心功能：防誤觸二次確認按鈕
            st.warning("⚠️ 確認檔案正確後點擊下方按鈕，這 92 步資料將接續附加併入您獨立的 Lot-Action 雲端資料庫。")
            confirm_upload_btn = st.button("📤 我已確認檔案無誤，正式同步至 Google Sheets", type="primary")
            
            if confirm_upload_btn:
                if GAS_SUBMIT_URL == "":
                    st.error("❌ 同步失敗：請先在 GitHub 程式碼中確認 GAS_SUBMIT_URL 設定！")
                else:
                    import base64
                    import json
                    import urllib.parse
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    success_count = 0
                    total_rows = len(processed_df)
                    status_text.text("🚀 正在啟用 JSON 雙向密道，實時寫入雲端中...")
                    
                    # 💡 終極優化：將整行打包成 JSON 再轉 Base64 網址參數，防止斜線與逗號錯位
                    for index, row in processed_df.iterrows():
                        row_list = [str(val).strip() for val in row.values]
                        json_bytes = json.dumps(row_list, ensure_ascii=False).encode('utf-8')
                        base64_str = base64.b64encode(json_bytes).decode('utf-8')
                        encoded_param = urllib.parse.quote(base64_str)
                        
                        get_url = f"{GAS_SUBMIT_URL}?d={encoded_param}"
                        
                        try:
                            response = requests.get(get_url, headers=headers, timeout=10)
                            if "SUCCESS" in response.text:
                                success_count += 1
                        except:
                            pass
                        
                        progress_bar.progress((index + 1) / total_rows)
                    
                    status_text.empty()
                    if success_count > 0:
                        st.success(f"🎉 附加同步成功！共計 {success_count} 筆製程步驟已成功寫入 Google Sheets 底部！")
                        st.cache_data.clear() # 強制刷新唯讀快取以載入最新附加數據
                    else:
                        st.error("❌ 網路同步失敗。請再次確認 Google Sheet 的 Apps Script 是否有發布成『新版本』，且權限開啟為『任何人 (Anyone)』。")
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
