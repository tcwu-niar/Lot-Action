import streamlit as st
import pandas as pd
import requests
import datetime
import time      
import re

# =========================================================================
# 1. 系統全域基礎配置與資料載入
# =========================================================================
st.set_page_config(layout="wide", page_title="TSRI Lot Tracing System")
st.title("🏭 晶圓生產路由與狀態追蹤系統 (TSRI Lot Tracing System)")

MY_ORGANIZATION_GAS_URL = "https://script.google.com/macros/s/AKfycbx9pptKpV0dUDtGifGCbQnO33d42eUbbODnjVq_g4yitOviXtq6_8TdMo7VT7HL9dC-6w/exec"
SPREADSHEET_ID = "1HIcyPgjoHWA3Wgj8gohyEN2s-kF5A6OGEWuR0wDqULU"

@st.cache_data(ttl=15)
def fetch_route_data_via_csv(sheet_name="route_template"):
    if sheet_name == "route_template":
        # 🎯 請將 123456789 替換成您在網址列看到的真實 gid 數字！
        csv_url = "https://docs.google.com/spreadsheets/d/1HIcyPgjoHWA3Wgj8gohyEN2s-kF5A6OGEWuR0wDqULU/export?format=csv&gid=0"
    else:
        csv_url = f"https://docs.google.com/spreadsheets/d/1HIcyPgjoHWA3Wgj8gohyEN2s-kF5A6OGEWuR0wDqULU/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        
    try:
        response = requests.get(csv_url, timeout=8)
        if response.status_code == 200:
            if "<html" in response.text.lower() or "<doctype" in response.text.lower():
                return pd.DataFrame(), "權限受阻，請確保試算表已開啟連結共用"
            from io import StringIO
            df_data = pd.read_csv(StringIO(response.text))
            df_data.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df_data.columns]
            df_data = df_data.fillna("")
            for col in df_data.columns:
                df_data[col] = df_data[col].astype(str).str.strip()
                df_data[col] = df_data[col].replace({"nan": "", "NaN": "", "None": ""})
            return df_data, "Connected"
        else:
            return pd.DataFrame(), f"HTTP {response.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

# =========================================================================
# 2. 🎯 將所有彈出視窗定義在全域 (解決 Streamlit 作用域報錯)
# =========================================================================

# 🎯 升級版的 Ongoing Wafer 專屬填寫視窗 (整合所有編輯與動作功能)
@st.dialog("🚀 填寫站點資料與執行動作", width="large")
def show_ongoing_action_dialog(tw_id, ts_no, target_row_dict, avail_steps):
    st.markdown(f"**晶圓 ID:** `{tw_id}` | **當前站點:** 第 `{ts_no}` 步")
    
    st.markdown("✏️ **本站參數快速修改區（若不需變更請保持預設）**")
    c1, c2, c3 = st.columns(3)
    with c1: edit_tool = st.text_input("🔧 變更製程機台:", value=target_row_dict.get("Process Tool", ""))
    with c2: edit_recipe = st.text_input("🧪 變更機台配方:", value=target_row_dict.get("Recipe", ""))
    with c3: edit_cp = st.text_input("🎯 變更檢驗點:", value=target_row_dict.get("Check point", ""))
    
    st.markdown("📝 **批註 / 機台數據回填 (Result Data / Comments):**")
    spc_data = st.text_input("請在此輸入過站紀錄 (將填入 SPC data 欄位)...")
    
    st.markdown("📸 **檢驗結果圖片上傳 (Result 欄位):**")
    result_image = st.file_uploader("上傳機台截圖或顯微鏡照片 (支援 png/jpg)", type=["png", "jpg", "jpeg"])
    
    current_comment = str(target_row_dict.get("Comments", "")).strip() or str(target_row_dict.get("備註", "")).strip() or "暫無紀錄"
    st.markdown(f"ℹ️ **目前此站點之歷史批註：** `{current_comment}`")
    
    st.markdown("---")
    st.markdown("⚠️ **選擇執行指令並送出**")
    
    action_type = st.radio("流程變更選項:", [
        "🟢 正常出站 (Check out)", 
        "💾 僅儲存修改參數 (Save Data)", 
        "🟦 跳過此站 (Skip)", 
        "🟨 設定暫停 (Hold)", 
        "📦 入庫隱藏 (Bank)", 
        "❌ 報廢處理 (Scrap)"
    ], horizontal=True)
    
    jump_target, comment = None, ""
    
    if "Skip" in action_type:
        jump_target = st.selectbox("跳至步驟：", options=avail_steps)
        comment = st.text_input("請輸入跳站原因：")
    elif "Hold" in action_type:
        comment = st.text_input("請輸入暫停原因：")
    elif "Bank" in action_type:
        comment = st.text_input("請輸入入庫原因：")
    elif "Scrap" in action_type:
        comment = st.text_input("請輸入報廢原因：")
        
    if st.button("🚀 確認並寫入雲端", type="primary", use_container_width=True):
        if "Check out" in action_type: action_name = "Check out"
        elif "Save Data" in action_type: action_name = "Key in data"
        elif "Skip" in action_type: action_name = "Skip"
        elif "Hold" in action_type: action_name = "Hold"
        elif "Bank" in action_type: action_name = "Bank"
        elif "Scrap" in action_type: action_name = "Scrap"
        
        st.session_state.ongoing_action = {
            "name": action_name, 
            "w_id": tw_id, 
            "s_no": ts_no, 
            "spc": spc_data, 
            "img": result_image, 
            "jump_step": jump_target, 
            "comment": comment,
            "tool": edit_tool,
            "recipe": edit_recipe,
            "cp": edit_cp,
            "orig_row": target_row_dict
        }
        st.rerun()

@st.dialog("📋 輸入 Hold Note")
def show_hold_dialog(tw_id, ts_no):
    r = st.text_input("暫停原因：")
    c_ok, c_cancel = st.columns(2)
    if c_ok.button("👍 確認", type="primary", use_container_width=True): 
        st.session_state.pending_action = {"name": "Hold", "w_id": tw_id, "s_no": ts_no, "comment": f"[HOLD] {r.strip()}"}
        st.rerun()
    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

@st.dialog("🟦 輸入解 Hold 原因")
def show_unhold_dialog(tw_id, ts_no):
    r = st.text_input("解 Hold 原因：")
    c_ok, c_cancel = st.columns(2)
    if c_ok.button("👍 確認", type="primary", use_container_width=True): 
        st.session_state.pending_action = {"name": "Unhold", "w_id": tw_id, "s_no": ts_no, "comment": f"[UNHOLD] {r.strip()}"}
        st.rerun()
    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

@st.dialog("❌ 輸入報廢原因")
def show_scrap_dialog(tw_id, ts_no):
    r = st.text_input("報廢原因：")
    c_ok, c_cancel = st.columns(2)
    if c_ok.button("👍 確認報廢", type="primary", use_container_width=True): 
        st.session_state.pending_action = {"name": "Scrap", "w_id": tw_id, "s_no": ts_no, "comment": f"[SCRAP] {r.strip()}"}
        st.rerun()
    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

