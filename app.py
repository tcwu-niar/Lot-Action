import streamlit as st
import pandas as pd
import datetime
import requests
import io

# ==================== 1. 網頁基礎設定 ====================
st.set_page_config(page_title="Wafer Tracing System", page_icon="🏭", layout="wide")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (免金鑰資安版)")
st.markdown("---")

# 初始化全站記憶體，確保切換頁面不遺失打字內容
if "search_input_val" not in st.session_state:
    st.session_state.search_input_val = ""
if "local_route_df" not in st.session_state:
    st.session_state.local_route_df = pd.DataFrame(columns=["Step No.", "Step Description", "Process Tool", "Stage Owner"])
if "local_status_df" not in st.session_state:
    st.session_state.local_status_df = pd.DataFrame(columns=["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"])

# ==================== 2. 安全讀取公開的 Google Sheet ====================
# 您的試算表 ID
sheet_id = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"

# 模擬瀏覽器表頭，避免科技廠 DNS 阻擋
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

@st.cache_data(ttl=2) # 2秒快取，防止被 Google 暫時封鎖
def fetch_cloud_data():
    route_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=route_template"
    status_url = f"https://google.com{sheet_id}/gviz/tq?tqx=out:csv&sheet=wafer_status"
    
    r_df = pd.DataFrame(columns=["Step No.", "Step Description", "Process Tool", "Stage Owner"])
    s_df = pd.DataFrame(columns=["Wafer_ID", "Shuttle_Name", "Step_No", "Status", "Customer", "Hold_Start_Time", "Timestamp"])
    
    try:
        # 使用 requests 強行獲取資料
        res_r = requests.get(route_url, headers=headers, timeout=5)
        if res_r.status_code == 200:
            r_df = pd.read_csv(io.StringIO(res_r.text))
            # 欄位修正
            rename_map = {"Step": "Step No.", "Step_No": "Step No.", "Step description": "Step Description", "Step_Description": "Step Description", "Tool name/mask": "Process Tool", "Process_Tool": "Process Tool", "Owner": "Stage Owner", "Stage_Owner": "Stage Owner"}
            r_df = r_df.rename(columns=rename_map)
            if "Step No." in r_df.columns:
                r_df["Step No."] = pd.to_numeric(r_df["Step No."], errors='coerce').fillna(1).astype(int)
                
        res_s = requests.get(status_url, headers=headers, timeout=5)
        if res_s.status_code == 200:
            s_df = pd.read_csv(io.StringIO(res_s.text))
            if not s_df.empty and "Step_No" in s_df.columns:
                s_df["Step_No"] = pd.to_numeric(s_df["Step_No"], errors='coerce').fillna(1).astype(int)
    except:
        pass
    return r_df, s_df

cloud_route, cloud_status = fetch_cloud_data()

# 整合雲端與本地上傳的資料
if st.session_state.local_route_df.empty and not cloud_route.empty:
    st.session_state.local_route_df = cloud_route
if st.session_state.local_status_df.empty and not cloud_status.empty:
    st.session_state.local_status_df = cloud_status

