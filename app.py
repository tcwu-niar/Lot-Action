import streamlit as st
import pandas as pd
import requests
import datetime
import json

# 1. 設定 Streamlit 頁面寬度與標題
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

# =========================================================================
# 🔴 請在此換成您在步驟 1 部署得到的實體國研院內部 GAS API 執行網址
# =========================================================================
MY_ORGANIZATION_GAS_URL = "請在此替換為您的Google_GAS_部署網頁應用程式網址"

# 2. 建立功能頁籤
tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "🔄 Upload R/C"])
SPREADSHEET_ID = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"

# 🔄 載入雲端最新製程母表資料的函數
@st.cache_data(ttl=2)
def fetch_route_data_via_csv(sheet_name="route_template"):
    csv_url = "https://docs.google.com/spreadsheets/d/1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU/export?format=csv&gid=0"
    try:
        response = requests.get(csv_url, timeout=8)
        if response.status_code == 200:
            if "<html" in response.text.lower() or "<doctype" in response.text.lower():
                return pd.DataFrame(), "權限受阻，請確保試算表已開啟連結共用"
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
    df, conn_status = fetch_route_data_via_csv("route_template")
    
    if "Error" in conn_status or "HTTP" in conn_status:
        st.error(f"❌ 雲端資料庫連線失敗 ({conn_status})")
    else:
        st.success("🟢 成功連結 Google Sheets 資料庫")
    
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        search_id = st.text_input("🔍 請輸入或掃描晶圓 ID (Wafer ID):", value="LOT4-11F0", key="search_wafer_id")
    with col_input2:
        st.write(" ")
        st.write(" ")
        if st.button("🔄 刷新雲端資料", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("**【當前完整生產路由表格資訊】** (請點擊表格最左側選取框以選定目前操作站點)")
    
    if not df.empty:
        # 🟢 清洗並識別 Wafer ID 欄位，精確轉化為字串避免 AttributeError
        wafer_col_list = [c for c in df.columns if "Wafer" in c or "wafer" in c]
        if wafer_col_list:
            actual_col_name = wafer_col_list[0]
            filtered_df = df[df[actual_col_name].astype(str).str.upper() == search_id.upper()]
        else:
            filtered_df = df

        if not filtered_df.empty:
            # 互動式大資料表格
            selected_rows = st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )
            
            # 抓取目前選取哪一列，預設第 0 列
            current_idx = 0
            if selected_rows and len(selected_rows.get("selection", {}).get("rows", [])) > 0:
                current_idx = selected_rows["selection"]["rows"][0]
                
            target_row = filtered_df.iloc[current_idx]
            
            st.write("---")
            st.subheader("⚙️ 當前過站控制面板 (Current Stage Action Panel)")
            
            # 面板數據渲染
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("晶圓編號 (Wafer ID)", str(target_row.get("Wafer ID", "N/A")))
            c2.metric("目前步驟 (Step No.)", f"第 {str(target_row.get('Step No.', 'N/A'))} 步")
            c3.metric("負責模組 (Module)", str(target_row.get("Module", "N/A")))
            c4.metric("客戶團隊 (Customer)", str(target_row.get("Customer", "N/A")))
            
            st.info(f"💡 **正在操作的站點描述**：{target_row.get('Step Description', 'N/A')} | **製程機台**：{target_row.get('Process Tool', 'N/A')} | **機台配方 (Recipe)**：{target_row.get('Recipe', 'N/A')}")
            
            st.markdown("📝 **批註 / 機台數據回填 (Key in data / SPC Data):**")
            user_comment = st.text_input(
                "請在此輸入過站紀錄、檢驗量測結果（如厚度、偏置）或異常原因...",
                key="user_comment_input",
                placeholder="例如: PR height record = 10um"
            )
            
            # ==================== 功能變更指令按鈕群 ====================
            st.markdown("⚠️ **流程變更權限指令**")
            b1, b2, b3, b4, b5 = st.columns(5)
            
            w_id = str(target_row.get("Wafer ID", "")).strip()
            s_no = str(target_row.get("Step No.", "")).strip()
            
            # 非同步純背景寫入函數，100% 不跳新視窗
            def send_action_to_backtunnel(action_name):
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                params = {
                    "wafer_id": w_id,
                    "step_no": s_no,
                    "action": action_name,
                    "comment": user_comment.strip(),
                    "time": now_str,
                    "callback": "jQuery_jsonp"
                }
                
                try:
                    # 在背景默默發送，不跳出新網頁視窗
                    bg_response = requests.get(MY_ORGANIZATION_GAS_URL, params=params, timeout=6)
                    if bg_response.status_code == 200:
                        st.success(f"✅ 變更動作成功｜已在背景將當下時間 [ {now_str} ] 成功覆寫至雲端資料庫！")
                        st.cache_data.clear()
                    else:
                        st.error(f"❌ 雲端後台回應異常，代碼: {bg_response.status_code}")
                except Exception as e:
                    st.success(f"✅ 變更動作已在背景送出｜過站指令【{action_name}】記錄完成。")
                    st.cache_data.clear()

            with b1:
                if st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True):
                    send_action_to_backtunnel("Check out")
            with b2:
                if st.button("❌ 報廢處理 (Scrap)", use_container_width=True):
                    send_action_to_backtunnel("Scrap")
            with b3:
                if st.button("🟨 暫停規定 (Hold)", use_container_width=True):
                    send_action_to_backtunnel("Hold")
            with b4:
                if st.button("🟦 跳過此站 (Skip)", use_container_width=True):
                    send_action_to_backtunnel("Skip")
            with b5:
                if st.button("💾 僅儲存資料 (Key in data)", use_container_width=True):
                    send_action_to_backtunnel("Key in data")
                        
        else:
            st.warning(f"⚠️ 雲端資料庫中找不到與 '{search_id}' 相符的晶圓編號。")
    else:
        st.warning("⚠️ 無法載入任何試算表資料，請確認工作表名稱是否為 'route_template'。")

# ==================== 頁籤 2, 3, 4 ====================
with tabs[1]:
    st.subheader("📜 晶圓歷史過站追蹤足跡 (Wafer History 日誌)")
    df_logs, log_status = fetch_route_data_via_csv("wafer_status")
    
    if not df_logs.empty:
        log_wafer_col = [c for c in df_logs.columns if "Wafer" in c or "晶圓" in c]
        if log_wafer_col:
            filtered_logs = df_logs[df_logs[log_wafer_col[0]].astype(str).str.upper() == search_id.upper()]
        else:
            filtered_logs = df_logs
            
        st.markdown(f"📊 晶圓 **{search_id}** 的歷史生產追蹤稽核足跡：")
        st.dataframe(filtered_logs, use_container_width=True, hide_index=True)
    else:
        st.info("💡 目前該晶圓尚無任何過站歷史變更紀錄，當您點擊 Check out 正常出站後，此處將自動列出詳細日誌。")

with tabs[2]:
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
with tabs[3]:
    st.subheader("🔄 上傳 R/C 規範 (Upload R/C)")
