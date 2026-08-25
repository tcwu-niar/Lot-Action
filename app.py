import streamlit as st
import pandas as pd
import datetime
import requests
import io

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統")
st.markdown("---")

# 初始化全站的跨頁面記憶體 (Session State)
if "global_route_df" not in st.session_state:
    st.session_state.global_route_df = pd.DataFrame(columns=["Step No.", "Step Description", "Process Tool", "Stage Owner"])
if "global_status_df" not in st.session_state:
    st.session_state.global_status_df = pd.DataFrame(columns=["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"])

# 嘗試從網路預載 (當作背景默默嘗試)
sheet_id = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
headers = {"User-Agent": "Mozilla/5.0 (Windows)"}
if st.session_state.global_route_df.empty:
    try:
        r = requests.get(f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=route_template", headers=headers, timeout=2)
        if r.status_code == 200:
            df_net = pd.read_csv(io.StringIO(r.text))
            df_net = df_net.rename(columns={"Step": "Step No.", "Step_No": "Step No.", "Step description": "Step Description", "Step_Description": "Step Description", "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", "Owner": "Stage Owner", "Stage_Owner": "Stage Owner"})
            st.session_state.global_route_df = df_net
    except:
        pass

# ==================== 2. 側邊欄導覽 ====================
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
    search_wafer = st.text_input("請輸入 晶圓/批次編號 (Wafer/Lot ID) 並按下 Enter：", placeholder="例如: LOT4-11F0").strip()
    
    if search_wafer:
        status_df = st.session_state.global_status_df
        current_wafer_info = status_df[status_df["Wafer_ID"] == search_wafer] if not status_df.empty else pd.DataFrame()
        
        if not current_wafer_info.empty:
            latest_info = current_wafer_info.sort_values(by="Timestamp").iloc[-1]
            current_step = int(latest_info["Step_No"])
            shuttle_name = latest_info["Shuttle_Name"]
            status_val = latest_info["Status"]
            customer_val = latest_info["Customer"]
            hold_start = latest_info["Hold_Start_Time"]
        else:
            current_step = 1
            shuttle_name = "T18-C14A"
            status_val = "INPR"
            customer_val = "蔡作敏/張振豪團隊"
            hold_start = ""

        st.markdown("---")
        st.subheader("🛤️ (中) 完整製程路由監控 (Full Route)")
        
        route_df = st.session_state.global_route_df
        if not route_df.empty:
            full_route_df = route_df.copy()
            full_route_df["Wafer_ID"] = search_wafer
            full_route_df["Shuttle_Name"] = shuttle_name
            
            available_cols = ["Wafer_ID", "Shuttle_Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"]
            display_cols = [col for col in available_cols if col in full_route_df.columns]
            full_route_df = full_route_df[display_cols].sort_values("Step No.")
            
            def highlight_current_step(row):
                if "Step No." in row and row["Step No."] == current_step:
                    return ['background-color: #ffe6e6; font-weight: bold; color: black'] * len(row)
                elif "Step No." in row and row["Step No."] < current_step:
                    return ['background-color: #f2f2f2; color: #888888'] * len(row)
                return [''] * len(row)
                
            st.dataframe(full_route_df.style.apply(highlight_current_step, axis=1), use_container_width=True, height=450)
        else:
            st.warning("⚠️ 系統記憶體中目前沒有路由資料。請先到『頁面三』導入 92 步 CSV 檔案。")

        st.markdown("---")
        st.subheader("📊 (下) 當前即時狀態指標")
        computed_hold_time = calculate_hold_time(hold_start) if status_val == "Hold" else "00:00:00"
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("當前狀態 (Status)", status_val)
        c2.metric("客戶名稱 (Customer)", customer_val)
        c3.metric("雪梭名稱 (Shuttle Name)", shuttle_name)
        c4.metric("暫停計時 (Hold Time)", computed_hold_time)
        
        # 允許直接在網頁虛擬操作過站測試
        with st.expander("🛠️ 本地模擬測試：變更此晶圓狀態或過站步驟"):
            with st.form("local_test_form"):
                ca, cb = st.columns(2)
                with ca:
                    next_status = st.selectbox("變更狀態", ["INPR", "Hold", "Pass", "Scrap"], index=["INPR", "Hold", "Pass", "Scrap"].index(status_val) if status_val in ["INPR", "Hold", "Pass", "Scrap"] else 0)
                    next_step = st.number_input("前進製程步數 (Step No.)", min_value=1, max_value=200, value=current_step)
                with cb:
                    input_cust = st.text_input("更新客戶名稱", value=customer_val)
                    input_shuttle = st.text_input("更新 Shuttle Name", value=shuttle_name)
                if st.form_submit_button("💾 本地模擬更新"):
                    new_log = pd.DataFrame([{
                        "Wafer_ID": search_wafer, "Shuttle_Name": input_shuttle, "Step_No": int(next_step),
                        "Status": next_status, "Customer": input_cust,
                        "Hold_Start_Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if next_status == "Hold" else "",
                        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    st.session_state.global_status_df = pd.concat([st.session_state.global_status_df, new_log], ignore_index=True)
                    st.success("更新成功！")
                    st.rerun()
    else:
        st.info("💡 請在上方空格中輸入 Wafer ID。")

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產變更紀錄總覽 (Wafer History)")
    if not st.session_state.global_status_df.empty:
        st.dataframe(st.session_state.global_status_df.sort_values(by="Timestamp", ascending=False), use_container_width=True)
    else:
        st.warning("目前尚無過站紀錄。請在第一頁下方的操作面板建立第一筆紀錄。")

# ==================== 📤 頁面三：上傳新路由檔案 ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案")
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"])
    if uploaded_file is not None:
        try:
            raw_df = pd.read_csv(uploaded_file)
            # 自動清洗與更名，精準與您的檔案欄位對應
            rename_map = {"Step": "Step No.", "Step description": "Step Description", "Tool name/mask": "Process Tool", "Owner": "Stage Owner"}
            processed = raw_df.rename(columns=rename_map)
            st.session_state.global_route_df = processed
            st.success("🎉 成功將 92 步製程數據導入全站記憶體！請切換至『頁面一』輸入 Wafer ID 查看成果。")
            st.dataframe(processed.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
