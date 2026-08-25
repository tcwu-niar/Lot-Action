import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
from streamlit_filesconnection import FilesConnection

# 網頁基礎設定
st.set_page_config(page_title="晶圓歷史紀錄與 SPC 系統", page_icon="🏭", layout="wide")
st.title("🏭 晶圓歷史與 SPC 管制系統")
st.markdown("##### 🗄️ 後端資料庫：Google Sheets 雲端連線中")
st.markdown("---")

# 從 Streamlit 後台安全讀取 Google Sheet 網址（部署時設定在 Secrets 中）
GSHEET_URL = st.secrets.get("gsheet_url", "")

if not GSHEET_URL:
    st.warning("⚠️ 系統偵測到尚未設定 Google Sheets 資料庫網址。請至 Streamlit App Settings -> Secrets 設定 `gsheet_url`。")
    st.stop()

try:
    # 初始化連線並讀取資料 (ttl=10 代表快取 10 秒，避免頻繁讀取被 Google 封鎖)
    conn = st.connection("gcs", type=FilesConnection)
    df = conn.read(GSHEET_URL, input_format="csv", ttl=10)
    
    # 確保資料型態正確
    if not df.empty:
        df["Thickness"] = pd.to_numeric(df["Thickness"], errors='coerce').fillna(0.0)
        df["Timestamp"] = df["Timestamp"].astype(str)
except Exception as e:
    st.error(f"❌ 無法連線至 Google Sheets，請檢查網址或權限。錯誤: {e}")
    st.stop()

# 側邊欄導覽功能
st.sidebar.header("🧭 系統選單")
menu = st.sidebar.radio("切換功能頁面：", ["📊 數據看板與 SPC 查詢", "➕ 新增生產製程紀錄"])

# === 頁面一：數據看板與 SPC 查詢 ===
if menu == "📊 數據看板與 SPC 查詢":
    st.subheader("🔍 關鍵字動態篩選")
    col1, col2 = st.columns(2)
    with col1:
        search_lot = st.text_input("輸入批次編號 (Lot ID) 搜尋：")
    with col2:
        status_options = df["Status"].unique().tolist() if not df.empty else ["Pass", "Abnormal"]
        filter_status = st.multiselect("篩選檢查狀態：", options=status_options, default=status_options)

    filtered_df = df.copy()
    if not filtered_df.empty:
        filtered_df = filtered_df[filtered_df["Status"].isin(filter_status)]
        if search_lot:
            filtered_df = filtered_df[filtered_df["Lot_ID"].str.contains(search_lot, case=False)]

    st.markdown("### 📈 即時生產指標")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("雲端資料總數", f"{len(filtered_df)} 筆")
    
    if len(filtered_df) > 0:
        abnormal_rate = (len(filtered_df[filtered_df["Status"] == "Abnormal"]) / len(filtered_df)) * 100
        avg_thickness = filtered_df["Thickness"].mean()
    else:
        abnormal_rate, avg_thickness = 0.0, 0.0
        
    kpi2.metric("平均量測厚度", f"{avg_thickness:.2f} Å")
    kpi3.metric("製程異常率", f"{abnormal_rate:.1f} %", delta=f"{abnormal_rate:.1f}%", delta_color="inverse")

    st.markdown("### 📋 晶圓歷史紀錄清單")
    st.dataframe(filtered_df, use_container_width=True)

    st.markdown("### 📉 晶圓量測厚度走勢圖 (SPC)")
    if not filtered_df.empty:
        fig = px.line(filtered_df, x="Timestamp", y="Thickness", title="Thickness Trend (Å)", markers=True, hover_data=["Wafer_ID", "Lot_ID"])
        fig.add_hline(y=120.0, line_dash="dash", line_color="green", annotation_text="Target: 120Å")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("⚠️ 沒有符合篩選條件的數據。")

# === 頁面二：新增生產製程紀錄 ===
elif menu == "➕ 新增生產製程紀錄":
    st.subheader("📝 輸入新晶圓生產數據")
    with st.form("input_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            input_wafer = st.text_input("晶圓編號 (Wafer ID) *")
            input_lot = st.text_input("批次編號 (Lot ID) *")
            input_step = st.selectbox("製程站別", ["黃光 (Litho)", "蝕刻 (Etch)", "薄膜 (CVD)", "擴散 (Diffusion)"])
        with c2:
            input_thickness = st.number_input("測量厚度 (Thickness Å)", min_value=0.0, value=120.0, step=0.1)
            input_status = st.radio("檢查結果", ["Pass", "Abnormal"], horizontal=True)
            
        submit_button = st.form_submit_button(label="💾 提交並寫入 Google Sheets")
        
        if submit_button:
            if not input_wafer or not input_lot:
                st.error("❌ 錯誤：『晶圓編號』與『批次編號』為必填欄位！")
            else:
                new_row = pd.DataFrame([{
                    "Wafer_ID": input_wafer, "Lot_ID": input_lot, "Step": input_step,
                    "Status": input_status, "Thickness": input_thickness,
                    "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                try:
                    conn.write(GSHEET_URL, updated_df, index=False)
                    st.success(f"🎉 數據成功同步至 Google Sheets！晶圓: {input_wafer}")
                    st.cache_data.clear()
                except Exception as write_error:
                    st.error(f"❌ 寫入雲端失敗，請確認該 Google 表格是否已開啟『任何人皆可編輯』。錯誤: {write_error}")
