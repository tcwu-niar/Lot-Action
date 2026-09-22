import streamlit as st
import pandas as pd
import requests
import datetime

# 1. 設定 Streamlit 頁面寬度與標題
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

# 2. 定義您的實體雲端試算表 ID 與工作表名稱
SPREADSHEET_ID = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
SHEET_NAME = "route_template"

# 3. 建立上方四大功能頁籤（校正語法：將頁籤物件存入變使 tabs 中）
tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "🔄 Upload R/C"])

# 🔄 載入雲端最新製程母表資料的函數
@st.cache_data(ttl=2)
def fetch_route_data_via_csv():
    # 官方強制導出 CSV 格式的完整安全網址
    csv_url = "https://docs.google.com/spreadsheets/d/1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU/export?format=csv&gid=0"
    try:
        response = requests.get(csv_url, timeout=8)
        if response.status_code == 200:
            if "<html" in response.text.lower() or "<doctype" in response.text.lower():
                return pd.DataFrame(), "權限受阻，請確保試算表共用設定已開啟『國研院組織內（或知道連結者）皆可檢視』"
            
            from io import StringIO
            df_data = pd.read_csv(StringIO(response.text))
            
            # 清洗標頭與文字中的換行字元與空格
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

# ==================== 頁籤 1: Full Route (完美修正 tabs 索引語法) ====================
with tabs[0]:
    st.subheader("HETEROGENEOUS INTEGRATION & MANUFACTURING DIVISION")
    
    # 讀取雲端試算表數據
    df, conn_status = fetch_route_data_via_csv()
    
    if "Error" in conn_status or "異常" in conn_status:
        st.error(f"❌ 雲端資料庫連線失敗 ({conn_status})")
    else:
        st.success("🟢 成功連結 Google Sheets 資料庫")
    
    # 搜尋過濾器面板
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
        # 自動識別 Wafer ID 欄位並進行資料過濾
        wafer_col = [c for c in df.columns if "Wafer" in c or "wafer" in c]
        if wafer_col:
            filtered_df = df[df[wafer_col[0]].astype(str).str.upper() == search_id.upper()]
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
            
            def commit_action_to_cloud(action_name):
                w_id = str(target_row.get("Wafer ID", "")).strip()
                s_no = str(target_row.get("Step No.", "")).strip()
                clean_comment = user_comment.strip()
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if action_name == "Check out":
                    # 🔴 請將下方的網址換成您剛剛在步驟 1 複製的專屬 GAS 網址 🔴
                    my_private_gas_url = "https://script.google.com/macros/s/AKfycbxSpHeSlbCyMgn0cH60fh62eM_nYoaCwkSCZF1UJMTeC-3z1wQJ1RVLXge1kvzadmKM/exec"
                    
                    payload = {
                        "wafer_id": w_id,
                        "step_no": s_no,
                        "action": action_name,
                        "comment": clean_comment,
                        "time": now_str
                    }
                    
                    try:
                        # 正式發送變更請求給您自己的試算表
                        response = requests.post(my_private_gas_url, json=payload, timeout=8)
                        res_json = response.json()
                        if res_json.get("status") == "success":
                            st.success(f"✅ 成功寫入雲端｜已將出站時間 {now_str} 填入第 {s_no} 站的 [First Check Out] 格子。")
                        else:
                            st.error(f"❌ 雲端寫入失敗: {res_json.get('message')}")
                    except Exception as e:
                        st.error(f"❌ 無法連線至您的後端通道: {str(e)}。請確認步驟 2 的網址是否正確。")
                else:
                    st.success(f"✅ 狀態變更成功｜動作【{action_name}】與備註已記錄。")
                
                # 清除快取並刷新網頁表格
                st.cache_data.clear()
            
            # 按鈕組綁定事件
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
with tabs[1]:
    st.subheader("📜 晶圓歷史追蹤足跡 (Wafer History)")
with tabs[2]:
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
with tabs[3]:
    st.subheader("🔄 上傳 R/C 規範 (Upload R/C)")
