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
# 💡 關鍵修改：將搜尋框的值存入記憶體，切換頁面不被清空
if "search_input_val" not in st.session_state:
    st.session_state.search_input_val = ""

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
    
    # 💡 記憶體鎖定輸入框：讀取與存入 session_state
    search_wafer = st.text_input(
        "請輸入 晶圓/批次/機台/負責人 關鍵字 (支援模糊搜尋)：", 
        value=st.session_state.search_input_val,
        placeholder="例如: LOT4-11F0 或 DISCO"
    ).strip()
    st.session_state.search_input_val = search_wafer  # 即時同步記憶體

    # 初始化預設狀態資訊 (永遠顯示基礎面板)
    current_step = 1
    shuttle_name = "T18-C14A"
    status_val = "INPR"
    customer_val = "蔡作敏/張振豪團隊"
    hold_start = ""

    # 如果輸入框有值，嘗試從歷史紀錄抓取最新狀態
    if search_wafer:
        status_df = st.session_state.global_status_df
        # 精準比對 Wafer ID
        current_wafer_info = status_df[status_df["Wafer_ID"] == search_wafer] if not status_df.empty else pd.DataFrame()
        if not current_wafer_info.empty:
            latest_info = current_wafer_info.sort_values(by="Timestamp").iloc[-1]
            current_step = int(latest_info["Step_No"])
            shuttle_name = latest_info["Shuttle_Name"]
            status_val = latest_info["Status"]
            customer_val = latest_info["Customer"]
            hold_start = latest_info["Hold_Start_Time"]

    st.markdown("---")
    st.subheader("🛤️ (中) 完整製程路由監控 (Full Route)")
    
    route_df = st.session_state.global_route_df
    if not route_df.empty:
        full_route_df = route_df.copy()
        
        # 補上基本欄位
        full_route_df["Wafer_ID"] = search_wafer if search_wafer else "LOT4-11F0"
        full_route_df["Shuttle_Name"] = shuttle_name
        
        available_cols = ["Wafer_ID", "Shuttle_Name", "Step No.", "Step Description", "Process Tool", "Stage Owner"]
        display_cols = [col for col in available_cols if col in full_route_df.columns]
        full_route_df = full_route_df[display_cols].sort_values("Step No.")
        
        # 💡 核心修改：實現模糊搜尋過濾表格 (只要任一欄位包含關鍵字就留著，若沒打字則秀出全部 92 步)
        if search_wafer:
            # 將所有欄位轉字串並進行小寫模糊比對
            mask = full_route_df.astype(str).apply(lambda x: x.str.contains(search_wafer, case=False)).any(axis=1)
            filtered_route_df = full_route_df[mask]
        else:
            filtered_route_df = full_route_df.copy()

        # 表格背景高亮邏輯
        def highlight_current_step(row):
            if "Step No." in row and row["Step No."] == current_step:
                return ['background-color: #ffe6e6; font-weight: bold; color: black'] * len(row)
            elif "Step No." in row and row["Step No."] < current_step:
                return ['background-color: #f2f2f2; color: #888888'] * len(row)
            return [''] * len(row)
            
        # 顯示過濾或完整的 92 步路由表
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
    
    # 本地虛擬操作過站面板
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
                target_id = search_wafer if search_wafer else "LOT4-11F0"
                new_log = pd.DataFrame([{
                    "Wafer_ID": target_id, "Shuttle_Name": input_shuttle, "Step_No": int(next_step),
                    "Status": next_status, "Customer": input_cust,
                    "Hold_Start_Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if next_status == "Hold" else "",
                    "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                st.session_state.global_status_df = pd.concat([st.session_state.global_status_df, new_log], ignore_index=True)
                st.success(f"更新成功！已變更 {target_id} 狀態。")
                st.rerun()

# ==================== 📜 頁面二：Wafer History ====================
elif menu == "📜 頁面二：Wafer History":
    st.subheader("📜 歷史生產變更紀錄總覽 (Wafer History)")
    
    # 💡 記憶體同步：此頁面一樣可以使用剛剛在第一頁打的關鍵字做自動過濾
    st.info(f"💡 目前正依據您的記憶體關鍵字 『{st.session_state.search_input_val}』 進行同步篩選。") if st.session_state.search_input_val else None
    
    if not st.session_state.global_status_df.empty:
        display_df = st.session_state.global_status_df.sort_values(by="Timestamp", ascending=False)
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
            st.session_state.global_route_df = processed
            st.success("🎉 成功將 92 步製程數據導入全站記憶體！請切換至『頁面一』查看成果。")
            st.dataframe(processed.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"❌ 解析失敗: {e}")