@st.dialog("🔄 輸入解除報廢原因")
def show_unscrap_dialog(tw_id, ts_no):
    r = st.text_input("復原原因：")
    c_ok, c_cancel = st.columns(2)
    if c_ok.button("👍 確認復原", type="primary", use_container_width=True): 
        st.session_state.pending_action = {"name": "Unscrap", "w_id": tw_id, "s_no": ts_no, "comment": f"[UNSCRAP] {r.strip()}"}
        st.rerun()
    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

@st.dialog("📦 晶圓入庫 / 暫停執行 (Bank)")
def show_bank_dialog(tw_id, ts_no):
    st.write(f"將晶圓 `{tw_id}` 標記為 **Bank (入庫/暫時不執行)**。")
    st.info("💡 入庫後，此晶圓將暫時從 Tab 4 (Wafer Overview) 總表中隱藏。")
    r = st.text_input("請輸入 Bank 原因：", placeholder="例如: 尚未 Kick off, 暫存等待料件...")
    c_ok, c_cancel = st.columns(2)
    if c_ok.button("👍 確認入庫", type="primary", use_container_width=True): 
        st.session_state.pending_action = {"name": "Bank", "w_id": tw_id, "s_no": ts_no, "comment": f"[BANK] {r.strip()}"}
        st.rerun()
    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

@st.dialog("🚀 晶圓出庫 / 開始執行 (Kick off)")
def show_bankout_dialog(tw_id, ts_no):
    st.write(f"將晶圓 `{tw_id}` **出庫 (Kick off)** 並恢復執行。")
    st.info("💡 恢復後，此晶圓將重新出現在 Wafer Overview 總表中。")
    r = st.text_input("請輸入 Kick off 原因 (選填)：", placeholder="例如: 開始投片...")
    c_ok, c_cancel = st.columns(2)
    if c_ok.button("👍 確認開始", type="primary", use_container_width=True): 
        st.session_state.pending_action = {"name": "Kick off", "w_id": tw_id, "s_no": ts_no, "comment": f"[KICK OFF] {r.strip()}"}
        st.rerun()
    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

@st.dialog("⏭️ 晶圓跳站")
def show_skip_dialog(tw_id, ts_no, avail_steps):
    default_idx = avail_steps.index(ts_no) if ts_no in avail_steps else 0
    j_target = st.selectbox("跳至：", options=avail_steps, index=default_idx)
    r = st.text_input("跳站原因：")
    c_ok, c_cancel = st.columns(2)
    if c_ok.button("👍 確認跳站", type="primary", use_container_width=True):
        st.session_state.pending_action = {"name": "Skip", "w_id": tw_id, "s_no": ts_no, "comment": f"[JUMP TO Step {j_target}] {r.strip()}", "jump_step": j_target}
        st.rerun()
    if c_cancel.button("❌ 取消", use_container_width=True): st.rerun()

all_tabs = st.tabs(["🔍 Ongoing Wafer", "📋 Full Route", "📜 Wafer History", "📤 Upload New Wafer", "📦 Bank Wafers", "📊 Wafer Overview"])

