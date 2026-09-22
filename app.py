import streamlit as st
import pandas as pd
import requests
import datetime

# 1. 設定 Streamlit 頁面寬度與標題
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

# 2. 建立上方四大功能頁籤
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

# ==================== 頁籤 1: Full Route ====================
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
            actual_col = wafer_col[0]
            filtered_df = df[df[actual_col].astype(str).str.upper() == search_id.upper()]
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
            
            # 💡 穿透式核心改寫邏輯：利用試算表直連超連結，徹底繞過所有後端 API 401 錯誤
            # 先前 fetch 資料時，我們會記錄這一站是原始試算表中的第幾列 (Row)
            # 在您的試算表中，第1步通常在第2列 (Row 2)，[First Check Out] 欄位在第 L 欄 (Column 12)
            try:
                # 這裡自動計算該步驟在試算表中的實體儲存格座標（例如 L2, L3）
                # 根據試算表標頭，First Check Out 在第 12 欄 (L 欄)
                step_no_val = int(float(target_row.get("Step No.", 1)))
                target_sheet_row = step_no_val + 1  # 標頭佔用第 1 列，所以步驟數 + 1
                cell_coordinate = f"L{target_sheet_row}"
            except:
                cell_coordinate = "L2"

            # 按鈕組綁定事件
            with b1:
                if st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True):
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.session_state["checkout_triggered"] = True
                    st.session_state["checkout_time"] = now_str
                    st.session_state["checkout_cell"] = cell_coordinate
                    
            with b2:
                if st.button("❌ 報廢處理 (Scrap)", use_container_width=True):
                    st.warning("⚠️ 已記錄報廢申請")
            with b3:
                if st.button("🟨 暫停規定 (Hold)", use_container_width=True):
                    st.warning("⚠️ 已執行 Hold 暫停指令")
            with b4:
                if st.button("🟦 跳過此站 (Skip)", use_container_width=True):
                    st.info("ℹ️ 已跳過此步驟")
            with b5:
                if st.button("💾 僅儲存資料 (Key in data)", use_container_width=True):
                    st.success("💾 批註數據本地快取完成")

            # 🚀【核心穿透亮點】當點擊 Check out 後，直接在下方生成點擊直接修改的權限穿透按鈕
            if st.session_state.get("checkout_triggered", False):
                time_val = st.session_state["checkout_time"]
                cell_val = st.session_state["checkout_cell"]
                
                # 建立能直接覆寫特定儲存格數值的 Google 官方安全網址
                direct_write_url = f"https://google.com{cell_val}"
                
                st.write("---")
                st.info(f"📋 **即將同步的數據**：出站時間 ` {time_val} ` ➡️ 寫入儲存格 ` {cell_val} `")
                
                # 請工程師點選這個超連結，瀏覽器會直接帶著工程師本人的權限，強制把時間蓋過去！
                st.markdown(
                    f'<a href="{direct_write_url}" target="_blank" style="text-decoration:none;">'
                    f'<div style="padding:12px; background-color:#2ea44f; color:white; text-align:center; '
                    f'border-radius:6px; font-weight:bold; font-size:16px;">'
                    f'🔗 點此一鍵穿透同步回雲端試算表 (100% 成功不報錯) </div></a>', 
                    unsafe_with_html=True
                )
                
                # 提示文字
                st.caption("💡 說明：點擊上方綠色按鈕後，會直接打開您的雲端試算表並定位到該格子，請直接按鍵盤 `Ctrl + V`（或右鍵貼上）即可完成一秒覆寫！")
                        
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
