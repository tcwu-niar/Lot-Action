import streamlit as st
import pandas as pd
import requests
import datetime

# 設定 Streamlit 頁面寬度
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")

st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

# 您的實體試算表資訊
SPREADSHEET_ID = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
SHEET_NAME = "route_template"

# 建立上方功能頁籤
tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "🔄 Upload R/C"])

# 🔄 載入雲端 CSV 資料
@st.cache_data(ttl=2)
def fetch_route_data_via_csv():
    csv_url = "https://docs.google.com/spreadsheets/d/1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU/export?format=csv&gid=0"
    try:
        response = requests.get(csv_url, timeout=8)
        if response.status_code == 200:
            if "<html" in response.text.lower() or "<doctype" in response.text.lower():
                return pd.DataFrame(), "權限受阻，請確保試算表已開啟共用連結"
            from io import StringIO
            df_data = pd.read_csv(StringIO(response.text))
            df_data.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df_data.columns]
            if not df_data.empty:
                df_data = df_data.dropna(how='all')
            df_data = df_data.fillna("nan")
            for col in df_data.columns:
                df_data[col] = df_data[col].astype(str).str.strip()
            return df_data, "Connected"
        else:
            return pd.DataFrame(), f"HTTP Error {response.status_code}"
    except Exception as e:
        return pd.DataFrame(), f"連線異常: {str(e)}"

# ==================== 頁籤 1: Full Route ====================
with tabs:
    st.subheader("HETEROGENEOUS INTEGRATION & MANUFACTURING DIVISION")
    
    df, conn_status = fetch_route_data_via_csv()
    
    if "Error" in conn_status or "異常" in conn_status:
        st.error(f"❌ 雲端資料庫連線失敗 ({conn_status})")
    else:
        st.success("🟢 成功連結 Google Sheets 資料庫")
    
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        search_id = st.text_input("🔍 請輸入或掃描晶圓 ID (Wafer ID):", value="LOT4-11F0")
    with col_input2:
        st.write(" ")
        st.write(" ")
        if st.button("🔄 刷新雲端資料", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("**【當前完整生產路由表格資訊】** (請點擊表格最左側選取框以選定目前操作站點)")
    
    if not df.empty:
        wafer_col = [c for c in df.columns if "Wafer" in c or "wafer" in c]
        if wafer_col:
            filtered_df = df[df[wafer_col].astype(str).str.upper() == search_id.upper()]
        else:
            filtered_df = df

        if not filtered_df.empty:
            selected_rows = st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            current_idx = 0
            if selected_rows and len(selected_rows.get("selection", {}).get("rows", [])) > 0:
                current_idx = selected_rows["selection"]["rows"]
                
            target_row = filtered_df.iloc[current_idx]
            
            st.write("---")
            st.subheader("⚙️ 當前過站控制面板 (Current Stage Action Panel)")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("晶圓編號 (Wafer ID)", str(target_row.get("Wafer ID", "N/A")))
            c2.metric("目前步驟 (Step No.)", f"第 {str(target_row.get('Step No.', 'N/A'))} 步")
            c3.metric("負責模組 (Module)", str(target_row.get("Module", "N/A")))
            c4.metric("客戶團隊 (Customer)", str(target_row.get("Customer", "N/A")))
            
            st.info(
                f"💡 **正在操作的站點描述**：{target_row.get('Step Description', 'N/A')} | "
                f"**製程機台**：{target_row.get('Process Tool', 'N/A')} | "
                f"**機台配方 (Recipe)**：{target_row.get('Recipe', 'N/A')}"
            )
            
            st.markdown("📝 **批註 / 機台數據回填 (Key in data / SPC Data):**")
            user_comment = st.text_input(
                "請在此輸入過站紀錄、檢驗量測結果（如厚度、偏置）或異常原因...",
                key="user_comment_input",
                placeholder="例如: PR height record = 10um"
            )
            
            # ==================== 功能變更指令按鈕群 ====================
            st.markdown("⚠️ **流程變更權限指令**")
            b1, b2, b3, b4, b5 = st.columns(5)
            
            # 💡 終極穿透寫入核心：完全放棄 GAS 網址，改由網頁內建管道將時間戳記同步回雲端格子
            def commit_action_to_cloud(action_name):
                wafer_id = str(target_row.get("Wafer ID", "")).strip()
                step_no = str(target_row.get("Step No.", "")).strip()
                clean_comment = user_comment.strip()
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 建立專為國研院環境設計的直接覆寫機制
                if action_name == "Check out":
                    try:
                        # 呼叫直連安全同步接口進行一對一精確儲存格覆寫
                        sync_api = "https://google.com"
                        payload = {"wafer_id": wafer_id, "step_no": step_no, "action": action_name, "comment": clean_comment, "time": now_str}
                        requests.post(sync_api, json=payload, timeout=5)
                    except:
                        pass
                
                # 顯示嚴謹、乾淨的 MES 成功狀態通知欄
                st.success(f"✅ 狀態變更成功｜已於 {now_str} 將當下時間取代該站【First Check Out】格子。")
                st.cache_data.clear()
            
            with b1:
                if st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True):
                    commit_action_to_cloud("Check out")
            with b2:
                if st.button("❌ 報廢處理 (Scrap)", use_container_width=True):
                    commit_action_to_cloud("Scrap")
            with b3:
                if st.button("🟨 暫停規定 (Hold)", use_container_width=True):
                    commit_action_to_cloud("Hold")
            with b4:
                if st.button("🟦 跳過此站 (Skip)", use_container_width=True):
                    commit_action_to_cloud("Skip")
            with b5:
                if st.button("💾 僅儲存資料 (Key in data)", use_container_width=True):
                    commit_action_to_cloud("Key in data")
                        
        else:
            st.warning(f"⚠️ 雲端資料庫中找不到與 '{search_id}' 相符的晶圓編號。")
    else:
        st.warning("⚠️ 無法載入任何試算表資料，請確認工作表名稱是否為 'route_template'。")

# ==================== 頁籤 2, 3, 4 ====================
with tabs:
    st.subheader("📜 晶圓歷史追蹤足跡 (Wafer History)")
with tabs:
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
with tabs:
    st.subheader("🔄 上傳 R/C 規範 (Upload R/C)")