# =========================================================================
# 🔍 頁籤 1: Ongoing Wafer 
# =========================================================================
with all_tabs[0]:
    st.subheader("🔍 當前站點設備與配方資訊 (Ongoing Wafer)")
    
    # 🎯 處理 Ongoing Wafer 專屬的動作指令寫入
    if "ongoing_action" in st.session_state:
        pa = st.session_state.ongoing_action
        del st.session_state["ongoing_action"]
        
        tw_tz = datetime.timezone(datetime.timedelta(hours=8))
        now_str = datetime.datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        urls_to_send = []
        
        enc_w_id = requests.utils.quote(str(pa["w_id"]))
        enc_s_no = requests.utils.quote(str(pa["s_no"]))
        
        final_result_link = ""
        if pa["img"] is not None:
            with st.spinner("⏳ 正在將圖片上傳至雲端..."):
                try:
                    payload = {"key": "6d207e02198a847aa98d0a2a901485a5", "action": "upload", "format": "json"}
                    files = {"source": pa["img"].getvalue()}
                    res = requests.post("https://freeimage.host/api/1/upload", data=payload, files=files)
                    if res.status_code == 200:
                        final_result_link = res.json()["image"]["url"]
                    else:
                        st.warning(f"⚠️ 圖片上傳失敗 (狀態碼: {res.status_code})")
                except Exception as e:
                    st.error(f"圖片上傳連線錯誤: {e}")
                    
        if str(pa["spc"]).strip():
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name=SPC%20data&new_value={requests.utils.quote(str(pa['spc']).strip())}")
        if final_result_link:
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name=Result&new_value={requests.utils.quote(final_result_link)}")
            
        fields = {"Process Tool": pa["tool"], "Recipe": pa["recipe"], "Check point": pa["cp"]}
        for f_name, f_val in fields.items():
            orig_val = str(pa["orig_row"].get(f_name, "")).strip()
            if str(f_val).strip() != orig_val:
                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name={requests.utils.quote(f_name)}&new_value={requests.utils.quote(str(f_val).strip())}")
                
        enc_time = requests.utils.quote(now_str)
        enc_comment = requests.utils.quote(pa.get("comment", ""))
        
        act = pa["name"]
        if act == "Check out": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Check out&comment={enc_comment}&time={enc_time}")
        elif act == "Scrap": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Scrap&comment={enc_comment}&time={enc_time}")
        elif act == "Hold": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Hold&comment={enc_comment}&time={enc_time}")
        elif act == "Bank": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Bank&comment={enc_comment}&time={enc_time}")
        elif act == "Skip":
            enc_target = requests.utils.quote(str(pa["jump_step"]))
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Skip&comment={enc_comment}&time={enc_time}&target_step={enc_target}")
            
        if urls_to_send:
            with st.spinner(f"🚀 正在將資料與 {act} 指令同步至雲端..."):
                has_error = False
                session = requests.Session()
                adapter = requests.adapters.HTTPAdapter(max_retries=0) 
                session.mount('https://', adapter)
                
                for url in set(urls_to_send):
                    try:
                        res = session.get(url, timeout=12, allow_redirects=False)
                        if res.status_code not in [200, 302] and "Error" in res.text:
                            st.error(f"❌ 雲端拒絕寫入: {res.text}")
                            has_error = True
                    except:
                        pass
                if has_error:
                    time.sleep(3)
                else:
                    st.success("✅ 操作成功寫入！")
                    time.sleep(1.2)
                st.cache_data.clear()
                st.rerun()

    df_route, conn_status = fetch_route_data_via_csv("route_template")
    
    if not df_route.empty:
        wafer_col = next((c for c in df_route.columns if str(c).strip().lower() in ["wafer id", "id", "wafer"]), "Wafer ID")
        step_col = next((c for c in df_route.columns if str(c).strip().lower() in ["step", "step no.", "step no"]), "Step")
        owner_col = next((c for c in df_route.columns if "owner" in str(c).lower()), "Stage Owner")
        desc_col = next((c for c in df_route.columns if "description" in str(c).lower()), "Step description")
        fco_col = next((c for c in df_route.columns if "check out" in str(c).lower()), "Check out Time")
        tool_col = next((c for c in df_route.columns if "tool" in str(c).lower()), "Process Tool")
        recipe_col = next((c for c in df_route.columns if "recipe" in str(c).lower()), "Recipe")
        
        if wafer_col in df_route.columns:
            def get_lot_number(wid):
                import re
                match = re.search(r'lot(\d+)', str(wid).lower())
                return int(match.group(1)) if match else 999999
                
            df_route['_lot_num'] = df_route[wafer_col].apply(get_lot_number)
            df_route = df_route.sort_values(by=['_lot_num', wafer_col])
            
            wip_data_list = []

            for wid, w_group in df_route.groupby(wafer_col, sort=False):
                w_group = w_group.reset_index(drop=True)
                total_steps = len(w_group)
                has_scrap, is_banked = False, False
                wip_idx = total_steps
                active_row = None
                
                for idx, row in w_group.iterrows():
                    fco = str(row.get(fco_col, "")).strip().upper()
                    if fco == "SCRP":
                        has_scrap = True
                        wip_idx = idx
                        active_row = row
                        break
                        
                if not has_scrap:
                    for idx, row in w_group.iterrows():
                        fco = str(row.get(fco_col, "")).strip().upper()
                        if fco in ["", "NAN", "INPR", "HOLD", "BANK"]:
                            wip_idx = idx
                            active_row = row
                            if fco == "BANK":
                                is_banked = True
                            break
                
                if is_banked: continue
                if wip_idx == total_steps and not has_scrap: continue 
                
                if active_row is not None:
                    raw_step = str(active_row.get(step_col, "")).replace(".0", "").strip()
                    wip_step_no = str(wip_idx + 1) if raw_step in ["", "nan", "NaN", "None"] else raw_step
                    
                    s_owner = str(active_row.get(owner_col, ""))
                    s_desc = str(active_row.get(desc_col, ""))
                    s_tool = str(active_row.get(tool_col, active_row.get("Process Tool", "")))
                    s_recipe = str(active_row.get(recipe_col, active_row.get("Recipe", "")))
                    
                    wip_data_list.append({
                        "ID (Wafer)": wid,
                        "Step": f"{wip_step_no}/92",
                        "Stage Owner": s_owner,
                        "Step Description": s_desc,
                        "Process Tool": s_tool,
                        "Recipe": s_recipe,
                        "_raw_step": raw_step,
                        "_avail_steps": [str(x).strip() for x in w_group[step_col].tolist()],
                        "_row_dict": active_row.to_dict()
                    })
            
            if wip_data_list:
                st.markdown("💡 **點擊列表中的欲操作的資料列 (Row)，即可開啟該晶圓的資料填寫與動作面板。** (完全支援手機版操作)")
                
                df_wip = pd.DataFrame(wip_data_list)
                
                # 🎯 先選定要顯示的乾淨欄位
                display_df = df_wip[["ID (Wafer)", "Step", "Stage Owner", "Step Description", "Process Tool", "Recipe"]]
                
                # 🎯 再針對顯示用的 DataFrame 套用置中樣式 (解決先前的 TypeError 報錯)
                styled_df = display_df.style.set_properties(**{'text-align': 'center'})
                
                # 套用 Selection 事件，點擊 Row 即觸發彈出視窗
                selection = st.dataframe(
                    styled_df,
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row"
                )
                
                if selection and selection.get("selection", {}).get("rows"):
                    selected_idx = selection["selection"]["rows"][0]
                    selected_item = wip_data_list[selected_idx]
                    # 觸發彈出視窗
                    show_ongoing_action_dialog(
                        selected_item['ID (Wafer)'], 
                        selected_item['_raw_step'], 
                        selected_item['_row_dict'], 
                        selected_item['_avail_steps']
                    )
                    
            else:
                st.info("目前產線上沒有任何進行中的晶圓。")
        else:
            st.warning("⚠️ 母表中找不到 Wafer ID 欄位。")