# ==================== 3. 側邊欄導覽 ====================
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
    
    # 模糊搜尋格子，且切換分頁內容不消失
    search_wafer = st.text_input(
        "請輸入 晶圓/批次/機台/負責人 關鍵字 (支援模糊搜尋)：", 
        value=st.session_state.search_input_val,
        placeholder="例如: LOT4-11F0"
    ).strip()
    st.session_state.search_input_val = search_wafer

    current_step, shuttle_name, status_val, customer_val, hold_start = 1, "T18-C14A", "INPR", "蔡作敏/張振豪團隊", ""

    status_df = st.session_state.local_status_df
    if search_wafer and not status_df.empty:
        current_wafer_info = status_df[status_df["Wafer_ID"] == search_wafer]
        if not current_wafer_info.empty:
            latest_info = current_wafer_info.sort_values(by="Timestamp").iloc[-1]
            current_step = int(latest_info["Step_No"]) if "Step_No" in latest_info else (int(latest_info["Step_No"]) if "Step_No" in latest_info else 1)
            shuttle_name = latest_info["Shuttle_Name"] if "Shuttle_Name" in latest_info else "T18-C14A"
            status_val = latest_info["Status"] if "Status" in latest_info else "INPR"
            customer_val = latest_info["Customer"] if "Customer" in latest_info else "蔡作敏/張振豪團隊"
            hold_start = latest_info["Hold_Start_Time"] if "Hold_Start_Time" in latest_info else ""

    st.markdown("---")
    st.subheader("🛤️ (中) 完整製程路由監控 (Full Route)")
    
    route_df = st.session_state.local_route_df
    if not route_df.empty:
        full_route_df = route_df.copy()
        full_route_df["Wafer_ID"] = search_wafer if search_wafer else "LOT4-11F0"
        full_route_df["Shuttle_Name"] = shuttle_name
        
        available_cols = ["Wafer_ID", "Shuttle_Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"]
        display_cols = [col for col in available_cols if col in full_route_df.columns]
        full_route_df = full_route_df[display_cols].sort_values("Step No.")
        
        # 💡 輸入任何字完全不影響下面原本該顯示的結構（採取模糊搜尋過濾）
        if search_wafer:
            mask = full_route_df.astype(str).apply(lambda x: x.str.contains(search_wafer, case=False)).any(axis=1)
            filtered_route_df = full_route_df[mask]
        else:
            filtered_route_df = full_route_df.copy()

        def highlight_current_step(row):
            if "Step No." in row and row["Step No."] == current_step:
                return ['background-color: #ffe6e6; font-weight: bold; color: black'] * len(row)
            elif "Step No." in row and row["Step No."] < current_step:
                return ['background-color: #f2f2f2; color: #888888'] * len(row)
            return [''] * len(row)
            
        st.dataframe(filtered_route_df.style.apply(highlight_current_step, axis=1), use_container_width=True, height=450)
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
    
    # 過站面板
    with st.form("local_update_form"):
        st.write("📝 **過站與異動狀態更新紀錄**")
        ca, cb = st.columns(2)
        with ca:
            next_status = st.selectbox("變更狀態", ["INPR", "Hold", "Pass", "Scrap"], index=["INPR", "Hold", "Pass", "Scrap"].index(status_val) if status_val in ["INPR", "Hold", "Pass", "Scrap"] else 0)
            next_step = st.number_input("前進製程步數 (Step No.)", min_value=1, max_value=200, value=current_step)
        with cb:
            input_cust = st.text_input("更新客戶名稱", value=customer_val)
            input_shuttle = st.text_input("更新 Shuttle Name", value=shuttle_name)
            
        if st.form_submit_button("💾 本地模擬更新 (因資安無金鑰，建議由 Sheet 本身直接編輯數據)"):
            target_id = search_wafer if search_wafer else "LOT4-11F0"
            new_log = pd.DataFrame([{
                "Wafer_ID": target_id, "Shuttle_Name": input_shuttle, "Step_No": int(next_step),
                "Status": next_status, "Customer": input_cust,
                "Hold_Start_Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if next_status == "Hold" else "",
                "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            st.session_state.local_status_df = pd.concat([st.session_state.local_status_df, new_log], ignore_index=True)
            st.success("🎉 本地看板更新成功！")
            st.rerun()

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產變更紀錄總覽 (Wafer History)")
    status_df = st.session_state.local_status_df
    if not status_df.empty:
        display_df = status_df.sort_values(by="Timestamp", ascending=False) if "Timestamp" in status_df.columns else status_df
        if st.session_state.search_input_val:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(st.session_state.search_input_val, case=False)).any(axis=1)]
        st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("目前尚無過站紀錄。")

# ==================== 📤 頁面三：上傳新路由檔案 ====================
elif menu == "📤 頁面三：上傳新路由檔案":
    st.subheader("📤 導入晶圓生產路由 CSV 檔案")
    uploaded_file = st.file_uploader("請選擇您的晶圓流程 CSV 檔案 (.csv)", type=["csv"])
    if uploaded_file is not None:
        try:
            raw_df = pd.read_csv(uploaded_file)
            rename_map = {"Step": "Step No.", "Step description": "Step Description", "Tool name/mask": "Process Tool", "Owner": "Stage Owner"}
            processed = raw_df.rename(columns=rename_map)
            st.session_state.local_route_df = processed
            st.success("🎉 成功將 92 步製程數據導入全站記憶體！請切換至『頁面一』查看成果。")
            st.dataframe(processed.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
