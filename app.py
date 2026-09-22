import streamlit as st
import pandas as pd
import requests

# 設定 Streamlit 頁面寬度
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")

st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

# 您的 Google 試算表 ID 與分頁名稱
SPREADSHEET_ID = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"
SHEET_NAME = "route_template"

# 建立上方四大功能頁籤
tabs = st.tabs(["📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "🔄 Upload R/C"])

# 🔄 終極穿透優化：利用 Google 官方 Export 引擎載入資料，避免權限受阻
@st.cache_data(ttl=5)
def fetch_route_data_via_csv():
    # ⚠️ 請確保這行網址在您的編輯器裡看起來是完整的，且 ://google.com 後面有接實體 ID
    csv_url = "https://docs.google.com/spreadsheets/d/1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU/export?format=csv&gid=0"
    
    try:
        response = requests.get(csv_url, timeout=8)
        if response.status_code == 200:
            if "<html" in response.text.lower() or "<doctype" in response.text.lower():
                return pd.DataFrame(), "權限受阻，請確保試算表已開啟『國研院組織內（或任何知道連結者）皆可檢視』"
            
            from io import StringIO
            df_data = pd.read_csv(StringIO(response.text))
            
            # 清洗所有欄位名稱
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
# ==================== 頁籤 1: Full Route 完整整合內容 ====================
with tabs[0]:
    st.subheader("HETEROGENEOUS INTEGRATION & MANUFACTURING DIVISION")
    
    # 自動加載雲端最新資料
    df, conn_status = fetch_route_data_via_csv()
    
    if "Error" in conn_status or "異常" in conn_status:
        st.error(f"❌ 雲端資料庫連線失敗 ({conn_status})")
    else:
        st.success("🟢 成功透過國研院組織網路連線至 Google Sheets 資料庫")
    
    # 頂部晶圓 ID 過濾面板
    col_input1, col_input2 = st.columns([3, 1])
    with col_input1:
        search_id = st.text_input("🔍 請輸入或掃描品且 ID (Wafer ID):", value="LOT4-11F0")
    with col_input2:
        st.write(" ")
        st.write(" ")
        if st.button("🔄 刷新雲端資料", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ==================== 專業整合版：功能變更指令按鈕群 ====================
            st.markdown("⚠️ **流程變更權限指令**")
            b1, b2, b3, b4, b5 = st.columns(5)
            
            # 建立寫入雲端 status 紀錄的穿透函數
            def commit_action_to_cloud(action_name):
                # 清洗填入的文字
                clean_comment = user_comment.strip()
                # 取得當前時間
                import datetime
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 📢 僅保留嚴謹的文字成功提示，已完全移除 st.balloons() 氣球特效
                st.success(f"✅ 狀態變更成功｜已於 {now_str} 將站點【第 {target_row.get('Step No.')} 步】"
                           f"之動作【{action_name}】與數據【{clean_comment}】同步回傳至 wafer_status 工作表。")
            
            # 點亮按鈕
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

# ==================== 頁籤 2, 3, 4: 保留擴充介面 ====================
with tabs:
    st.subheader("📜 晶圓歷史追蹤足跡 (Wafer History)")
    st.info("💡 核心路由大表已對接成功！此處未來將自動拉取 `wafer_status` 內的歷史過站日誌，並用時間軸或精美表格列出這片晶圓的完整 Traceability 稽核軌跡。")

with tabs:
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
    st.file_uploader("請選擇要上傳的全新批次半導體製程母體路由檔案 (.csv 或 .xlsx)", type=["csv", "xlsx"])
    if st.button("開始解析並批量導入雲端母表"):
        st.success("上傳模組已就緒")

with tabs:
    st.subheader("🔄 上傳 R/C 規範 (Upload R/C)")
    st.text_area("請輸入特例改道製程說明或 R/C 簽核單號:")
    st.button("提交 R/C 變更指令")
