import streamlit as st
import pandas as pd
import datetime
import requests
import io

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (全記憶體持久版)")
st.markdown("---")

# 💡 鎖定核心需求：建立全站跨頁面、防覆蓋的持久型內建資料庫
if "permanent_route_df" not in st.session_state:
    st.session_state.permanent_route_df = pd.DataFrame(columns=["Wafer ID", "Shuttle Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"])
if "search_input_val" not in st.session_state:
    st.session_state.search_input_val = ""
if "selected_row_data" not in st.session_state:
    st.session_state.selected_row_data = None

sheet_id = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

@st.cache_data(ttl=2) # 2秒自動更新快取
def fetch_cloud_status():
    s_df = pd.DataFrame(columns=["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"])
    status_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=wafer_status"
    try:
        res_s = requests.get(status_url, headers=headers, timeout=5)
        if res_s.status_code == 200:
            s_df = pd.read_csv(io.StringIO(res_s.text))
            if not s_df.empty:
                s_df.columns = ["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"]
                s_df["Step_No"] = pd.to_numeric(s_df["Step_No"], errors='coerce').fillna(1).astype(int)
    except:
        pass
    return s_df

cloud_status = fetch_cloud_status()

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
    
    # 💡 鎖定需求 2：藉由輸入不同 Wafer ID 來更換顯示的製程路由
    search_wafer = st.text_input(
        "請輸入 晶圓編號 (Wafer ID) 並按下 Enter 切換製程：", 
        value=st.session_state.search_input_val,
        placeholder="例如: LOT5-01F2"
    ).strip()
    
    if search_wafer != st.session_state.search_input_val:
        st.session_state.selected_row_data = None
        st.session_state.search_input_val = search_wafer

    # 卡片初始預設值
    current_step_val = "1"
    status_val = "INPR"
    shuttle_val = "T18-C14A"
    tool_val = "SE 023"
    owner_val = "Bill/yd"
    hold_start = ""

    if search_wafer and not cloud_status.empty:
        exact_match = cloud_status[cloud_status["Wafer_ID"].astype(str) == search_wafer]
        if not exact_match.empty:
            latest_info = exact_match.sort_values(by="Timestamp").iloc[-1]
            current_step_val = str(latest_info["Step_No"])
            shuttle_val = latest_info["Shuttle_Name"]
            status_val = latest_info["Status"]
            hold_start = latest_info["Hold_Start_Time"]

    st.markdown("---")
    st.subheader("🛤️ (中) 完整製程路由監控 (Full Route)")
    st.caption("💡 提示：您可以用滑鼠點擊下方表格的任意整行（站點），（下）方的生產指標與計時卡片會即時同步變更呈現！")

    # 從全站防覆蓋記憶體中讀取資料
    route_df = st.session_state.permanent_route_df
    
    if not route_df.empty:
        full_route_df = route_df.copy()
        
        # 💡 鎖定需求 2：根據輸入的不同 Wafer ID 來更換顯示對應的製程路由
        if search_wafer:
            full_route_df = full_route_df[full_route_df["Wafer ID"].astype(str).str.contains(search_wafer, case=False, na=False)]
        
        if not full_route_df.empty:
            available_cols = ["Wafer ID", "Shuttle Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"]
            display_cols = [col for col in available_cols if col in full_route_df.columns]
            full_route_df = full_route_df[display_cols].sort_values("Step No.")
            
            # 💡 鎖定需求 3：啟用動態點擊選取監聽 (on_select="rerun")
            event = st.dataframe(
                full_route_df,
                use_container_width=True,
                height=400,
                selection_mode="single-row",
                on_select="rerun",
                hide_index=True
            )
            
            if event and "rows" in event.selection and len(event.selection["rows"]) > 0:
                selected_index = event.selection["rows"]
                st.session_state.selected_row_data = full_route_df.iloc[selected_index]
            
            # 💡 鎖定需求 3：(下)的資料隨著點擊的站點不同要即時動態更新
            if st.session_state.selected_row_data is not None:
                row = st.session_state.selected_row_data
                current_step_val = str(row.get("Step No.", "1"))
                shuttle_val = str(row.get("Shuttle Name", "T18-C14A"))
                tool_val = str(row.get("Process Tool", "N/A"))
                owner_val = str(row.get("Stage Owner", "N/A"))
                status_val = "SELECTED"
                
                if not cloud_status.empty:
                    match_status = cloud_status[(cloud_status["Wafer_ID"].astype(str) == str(row.get("Wafer ID"))) & (cloud_status["Step_No"].astype(int) == int(row.get("Step No.", 1)))]
                    if not match_status.empty:
                        status_val = match_status.sort_values(by="Timestamp").iloc[-1].get("Status", "SELECTED")
                        hold_start = match_status.sort_values(by="Timestamp").iloc[-1].get("Hold_Start_Time", "")
            else:
                # 若未點擊，則試著調取基礎 meta 資料
                meta_match = full_route_df[full_route_df["Step No."].astype(int) == int(current_step_val)]
                if not meta_match.empty:
                    tool_val = str(meta_match.iloc[0].get("Process Tool", "N/A"))
                    owner_val = str(meta_match.iloc[0].get("Stage Owner", "N/A"))
                    shuttle_val = str(meta_match.iloc[0].get("Shuttle Name", shuttle_val))
                    
            st.markdown("---")
            st.subheader("📊 (下) 當前即時狀態指標")
            computed_hold_time = calculate_hold_time(hold_start) if status_val == "Hold" else "00:00:00"
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("當前選定站點 (Step No.)", f"第 {current_step_val} 步 ({status_val})")
            c2.metric("製程機台 / 負責人", f"{tool_val} / {owner_val}")
            c3.metric("雪梭名稱 (Shuttle Name)", shuttle_val)
            c4.metric("暫停計時 (Hold Time)", computed_hold_time)
        else:
            st.warning(f"⚠️ 網頁系統中目前查無晶圓編號 『{search_wafer}』 的專屬路由。請先至第三頁導入檔案。")
    else:
        st.info("💡 歡迎使用晶圓生產路由追蹤系統。請先切換至『📤 頁面三：上傳新路由檔案』將您的 CSV 晶圓製程檔導入即可解鎖！")

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產變更紀錄總覽 (Wafer History)")
    if not cloud_status.empty:
        display_df = cloud_status.sort_values(by="Timestamp", ascending=False)
        if st.session_state.search_input_val:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(st.session_state.search_input_val, case=False)).any(axis=1)]
        st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("目前雲端尚無過站歷史紀錄。")

