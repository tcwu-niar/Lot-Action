import streamlit as st
import pandas as pd
import requests
import datetime

st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "🔄 Upload R/C"])

SPREADSHEET_ID = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"

@st.cache_data(ttl=2)
def fetch_route_data_via_csv():
    csv_url = "https://docs.google.com/spreadsheets/d/1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU/export?format=csv&gid=0"
    try:
        response = requests.get(csv_url, timeout=8)
        if response.status_code == 200:
            from io import StringIO
            df_data = pd.read_csv(StringIO(response.text))
            df_data.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df_data.columns]
            df_data = df_data.fillna("nan")
            for col in df_data.columns:
                df_data[col] = df_data[col].astype(str).str.strip()
            return df_data, "Connected"
        else:
            return pd.DataFrame(), f"HTTP {response.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

# ==================== 頁籤 1: Full Route ====================
with tabs[0]:
    st.subheader("HETEROGENEOUS INTEGRATION & MANUFACTURING DIVISION")
    df, conn_status = fetch_route_data_via_csv()
    
    if "Error" in conn_status or "HTTP" in conn_status:
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

    if not df.empty:
        wafer_col = [c for c in df.columns if "Wafer" in c or "wafer" in c]
        filtered_df = df[df[wafer_col[0]].astype(str).str.upper() == search_id.upper()] if wafer_col else df

        if not filtered_df.empty:
            selected_rows = st.dataframe(filtered_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            current_idx = selected_rows["selection"]["rows"][0] if selected_rows and selected_rows.get("selection", {}).get("rows") else 0
            target_row = filtered_df.iloc[current_idx]
            
            st.write("---")
            st.subheader("⚙️ 當前過站控制面板 (Current Stage Action Panel)")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("晶圓編號 (Wafer ID)", str(target_row.get("Wafer ID", "N/A")))
            c2.metric("目前步驟 (Step No.)", f"第 {str(target_row.get('Step No.', 'N/A'))} 步")
            c3.metric("負責模組 (Module)", str(target_row.get("Module", "N/A")))
            c4.metric("客戶團隊 (Customer)", str(target_row.get("Customer", "N/A")))
            
            st.markdown("📝 **批註 / 機台數據回填 (Key in data / SPC Data):**")
            user_comment = st.text_input("請在此輸入過站紀錄...", key="user_comment_input", placeholder="例如: PR height record = 10um")
            
            st.markdown("⚠️ **流程變更權限指令**")
            b1, b2, b3, b4, b5 = st.columns(5)
            
            w_id = str(target_row.get("Wafer ID", "")).strip()
            s_no = str(target_row.get("Step No.", "")).strip()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 🔴 請在此換成您剛剛在步驟 1 產生的實體國研院內部 /exec 網址 🔴
            MY_ORGANIZATION_GAS_URL = "https://script.google.com/macros/s/AKfycbxSpHeSlbCyMgn0cH60fh62eM_nYoaCwkSCZF1UJMTeC-3z1wQJ1RVLXge1kvzadmKM/exec"
            
            # 拼裝穿透網址
            final_redirect_url = f"{MY_ORGANIZATION_GAS_URL}?wafer_id={w_id}&step_no={s_no}&action=Check out&time={requests.utils.quote(now_str)}"
            
            with b1:
                # 🚀 終極亮點：點擊按鈕直接開啟隱形中繼點，利用您自己的瀏覽器權限直接秒速完成覆寫！
                if st.link_button("🟢 正常出站 (Check out)", final_redirect_url, type="primary", use_container_width=True):
                    st.cache_data.clear()
            with b2: st.button("❌ 報廢處理 (Scrap)", use_container_width=True)
            with b3: st.button("🟨 暫停規定 (Hold)", use_container_width=True)
            with b4: st.button("🟦 跳過此站 (Skip)", use_container_width=True)
            with b5: st.button("💾 僅儲存資料 (Key in data)", use_container_width=True)

# ==================== 頁籤 2, 3, 4 ====================
with tabs[1]:
    st.subheader("📜 晶圓歷史追蹤足跡 (Wafer History)")
with tabs[2]:
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
with tabs[3]:
    st.subheader("🔄 上傳 R/C 規範 (Upload R/C)")
