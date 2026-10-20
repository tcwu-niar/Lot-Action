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

# 🎯 自訂主標題樣式 (字體 20px)
st.markdown("<div style='font-size: 20px; font-weight: bold; padding-top: 1rem; padding-bottom: 1rem;'>TSRI Lot Tracing System</div>", unsafe_allow_html=True)

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
# 2. 🎯 將所有彈出視窗定義在全域
# =========================================================================

@st.dialog(" ", width="large")
def show_ongoing_action_dialog(tw_id, ts_no, target_row_dict, avail_steps):
    st.markdown(f"**Wafer ID:** `{tw_id}` | **Step:** `{ts_no}`")
    
    current_status = str(target_row_dict.get("Check out Time", "")).strip().upper()
    is_held = (current_status == "HOLD")
    is_scrap = (current_status == "SCRP")
    
    if is_scrap: st.error("This wafer is currently SCRAPPED.")
    elif is_held: st.warning("This wafer is currently on HOLD.")
    
    st.markdown("**Process Parameters**")
    c1, c2, c3 = st.columns(3)
    with c1: edit_tool = st.text_input("Process Tool", value=target_row_dict.get("Process Tool", ""))
    with c2: edit_recipe = st.text_input("Process Recipe", value=target_row_dict.get("Recipe", ""))
    with c3: edit_cp = st.text_input("Check Point", value=target_row_dict.get("Check point", ""))
    
    spc_data = st.text_input("**Result Data**")
    result_image = st.file_uploader("**Result Image**", type=["png", "jpg", "jpeg"], key=f"img_{tw_id}_{ts_no}")
    
    st.markdown("---")
    st.markdown("**Wafer Action**")
    
    options = []
    if is_scrap:
        options = ["Unscrap"]
    elif is_held:
        options = ["Release Hold"]
    else:
        options = [
            "Check Out", 
            "Save Data Only", 
            "Skip Stage", 
            "Hold", 
            "Bank in", 
            "Scrap"
        ]
        
    action_type = st.radio("Wafer Action Options", options, horizontal=True, label_visibility="collapsed")
    
    jump_target, comment = None, ""
    
    if action_type == "Skip Stage":
        jump_target = st.selectbox("Jump to step:", options=avail_steps)
        comment = st.text_input("Reason for skip:")
    elif action_type == "Hold":
        comment = st.text_input("Reason for hold:")
    elif action_type == "Bank in":
        comment = st.text_input("Reason for bank:")
    elif action_type == "Scrap":
        comment = st.text_input("Reason for scrap:")
    elif action_type == "Unscrap":
        comment = st.text_input("Reason for unscrap:")
    elif action_type == "Release Hold":
        comment = st.text_input("Reason for release:")
        
    if st.button("Confirm and Submit", type="primary", use_container_width=True):
        action_name = ""
        if action_type == "Check Out": action_name = "Check out"
        elif action_type == "Save Data Only": action_name = "Key in data"
        elif action_type == "Skip Stage": action_name = "Skip"
        elif action_type == "Hold": action_name = "Hold"
        elif action_type == "Release Hold": action_name = "Unhold"
        elif action_type == "Bank in": action_name = "Bank"
        elif action_type == "Scrap": action_name = "Scrap"
        elif action_type == "Unscrap": action_name = "Unscrap"
        
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

@st.dialog("Edit History Data", width="large")
def show_history_edit_dialog(tw_id, ts_no, target_row_dict):
    st.markdown(f"**Wafer ID:** `{tw_id}` | **Step:** `{ts_no}`")
    st.info("Note: Modifications here will overwrite the Route Template records.")
    
    st.markdown("**Process Parameters**")
    c1, c2, c3 = st.columns(3)
    with c1: edit_tool = st.text_input("Process Tool", value=str(target_row_dict.get("Process Tool", "")))
    with c2: edit_recipe = st.text_input("Process Recipe", value=str(target_row_dict.get("Recipe", "")))
    with c3: edit_cp = st.text_input("Check Point", value=str(target_row_dict.get("Check point", "")))
    
    current_comment = str(target_row_dict.get("SPC data", "")).strip()
    if not current_comment: current_comment = str(target_row_dict.get("Comments", "")).strip()
    if not current_comment: current_comment = str(target_row_dict.get("備註", "")).strip()
    
    st.markdown("**Result Data**")
    spc_data = st.text_input("Update Action Record & SPC data:", value=current_comment)
    
    st.markdown("**Result Image**")
    result_image = st.file_uploader("Upload new image to overwrite", type=["png", "jpg", "jpeg"], key=f"hist_img_{tw_id}_{ts_no}")
    
    if st.button("Confirm and Submit", type="primary", use_container_width=True):
        st.session_state.history_edit_action = {
            "w_id": tw_id,
            "s_no": ts_no,
            "spc": spc_data,
            "img": result_image,
            "tool": edit_tool,
            "recipe": edit_recipe,
            "cp": edit_cp,
            "orig_row": target_row_dict
        }
        st.rerun()