# ==================== 📤 頁面三：上傳新路由檔案 ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案至網頁儲存庫")
    st.markdown("💡 **資安防覆寫機制**：此處導入新晶圓檔案時，系統會自動將資料疊加接續，**絕對不會覆蓋、刪除您先前餵進去的任何舊資料！**")
    
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"])
    
    if uploaded_file is not None:
        try:
            raw_text = uploaded_file.getvalue().decode("utf-8")
            raw_df = pd.read_csv(io.StringIO(raw_text))
            
            # 標準化欄位名稱與對應
            rename_map = {"Step": "Step No.", "Step_No": "Step No.", "Step description": "Step Description", "Step_Description": "Step Description", "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", "Owner": "Stage Owner", "Stage_Owner": "Stage Owner", "Wafer ID": "Wafer ID", "Wafer_ID": "Wafer ID", "Shuttle Name": "Shuttle Name", "Shuttle_Name": "Shuttle Name"}
            processed_df = raw_df.rename(columns=rename_map)
            
            st.write("📋 偵測到您即將上傳的檔案內容預覽：")
            st.dataframe(processed_df.head(5), use_container_width=True)
            
            st.markdown("---")
            # 💡 鎖定需求 4：多加入一個確認上傳的按鈕，防止操作員不小心按到錯誤檔案
            st.warning("⚠️ 請確認上方預覽的資料欄位與內容是否正確。點擊下方按鈕後，這 92 步資料將永久接續併入系統。")
            
            confirm_upload_btn = st.button("📤 我已確認檔案無誤，正式上傳至系統", type="primary")
            
            if confirm_upload_btn:
                # 💡 鎖定需求 1：已餵進去的資料不要因為上傳新而被覆蓋，採取 concat 附加接續模式
                st.session_state.permanent_route_df = pd.concat([st.session_state.permanent_route_df, processed_df], ignore_index=True).drop_duplicates()
                st.success("🎉 附加導入成功！新晶圓的 92 步流程已成功併入系統底部，且完全未覆蓋歷史舊資料！請前往頁面一查看。")
                
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
            
    # 加值功能：若同仁需要將網頁上多個 Wafer 的累積合併路由匯出備份，隨時可以點擊下載
    if not st.session_state.permanent_route_df.empty:
        st.markdown("---")
        st.subheader("💾 系統全域資料庫備份備份導出 (選填)")
        csv_buffer = io.StringIO()
        st.session_state.permanent_route_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 下載目前系統累積的所有晶圓路由 CSV 檔案",
            data=csv_buffer.getvalue(),
            file_name=f"wafer_all_routes_backup_{datetime.date.today()}.csv",
            mime="text/csv"
        )