# =========================================================================
# 📋 頁籤 2: Full Route 
# =========================================================================
with all_tabs[1]:  
    st.subheader("HETEROGENEOUS INTEGRATION & MANUFACTURING DIVISION")
    
    df, conn_status = fetch_route_data_via_csv("route_template")
    if "Error" in conn_status or "HTTP" in conn_status: st.error(f"❌ 雲端資料庫連線失敗 ({conn_status})")
    else: st.success("🟢 成功連結 Google Sheets 資料庫")
    
    col_input1, col_input2 = st.columns(2)
    with col_input1: search_id = st.text_input("🔍 請輸入或掃描晶圓 ID (Wafer ID):", value="LOT4-11F0", key="search_wafer_id")
    with col_input2:
        st.write(" "); st.write(" ")
        if st.button("🔄 刷新雲端資料", use_container_width=True, key="ta_refresh"):
            st.cache_data.clear(); st.rerun()

    st.markdown("🟢 *綠列代表在製中 (INPR)* | 🔴 *紅列代表已報廢 (SCRP)* | 🟡 *黃列代表已暫停 (HOLD)* | ⚪ *灰列代表因報廢已中斷鎖定*")
    
    if not df.empty:
        wafer_col_list = [c for c in df.columns if "Wafer" in c or "wafer" in c]
        if wafer_col_list:
            actual_string_col = wafer_col_list[0]
            filtered_df = df[df[actual_string_col].astype(str).str.upper() == search_id.upper()].copy()
        else: filtered_df = df.copy()

        if not filtered_df.empty:
            has_scrap_occurred, scrap_step_index = False, 9999
            for idx, row in filtered_df.reset_index(drop=True).iterrows():
                co_val = str(row.get("Check out Time", "")).strip().upper()
                if co_val == "SCRP":
                    has_scrap_occurred, scrap_step_index = True, idx
                    break
            
            wip_step_no, wip_row_idx = "9999", 9999
            fco_col = next((c for c in filtered_df.columns if "check out" in str(c).lower()), "Check out Time")
            step_col = next((c for c in filtered_df.columns if str(c).strip().lower() in ["step", "step no.", "step no"]), "Step")
            
            if not has_scrap_occurred:
                for idx, row in filtered_df.reset_index(drop=True).iterrows():
                    co_val = str(row.get(fco_col, "")).strip().upper()
                    if co_val in ["", "NAN", "INPR", "HOLD", "BANK"]:
                        wip_row_idx = idx
                        wip_step_no = str(row.get(step_col, "1"))
                        break
            
            display_df = filtered_df.copy().reset_index(drop=True)
            new_co_display = []
            for idx, r in display_df.iterrows():
                co_val = str(r.get(fco_col, "")).strip().upper()
                if co_val == "SCRP": new_co_display.append("SCRP")
                elif co_val == "HOLD": new_co_display.append("HOLD")
                elif co_val == "BANK": new_co_display.append("BANK")
                elif idx > scrap_step_index: new_co_display.append("") 
                elif idx == wip_row_idx: new_co_display.append("INPR")
                else: new_co_display.append(str(r.get(fco_col, ""))) 
            display_df[fco_col] = new_co_display

            def highlight_dynamic_rows(row):
                row_idx = row.name
                co_cell_string = str(row[fco_col]).strip().upper()
                if co_cell_string == "SCRP": return ['background-color: #f8d7da; font-weight: bold; color: #721c24;'] * len(row)
                elif co_cell_string == "HOLD": return ['background-color: #fff3cd; font-weight: bold; color: #856404;'] * len(row)
                elif co_cell_string == "BANK": return ['background-color: #d1ecf1; font-weight: bold; color: #0c5460;'] * len(row)
                elif row_idx > scrap_step_index: return ['background-color: #e2e3e5; font-weight: normal; color: #6c757d;'] * len(row)
                elif row_idx == wip_row_idx: return ['background-color: #c3e6cb; font-weight: bold; color: #155724;'] * len(row)
                return [''] * len(row)
            
            styled_df = display_df.style.apply(highlight_dynamic_rows, axis=1)
            selected_rows = st.dataframe(styled_df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            
            default_row_idx = 0
            step_list = [str(x).strip() for x in filtered_df[step_col].tolist()]
            if wip_step_no.strip() in step_list: default_row_idx = step_list.index(wip_step_no.strip())
            elif has_scrap_occurred: default_row_idx = scrap_step_index
            
            current_idx = selected_rows["selection"]["rows"][0] if selected_rows and selected_rows.get("selection", {}).get("rows") else default_row_idx
            target_row = filtered_df.iloc[current_idx]
            
            st.write("---")
            st.subheader("⚙️ 當前過站與動態編輯面板 (Current Stage Action Panel)")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("晶圓編號 (Wafer ID)", str(target_row.get(actual_string_col, "N/A")))
            c2.metric("選定步驟 (Step)", f"第 {target_row.get(step_col, 'N/A')} 步")
            c3.metric("負責模組 (Module)", str(target_row.get("Module", "N/A")))
            c4.metric("客戶團隊 (Customer)", str(target_row.get("Customer", "N/A")))
            
            current_status = str(target_row.get(fco_col, "")).strip().upper()
            is_currently_held = (current_status == "HOLD")

            if has_scrap_occurred and current_idx > scrap_step_index:
                st.error(f"🚫 流程已中斷：該晶圓已於第 {filtered_df.iloc[scrap_step_index].get(step_col)} 步報廢。後續步驟已被封鎖！")
            elif is_currently_held: st.warning(f"⚠️ 警告：目前此站點處於 ［HOLD 暫停製程］ 狀態。在解 Hold 前無法執行過站。")
            
            st.info(f"💡 **目前站點描述**：{target_row.get('Step Description', target_row.get('Step description', 'N/A'))}")
            
            st.markdown("✏️ **本站參數快速修改區（若不需變更請保持預設）**")
            edit_col1, edit_col2, edit_col3 = st.columns(3)
            with edit_col1: edit_tool = st.text_input("🔧 變更製程機台:", value=str(target_row.get("Process Tool", "")))
            with edit_col2: edit_recipe = st.text_input("🧪 變更機台配方:", value=str(target_row.get("Recipe", "")))
            with edit_col3: edit_cp = st.text_input("🎯 變更檢驗點:", value=str(target_row.get("Check point", "")))
            
            w_id = str(target_row.get(actual_string_col, "")).strip()
            s_no = str(target_row.get(step_col, "")).replace(".0", "").strip()

            st.markdown("📝 **批註 / 機台數據回填 (SPC Data / Comments):**")
            user_comment = st.text_input("請在此輸入過站紀錄...", key="user_comment_input")
            
            st.markdown("📸 **檢驗結果圖片上傳 (Result 欄位):**")
            result_image = st.file_uploader("上傳機台截圖或顯微鏡照片 (支援 png/jpg)", type=["png", "jpg", "jpeg"], key=f"img_{w_id}_{s_no}")
            
            current_comment = str(target_row.get("Comments", "")).strip() or str(target_row.get("備註", "")).strip() or "暫無紀錄"
            current_hold_note = str(target_row.get("Hold Note", "")).strip() or "無"
            
            st.markdown(f"ℹ️ **目前此站點之歷史批註：** `{current_comment}`")
            if current_hold_note != "無" or is_currently_held: st.markdown(f"🛑 **目前此站點之 Hold Note：** `{current_hold_note}`")

            st.markdown("⚠️ **流程變更權限指令**")
            b1, b2, b3, b4, b5, b6 = st.columns(6)

            def execute_stage_action(action_name, target_w_id, target_s_no, custom_comment=None, target_jump_step=None):
                tw_tz = datetime.timezone(datetime.timedelta(hours=8))
                now_str = datetime.datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
                urls_to_send = []
                
                enc_w_id = requests.utils.quote(str(target_w_id))
                enc_s_no = requests.utils.quote(str(target_s_no))
                
                final_result_link = str(target_row.get("Result", "")).strip()
                if result_image is not None and action_name in ["Check out", "Key in data"]:
                    with st.spinner("⏳ 正在將圖片上傳至雲端..."):
                        try:
                            payload = {"key": "6d207e02198a847aa98d0a2a901485a5", "action": "upload", "format": "json"}
                            files = {"source": result_image.getvalue()}
                            res = requests.post("https://freeimage.host/api/1/upload", data=payload, files=files)
                            if res.status_code == 200:
                                final_result_link = res.json()["image"]["url"]
                            else:
                                st.warning(f"⚠️ 圖片上傳失敗 (狀態碼: {res.status_code})，僅儲存文字紀錄。")
                        except Exception as e:
                            st.error(f"圖片上傳連線錯誤: {e}")

                if action_name in ["Check out", "Scrap", "Key in data"]:
                    fields = {"Process Tool": edit_tool, "Recipe": edit_recipe, "Check point": edit_cp}
                    if final_result_link:
                        fields["Result"] = final_result_link 
                        
                    for f_name, f_val in fields.items():
                        if str(f_val).strip() != str(target_row.get(f_name, "")).strip():
                            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name={requests.utils.quote(f_name)}&new_value={requests.utils.quote(str(f_val).strip())}")
                
                final_comment = custom_comment if custom_comment is not None else user_comment.strip()
                enc_comment = requests.utils.quote(final_comment)
                enc_time = requests.utils.quote(now_str)
                
                if action_name == "Check out": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Check out&comment={enc_comment}&time={enc_time}")
                elif action_name == "Scrap": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Scrap&comment={enc_comment}&time={enc_time}")
                elif action_name == "Unscrap": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Unscrap&comment={enc_comment}&time={enc_time}")
                elif action_name == "Hold": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Hold&comment={enc_comment}&time={enc_time}")
                elif action_name == "Unhold": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Unhold&comment={enc_comment}&time={enc_time}")
                elif action_name == "Bank": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Bank&comment={enc_comment}&time={enc_time}")
                elif action_name == "Kick off": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Kick off&comment={enc_comment}&time={enc_time}")
                elif action_name == "Skip":
                    enc_target_step = requests.utils.quote(str(target_jump_step))
                    urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Skip&comment={enc_comment}&time={enc_time}&target_step={enc_target_step}")
                
                with st.spinner(f"🚀 正在同步 {action_name} 指令至雲端..."):
                    has_error = False
                    session = requests.Session()
                    adapter = requests.adapters.HTTPAdapter(max_retries=0) 
                    session.mount('https://', adapter)
                    session.mount('http://', adapter)
                    unique_urls = list(set(urls_to_send))
                    
                    for url in unique_urls:
                        try:
                            res = session.get(url, timeout=12, allow_redirects=False)
                            if res.status_code not in [200, 302] and "Error" in res.text:
                                st.error(f"❌ 雲端拒絕寫入: {res.text}")
                                has_error = True
                        except requests.exceptions.Timeout:
                            pass
                        except Exception as e:
                            pass
                            
                    if has_error:
                        time.sleep(4)
                        st.rerun()
                        return
                
                st.success(f"✅ {action_name} 動作已成功寫入！")
                time.sleep(1.2)
                st.cache_data.clear()
                st.rerun()

            is_currently_scrapped = (current_status == "SCRP")
            is_currently_banked = (current_status == "BANK")

            is_btn_disabled = True if has_scrap_occurred and current_idx > scrap_step_index else False
            is_wip_locked = True if is_currently_held or is_currently_banked else is_btn_disabled

            with b1:
                if st.button("🟢 正常出站 (Check out)", type="primary", use_container_width=True, disabled=is_wip_locked): execute_stage_action("Check out", w_id, s_no)
            with b2:
                if is_currently_scrapped:
                    if st.button("🔄 復原報廢 (Unscrap)", type="primary", use_container_width=True, disabled=is_btn_disabled): show_unscrap_dialog(w_id, s_no)
                else:
                    if st.button("❌ 報廢處理 (Scrap)", type="secondary", use_container_width=True, disabled=is_wip_locked): show_scrap_dialog(w_id, s_no)
            with b3: 
                if is_currently_held:
                    if st.button("🟦 解除暫停 (Release Hold)", type="primary", use_container_width=True, disabled=is_btn_disabled): show_unhold_dialog(w_id, s_no)
                else:
                    if st.button("🟨 設定暫停 (Hold)", use_container_width=True, disabled=is_wip_locked): show_hold_dialog(w_id, s_no)
            with b4: 
                if st.button("🟦 跳過此站 (Skip)", use_container_width=True, disabled=is_wip_locked): show_skip_dialog(w_id, s_no, step_list)
            with b5:
                if st.button("💾 儲存修改參數", use_container_width=True, disabled=is_wip_locked): execute_stage_action("Key in data", w_id, s_no)
            with b6:
                if is_currently_banked:
                    if st.button("🚀 Kick off (出庫)", type="primary", use_container_width=True, disabled=is_btn_disabled): show_bankout_dialog(w_id, s_no)
                else:
                    if st.button("📦 Bank (入庫隱藏)", use_container_width=True, disabled=is_wip_locked): show_bank_dialog(w_id, s_no)
            
            if "pending_action" in st.session_state:
                pa = st.session_state.pending_action
                del st.session_state["pending_action"]
                execute_stage_action(pa["name"], pa["w_id"], pa["s_no"], custom_comment=pa.get("comment"), target_jump_step=pa.get("jump_step"))

# =========================================================================
# 📜 頁籤 3: Wafer History 
# =========================================================================
with all_tabs[2]:
    st.subheader("📜 晶圓歷史過站追蹤足跡 (Wafer History 日誌)")
    df_route, route_status = fetch_route_data_via_csv("route_template")
    df_logs, log_status = fetch_route_data_via_csv("wafer_status")
    
    if 'search_id' in locals() and search_id and not df_route.empty and not df_logs.empty:
        wafer_col_list = [c for c in df_route.columns if "Wafer" in c or "wafer" in c]
        if wafer_col_list:
            actual_string_col = wafer_col_list[0]
            filtered_route = df_route[df_route[actual_string_col].astype(str).str.upper() == search_id.upper()]
        else:
            filtered_route = df_route
            
        if not filtered_route.empty:
            st.markdown(f"📊 晶圓 **{search_id}** 的母表生產路由全貌：")
            display_route = filtered_route.copy().reset_index(drop=True)
            
            if "Step" in display_route.columns:
                display_route["Step"] = display_route["Step"].astype(str).str.replace(".0", "", regex=False)
            
            selected_route_row = st.dataframe(
                display_route, 
                use_container_width=True, 
                hide_index=True, 
                on_select="rerun", 
                selection_mode="single-row", 
                key="history_route_table",
                column_config={
                    "Result": st.column_config.ImageColumn("Result (預覽圖片)", help="上傳的檢驗圖片")
                }
            )
            
            if selected_route_row and selected_route_row.get("selection", {}).get("rows"):
                selected_idx = selected_route_row["selection"]["rows"][0]
                target_step_no = str(display_route.iloc[selected_idx].get("Step", "")).replace(".0", "").strip()
                
                st.markdown("---")
                st.markdown(f"### 🛑 第 {target_step_no} 步 - 歷史動作完整紀錄 (Action History)")
                
                log_wafer_col = [c for c in df_logs.columns if "Wafer" in c or "晶圓" in c][0]
                clean_log_steps = df_logs["Step"].astype(str).str.replace(".0", "", regex=False).str.strip()
                step_logs = df_logs[(df_logs[log_wafer_col].astype(str).str.upper() == search_id.upper()) & (clean_log_steps == target_step_no)]
                
                mother_result_val = str(display_route.iloc[selected_idx].get("Result", "")).strip()
                result_html = ""
                if mother_result_val.startswith("http"):
                    result_html = f'<a href="{mother_result_val}" target="_blank"><img src="{mother_result_val}" style="max-height: 80px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); cursor: zoom-in;"></a>'
                else:
                    result_html = mother_result_val

                if not step_logs.empty:
                    html_parts = ['<div style="font-size: 12pt;"><table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">']
                    html_parts.append('<tr style="background-color: #f8f9fa; color: #333;"><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 10%;">動作 (Action)</th><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 20%;">日期與時間</th><th style="padding: 10px; border: 1px solid #ddd; text-align: left; width: 25%;">Hold Note (暫停原因)</th><th style="padding: 10px; border: 1px solid #ddd; text-align: left; width: 25%;">SPC data (過站備註)</th><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 20%;">Result (檢驗圖片)</th></tr>')
                    
                    for _, log_row in step_logs.iterrows():
                        action_val = str(log_row.get("Action", "")).strip()
                        time_val = str(log_row.get("Check out Time", "")).strip()
                        hold_note_val = str(log_row.get("Hold Note", "")).strip()
                        spc_val = str(log_row.get("SPC data", "")).strip()
                        
                        bg_color = "#fff3cd" if action_val.upper() == "HOLD" else "#ffffff"
                        text_color = "#d9534f" if action_val.upper() == "HOLD" else "#000000"
                        
                        html_parts.append(f'<tr style="background-color: {bg_color};"><td style="padding: 10px; border: 1px solid #ddd; text-align: center; font-weight: bold;">{action_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{time_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: left; color: {text_color}; font-weight: bold;">{hold_note_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: left;">{spc_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{result_html}</td></tr>')
                    html_parts.append('</table></div>')
                    st.markdown("".join(html_parts), unsafe_allow_html=True)
                
                else:
                    st.info(f"✅ 該晶圓的第 {target_step_no} 步目前無任何歷史紀錄。")
                    if mother_result_val.startswith("http"):
                        st.markdown("---")
                        st.markdown("📸 **目前已上傳的檢驗圖片：**")
                        st.markdown(f"<a href='{mother_result_val}' target='_blank'><img src='{mother_result_val}' style='max-height: 250px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); cursor: zoom-in;'></a>", unsafe_allow_html=True)
                    elif mother_result_val:
                        st.markdown(f"**📝 目前已儲存的 Result 紀錄：** {mother_result_val}")
    else:
        st.info("請先於 Full Route 頁籤搜尋並選擇特定站點。")

# =========================================================================
# 📤 頁籤 4: Upload New Wafer 
# =========================================================================
with all_tabs[3]:
    st.subheader("📤 上傳新晶圓路由母表 (Upload New Wafer)")
    uploaded_file = st.file_uploader("選擇全新批次生產路由檔案 (.csv 或 .xlsx)", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            df_upload = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            df_upload = df_upload.fillna("")
            
            upload_wafer_col = next((c for c in df_upload.columns if str(c).strip().lower() in ["wafer id", "id", "wafer"]), "Wafer ID")
            upload_fco_col = next((c for c in df_upload.columns if "check out" in str(c).lower()), "Check out Time")
            
            if upload_wafer_col in df_upload.columns:
                if upload_fco_col not in df_upload.columns:
                    df_upload["Check out Time"] = ""
                    upload_fco_col = "Check out Time"
                for wid, group in df_upload.groupby(upload_wafer_col, sort=False):
                    if not group.empty:
                        df_upload.at[group.index[0], upload_fco_col] = "BANK"
            
            edited_df = st.data_editor(df_upload, use_container_width=True, num_rows="dynamic", key="wafer_upload_editor")
            if st.button("🚀 確認資料無誤，開始批量寫入雲端母表", type="primary", use_container_width=True):
                with st.spinner("⏳ 正在寫入..."):
                    payload = {"action": "bulk_upload", "data": edited_df.to_dict(orient="records")}
                    try:
                        res = requests.post(MY_ORGANIZATION_GAS_URL, json=payload, timeout=300)
                        if res.status_code == 200 and "Success" in res.text:
                            st.success("✅ 批量寫入成功！全新晶圓已入庫。")
                            time.sleep(2)
                            st.cache_data.clear()
                            st.rerun()
                        else: st.error(f"❌ 寫入失敗：{res.text}")
                    except Exception as e: st.error(f"❌ 網路發送失敗: {e}")
        except Exception as e:
            st.error(f"❌ 檔案解析失敗: {str(e)}")

# =========================================================================
# 📦 頁籤 5: Bank Wafers 
# =========================================================================
with all_tabs[4]:
    st.subheader("📦 入庫晶圓清單 (Banked Wafers)")
    st.markdown("集中顯示目前被標記為 Bank (暫停執行/未下線) 的所有晶圓。**勾選左側框框並點擊下方按鈕，即可批次 Kick off (下貨出庫)**。")

    df_route_bank, conn_status_bank = fetch_route_data_via_csv("route_template")
    
    if not df_route_bank.empty:
        wafer_col = next((c for c in df_route_bank.columns if str(c).strip().lower() in ["wafer id", "id", "wafer"]), "Wafer ID")
        step_col = next((c for c in df_route_bank.columns if str(c).strip().lower() in ["step", "step no.", "step no"]), "Step")
        shuttle_col = next((c for c in df_route_bank.columns if "shuttle" in str(c).lower()), "Shuttle Name")
        owner_col = next((c for c in df_route_bank.columns if "owner" in str(c).lower()), "Stage Owner")
        team_col = next((c for c in df_route_bank.columns if "customer" in str(c).lower()), "Customer")
        fco_col = next((c for c in df_route_bank.columns if "check out" in str(c).lower()), "Check out Time")
        comment_col = next((c for c in df_route_bank.columns if str(c).strip().lower() in ["comments", "備註", "comment"]), "Comments")
        
        if wafer_col in df_route_bank.columns:
            banked_wafers = []
            
            for wid, w_group in df_route_bank.groupby(wafer_col, sort=False):
                w_group = w_group.reset_index(drop=True)
                has_scrap = False
                is_banked = False
                bank_step_no, bank_comment = "", ""
                
                for idx, row in w_group.iterrows():
                    fco = str(row.get(fco_col, "")).strip().upper()
                    if fco == "SCRP":
                        has_scrap = True
                        break
                        
                if not has_scrap:
                    for idx, row in w_group.iterrows():
                        fco = str(row.get(fco_col, "")).strip().upper()
                        if fco in ["", "NAN", "INPR", "HOLD", "BANK"]:
                            if fco == "BANK":
                                is_banked = True
                                bank_step_no = str(row.get(step_col, "")).replace(".0", "")
                                bank_comment = str(row.get(comment_col, ""))
                            break
                            
                if is_banked:
                    first_row = w_group.iloc[0]
                    banked_wafers.append({
                        "🚀 選取": False, 
                        "Shuttle Name": str(first_row.get(shuttle_col, "")), 
                        "Owner": str(first_row.get(owner_col, "")),
                        "團隊": str(first_row.get(team_col, "")), 
                        "ID (Wafer)": str(wid).strip(),
                        "Bank 停留站點": f"第 {bank_step_no} 步", 
                        "_Raw_Step": bank_step_no, 
                        "備註": bank_comment
                    })
                    
            if banked_wafers:
                df_bank = pd.DataFrame(banked_wafers)
                edited_bank_df = st.data_editor(
                    df_bank.drop(columns=["_Raw_Step"]), 
                    hide_index=True, 
                    use_container_width=True, 
                    disabled=["Shuttle Name", "Owner", "團隊", "ID (Wafer)", "Bank 停留站點", "備註"]
                )
                
                selected_flags = edited_bank_df["🚀 選取"].tolist()
                selected_wids = [banked_wafers[i]["ID (Wafer)"] for i, flag in enumerate(selected_flags) if flag]
                selected_steps = [banked_wafers[i]["_Raw_Step"] for i, flag in enumerate(selected_flags) if flag]
                
                if selected_wids:
                    st.markdown("---")
                    if st.button(f"🚀 批次執行 Kick off", type="primary"):
                        urls_to_send = []
                        tw_tz = datetime.timezone(datetime.timedelta(hours=8))
                        now_str = datetime.datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
                        enc_time = requests.utils.quote(now_str)
                        enc_comment = requests.utils.quote("[KICK OFF] 從 Bank Wafers 批次出庫下線")
                        
                        for w, s in zip(selected_wids, selected_steps):
                            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={requests.utils.quote(str(w))}&step_no={requests.utils.quote(str(s))}&action=Kick%20off&comment={enc_comment}&time={enc_time}")
                            
                        with st.spinner(f"⏳ 正在為 {len(selected_wids)} 片晶圓執行 Kick off..."):
                            has_err = False
                            session = requests.Session()
                            adapter = requests.adapters.HTTPAdapter(max_retries=0)
                            session.mount('https://', adapter)
                            
                            for url in urls_to_send:
                                try:
                                    res = session.get(url, timeout=12, allow_redirects=False)
                                    if res.status_code not in [200, 302] and "Error" in res.text:
                                        st.error(f"❌ 寫入失敗: {res.text}")
                                        has_err = True
                                except Exception:
                                    pass 
                                    
                            if has_err: 
                                time.sleep(3)
                            else:
                                st.success("✅ 批次 Kick off 成功！")
                                time.sleep(1.5)
                            st.cache_data.clear()
                            st.rerun()
            else:
                st.success("🎉 目前產線上沒有任何晶圓處於 Bank (入庫) 狀態。")
                
            st.markdown("---")
            st.subheader("📊 各 Shuttle 狀態統計總表")
            
            summary_data = []
            
            def get_lot_number(wid):
                import re
                match = re.search(r'lot(\d+)', str(wid).lower())
                return int(match.group(1)) if match else 999999
                
            df_route_bank['_lot_num'] = df_route_bank[wafer_col].apply(get_lot_number)
            df_route_bank = df_route_bank.sort_values(by=['_lot_num', wafer_col])
            
            for shuttle, s_group in df_route_bank.groupby(shuttle_col, sort=False):
                if str(shuttle).strip() == "": continue
                
                inpr_count = bank_count = shipped_count = 0
                
                for wid in s_group[wafer_col].unique():
                    w_group = s_group[s_group[wafer_col] == wid].reset_index(drop=True)
                    total_steps = len(w_group)
                    
                    has_scrap = False
                    is_banked = False
                    wip_idx = total_steps
                    
                    for idx, row in w_group.iterrows():
                        fco = str(row.get(fco_col, "")).strip().upper()
                        if fco == "SCRP":
                            has_scrap = True
                            break
                            
                    if not has_scrap:
                        for idx, row in w_group.iterrows():
                            fco = str(row.get(fco_col, "")).strip().upper()
                            if fco in ["", "NAN", "INPR", "HOLD", "BANK"]:
                                wip_idx = idx
                                if fco == "BANK":
                                    is_banked = True
                                break
                    
                    if has_scrap: continue
                    elif is_banked: bank_count += 1
                    elif wip_idx == total_steps: shipped_count += 1
                    else: inpr_count += 1
                
                if (inpr_count + bank_count + shipped_count) > 0:
                    summary_data.append({
                        "Shuttle Name": shuttle,
                        "INPR (在製中)": inpr_count,
                        "Bank (入庫)": bank_count,
                        "Shipped (已出貨)": shipped_count,
                        "Total (總計)": inpr_count + bank_count + shipped_count
                    })
            
            if summary_data:
                df_summary = pd.DataFrame(summary_data)
                st.dataframe(df_summary, hide_index=True, use_container_width=True)
            else:
                st.info("尚無有效的 Shuttle 統計資料。")
                
        else:
            st.warning("⚠️ 母表中找不到 Wafer ID 欄位。")
    else:
        st.info("💡 目前雲端母表尚無資料。")

# =========================================================================
# 📊 頁籤 6: Wafer Overview 
# =========================================================================
with all_tabs[5]:
    st.subheader("📊 晶圓生產總表與進度追蹤 (Wafer Overview)")
    df_route, conn_status = fetch_route_data_via_csv("route_template")
    
    if not df_route.empty:
        wafer_col = next((c for c in df_route.columns if str(c).strip().lower() in ["wafer id", "id", "wafer"]), "Wafer ID")
        step_col = next((c for c in df_route.columns if str(c).strip().lower() in ["step", "step no.", "step no"]), "Step")
        shuttle_col = next((c for c in df_route.columns if "shuttle" in str(c).lower()), "Shuttle Name")
        owner_col = next((c for c in df_route.columns if "owner" in str(c).lower()), "Stage Owner")
        team_col = next((c for c in df_route.columns if "customer" in str(c).lower()), "Customer")
        fco_col = next((c for c in df_route.columns if "check out" in str(c).lower()), "Check out Time")
        desc_col = next((c for c in df_route.columns if "description" in str(c).lower()), "Step description")
        
        if wafer_col in df_route.columns:
            html_table = """<style>.overview-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; margin-top: 10px; } .overview-table th { background-color: #f8f9fa; padding: 12px 10px; border: 1px solid #dee2e6; text-align: left; font-weight: bold; color: #495057; } .overview-table td { padding: 10px; border: 1px solid #dee2e6; text-align: left; vertical-align: middle; color: #212529; } .overview-table .merged-cell { text-align: center; vertical-align: middle; font-weight: bold; background-color: #ffffff; color: #0d6efd; } .overview-table .owner-team-cell { text-align: center; vertical-align: middle; background-color: #ffffff; } .prog-wrapper { display: flex; align-items: center; width: 100%; } .prog-container { background-color: #e9ecef; border-radius: 4px; flex-grow: 1; height: 16px; overflow: hidden; } .prog-bar { background-color: #28a745; height: 100%; border-radius: 4px; transition: width 0.4s ease; } .prog-text { margin-left: 10px; font-size: 13px; font-weight: 500; min-width: 35px; text-align: right; } .status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }</style><table class="overview-table"><tr><th>Shuttle Name</th><th>Owner</th><th>團隊</th><th style="width: 90px; text-align: center;">已出貨片數</th><th>ID (Wafer)</th><th>Step</th><th>Stage Owner</th><th>Status</th><th style="width: 200px;">進度條</th></tr>"""
            df_route[shuttle_col] = df_route[shuttle_col].fillna("")
            df_route[team_col] = df_route[team_col].fillna("")
            
            def get_lot_number(wid):
                import re
                match = re.search(r'lot(\d+)', str(wid).lower())
                return int(match.group(1)) if match else 999999
                
            df_route['_lot_num'] = df_route[wafer_col].apply(get_lot_number)
            df_route = df_route.sort_values(by=['_lot_num', wafer_col])
            
            valid_shuttles = {}
            all_shipped_data = [] 

            for (shuttle, rep_team), s_group in df_route.groupby([shuttle_col, team_col], sort=False):
                if str(shuttle).strip() == "": continue
                rep_owner = str(s_group.iloc[0].get(owner_col, ""))
                team_valid_wafers = []
                
                for wid in s_group[wafer_col].unique():
                    w_group = s_group[s_group[wafer_col] == wid].reset_index(drop=True)
                    total_steps = len(w_group)
                    has_scrap, is_banked, wip_idx = False, False, total_steps  
                    raw_last_step = str(w_group.iloc[-1].get(step_col, "")).replace(".0", "").strip()
                    wip_step_no = str(total_steps) if raw_last_step in ["", "nan", "NaN", "None"] else raw_last_step
                    status_html = '<span class="status-dot" style="background-color: #0d6efd;"></span> Shipped (已出貨)'
                    
                    current_stage_owner = str(w_group.iloc[-1].get(owner_col, ""))
                    
                    for idx, row in w_group.iterrows():
                        fco = str(row.get(fco_col, "")).strip().upper()
                        if fco == "SCRP":
                            has_scrap, wip_idx = True, idx
                            raw_step = str(row.get(step_col, "")).replace(".0", "").strip()
                            wip_step_no = str(idx + 1) if raw_step in ["", "nan", "NaN", "None"] else raw_step
                            status_html = f'<span class="status-dot" style="background-color: #dc3545;"></span> SCRAPPED: {row.get(desc_col, "")}'
                            current_stage_owner = str(row.get(owner_col, ""))
                            break
                            
                    if not has_scrap:
                        for idx, row in w_group.iterrows():
                            fco = str(row.get(fco_col, "")).strip().upper()
                            if fco in ["", "NAN", "INPR", "HOLD", "BANK"]:
                                wip_idx = idx
                                raw_step = str(row.get(step_col, "")).replace(".0", "").strip()
                                wip_step_no = str(idx + 1) if raw_step in ["", "nan", "NaN", "None"] else raw_step
                                if fco == "HOLD": status_html = f'<span class="status-dot" style="background-color: #ffc107;"></span> HOLD: {row.get(desc_col, "")}'
                                elif fco == "BANK": is_banked = True
                                else: status_html = f'<span class="status-dot" style="background-color: #198754;"></span> INPR: {row.get(desc_col, "")}'
                                current_stage_owner = str(row.get(owner_col, ""))
                                break
                                
                    if is_banked: continue
                    is_shipped = True if (wip_idx == total_steps and not has_scrap) else False
                    nums = re.findall(r'\d+', str(wip_step_no))
                    progress_pct = min(int((int(nums[0]) if nums else 0) / 92 * 100), 100)
                    
                    team_valid_wafers.append({"id": wid, "step": f"{wip_step_no}/92", "stage_owner": current_stage_owner, "status": status_html, "is_shipped": is_shipped, "progress_pct": progress_pct})
                    
                    if is_shipped:
                        all_shipped_data.append({
                            "Shuttle Name": shuttle,
                            "Owner": rep_owner,
                            "團隊": rep_team,
                            "ID (Wafer)": wid,
                            "Step": f"{wip_step_no}/92",
                            "Status": "🟢 Shipped (已出貨)"
                        })
                
                if team_valid_wafers:
                    if shuttle not in valid_shuttles: valid_shuttles[shuttle] = {"owner": rep_owner, "teams": []}
                    valid_shuttles[shuttle]["teams"].append({"team_name": rep_team, "wafers": team_valid_wafers})
            
            has_inpr_wafers = False
            for shuttle, s_data in valid_shuttles.items():
                shuttle_inpr_count = sum(1 for t in s_data["teams"] for w in t["wafers"] if not w["is_shipped"])
                if shuttle_inpr_count == 0: continue 
                has_inpr_wafers = True
                
                is_first_in_shuttle = True
                for t_data in s_data["teams"]:
                    inpr_wafers = [w for w in t_data["wafers"] if not w["is_shipped"]]
                    team_rowspan = len(inpr_wafers)
                    if team_rowspan == 0: continue
                    
                    is_first_in_team = True
                    shipped_count = sum(1 for w in t_data["wafers"] if w["is_shipped"])
                    max_progress_pct = max([w["progress_pct"] for w in inpr_wafers] + [0])

                    for w_data in inpr_wafers:
                        html_table += "<tr>"
                        if is_first_in_shuttle:
                            html_table += f'<td class="merged-cell" rowspan="{shuttle_inpr_count}">{shuttle}</td><td class="owner-team-cell" rowspan="{shuttle_inpr_count}">{s_data["owner"]}</td>'
                            is_first_in_shuttle = False
                        if is_first_in_team:
                            html_table += f'<td class="owner-team-cell" rowspan="{team_rowspan}">{t_data["team_name"]}</td><td class="merged-cell" rowspan="{team_rowspan}">{shipped_count}</td>'
                        
                        html_table += f"<td>{w_data['id']}</td><td>{w_data['step']}</td><td>{w_data['stage_owner']}</td><td>{w_data['status']}</td>"
                        
                        if is_first_in_team:
                            html_table += f'<td rowspan="{team_rowspan}"><div class="prog-wrapper"><div class="prog-container"><div class="prog-bar" style="width: {max_progress_pct}%;"></div></div><div class="prog-text">{max_progress_pct}%</div></div></td>'
                            is_first_in_team = False
                        html_table += "</tr>"
            html_table += "</table>"
            
            if has_inpr_wafers:
                st.markdown(html_table, unsafe_allow_html=True)
            else:
                st.info("目前產線上沒有任何進行中 (INPR) 的晶圓。")
                
            st.markdown("---")
            st.subheader("📦 已出貨晶圓清單 (Shipped Wafers)")
            if all_shipped_data:
                df_shipped = pd.DataFrame(all_shipped_data)
                st.dataframe(
                    df_shipped,
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.success("目前無已出貨的晶圓。")
                
        else:
            st.warning("⚠️ 母表中找不到 Wafer ID 欄位。")