# 🎯 頁籤名稱加上圖案
all_tabs = st.tabs(["🔍 Ongoing Wafer", "📜 Wafer History", "📤 Upload New Wafer", "📦 Bank Wafers", "📊 Wafer Overview"])

# =========================================================================
# 🔍 頁籤 1: Ongoing Wafer 
# =========================================================================
with all_tabs[0]:
    st.markdown("<div style='font-size: 18px; font-weight: bold; padding-bottom: 0.5rem;'>Ongoing Wafer List</div>", unsafe_allow_html=True)
    
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
            with st.spinner("Uploading..."):
                try:
                    payload = {"key": "6d207e02198a847aa98d0a2a901485a5", "action": "upload", "format": "json"}
                    files = {"source": pa["img"].getvalue()}
                    res = requests.post("https://freeimage.host/api/1/upload", data=payload, files=files)
                    if res.status_code == 200:
                        final_result_link = res.json()["image"]["url"]
                    else:
                        st.warning(f"Image upload failed: {res.status_code}")
                except Exception as e:
                    st.error(f"Upload error: {e}")
                    
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
        elif act == "Unscrap": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Unscrap&comment={enc_comment}&time={enc_time}")
        elif act == "Hold": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Hold&comment={enc_comment}&time={enc_time}")
        elif act == "Unhold": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Unhold&comment={enc_comment}&time={enc_time}")
        elif act == "Bank": urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Bank&comment={enc_comment}&time={enc_time}")
        elif act == "Skip":
            enc_target = requests.utils.quote(str(pa["jump_step"]))
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Skip&comment={enc_comment}&time={enc_time}&target_step={enc_target}")
            
        if urls_to_send:
            with st.spinner(f"Syncing {act} to Cloud..."):
                has_error = False
                session = requests.Session()
                adapter = requests.adapters.HTTPAdapter(max_retries=0) 
                session.mount('https://', adapter)
                
                for url in set(urls_to_send):
                    try:
                        res = session.get(url, timeout=12, allow_redirects=False)
                        if res.status_code not in [200, 302] and "Error" in res.text:
                            st.error(f"Cloud Error: {res.text}")
                            has_error = True
                    except:
                        pass
                if has_error:
                    time.sleep(3)
                else:
                    st.success("Action Successfully Submitted!")
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
                df_wip = pd.DataFrame(wip_data_list)
                display_df = df_wip[["ID (Wafer)", "Step", "Stage Owner", "Step Description", "Process Tool", "Recipe"]]
                styled_df = display_df.style.set_properties(**{'text-align': 'center'})
                
                if "ongoing_last_sel" not in st.session_state:
                    st.session_state.ongoing_last_sel = []

                selection = st.dataframe(
                    styled_df,
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key="ongoing_wafer_table"
                )
                
                curr_sel = selection.get("selection", {}).get("rows", [])
                
                if curr_sel != st.session_state.ongoing_last_sel:
                    st.session_state.ongoing_last_sel = curr_sel
                    
                    if curr_sel:
                        selected_idx = curr_sel[0]
                        selected_item = wip_data_list[selected_idx]
                        
                        show_ongoing_action_dialog(
                            selected_item['ID (Wafer)'], 
                            selected_item['_raw_step'], 
                            selected_item['_row_dict'], 
                            selected_item['_avail_steps']
                        )
            else:
                st.info("No Ongoing Wafers at this moment.")
        else:
            st.warning("⚠️ Wafer ID column not found in database.")

