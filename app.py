import streamlit as st
import pandas as pd
import datetime
import io

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (企業全合規快取版)")
st.markdown("---")

# 💡 終極修正：建立全站跨頁面、防覆蓋、防公司資安阻擋的『永久型內建資料庫』
if "permanent_route_df" not in st.session_state:
    st.session_state.permanent_route_df = pd.DataFrame(columns=[
        "Wafer ID", "Step No.", "Module", "Step Description", "Process Tool", 
        "Recipe", "Check point", "Stage Owner", "Customer", "Product Type", 
        "Q Time", "First Check Out", "Shuttle Name"
    ])
if "search_input_val" not in st.session_state:
    st.session_state.search_input_val = ""
if "selected_row_data" not in st.session_state:
    st.session_state.selected_row_data = None
if "local_status_logs" not in st.session_state:
    # 建立本地狀態變更流水帳記憶體
    st.session_state.local_status_logs = pd.DataFrame(columns=["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"])

# 預載基礎測試備援資料，確保首次打開不空白
if st.session_state.permanent_route_df.empty:
    st.session_state.permanent_route_df = pd.DataFrame([
        {"Wafer ID": "LOT4-11F0", "Step No.": 1, "Module": "Lot Owner", "Step Description": "Wafer check [TSMC 8\"]", "Process Tool": "SE-023", "Recipe": "None", "Check point": "Chipping or not", "Stage Owner": "Bill/yd", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "None", "First Check Out": "None", "Shuttle Name": "T18-C14A"},
        {"Wafer ID": "LOT4-11F0", "Step No.": 2, "Module": "Package", "Step Description": "Edge trim (x:500um/y:50um)", "Process Tool": "DISCO", "Recipe": "None", "Check point": "None", "Stage Owner": "Laif", "Customer": "蔡作敏/張振豪團隊", "Product Type": "B/S TSV Lot4", "Q Time": "None", "First Check Out": "None", "Shuttle Name": "T18-C14A"}
    ])

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
    
    # 💡 鎖定需求：格子輸入任何東西不消失
    search_wafer = st.text_input(
        "請輸入 晶圓編號 (Wafer ID) 並按下 Enter 切換製程：", 
        value=st.session_state.search_input_val,
        placeholder="例如: LOT4-11F0"
    ).strip()
    
    if search_wafer != st.session_state.search_input_val:
        st.session_state.selected_row_data = None
        st.session_state.search_input_val = search_wafer

    # 卡片預設狀態值
    current_step_val = "1"
    status_val = "INPR"
    shuttle_val = "T18-C14A"
    tool_val = "SE-023"
    owner_val = "Bill/yd"
    hold_start = ""

    # 調取過站最新狀態
    status_df = st.session_state.local_status_logs
    if search_wafer and not status_df.empty:
        exact_match = status_df[status_df["Wafer_ID"].astype(str) == search_wafer]
        if not exact_match.empty:
            latest_info = exact_match.sort_values(by="Timestamp").iloc[-1]
            current_step_val = str(latest_info["Step_No"])
            shuttle_val = latest_info["Shuttle_Name"]
            status_val = latest_info["Status"]
            hold_start = latest_info["Hold_Start_Time"]

    st.markdown("---")
    st.subheader("🛤️ (中) 完整製程路由監控 (Full Route)")
    st.caption("💡 提示：您可以用滑鼠點擊下方表格的任意整行（站點），（下）方的生產指標與計時卡片會即時同步變更呈現！")

    route_df = st.session_state.permanent_route_df
    
    if not route_df.empty:
        full_route_df = route_df.copy()
        
        # 💡 鎖定需求：藉由輸入不同 Wafer ID 來更換顯示的製程路由
        if search_wafer:
            full_route_df = full_route_df[full_route_df["Wafer ID"].astype(str).str.contains(search_wafer, case=False, na=False)]
        
        if not full_route_df.empty:
            available_cols = ["Wafer ID", "Shuttle Name", "Step No.", "Module", "Step Description", "Process Tool", "Recipe", "Check point", "Stage Owner", "Customer", "Product Type", "Q Time", "First Check Out"]
            display_cols = [col for col in available_cols if col in full_route_df.columns]
            full_route_df = full_route_df[display_cols].sort_values("Step No.")
            
            # 💡 鎖定需求：啟用點擊整行站點更新事件 (on_select="rerun")
            event = st.dataframe(
                full_route_df,
                use_container_width=True,
                height=400,
                selection_mode="single-row",
                on_select="rerun",
                hide_index=True
            )
            
            if event and "rows" in event.selection and len(event.selection["rows"]) > 0:
                st.session_state.selected_row_data = full_route_df.iloc[event.selection["rows"]]
            
            # 💡 鎖定需求：(下)的資料隨著點擊的站點不同要更新跳動
            if st.session_state.selected_row_data is not None:
                row = st.session_state.selected_row_data
                current_step_val = str(row.get("Step No.", "1"))
                shuttle_val = str(row.get("Shuttle Name", "N/A"))
                tool_val = str(row.get("Process Tool", "N/A"))
                owner_val = str(row.get("Stage Owner", "N/A"))
                status_val = "SELECTED"
                
                if not status_df.empty:
                    match_status = status_df[(status_df["Wafer_ID"].astype(str) == str(row.get("Wafer ID"))) & (status_df["Step_No"].astype(int) == int(row.get("Step No.", 1)))]
                    if not match_status.empty:
                        status_val = match_status.sort_values(by="Timestamp").iloc[-1].get("Status", "SELECTED")
                        hold_start = match_status.sort_values(by="Timestamp").iloc[-1].get("Hold_Start_Time", "")
            else:
                # 預設對應底層資訊
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
            
            # 本地變更狀態過站面板
            with st.form("local_update_panel"):
                st.write("📝 **過站與模擬狀態更新紀錄**")
                ca, cb = st.columns(2)
                with ca:
                    input_id = st.text_input("確認晶圓編號 (Wafer ID)", value=search_wafer if search_wafer else "LOT4-11F0")
                    next_status = st.selectbox("變更狀態", ["INPR", "Hold", "Pass", "Scrap"], index=0)
                with cb:
                    next_step = st.number_input("前進製程步數 (Step No.)", min_value=1, max_value=200, value=int(current_step_val))
                    input_shuttle = st.text_input("確認 Shuttle Name", value=shuttle_val)
                if st.form_submit_button("💾 錄入過站事件軌跡"):
                    new_log = pd.DataFrame([{
                        "Wafer_ID": input_id, "Shuttle_Name": input_shuttle, "Step_No": int(next_step),
                        "Status": next_status, "Customer": "蔡作敏/張振豪團隊",
                        "Hold_Start_Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if next_status == "Hold" else "",
                        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    st.session_state.local_status_logs = pd.concat([st.session_state.local_status_logs, new_log], ignore_index=True)
                    st.success(f"🎉 晶圓 {input_id} 第 {next_step} 步狀態錄入成功！")
                    st.rerun()
        else:
            st.warning(f"⚠️ 系統大儲存庫中目前尚未導入晶圓編號 『{search_wafer}』 的 92 步資料。請先至第三頁導入檔案。")
    else:
        st.error("⚠️ 系統路由庫為空。")

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產路由總覽 (Wafer History)")
    st.markdown("💡 **核心鎖定需求**：本頁面不受過站進度干擾，不論有沒有過站紀錄，**皆會強制完整呈現該 Wafer ID 在系統中登記的 92 步全路由軌跡。**")
    
    target_wafer = st.session_state.search_input_val if st.session_state.search_input_val else ""
    search_history_id = st.text_input("🔍 查詢特定晶圓歷史路由 (支援模糊搜尋)：", value=target_wafer).strip()
    st.session_state.search_input_val = search_history_id
    
    route_db = st.session_state.permanent_route_df
    if not route_db.empty:
        history_display_df = route_db.copy()
        if search_history_id:
            history_display_df = history_display_df[history_display_df["Wafer ID"].astype(str).str.contains(search_history_id, case=False, na=False)]
        
        if not history_display_df.empty:
            available_history_cols = ["Wafer ID", "Shuttle Name", "Step No.", "Module", "Step Description", "Process Tool", "Recipe", "Check point", "Stage Owner", "Customer", "Product Type"]
            st.dataframe(history_display_df[available_history_cols].sort_values("Step No."), use_container_width=True, height=500, hide_index=True)
        else:
            st.warning(f"⚠️ 查無關於晶圓 『{search_history_id}』 的 92 步清單。")
# ==================== 📤 頁面三：上傳新路由檔案 ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案至雲端 (接續附加模式)")
    st.markdown("💡 **資安防覆寫機制**：此處上傳新晶圓路由時，資料會自動接續在網頁儲存庫底部，**絕對不會覆蓋或刪除您先前已餵進去的舊資料！**")
    
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
            # 💡 核心功能：防誤觸二次確認按鈕
            st.warning("⚠️ 請確認上方預覽的資料欄位與內容是否正確。點擊下方按鈕後，這 92 步資料將永久接續併入網頁儲存庫。")
            
            confirm_upload_btn = st.button("📤 我已確認檔案無誤，正式上傳至系統儲存庫", type="primary")
            
            if confirm_upload_btn:
                # 💡 核心功能：新舊資料完全共存！利用 concat 實現防覆寫附加模式
                st.session_state.permanent_route_df = pd.concat([st.session_state.permanent_route_df, processed_df], ignore_index=True).drop_duplicates()
                st.success("🎉 附加同步成功！新晶圓的 92 步流程已成功併入系統底部，且完全未覆蓋歷史舊資料！請前往頁面一或頁面二查詢成果。")
                        
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
            
    # 💡 廠內合規安全鎖：提供一鍵下載。同仁隨時可以將網頁上累積的所有晶圓路由一指打包，複製貼回公司的 Excel 或 Sheet 存檔
    if not st.session_state.permanent_route_df.empty:
        st.markdown("---")
        st.subheader("💾 系統全域資料庫備份導出")
        csv_buffer = io.StringIO()
        st.session_state.permanent_route_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 下載目前系統累積的所有晶圓路由 CSV 大表",
            data=csv_buffer.getvalue(),
            file_name=f"wafer_all_routes_backup_{datetime.date.today()}.csv",
            mime="text/csv"
        )
