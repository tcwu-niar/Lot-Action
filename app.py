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
    st.session_state.permanent_route_df = pd.DataFrame(columns=["Wafer ID", "Shuttle Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"])

# 💡 安全隔離：導回您專屬的 Lot-Action 專案 Apps Script 通道
GAS_SUBMIT_URL = "https://script.google.com/macros/s/AKfycbxSpHeSlbCyMgn0cH60fh62eM_nYoaCwkSCZF1UJMTeC-3z1wQJ1RVLXge1kvzadmKM/exec"

# 💡 安全隔離：導回您最初建立的專屬 Lot-Action 試算表 ID，絕對不改動到其他系統！
sheet_id = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

@st.cache_data(ttl=1) # 1秒動態刷新
def fetch_cloud_data():
    r_df = pd.DataFrame(columns=["Wafer ID", "Shuttle Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"])
    s_df = pd.DataFrame(columns=["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"])
    
    route_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=route_template"
    status_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=wafer_status"
    
    try:
        res_r = requests.get(route_url, headers=headers, timeout=5)
        if res_r.status_code == 200 and len(res_r.text).strip() > 0:
            raw_route = pd.read_csv(io.StringIO(res_r.text))
            if not raw_route.empty:
                # 💡 自動相容廠內各種 CSV 的欄位命名變形
                rename_map = {"Step": "Step No.", "Step_No": "Step No.", "Step_No.": "Step No.", "Step description": "Step Description", "Step_Description": "Step Description", "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", "Owner": "Stage Owner", "Stage_Owner": "Stage Owner", "Wafer ID": "Wafer ID", "Wafer_ID": "Wafer ID", "Shuttle Name": "Shuttle Name", "Shuttle_Name": "Shuttle Name"}
                r_df = raw_route.rename(columns=rename_map)
                if "Step No." in r_df.columns:
                    r_df["Step No."] = pd.to_numeric(r_df["Step No."], errors='coerce').fillna(1).astype(int)
                
        res_s = requests.get(status_url, headers=headers, timeout=5)
        if res_s.status_code == 200 and len(res_s.text).strip() > 0:
            raw_status = pd.read_csv(io.StringIO(res_s.text))
            if not raw_status.empty:
                s_df = raw_status
                s_df.columns = ["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"]
                s_df["Step_No"] = pd.to_numeric(s_df["Step_No"], errors='coerce').fillna(1).astype(int)
    except:
        pass
    return r_df, s_df

cloud_route, cloud_status = fetch_cloud_data()

# 確保基礎欄位結構在記憶體中永不丟失
if not cloud_route.empty:
    st.session_state.permanent_route_df = cloud_route
else:
    if st.session_state.permanent_route_df.empty:
        st.session_state.permanent_route_df = pd.DataFrame(columns=["Wafer ID", "Shuttle Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"])

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

    st.markdown("---")
    st.subheader("🛤️ (中) 完整製程路由監控 (Full Route)")

    route_df = st.session_state.permanent_route_df
    
    if not route_df.empty and len(route_df) > 0:
        full_route_df = route_df.copy()
        if search_wafer:
            full_route_df = full_route_df[full_route_df["Wafer ID"].astype(str).str.contains(search_wafer, case=False, na=False)]
        
        if not full_route_df.empty:
            available_cols = ["Wafer ID", "Shuttle Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"]
            display_cols = [col for col in available_cols if col in full_route_df.columns]
            full_route_df = full_route_df[display_cols]
            
            if "Step No." in full_route_df.columns:
                full_route_df = full_route_df.sort_values("Step No.")
            
            # 💡 滑鼠滑過單行點擊選取監聽
            event = st.dataframe(full_route_df, use_container_width=True, height=400, selection_mode="single-row", on_select="rerun", hide_index=True)
            
            if event and "rows" in event.selection and len(event.selection["rows"]) > 0:
                st.session_state.selected_row_data = full_route_df.iloc[event.selection["rows"]]
            
            # 💡 隨點擊行動態更新卡片
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
            st.warning(f"⚠️ 獨立路由庫中目前查無晶圓編號 『{search_wafer}』 的 92 步資料。")
    else:
        st.info("💡 歡迎回到獨立隔離系統！請前往『📤 頁面三：上傳新路由檔案』引入新製程，數據會安全寫入您專屬的 Lot-Action 底部。")

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
    if not route_db.empty and len(route_db) > 0:
        history_display_df = route_db.copy()
        if search_history_id:
            history_display_df = history_display_df[history_display_df["Wafer ID"].astype(str).str.contains(search_history_id, case=False, na=False)]
        if not history_display_df.empty:
            available_cols = ["Wafer ID", "Shuttle Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"]
            st.dataframe(history_display_df[available_cols], use_container_width=True, height=500, hide_index=True)
    else:
        st.warning("⚠️ 獨立系統雲端目前尚無任何路由紀錄。")
# ==================== 📤 頁面三：上傳新路由檔案 ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案至雲端 (接續附加模式)")
    st.markdown("💡 **安全隔離機制**：此處上傳的資料只會寫入您專屬的 `Lot-Action` 試算表，**絕對不會覆蓋或改動到其他系統的試算表（如 SPC_Live_DB）！**")
    
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"])
    
    if uploaded_file is not None:
        try:
            raw_text = uploaded_file.getvalue().decode("utf-8")
            raw_df = pd.read_csv(io.StringIO(raw_text))
            
            rename_map = {"Step": "Step No.", "Step_No": "Step No.", "Step description": "Step Description", "Step_Description": "Step Description", "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", "Owner": "Stage Owner", "Stage_Owner": "Stage Owner", "Wafer ID": "Wafer ID", "Wafer_ID": "Wafer ID", "Shuttle Name": "Shuttle Name", "Shuttle_Name": "Shuttle Name"}
            processed_df = raw_df.rename(columns=rename_map)
            
            st.write("📋 偵測到您即將上傳的檔案內容預覽：")
            st.dataframe(processed_df.head(5), use_container_width=True)
            
            st.markdown("---")
            st.warning("⚠️ 確認檔案正確後點擊下方按鈕，這 92 步資料將接續附加併入您獨立的 Lot-Action 雲端資料庫。")
            
            confirm_upload_btn = st.button("📤 我已確認檔案無誤，正式同步至 Google Sheets", type="primary")
            
            if confirm_upload_btn:
                with st.spinner("🚀 正在安全附加資料至專屬獨立試算表中..."):
                    # 💡 終極解鎖：利用 Text 純文字串流直接 POST 發送，完全穿透 Google 組織型重導向的 405 封鎖
                    response = requests.post(
                        GAS_SUBMIT_URL, 
                        data=raw_text.encode('utf-8'), 
                        headers={"Content-Type": "text/plain"},
                        timeout=15
                    )
                    
                    if "SUCCESS" in response.text:
                        st.success("🎉 附加同步成功！數據已安全併入專屬 Lot-Action 試算表底部，與其他系統完全隔離！")
                        st.cache_data.clear() # 強制清空網頁快取以載入雲端最新附加數據
                    else:
                        st.error(f"❌ 雲端拒絕更新。後台錯誤回報: {response.text}")
                        
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