# =========================================================================
# 📜 頁籤 2: Wafer History
# =========================================================================
with all_tabs[1]:
    st.markdown("<div style='font-size: 20px; font-weight: bold; padding-bottom: 0.5rem;'>Wafer History</div>", unsafe_allow_html=True)
    
    if "history_edit_action" in st.session_state:
        pa = st.session_state.history_edit_action
        del st.session_state["history_edit_action"]
        
        urls_to_send = []
        enc_w_id = requests.utils.quote(str(pa["w_id"]))
        enc_s_no = requests.utils.quote(str(pa["s_no"]))
        
        final_result_link = ""
        if pa["img"] is not None:
            with st.spinner("Uploading..."):
                try:
                    payload = {"key": "6d207e02198a847aa98d0a2a901485a5", "action": "upload", "format": "json"}
                    files = {"source": pa["img"].getvalue()}
                    res = requests.post("https://freeimage.host/api/1/upload", data=payload, files=files)
                    if res.status_code == 200:
                        final_result_link = res.json()["image"]["url"]
                    else:
                        st.warning(f"Image upload failed: {res.status_code}")
                except Exception as e:
                    st.error(f"Upload error: {e}")
        
        orig_comment = str(pa["orig_row"].get("Comments", "")).strip() or str(pa["orig_row"].get("備註", "")).strip()
        if str(pa["spc"]).strip() != orig_comment:
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name=Comments&new_value={requests.utils.quote(str(pa['spc']).strip())}")
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name=SPC%20data&new_value={requests.utils.quote(str(pa['spc']).strip())}")

        if final_result_link:
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name=Result&new_value={requests.utils.quote(final_result_link)}")

        fields = {"Process Tool": pa["tool"], "Recipe": pa["recipe"], "Check point": pa["cp"]}
        for f_name, f_val in fields.items():
            orig_val = str(pa["orig_row"].get(f_name, "")).strip()
            if str(f_val).strip() != orig_val:
                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name={requests.utils.quote(f_name)}&new_value={requests.utils.quote(str(f_val).strip())}")

        if urls_to_send:
            with st.spinner("Syncing modifications to Cloud..."):
                has_error = False
                session = requests.Session()
                adapter = requests.adapters.HTTPAdapter(max_retries=0)
                session.mount('https://', adapter)

                for url in set(urls_to_send):
                    try:
                        res = session.get(url, timeout=12, allow_redirects=False)
                        if res.status_code not in [200, 302] and "Error" in res.text:
                            st.error(f"Cloud Error: {res.text}")
                            has_error = True
                    except:
                        pass
                if has_error:
                    time.sleep(3)
                else:
                    st.success("Modifications Successfully Submitted!")
                    time.sleep(1.2)
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("No modifications detected.")
            time.sleep(1)
            st.rerun()
    
    col_input1, col_input2 = st.columns(2)
    with col_input1: 
        search_id = st.text_input("Please Key in Wafer ID", value="LOT4-11F0", key="search_wafer_id_history")
    with col_input2:
        st.write(" "); st.write(" ")
        if st.button("Refresh Data", use_container_width=True, key="history_refresh"):
            st.cache_data.clear(); st.rerun()

    df_route, route_status = fetch_route_data_via_csv("route_template")
    df_logs, log_status = fetch_route_data_via_csv("wafer_status")
    
    if search_id and not df_route.empty and not df_logs.empty:
        wafer_col_list = [c for c in df_route.columns if "Wafer" in c or "wafer" in c]
        if wafer_col_list:
            actual_string_col = wafer_col_list[0]
            filtered_route = df_route[df_route[actual_string_col].astype(str).str.upper() == search_id.upper()]
        else:
            filtered_route = df_route
            
        if not filtered_route.empty:
            display_route = filtered_route.copy().reset_index(drop=True)
            
            if "Step" in display_route.columns:
                display_route["Step"] = display_route["Step"].astype(str).str.replace(".0", "", regex=False)
            
            col_cfg = {
                "Result": st.column_config.ImageColumn("Result (預覽圖片)", help="上傳的檢驗圖片")
            }
            for col_name in display_route.columns:
                c_lower = str(col_name).lower().strip()
                if c_lower in ["step description", "recipe", "customer"]:
                    col_cfg[col_name] = st.column_config.TextColumn(width="large")

            selected_route_row = st.dataframe(
                display_route, 
                use_container_width=True, 
                hide_index=True, 
                on_select="rerun", 
                selection_mode="single-row", 
                key="history_route_table", 
                column_config=col_cfg
            )
            
            if selected_route_row and selected_route_row.get("selection", {}).get("rows"):
                selected_idx = selected_route_row["selection"]["rows"][0]
                target_step_no = str(display_route.iloc[selected_idx].get("Step", "")).replace(".0", "").strip()
                target_row_data = display_route.iloc[selected_idx].to_dict()
                
                st.markdown("---")
                
                hc1, hc2 = st.columns([4, 1])
                hc1.markdown(f"<div style='font-size: 20px; font-weight: bold;'>Step {target_step_no} Action History</div>", unsafe_allow_html=True)
                if hc2.button("Edit Data", use_container_width=True, type="secondary"):
                    show_history_edit_dialog(search_id, target_step_no, target_row_data)
                
                log_wafer_col = [c for c in df_logs.columns if "Wafer" in c or "晶圓" in c][0]
                clean_log_steps = df_logs["Step"].astype(str).str.replace(".0", "", regex=False).str.strip()
                step_logs = df_logs[(df_logs[log_wafer_col].astype(str).str.upper() == search_id.upper()) & (clean_log_steps == target_step_no)]
                
                mother_result_val = str(display_route.iloc[selected_idx].get("Result", "")).strip()
                result_html = ""
                if mother_result_val.startswith("http"):
                    result_html = f'<a href="{mother_result_val}" target="_blank"><img src="{mother_result_val}" style="max-height: 80px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); cursor: zoom-in;"></a>'
                else:
                    result_html = mother_result_val

                mother_spc_val = str(display_route.iloc[selected_idx].get("SPC data", "")).strip()
                if not mother_spc_val: mother_spc_val = str(display_route.iloc[selected_idx].get("Comments", "")).strip()
                if not mother_spc_val: mother_spc_val = str(display_route.iloc[selected_idx].get("備註", "")).strip()

                if not step_logs.empty:
                    html_parts = ['<div style="font-size: 12pt;"><table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">']
                    html_parts.append('<tr style="background-color: #f8f9fa; color: #333;"><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 10%;">動作 (Action)</th><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 20%;">日期與時間</th><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 25%;">Action Record</th><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 25%;">SPC data</th><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 20%;">Result (檢驗圖片)</th></tr>')
                    
                    for _, log_row in step_logs.iterrows():
                        action_val = str(log_row.get("Action", "")).strip()
                        time_val = str(log_row.get("Check out Time", "")).strip()
                        hold_note_val = str(log_row.get("Hold Note", "")).strip()
                        
                        spc_val = mother_spc_val
                        if not spc_val: spc_val = str(log_row.get("SPC data", "")).strip()
                        if not spc_val: spc_val = str(log_row.get("Comments", "")).strip()
                        if not spc_val: spc_val = str(log_row.get("備註", "")).strip()
                        
                        bg_color = "#fff3cd" if action_val.upper() == "HOLD" else "#ffffff"
                        text_color = "#d9534f" if action_val.upper() == "HOLD" else "#000000"
                        
                        html_parts.append(f'<tr style="background-color: {bg_color};"><td style="padding: 10px; border: 1px solid #ddd; text-align: center; font-weight: bold;">{action_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{time_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: center; color: {text_color}; font-weight: bold;">{hold_note_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{spc_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{result_html}</td></tr>')
                    html_parts.append('</table></div>')
                    st.markdown("".join(html_parts), unsafe_allow_html=True)
                
                else:
                    st.info("No Record")
                    if mother_result_val.startswith("http"):
                        st.markdown("---")
                        st.markdown("**Uploaded Result Image:**")
                        st.markdown(f"<a href='{mother_result_val}' target='_blank'><img src='{mother_result_val}' style='max-height: 250px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); cursor: zoom-in;'></a>", unsafe_allow_html=True)
                    elif mother_result_val:
                        st.markdown(f"**Saved Result Record:** {mother_result_val}")
    else:
        st.info("請先於上方搜尋欄輸入特定 Wafer ID 並從表格中選擇特定站點。")

# =========================================================================
# 📤 頁籤 3: Upload New Wafer 
# =========================================================================
with all_tabs[2]:
    st.markdown("<div style='font-size: 20px; font-weight: bold; padding-bottom: 0.5rem;'>Upload New Wafer</div>", unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Only .csv", type=["csv"])
    
    if uploaded_file is not None:
        try:
            df_upload = pd.read_csv(uploaded_file)
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
            
            if st.button("Check Upload to System", type="primary", use_container_width=True):
                with st.spinner("Uploading..."):
                    payload = {"action": "bulk_upload", "data": edited_df.to_dict(orient="records")}
                    try:
                        res = requests.post(MY_ORGANIZATION_GAS_URL, json=payload, timeout=300)
                        if res.status_code == 200 and "Success" in res.text:
                            st.success("Successfully uploaded to the system.")
                            time.sleep(2)
                            st.cache_data.clear()
                            st.rerun()
                        else: st.error(f"Upload failed: {res.text}")
                    except Exception as e: st.error(f"Network error: {e}")
        except Exception as e:
            st.error(f"Failed to parse file: {str(e)}")

# =========================================================================
# 📦 頁籤 4: Bank Wafers 
# =========================================================================
with all_tabs[3]:
    st.markdown("<div style='font-size: 20px; font-weight: bold; padding-bottom: 0.5rem;'>Bank Wafers & Wait Kick-off Wafers</div>", unsafe_allow_html=True)

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
                        "Select": False, 
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
                
                selected_flags = edited_bank_df["Select"].tolist()
                selected_wids = [banked_wafers[i]["ID (Wafer)"] for i, flag in enumerate(selected_flags) if flag]
                selected_steps = [banked_wafers[i]["_Raw_Step"] for i, flag in enumerate(selected_flags) if flag]
                
                if selected_wids:
                    st.markdown("---")
                    if st.button("Bank Out/Kick-off", type="primary"):
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
            st.markdown("<div style='font-size: 20px; font-weight: bold; padding-bottom: 0.5rem;'>Shuttle Wafer Status</div>", unsafe_allow_html=True)
            
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
# 📊 頁籤 5: Wafer Overview 
# =========================================================================
with all_tabs[4]:
    # 🎯 標題正名與字體設定
    st.markdown("<div style='font-size: 20px; font-weight: bold; padding-bottom: 0.5rem;'>Active Interposer Wafer Status</div>", unsafe_allow_html=True)
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
            html_table = """<style>.overview-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; margin-top: 10px; } .overview-table th { background-color: #f8f9fa; padding: 12px 10px; border: 1px solid #dee2e6; text-align: left; font-weight: bold; color: #495057; } .overview-table td { padding: 10px; border: 1px solid #dee2e6; text-align: left; vertical-align: middle; color: #212529; } .overview-table .merged-cell { text-align: center; vertical-align: middle; font-weight: bold; background-color: #ffffff; color: #0d6efd; } .overview-table .owner-team-cell { text-align: center; vertical-align: middle; background-color: #ffffff; } .prog-wrapper { display: flex; align-items: center; width: 100%; } .prog-container { background-color: #e9ecef; border-radius: 4px; flex-grow: 1; height: 16px; overflow: hidden; } .prog-bar { background-color: #28a745; height: 100%; border-radius: 4px; transition: width 0.4s ease; } .prog-text { margin-left: 10px; font-size: 13px; font-weight: 500; min-width: 35px; text-align: right; } .status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }</style><table class="overview-table"><tr><th>Shuttle Name</th><th>Owner</th><th>團隊</th><th style="width: 90px; text-align: center;">已出貨片數</th><th>ID (Wafer)</th><th>Step</th><th>Status</th><th style="width: 200px;">進度條</th></tr>"""
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
                    
                    for idx, row in w_group.iterrows():
                        fco = str(row.get(fco_col, "")).strip().upper()
                        if fco == "SCRP":
                            has_scrap, wip_idx = True, idx
                            raw_step = str(row.get(step_col, "")).replace(".0", "").strip()
                            wip_step_no = str(idx + 1) if raw_step in ["", "nan", "NaN", "None"] else raw_step
                            status_html = f'<span class="status-dot" style="background-color: #dc3545;"></span> SCRAPPED: {row.get(desc_col, "")}'
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
                                break
                                
                    if is_banked: continue
                    is_shipped = True if (wip_idx == total_steps and not has_scrap) else False
                    nums = re.findall(r'\d+', str(wip_step_no))
                    progress_pct = min(int((int(nums[0]) if nums else 0) / 92 * 100), 100)
                    
                    team_valid_wafers.append({"id": wid, "step": f"{wip_step_no}/92", "status": status_html, "is_shipped": is_shipped, "progress_pct": progress_pct})
                    
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
                        
                        html_table += f"<td>{w_data['id']}</td><td>{w_data['step']}</td><td>{w_data['status']}</td>"
                        
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
            # 🎯 已出貨標題正名與字體設定
            st.markdown("<div style='font-size: 20px; font-weight: bold; padding-bottom: 0.5rem;'>Shipped Wafers</div>", unsafe_allow_html=True)
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
