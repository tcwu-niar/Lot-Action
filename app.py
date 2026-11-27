import streamlit as st
import pandas as pd
import requests
import datetime
import time      
import re
import concurrent.futures
import html as html_lib

# =========================================================================
# 1. 系統全域基礎配置、RWD 響應式樣式與資料載入
# =========================================================================
st.set_page_config(
    layout="wide",
    page_title="TSRI Lot Tracing System",
    initial_sidebar_state="collapsed"
)

# 全域 RWD 響應式 CSS：確保電腦滿版美觀、手機維持正常比例與順暢觸控滑動
st.markdown("""
<style>
div[data-baseweb="tab-list"] {
    overflow-x: auto !important;
    overflow-y: hidden !important;
    flex-wrap: nowrap !important;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
    gap: 6px;
}
div[data-baseweb="tab-list"] button {
    white-space: nowrap !important;
    flex-shrink: 0 !important;
}

.rwd-table-scroll {
    width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin-top: 8px;
    margin-bottom: 12px;
    border-radius: 6px;
}

.ksr-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    border-bottom: 3px solid #b8860b;
    padding-bottom: 8px;
    margin-bottom: 16px;
    gap: 12px;
}
.ksr-legend {
    font-size: 13px;
    line-height: 1.6;
    font-weight: bold;
    min-width: 150px;
}
.ksr-title {
    font-size: 30px;
    font-weight: bold;
    color: #b30000;
    text-align: center;
    flex-grow: 1;
}
.ksr-spacer {
    min-width: 150px;
}
.mobile-swipe-hint {
    display: none;
    font-size: 12px;
    color: #6c757d;
    margin-bottom: 6px;
}

@media screen and (max-width: 768px) {
    .block-container {
        padding-top: 2.2rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        padding-bottom: 2rem !important;
    }
    .app-main-title {
        font-size: 18px !important;
        padding-top: 0.4rem !important;
        padding-bottom: 0.5rem !important;
    }
    div[role="dialog"] {
        width: 96vw !important;
        max-width: 96vw !important;
        margin: 0 auto !important;
    }
    .stButton > button {
        min-height: 42px !important;
        font-size: 15px !important;
    }
    div[role="radiogroup"] {
        gap: 8px !important;
        flex-wrap: wrap !important;
    }
    .ksr-header {
        flex-direction: column-reverse;
        align-items: center;
        text-align: center;
        gap: 6px;
    }
    .ksr-title {
        font-size: 22px;
    }
    .ksr-legend {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        justify-content: center;
        min-width: unset;
        font-size: 12px;
    }
    .ksr-legend br {
        display: none;
    }
    .ksr-spacer {
        display: none;
    }
    .mobile-swipe-hint {
        display: block;
    }
}
</style>
""", unsafe_allow_html=True)

if "search_wafer_id_history" not in st.session_state:
    st.session_state.search_wafer_id_history = ""

if "ongoing_table_ver" not in st.session_state:
    st.session_state.ongoing_table_ver = 0

st.markdown("<div class='app-main-title' style='font-size: 20px; font-weight: bold; padding-top: 1rem; padding-bottom: 1rem;'>TSRI Lot Tracing System</div>", unsafe_allow_html=True)

MY_ORGANIZATION_GAS_URL = "https://script.google.com/macros/s/AKfycbxSpHeSlbCyMgn0cH60fh62eM_nYoaCwkSCZF1UJMTeC-3z1wQJ1RVLXge1kvzadmKM/exec"
SPREADSHEET_ID = "1RQt29KIb4rkVo4A-Y3GouMAezYEBakb1q283d1sgdZU"

def clean_step(val):
    s = str(val).strip()
    if not s or s in ["nan", "NaN", "None"]:
        return ""
    try:
        f_val = float(s)
        if abs(f_val - round(f_val)) < 1e-6:
            return str(int(round(f_val)))
        else:
            return f"{f_val:.2f}"
    except:
        if s.endswith(".0"):
            return s[:-2]
        return s

def gas_safe_step(val):
    s = str(val).strip()
    try:
        f = round(float(s), 2)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except:
        return s

@st.cache_data(ttl=15)
def fetch_route_data_via_csv(sheet_name="route_template"):
    if sheet_name == "route_template":
        csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid=0"
    else:
        csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        
    try:
        response = requests.get(csv_url, timeout=8)
        if response.status_code == 200:
            if "<html" in response.text.lower() or "<doctype" in response.text.lower():
                return pd.DataFrame(), "權限受阻，請確保試算表已開啟連結共用"
            from io import StringIO
            df_data = pd.read_csv(StringIO(response.text), dtype=str)
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

def build_log_hold_note_map(df_logs):
    hold_map = {}
    if df_logs is None or df_logs.empty:
        return hold_map
    lw_cols = [c for c in df_logs.columns if "wafer" in str(c).lower() or "晶圓" in str(c)]
    ls_col = next((c for c in df_logs.columns if "step" in str(c).lower()), "Step")
    lh_col = next((c for c in df_logs.columns if "hold note" in str(c).lower()), "Hold Note")
    la_col = next((c for c in df_logs.columns if "action" in str(c).lower()), "Action")
    if lw_cols and ls_col in df_logs.columns and lh_col in df_logs.columns:
        lw_col = lw_cols[0]
        for _, lrow in df_logs.iterrows():
            k = (str(lrow.get(lw_col, "")).strip().upper(), clean_step(lrow.get(ls_col, "")))
            act_v = str(lrow.get(la_col, "")).strip().upper()
            note_v = str(lrow.get(lh_col, "")).strip()
            if act_v == "HOLD" and note_v:
                hold_map[k] = note_v
            elif act_v == "UNHOLD":
                hold_map.pop(k, None)
    return hold_map

# =========================================================================
# 1.5 純向量無背景無標題 Process Flow SVG 產生器 (供 KSR 點擊區間顯示)
# =========================================================================
def build_process_flow_svgs():
    C_SI = "#4A90D9"
    C_OX = "#92D050"
    C_M1 = "#BFBFBF"
    C_GLUE = "#D9D9D9"
    C_GLASS = "#DDEBF7"
    C_PR = "#F49AC1"
    C_LINER = "#FFFF00"
    C_SEED = "#ED7D31"
    C_CU = "#FFC000"
    C_STUD = "#F8CBAD"
    C_SN = "#BFBFBF"
    C_TAPE = "#66CCFF"

    def rct(x, y, w, h, fill, sw=1.2, dash=""):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" stroke="#000" stroke-width="{sw}"{d}/>'

    def txt(x, y, s, sz=10, col="#000", bold=True, rot=0):
        fw = "bold" if bold else "normal"
        tf = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot else ""
        return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="central" font-size="{sz}" font-weight="{fw}" fill="{col}" font-family="sans-serif"{tf}>{s}</text>'

    def sub_txt(x, y, prefix, sub, suffix, sz=14):
        return (
            f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-size="{sz}" font-weight="bold" fill="#000" font-family="sans-serif">'
            f'{prefix}<tspan dy="4" font-size="{int(sz*0.72)}">{sub}</tspan><tspan dy="-4">{suffix}</tspan></text>'
        )

    def timeline_row(y_line, nodes, x1=45, x2=1145, arr_id="pf-arr"):
        p = [f'<line x1="{x1}" y1="{y_line}" x2="{x2}" y2="{y_line}" stroke="#000" stroke-width="2.5" marker-end="url(#{arr_id})"/>']
        for nx, title_html, step_num in nodes:
            p.append(title_html)
            p.append(f'<circle cx="{nx}" cy="{y_line}" r="11" fill="#fff" stroke="#000" stroke-width="2"/>')
            if step_num:
                p.append(txt(nx, y_line, step_num, sz=11, col="#000"))
        return "".join(p)

    def base_stack(cx, y_m1, w=170, has_glass=True):
        x0 = cx - w / 2.0
        s = [
            rct(x0, y_m1, w, 11, C_M1),
            txt(cx, y_m1 + 5.5, "T18-M1", sz=8.5, col="#fff")
        ]
        if has_glass:
            s.extend([
                rct(x0, y_m1 + 11, w, 9, C_GLUE),
                txt(cx, y_m1 + 15.5, "Glue", sz=8, col="#000"),
                rct(x0, y_m1 + 20, w, 11, C_GLASS),
                txt(cx, y_m1 + 25.5, "Glass", sz=8.5, col="#000")
            ])
        return "".join(s)

    # 3 柱 2 孔 TSV 結構基底 (總寬 170: 柱寬 46 * 3 + 孔寬 16 * 2 = 170)
    def tsv_pillars_ox_si(cx, y_top, top_ox=True, si_etch=True, bot_ox_etch=True, ox_col_txt="#fff", bot_ox_col="#fff", si_col="#fff"):
        x0 = cx - 85.0
        pxs = [x0, x0 + 62.0, x0 + 124.0]
        vxs = [x0 + 46.0, x0 + 108.0]
        y_ox1 = y_top
        y_si = y_top + 14.0
        y_ox2 = y_si + 38.0
        p = []
        # Bottom OX
        if not bot_ox_etch:
            p.append(rct(x0, y_ox2, 170, 13, C_OX))
            p.append(txt(cx, y_ox2 + 6.5, "OX", sz=9.5, col=bot_ox_col))
        else:
            for px in pxs:
                p.append(rct(px, y_ox2, 46, 13, C_OX))
                p.append(txt(px + 23, y_ox2 + 6.5, "OX", sz=9.5, col=bot_ox_col))
        # Si
        if not si_etch:
            p.append(rct(x0, y_si, 170, 38, C_SI))
            p.append(txt(cx, y_si + 19, "Si", sz=10, col=si_col))
        else:
            for px in pxs:
                p.append(rct(px, y_si, 46, 38, C_SI))
                p.append(txt(px + 23, y_si + 19, "Si", sz=10, col=si_col))
        # Top OX
        if top_ox == "full":
            p.append(rct(x0, y_ox1, 170, 14, C_OX))
            p.append(txt(cx, y_ox1 + 7, "OX", sz=9.5, col=ox_col_txt))
        elif top_ox == "pillars":
            for px in pxs:
                p.append(rct(px, y_ox1, 46, 14, C_OX))
                p.append(txt(px + 23, y_ox1 + 7, "OX", sz=9.5, col=ox_col_txt))
        return "".join(p), pxs, vxs, y_ox1, y_si, y_ox2

    # 已填滿 Liner + Seed + TSV Cu 並平坦化後的 3 柱 2 孔標準基底 (高 75: LinerTop 8 + OX 13 + Si 41 + OX 13)
    def filled_tsv_core(cx, y_top, has_glass=True):
        x0 = cx - 85.0
        pxs = [x0, x0 + 62.0, x0 + 124.0]
        vxs = [x0 + 46.0, x0 + 108.0]
        p = []
        y_lt = y_top
        y_ox1 = y_top + 7.0
        y_si = y_ox1 + 13.0
        y_ox2 = y_si + 40.0
        y_m1 = y_ox2 + 13.0
        for px in pxs:
            p.append(rct(px, y_lt, 46, 7, C_LINER))
            p.append(rct(px, y_ox1, 46, 13, C_OX))
            p.append(txt(px + 23, y_ox1 + 6.5, "OX", sz=9, col="#fff"))
            p.append(rct(px, y_si, 46, 40, C_SI))
            p.append(txt(px + 23, y_si + 20, "Si", sz=9.5, col="#fff"))
            p.append(rct(px, y_ox2, 46, 13, C_OX))
            p.append(txt(px + 23, y_ox2 + 6.5, "OX", sz=9, col="#fff"))
        # 每個 Via 寬 16: 左 Liner(2.5) + Seed(1.5) + TSV Cu(8) + Seed(1.5) + 右 Liner(2.5)
        for vx in vxs:
            p.append(rct(vx, y_lt, 2.5, 73, C_LINER, sw=0.8))
            p.append(rct(vx + 13.5, y_lt, 2.5, 73, C_LINER, sw=0.8))
            p.append(rct(vx + 2.5, y_lt, 1.5, 73, C_SEED, sw=0.6))
            p.append(rct(vx + 12.0, y_lt, 1.5, 73, C_SEED, sw=0.6))
            p.append(rct(vx + 4.0, y_lt, 8.0, 73, C_CU, sw=0.9))
            p.append(txt(vx + 8.0, y_lt + 37, "TSV Cu", sz=8.5, col="#000", rot=90))
        p.append(base_stack(cx, y_m1, w=170, has_glass=has_glass))
        return "".join(p), pxs, vxs, y_lt, y_m1

    defs = (
        '<defs><marker id="pf-arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto">'
        '<path d="M 0 1 L 10 5 L 0 9 z" fill="#000"/></marker></defs>'
    )

    # ---------------------------------------------------------------------
    # 1. W2W Bonding & Grinding
    # ---------------------------------------------------------------------
    xs5 = [145, 370, 595, 820, 1045]
    s1 = [f'<svg viewBox="0 0 1190 275" style="width:100%; min-width:860px; height:auto; display:block;">{defs}']
    s1.append(timeline_row(48, [
        (xs5[0], txt(xs5[0], 20, "305 Glue on Wafer", sz=14), ""),
        (xs5[1], txt(xs5[1], 20, "701 Glue on Glass", sz=14), ""),
        (xs5[2], txt(xs5[2], 20, "W2W Bonding", sz=14), ""),
        (xs5[3], txt(xs5[3], 20, "Wafer Edge Trim", sz=14), ""),
        (xs5[4], txt(xs5[4], 20, "Wafer Grinding &amp; CMP(拋光)", sz=13.5), "")
    ]))
    # Node 1 & 2 top wafer stack
    for idx in [0, 1]:
        cx = xs5[idx]
        x0 = cx - 85
        s1.extend([
            rct(x0, 82, 170, 16, C_GLUE), txt(cx, 90, "305 Glue", sz=9.5, col="#002080"),
            rct(x0, 98, 170, 20, C_M1), txt(cx, 108, "Device (T18-M1)", sz=9.5, col="#000"),
            rct(x0, 118, 170, 13, C_OX), txt(cx, 124.5, "OX", sz=9.5, col="#fff"),
            rct(x0, 131, 170, 38, C_SI), txt(cx, 150, "Si", sz=10, col="#fff")
        ])
    # Node 2 bottom glass carrier
    cx2 = xs5[1]
    s1.extend([
        rct(cx2 - 85, 205, 170, 18, C_GLUE), txt(cx2, 214, "701 Glue", sz=9.5, col="#002080"),
        rct(cx2 - 85, 223, 170, 18, C_GLASS), txt(cx2, 232, "Glass", sz=9.5, col="#000")
    ])
    # Node 3: W2W Bonding (flipped)
    cx3 = xs5[2]
    s1.extend([
        rct(cx3 - 85, 82, 170, 36, C_SI), txt(cx3, 100, "Si", sz=10, col="#fff"),
        rct(cx3 - 85, 118, 170, 13, C_OX), txt(cx3, 124.5, "OX", sz=9.5, col="#fff"),
        rct(cx3 - 85, 131, 170, 20, C_M1), txt(cx3, 141, "Device (T18-M1)", sz=9.5, col="#000"),
        rct(cx3 - 85, 151, 170, 15, C_GLUE), txt(cx3, 158.5, "305 Glue", sz=9.5, col="#002080"),
        rct(cx3 - 85, 166, 170, 15, C_GLUE), txt(cx3, 173.5, "701 Glue", sz=9.5, col="#002080"),
        rct(cx3 - 85, 181, 170, 16, C_GLASS), txt(cx3, 189, "Glass", sz=9.5, col="#000")
    ])
    # Node 4: Wafer Edge Trim (stepped Si + sidewall 305 glue)
    cx4 = xs5[3]
    x4 = cx4 - 85
    s1.append(
        f'<polygon points="{x4+7},82 {x4+163},82 {x4+163},105 {x4+170},105 {x4+170},118 {x4},118 {x4},105 {x4+7},105" '
        f'fill="{C_SI}" stroke="#000" stroke-width="1.2"/>'
    )
    s1.append(txt(cx4, 100, "Si", sz=10, col="#fff"))
    s1.extend([
        rct(x4 + 7, 118, 156, 13, C_OX), txt(cx4, 124.5, "OX", sz=9.5, col="#fff"),
        rct(x4 + 7, 131, 156, 20, C_M1), txt(cx4, 141, "Device (T18-M1)", sz=9.5, col="#000"),
        f'<polygon points="{x4},105 {x4+7},105 {x4+7},151 {x4+163},151 {x4+163},105 {x4+170},105 {x4+170},166 {x4},166" fill="{C_GLUE}" stroke="#000" stroke-width="1.2"/>',
        txt(cx4, 158.5, "305 Glue", sz=9.5, col="#002080"),
        rct(x4, 166, 170, 15, C_GLUE), txt(cx4, 173.5, "701 Glue", sz=9.5, col="#002080"),
        rct(x4, 181, 170, 16, C_GLASS), txt(cx4, 189, "Glass", sz=9.5, col="#000")
    ])
    # Node 5: Wafer Grinding & CMP (thinned)
    cx5 = xs5[4]
    s1.extend([
        rct(cx5 - 85, 104, 170, 34, C_SI), txt(cx5, 121, "Si", sz=10, col="#fff"),
        rct(cx5 - 85, 138, 170, 12, C_OX), txt(cx5, 144, "OX", sz=9.5, col="#fff"),
        base_stack(cx5, 150, w=170, has_glass=True)
    ])
    s1.append("</svg>")
    svg_bonding = "".join(s1)

    # ---------------------------------------------------------------------
    # 2. TSV Etch Section
    # ---------------------------------------------------------------------
    s2 = [f'<svg viewBox="0 0 1190 225" style="width:100%; min-width:860px; height:auto; display:block;">{defs}']
    s2.append(timeline_row(48, [
        (xs5[0], sub_txt(xs5[0], 20, "Top SiO", "2", " CVD"), "37"),
        (xs5[1], txt(xs5[1], 20, "LIT Patterning", sz=14), "40"),
        (xs5[2], sub_txt(xs5[2], 20, "Surface SiO", "2", " Etch"), "45"),
        (xs5[3], txt(xs5[3], 20, "Bosch Si Etch", sz=14), "47"),
        (xs5[4], sub_txt(xs5[4], 20, "1st BT SiO", "2", " Etch"), "52")
    ]))
    configs_etch = [
        (xs5[0], False, "full", False, False, "#002080", "#fff", "#fff"),
        (xs5[1], True, "full", False, False, "#fff", "#fff", "#fff"),
        (xs5[2], True, "pillars", False, False, "#002080", "#fff", "#fff"),
        (xs5[3], True, "pillars", True, False, "#fff", "#fff", "#002080"),
        (xs5[4], True, "pillars", True, True, "#fff", "#002080", "#fff"),
    ]
    for cx, has_pr, t_ox, s_et, b_et, t_col, b_col, s_col in configs_etch:
        body_svg, pxs, _, y_ox1, _, y_ox2 = tsv_pillars_ox_si(
            cx, 102, top_ox=t_ox, si_etch=s_et, bot_ox_etch=b_et,
            ox_col_txt=t_col, bot_ox_col=b_col, si_col=s_col
        )
        if has_pr:
            for px in pxs:
                s2.append(rct(px, 82, 46, 20, C_PR))
                s2.append(txt(px + 23, 92, "PR", sz=9.5, col="#000"))
        s2.append(body_svg)
        s2.append(base_stack(cx, y_ox2 + 13, w=170, has_glass=True))
    s2.append("</svg>")
    svg_etch = "".join(s2)

    # ---------------------------------------------------------------------
    # 3. TSV Cu ECP (TSV Cu Section)
    # ---------------------------------------------------------------------
    xs4 = [210, 465, 720, 975]
    s3 = [f'<svg viewBox="0 0 1190 235" style="width:100%; min-width:820px; height:auto; display:block;">{defs}']
    n2_lbl = (
        sub_txt(xs4[1], 14, "2nd Bottom SiO", "2", " Etch", sz=13.5).replace('fill="#000"', 'fill="#1c3faa"') +
        txt(xs4[1], 32, "(蝕刻完M1會裸露)", sz=12.5, col="#1c3faa")
    )
    s3.append(timeline_row(56, [
        (xs4[0], sub_txt(xs4[0], 24, "Liner SiO", "2", " CVD"), "60"),
        (xs4[1], n2_lbl, "61"),
        (xs4[2], txt(xs4[2], 24, "Ti/Cu seed layer", sz=14), "64"),
        (xs4[3], txt(xs4[3], 24, "TSV Cu ECP", sz=14), "66")
    ], x1=90, x2=1110))

    for i, cx in enumerate(xs4):
        x0 = cx - 85.0
        pxs = [x0, x0 + 62.0, x0 + 124.0]
        vxs = [x0 + 46.0, x0 + 108.0]
        y_lt, y_ox1, y_si, y_ox2, y_m1 = 88.0, 102.0, 115.0, 153.0, 166.0
        # 3 pillars
        for px in pxs:
            s3.append(rct(px, y_lt, 46, 14, C_LINER))
            s3.append(txt(px + 23, y_lt + 7, "Liner", sz=9.5, col="#000"))
            s3.append(rct(px, y_ox1, 46, 13, C_OX))
            s3.append(txt(px + 23, y_ox1 + 6.5, "OX", sz=9, col="#fff"))
            s3.append(rct(px, y_si, 46, 38, C_SI))
            s3.append(txt(px + 23, y_si + 19, "Si", sz=9.5, col="#fff"))
            s3.append(rct(px, y_ox2, 46, 13, C_OX))
            s3.append(txt(px + 23, y_ox2 + 6.5, "OX", sz=9, col="#fff"))
        # Via sidewalls & bottoms
        for vx in vxs:
            s3.append(rct(vx, y_lt, 3.0, 78, C_LINER, sw=0.9))
            s3.append(rct(vx + 13.0, y_lt, 3.0, 78, C_LINER, sw=0.9))
            if i == 0:
                # Step 60: Liner covering bottom of via
                s3.append(rct(vx, y_m1 - 6, 16.0, 6, C_LINER, sw=0.9))
            elif i == 1:
                # Step 61: 2nd bottom etch dashed blue line
                s3.append(f'<line x1="{vx+3:.1f}" y1="{y_ox2:.1f}" x2="{vx+13:.1f}" y2="{y_ox2:.1f}" stroke="#0000ff" stroke-width="1.8" stroke-dasharray="2,2"/>')
            elif i == 2:
                # Step 64: conformal Ti/Cu seed layer
                s3.append(rct(vx + 3.0, y_lt - 2, 1.8, 80, C_SEED, sw=0.6))
                s3.append(rct(vx + 11.2, y_lt - 2, 1.8, 80, C_SEED, sw=0.6))
                s3.append(rct(vx + 3.0, y_m1 - 2.5, 10.0, 2.5, C_SEED, sw=0.6))
            elif i == 3:
                # Step 66: TSV Cu ECP filled
                s3.append(rct(vx + 3.0, y_lt - 2, 1.5, 80, C_SEED, sw=0.6))
                s3.append(rct(vx + 11.5, y_lt - 2, 1.5, 80, C_SEED, sw=0.6))
                s3.append(rct(vx + 4.5, y_lt - 2, 7.0, 80, C_CU, sw=0.9))
                s3.append(txt(vx + 8.0, y_lt + 39, "TSV Cu", sz=8.5, col="#002080", rot=90))
        if i in [2, 3]:
            for px in pxs:
                s3.append(rct(px, y_lt - 2.5, 46, 2.5, C_SEED, sw=0.6))
        s3.append(base_stack(cx, y_m1, w=170, has_glass=True))
    s3.append("</svg>")
    svg_cu_ecp = "".join(s3)

    # ---------------------------------------------------------------------
    # 4. Cu Pad (RDL) - 雙排共 10 個製程階段
    # ---------------------------------------------------------------------
    s4 = [f'<svg viewBox="0 0 1190 455" style="width:100%; min-width:860px; height:auto; display:block;">{defs}']
    # 第一排: Cu ECP (Over) -> Cu CMP -> RDL Pattern by C4 Mask -> Cu Etch -> PR Remove
    s4.append(timeline_row(44, [
        (xs5[0], txt(xs5[0], 18, "Cu ECP (Over)", sz=14), ""),
        (xs5[1], txt(xs5[1], 18, "Cu CMP", sz=14), ""),
        (xs5[2], txt(xs5[2], 18, "RDL Pattern by C4 Mask", sz=13.5), ""),
        (xs5[3], txt(xs5[3], 18, "Cu Etch", sz=14), ""),
        (xs5[4], txt(xs5[4], 18, "PR Remove", sz=14), "")
    ]))
    for i, cx in enumerate(xs5):
        core_svg, pxs, vxs, y_lt, _ = filled_tsv_core(cx, 102, has_glass=True)
        s4.append(core_svg)
        x0 = cx - 85.0
        # 覆蓋於兩顆 TSV Via 上方的 Cu Pad 位置
        pads_x = [vxs[0] - 11.0, vxs[1] - 11.0]  # 寬 38 居中於 16px via
        if i == 0:
            # Cu Overburden
            s4.append(rct(x0, 84, 170, 18, C_CU))
            s4.append(txt(cx, 93, "TSV Cu (Over)", sz=9.5, col="#000"))
        elif i == 1:
            # Cu CMP (薄銅層齊平/微凸於上方)
            s4.append(rct(x0, 95, 170, 7, C_CU))
        elif i == 2:
            s4.append(rct(x0, 95, 170, 7, C_CU))
            for pdx in pads_x:
                s4.append(rct(pdx, 81, 38, 14, C_PR))
                s4.append(txt(pdx + 19, 88, "PR", sz=9, col="#002080"))
        elif i == 3:
            for pdx in pads_x:
                s4.append(rct(pdx, 94, 38, 8, C_CU))
                s4.append(txt(pdx + 19, 98, "Cu", sz=8, col="#002080"))
                s4.append(rct(pdx, 80, 38, 14, C_PR))
                s4.append(txt(pdx + 19, 87, "PR", sz=9, col="#002080"))
        elif i == 4:
            for pdx in pads_x:
                s4.append(rct(pdx, 94, 38, 8, C_CU))
                s4.append(txt(pdx + 19, 98, "Cu", sz=8, col="#002080"))

    # 第二排: SiO2 CVD -> SiO2 CMP -> LIT Pattern for SiO2 Etch -> SiO2 Etch -> PR Remove
    s4.append(timeline_row(268, [
        (xs5[0], sub_txt(xs5[0], 242, "SiO", "2", " CVD"), ""),
        (xs5[1], sub_txt(xs5[1], 242, "SiO", "2", " CMP"), ""),
        (xs5[2], sub_txt(xs5[2], 242, "LIT Pattern for SiO", "2", " Etch", sz=13.5), ""),
        (xs5[3], sub_txt(xs5[3], 242, "SiO", "2", " Etch"), ""),
        (xs5[4], txt(xs5[4], 242, "PR Remove", sz=14), "")
    ]))
    for i, cx in enumerate(xs5):
        core_svg, pxs, vxs, y_lt, _ = filled_tsv_core(cx, 336, has_glass=True)
        x0 = cx - 85.0
        pads_x = [vxs[0] - 11.0, vxs[1] - 11.0]
        # 先畫 OX 鈍化保護層，再疊上 Cu Pad 以呈現包覆效果
        if i == 0:
            s4.append(rct(x0, 306, 170, 30, C_OX))
            s4.append(txt(cx, 318, "OX", sz=9.5, col="#002080"))
        elif i in [1, 2]:
            s4.append(rct(x0, 316, 170, 20, C_OX))
            s4.append(txt(cx, 323, "OX", sz=9, col="#002080" if i == 1 else "#000"))
        elif i in [3, 4]:
            # 開孔露出 Cu Pad 中央 (三段式 OX 保護層)
            ox_segs = [(x0, 39.0), (x0 + 69.0, 32.0), (x0 + 131.0, 39.0)]
            for sx, sw_ox in ox_segs:
                s4.append(rct(sx, 316, sw_ox, 20, C_OX))
                s4.append(txt(sx + sw_ox / 2.0, 326, "OX", sz=8.5, col="#002080"))
        if i in [2, 3]:
            pr_segs = [(x0, 39.0), (x0 + 69.0, 32.0), (x0 + 131.0, 39.0)]
            for sx, sw_pr in pr_segs:
                s4.append(rct(sx, 302, sw_pr, 14, C_PR))
                s4.append(txt(sx + sw_pr / 2.0, 309, "PR", sz=8.5, col="#002080"))
        s4.append(core_svg)
        for pdx in pads_x:
            s4.append(rct(pdx, 328, 38, 8, C_CU))
            s4.append(txt(pdx + 19, 332, "Cu", sz=8, col="#000"))
    s4.append("</svg>")
    svg_cu_pad = "".join(s4)

    # ---------------------------------------------------------------------
    # 5. Bumping Section
    # ---------------------------------------------------------------------
    xb4 = [175, 425, 675, 925]
    s5 = [f'<svg viewBox="0 0 1190 250" style="width:100%; min-width:820px; height:auto; display:block;">{defs}']
    s5.append(timeline_row(48, [
        (xb4[0], txt(xb4[0], 20, "Ti/Cu seed layer", sz=14), ""),
        (xb4[1], txt(xb4[1], 20, "JSR Patterning", sz=14), ""),
        (xb4[2], txt(xb4[2], 20, "Cu Stud + Sn/Ag Bump", sz=14), ""),
        (xb4[3], txt(xb4[3], 20, "JSR Remove", sz=14), "")
    ], x1=65, x2=1120))
    for i, cx in enumerate(xb4):
        x0 = cx - 85.0
        core_svg, pxs, vxs, y_lt, _ = filled_tsv_core(cx, 126, has_glass=True)
        pads_x = [vxs[0] - 11.0, vxs[1] - 11.0]
        ox_segs = [(x0, 39.0), (x0 + 69.0, 32.0), (x0 + 131.0, 39.0)]
        for sx, sw_ox in ox_segs:
            s5.append(rct(sx, 108, sw_ox, 18, C_OX))
            s5.append(txt(sx + sw_ox / 2.0, 117, "OX", sz=8.5, col="#fff"))
        s5.append(core_svg)
        for pdx in pads_x:
            s5.append(rct(pdx, 118, 38, 8, C_CU))
            s5.append(txt(pdx + 19, 122, "Cu", sz=8, col="#000"))
        # Conformal orange seed line across OX & Cu Pad openings
        if i in [0, 1, 2]:
            s5.append(f'<polyline points="{x0},107 {x0+39},107 {x0+39},117 {x0+69},117 {x0+69},107 {x0+101},107 {x0+101},117 {x0+131},117 {x0+131},107 {x0+170},107" fill="none" stroke="{C_SEED}" stroke-width="2.5"/>')
        if i in [1, 2]:
            for sx, sw_j in ox_segs:
                s5.append(rct(sx, 80, sw_j, 26, C_PR))
                s5.append(txt(sx + sw_j / 2.0, 93, "JSR", sz=8.5, col="#002080" if i == 1 else "#000"))
        if i in [2, 3]:
            open_xs = [x0 + 39.0, x0 + 101.0]  # 寬 30 的 Bump 開口
            for ox_p in open_xs:
                if i == 3:
                    s5.append(rct(ox_p, 115, 30, 3, C_SEED, sw=0.6))
                s5.append(rct(ox_p, 105, 30, 11, C_STUD))
                s5.append(txt(ox_p + 15, 110.5, "Cu", sz=8, col="#002080"))
                s5.append(rct(ox_p, 80, 30, 25, C_SN))
                s5.append(txt(ox_p + 15, 92.5, "SnAg", sz=8.5, col="#002080"))
    s5.append("</svg>")
    svg_bump = "".join(s5)

    # ---------------------------------------------------------------------
    # 6. Dicing Section
    # ---------------------------------------------------------------------
    s6 = [f'<svg viewBox="0 0 1190 250" style="width:100%; min-width:860px; height:auto; display:block;">{defs}']
    s6.append(timeline_row(48, [
        (xs5[0], txt(xs5[0], 20, "Cu/Ti seed layer Etch", sz=14), "83"),
        (xs5[1], txt(xs5[1], 20, "Bump cover by PR", sz=14), "88"),
        (xs5[2], txt(xs5[2], 20, "Dicing tape lamination", sz=14), "89"),
        (xs5[3], txt(xs5[3], 20, "Laser Debond", sz=14), "90"),
        (xs5[4], txt(xs5[4], 20, "Dicing &amp; Pick-up Chip-let", sz=13.5), "91")
    ]))
    for i, cx in enumerate(xs5):
        has_gls = (i < 3)
        core_svg, pxs, vxs, y_lt, _ = filled_tsv_core(cx, 126, has_glass=has_gls)
        x0 = cx - 85.0
        # PR 保護層 (i == 1, 2, 3)
        if i in [1, 2, 3]:
            s6.append(rct(x0, 94, 170, 32, C_PR))
            s6.append(txt(cx, 110, "PR", sz=9.5, col="#002080" if i == 1 else "#000"))
        # Blue Tape (i == 2, 3)
        if i in [2, 3]:
            s6.append(rct(x0, 74, 170, 20, C_TAPE))
            s6.append(txt(cx, 84, "Blue Tape", sz=9.5, col="#002080" if i == 2 else "#000"))
        s6.append(core_svg)
        # Bumps on top of vias
        for vx in vxs:
            bx = vx - 10.0  # 寬 36
            s6.append(rct(bx, 123, 36, 3.5, C_SEED, sw=0.7))
            s6.append(rct(bx + 2, 111, 32, 12, C_STUD))
            s6.append(txt(bx + 18, 117, "Cu", sz=8.5, col="#000"))
            s6.append(rct(bx + 2, 97, 32, 14, C_SN))
            s6.append(txt(bx + 18, 104, "Sn", sz=8.5, col="#000"))
    s6.append("</svg>")
    svg_dicing = "".join(s6)

    return {
        "bonding": svg_bonding,
        "etch": svg_etch,
        "cu_ecp": svg_cu_ecp,
        "cu_pad": svg_cu_pad,
        "bump": svg_bump,
        "dicing": svg_dicing,
    }

# =========================================================================
# 2. 將所有彈出視窗定義在全域
# =========================================================================

@st.dialog(" ", width="large")
def show_ongoing_action_dialog(tw_id, ts_no, target_row_dict, avail_steps):
    safe_ts_no = clean_step(ts_no)
    st.markdown(f"**Wafer ID:** `{tw_id}` | **Step:** `{safe_ts_no}`")
    st.caption("*(💡 This Wafer ID has been synced to the Wafer History tab)*")
    
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
    
    spc_data = st.text_input("**Data**")
    result_image = st.file_uploader("**Result Image**", type=["png", "jpg", "jpeg"], key=f"img_{tw_id}_{safe_ts_no}")
    
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
            "Jump / Skip Stage", 
            "Hold", 
            "Bank in", 
            "Scrap"
        ]
        
    action_type = st.radio("Wafer Action Options", options=options, horizontal=True, label_visibility="collapsed")
    
    jump_target, comment = None, ""
    
    if action_type == "Jump / Skip Stage":
        jump_target = st.selectbox("Jump to step (Forward or Backward):", options=avail_steps)
        comment = st.text_input("Reason for jump/skip:")
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
        elif action_type == "Jump / Skip Stage": action_name = "Jump / Skip Stage"
        elif action_type == "Hold": action_name = "Hold"
        elif action_type == "Release Hold": action_name = "Unhold"
        elif action_type == "Bank in": action_name = "Bank"
        elif action_type == "Scrap": action_name = "Scrap"
        elif action_type == "Unscrap": action_name = "Unscrap"
        
        st.session_state.ongoing_action = {
            "name": action_name, 
            "w_id": tw_id, 
            "s_no": safe_ts_no,
            "spc": spc_data, 
            "img": result_image, 
            "jump_step": jump_target, 
            "comment": comment,
            "tool": edit_tool,
            "recipe": edit_recipe,
            "cp": edit_cp,
            "avail_steps": avail_steps,
            "orig_row": target_row_dict
        }
        st.rerun()

    st.markdown("---")
    with st.expander("📜 View Wafer History", expanded=True):
        df_route_hist, _ = fetch_route_data_via_csv("route_template")
        df_logs_hist, _ = fetch_route_data_via_csv("wafer_status")
        if not df_route_hist.empty:
            wafer_col_list = [c for c in df_route_hist.columns if "Wafer" in c or "wafer" in c]
            if wafer_col_list:
                actual_string_col = wafer_col_list[0]
                filtered_route = df_route_hist[df_route_hist[actual_string_col].astype(str).str.upper() == str(tw_id).upper()]
                if not filtered_route.empty:
                    display_route = filtered_route.copy().reset_index(drop=True)
                    if "Step" in display_route.columns:
                        display_route["Step"] = display_route["Step"].apply(clean_step)
                    
                    hn_col_hist = next((c for c in display_route.columns if str(c).strip().lower() == "hold note"), None)
                    if hn_col_hist and not df_logs_hist.empty:
                        hold_map_hist = build_log_hold_note_map(df_logs_hist)
                        wid_upper = str(tw_id).strip().upper()
                        for idx, r in display_route.iterrows():
                            if not str(r.get(hn_col_hist, "")).strip():
                                s_clean = clean_step(r.get("Step", ""))
                                if (wid_upper, s_clean) in hold_map_hist:
                                    display_route.at[idx, hn_col_hist] = hold_map_hist[(wid_upper, s_clean)]

                    wip_row_idx = 0
                    wip_is_hold = False
                    fco_col_hist = next((c for c in display_route.columns if "check out" in str(c).lower()), "Check out Time")
                    has_scrap = False
                    for idx, row in display_route.iterrows():
                        co_val = str(row.get(fco_col_hist, "")).strip().upper()
                        if co_val == "SCRP":
                            has_scrap = True
                            break
                    
                    if not has_scrap:
                        for idx, row in display_route.iterrows():
                            co_val = str(row.get(fco_col_hist, "")).strip().upper()
                            if co_val in ["", "NAN", "INPR", "HOLD", "BANK"]:
                                wip_row_idx = idx
                                if co_val == "HOLD":
                                    wip_is_hold = True
                                break

                    target_cols_order = [
                        "step", "stage owner", "step description", "process tool", "recipe", 
                        "check point", "spc data", "result", "check out time", "q time", 
                        "spc group", "target", "ucl", "lcl", "spc result", "hold note"
                    ]
                    
                    final_cols = []
                    for tgt in target_cols_order:
                        for c in display_route.columns:
                            if str(c).strip().lower() == tgt:
                                final_cols.append(c)
                                break
                                
                    display_route_show = display_route[final_cols]
                    
                    col_cfg = {
                        "Result": st.column_config.ImageColumn("Result (預覽圖片)", help="上傳的檢驗圖片")
                    }
                    for col_name in display_route_show.columns:
                        c_lower = str(col_name).lower().strip()
                        if c_lower in ["step description", "recipe", "hold note"]:
                            col_cfg[col_name] = st.column_config.TextColumn(width="large")

                    def highlight_wip_row(row):
                        if row.name == wip_row_idx and not has_scrap:
                            if wip_is_hold:
                                return ['background-color: #fff3cd; color: #856404; font-weight: bold;'] * len(row)
                            return ['background-color: #d4edda; color: #155724; font-weight: bold;'] * len(row)
                        return [''] * len(row)
                    
                    styled_display_route = display_route_show.style.apply(highlight_wip_row, axis=1)
                            
                    st.dataframe(
                        styled_display_route, 
                        use_container_width=True, 
                        hide_index=True, 
                        column_config=col_cfg
                    )
                else:
                    st.info("No history found for this wafer.")
        else:
            st.info("Cannot connect to history database.")

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
    
    cd_spc, cd_hn = st.columns(2)
    with cd_spc:
        st.markdown("**SPC Data**")
        spc_data = st.text_input("Update SPC Data:", value=current_comment, label_visibility="collapsed")
    with cd_hn:
        st.markdown("**Hold Note**")
        hn_col_key = next((k for k in target_row_dict.keys() if str(k).strip().lower() == "hold note"), "Hold Note")
        edit_hold_note = st.text_input("Update Hold Note:", value=str(target_row_dict.get(hn_col_key, "")).strip(), label_visibility="collapsed")
    
    st.markdown("**Result Image**")
    result_image = st.file_uploader("Upload new image to overwrite", type=["png", "jpg", "jpeg"], key=f"hist_img_{tw_id}_{ts_no}")
    
    st.markdown("---")
    st.markdown("**Status Management (Rework / Undo)**")
    
    current_fco = str(target_row_dict.get("Check out Time", "")).strip()
    st.markdown(f"**Current Status / Time:** `{current_fco if current_fco else 'Empty'}`")
    
    fco_action = st.radio(
        "Modify Check out Time:",
        ["Keep Original (保持原本狀態)", "Set New Date & Time (設定新時間)", "Clear Time (清除時間以退站)"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"fco_action_{tw_id}_{ts_no}"
    )
    
    default_date = datetime.datetime.now().date()
    default_time = datetime.datetime.now().time()
    
    if current_fco:
        try:
            parsed_dt = pd.to_datetime(current_fco)
            default_date = parsed_dt.date()
            default_time = parsed_dt.time()
        except:
            pass
            
    cd1, cd2 = st.columns(2)
    is_disabled = st.session_state[f"fco_action_{tw_id}_{ts_no}"] != "Set New Date & Time (設定新時間)"
    
    with cd1:
        sel_date = st.date_input("Select Date", value=default_date, disabled=is_disabled)
    with cd2:
        sel_time = st.time_input("Select Time", value=default_time, step=60, disabled=is_disabled)
        
    if fco_action == "Keep Original (保持原本狀態)":
        edit_fco = current_fco
    elif fco_action == "Clear Time (清除時間以退站)":
        edit_fco = ""
    else:
        edit_fco = f"{sel_date.strftime('%Y-%m-%d')} {sel_time.strftime('%H:%M:%S')}"
    
    if st.button("Confirm and Submit", type="primary", use_container_width=True):
        st.session_state.history_edit_action = {
            "w_id": tw_id,
            "s_no": ts_no,
            "spc": spc_data,
            "hold_note": edit_hold_note,
            "hn_col_name": hn_col_key,
            "img": result_image,
            "tool": edit_tool,
            "recipe": edit_recipe,
            "cp": edit_cp,
            "fco": edit_fco,
            "orig_row": target_row_dict
        }
        st.rerun()

all_tabs = st.tabs([
    "🔍 Ongoing Wafer", 
    "📜 Wafer History", 
    "📤 Upload New Wafer", 
    "📦 Bank Wafers", 
    "📊 Wafer Overview", 
    "📈 Key Stage Report (KSR)"
])

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
        enc_s_no = requests.utils.quote(gas_safe_step(pa["s_no"]))
        
        final_result_link = ""
        if pa["img"] is not None:
            with st.spinner("Uploading Image..."):
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
                    
        fields = {"Process Tool": pa["tool"], "Recipe": pa["recipe"], "Check point": pa["cp"]}
        for f_name, f_val in fields.items():
            orig_val = str(pa["orig_row"].get(f_name, "")).strip()
            new_v_str = str(f_val).strip()
            if new_v_str != orig_val:
                safe_val = new_v_str if new_v_str != "" else " "
                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name={requests.utils.quote(f_name)}&new_value={requests.utils.quote(safe_val)}")
                
        new_spc_val = str(pa["spc"]).strip()
        if new_spc_val:
            if "SPC data" in pa["orig_row"]:
                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name=SPC%20data&new_value={requests.utils.quote(new_spc_val)}")
            elif "Comments" in pa["orig_row"]:
                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name=Comments&new_value={requests.utils.quote(new_spc_val)}")
            elif "備註" in pa["orig_row"]:
                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name=備註&new_value={requests.utils.quote(new_spc_val)}")
                
        if final_result_link:
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name=Result&new_value={requests.utils.quote(final_result_link)}")
                
        enc_time = requests.utils.quote(now_str)
        raw_comment_str = str(pa.get("comment", "")).strip()
        enc_comment = requests.utils.quote(raw_comment_str)
        act = pa["name"]
        hn_actual_col = next((k for k in pa["orig_row"].keys() if str(k).strip().lower() == "hold note"), None)
        
        if act == "Check out":
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Check%20out&comment={enc_comment}&time={enc_time}")
        elif act == "Scrap":
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Scrap&comment={enc_comment}&time={enc_time}")
        elif act == "Unscrap":
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Unscrap&comment={enc_comment}&time={enc_time}")
        elif act == "Hold":
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Hold&comment={enc_comment}&time={enc_time}")
            if hn_actual_col and raw_comment_str:
                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name={requests.utils.quote(hn_actual_col)}&new_value={enc_comment}")
        elif act == "Unhold":
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Unhold&comment={enc_comment}&time={enc_time}")
            if hn_actual_col:
                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name={requests.utils.quote(hn_actual_col)}&new_value=%20")
        elif act == "Bank":
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Bank&comment={enc_comment}&time={enc_time}")
        elif act == "Jump / Skip Stage":
            curr_step = clean_step(pa["s_no"])
            target_step = clean_step(pa["jump_step"])
            avail = [clean_step(x) for x in pa["avail_steps"]]
            
            try:
                curr_idx = avail.index(curr_step)
                tgt_idx = avail.index(target_step)
            except Exception as e:
                curr_idx, tgt_idx = 0, 0
                st.error(f"Cannot find Step Index: {curr_step} or {target_step}")
                
            if tgt_idx < curr_idx:
                for i in range(tgt_idx, curr_idx + 1):
                    enc_step = requests.utils.quote(gas_safe_step(avail[i]))
                    urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_step}&column_name=Check%20out%20Time&new_value=%20")
            elif tgt_idx > curr_idx:
                enc_target = requests.utils.quote(gas_safe_step(target_step))
                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&action=Skip&comment={enc_comment}&time={enc_time}&target_step={enc_target}")
            
        if urls_to_send:
            with st.spinner(f"Syncing to Cloud (Sequential Safe Mode)..."):
                has_error = False
                success_count = 0
                
                session = requests.Session()
                for url in urls_to_send:
                    try:
                        res = session.get(url, timeout=20, allow_redirects=True)
                        if res.status_code not in [200, 302]:
                            st.error(f"HTTP Error {res.status_code}: {res.text}")
                            has_error = True
                        elif "Error" in res.text or "Exception" in res.text or "找不到對應的 Wafer ID 與 Step" in res.text:
                            st.error(f"GAS Error: {res.text}")
                            has_error = True
                        else:
                            success_count += 1
                    except Exception as e:
                        st.error(f"Request Exception: {str(e)}")
                        has_error = True

                if has_error:
                    st.warning(f"⚠️ 請求遭遇異常 (成功 {success_count}/{len(urls_to_send)})，請截圖本畫面回報開發人員！")
                    time.sleep(5)
                else:
                    st.success(f"Action Successfully Submitted! ({success_count} requests)")
                    time.sleep(1.2)
                    
                st.cache_data.clear()
                st.session_state.ongoing_table_ver += 1
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
        module_col = next((c for c in df_route.columns if "module" in str(c).lower()), "Module")
        
        if wafer_col in df_route.columns:
            def get_lot_number(wid):
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
                lot_owner = ""
                
                for _, row in w_group.iterrows():
                    raw_s = clean_step(row.get(step_col, ""))
                    if raw_s == "1":
                        lot_owner = str(row.get(owner_col, ""))
                        break
                if not lot_owner and not w_group.empty:
                    lot_owner = str(w_group.iloc[0].get(owner_col, ""))
                
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
                    raw_step = clean_step(active_row.get(step_col, ""))
                    
                    sub_steps = [clean_step(x) for x in w_group[step_col] if "." in clean_step(x)]
                    has_sub_route = len(sub_steps) > 0
                    
                    curr_main_val = 0
                    curr_sub_val = 0
                    
                    if "." in raw_step:
                        parts = raw_step.split(".")
                        curr_main_val = int(re.findall(r'\d+', parts[0])[0]) if re.findall(r'\d+', parts[0]) else 0
                        curr_sub_val = int(re.findall(r'\d+', parts[1])[0]) if re.findall(r'\d+', parts[1]) else 0
                    else:
                        curr_main_val = int(re.findall(r'\d+', raw_step)[0]) if re.findall(r'\d+', raw_step) else 0
                        if has_sub_route:
                            sub_main_str = sub_steps[0].split(".")[0]
                            sub_main_val = int(re.findall(r'\d+', sub_main_str)[0]) if re.findall(r'\d+', sub_main_str) else 0
                            if curr_main_val > sub_main_val:
                                curr_sub_val = len(sub_steps)
                            else:
                                curr_sub_val = 0
                                
                    if has_sub_route:
                        actual_sub_val = raw_step.split(".")[1] if "." in raw_step else curr_sub_val
                        wip_step_no = f"{curr_main_val}/92 (Sub: {actual_sub_val}/{len(sub_steps)})"
                    else:
                        wip_step_no = f"{curr_main_val}/92"
                    
                    s_owner = str(active_row.get(owner_col, ""))
                    s_desc = str(active_row.get(desc_col, ""))
                    s_tool = str(active_row.get(tool_col, active_row.get("Process Tool", "")))
                    s_recipe = str(active_row.get(recipe_col, active_row.get("Recipe", "")))
                    s_module = str(active_row.get(module_col, ""))
                    
                    wip_data_list.append({
                        "Lot Owner": lot_owner,
                        "ID (Wafer)": wid,
                        "Step": wip_step_no,
                        "Stage Owner": s_owner,
                        "Module": s_module,
                        "Step Description": s_desc,
                        "Process Tool": s_tool,
                        "Recipe": s_recipe,
                        "_raw_step": raw_step,
                        "_avail_steps": [clean_step(x) for x in w_group[step_col].tolist()],
                        "_row_dict": active_row.to_dict()
                    })
            
            if wip_data_list:
                df_wip = pd.DataFrame(wip_data_list)
                display_df = df_wip[["Lot Owner", "ID (Wafer)", "Step", "Stage Owner", "Module", "Step Description", "Process Tool", "Recipe"]]
                styled_df = display_df.style.set_properties(**{'text-align': 'center'})
                
                table_placeholder = st.empty()
                curr_table_key = f"ongoing_wafer_table_{st.session_state.ongoing_table_ver}"
                
                selection = table_placeholder.dataframe(
                    styled_df,
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    key=curr_table_key
                )
                
                curr_sel = selection.get("selection", {}).get("rows", [])
                
                if curr_sel:
                    selected_idx = curr_sel[0]
                    selected_item = wip_data_list[selected_idx]
                    
                    st.session_state.search_wafer_id_history = str(selected_item['ID (Wafer)']).strip()
                    
                    st.session_state.ongoing_table_ver += 1
                    if curr_table_key in st.session_state:
                        del st.session_state[curr_table_key]
                    
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
        enc_s_no = requests.utils.quote(gas_safe_step(pa["s_no"]))
        
        final_result_link = ""
        if pa["img"] is not None:
            with st.spinner("Uploading Image..."):
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
        
        new_spc = str(pa['spc']).strip()
        for col_name in ["SPC data", "Comments", "備註"]:
            if col_name in pa["orig_row"]:
                orig_val = str(pa["orig_row"].get(col_name, "")).strip()
                if new_spc != orig_val:
                    safe_val = new_spc if new_spc != "" else " "
                    urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name={requests.utils.quote(col_name)}&new_value={requests.utils.quote(safe_val)}")

        if final_result_link:
            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name=Result&new_value={requests.utils.quote(final_result_link)}")

        fields = {"Process Tool": pa["tool"], "Recipe": pa["recipe"], "Check point": pa["cp"], "Check out Time": pa.get("fco", "")}
        if pa.get("hn_col_name") in pa["orig_row"]:
            fields[pa["hn_col_name"]] = pa.get("hold_note", "")

        for f_name, f_val in fields.items():
            orig_val = str(pa["orig_row"].get(f_name, "")).strip()
            new_v_str = str(f_val).strip()
            if new_v_str != orig_val:
                safe_val = new_v_str if new_v_str != "" else " "
                urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={enc_w_id}&step_no={enc_s_no}&column_name={requests.utils.quote(f_name)}&new_value={requests.utils.quote(safe_val)}")

        if urls_to_send:
            with st.spinner("Syncing modifications to Cloud (Sequential Safe Mode)..."):
                has_error = False
                success_count = 0
                session = requests.Session()
                for url in urls_to_send:
                    try:
                        res = session.get(url, timeout=20, allow_redirects=True)
                        if res.status_code not in [200, 302]:
                            st.error(f"HTTP Error {res.status_code}: {res.text}")
                            has_error = True
                        elif "Error" in res.text or "Exception" in res.text or "找不到對應的 Wafer ID 與 Step" in res.text:
                            st.error(f"GAS Error: {res.text}")
                            has_error = True
                        else:
                            success_count += 1
                    except Exception as e:
                        st.error(f"Request Exception: {str(e)}")
                        has_error = True
                        
                if has_error:
                    st.warning(f"⚠️ 請求遭遇異常 (成功 {success_count}/{len(urls_to_send)})，請截圖本畫面回報開發人員！")
                    time.sleep(5)
                else:
                    st.success(f"Modifications Successfully Submitted! ({success_count} requests)")
                    time.sleep(1.2)
                st.cache_data.clear()
                st.rerun()
        else:
            st.info("No modifications detected.")
            time.sleep(1)
            st.rerun()
    
    col_input1, col_input2 = st.columns([3, 1], vertical_alignment="bottom")
    with col_input1: 
        search_id = st.text_input("Please Key in Wafer ID", key="search_wafer_id_history")
    with col_input2:
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
                display_route["Step"] = display_route["Step"].apply(clean_step)

            original_display_route = display_route.copy()
            hn_col_main = next((c for c in display_route.columns if str(c).strip().lower() == "hold note"), None)
            if hn_col_main:
                hold_map_main = build_log_hold_note_map(df_logs)
                wid_upper = str(search_id).strip().upper()
                for idx, r in display_route.iterrows():
                    if not str(r.get(hn_col_main, "")).strip():
                        s_clean = clean_step(r.get("Step", ""))
                        if (wid_upper, s_clean) in hold_map_main:
                            display_route.at[idx, hn_col_main] = hold_map_main[(wid_upper, s_clean)]
            
            wip_row_idx = 0
            wip_is_hold = False
            fco_col_hist = next((c for c in display_route.columns if "check out" in str(c).lower()), "Check out Time")
            has_scrap = False
            for idx, row in display_route.iterrows():
                co_val = str(row.get(fco_col_hist, "")).strip().upper()
                if co_val == "SCRP":
                    has_scrap = True
                    break
            
            if not has_scrap:
                for idx, row in display_route.iterrows():
                    co_val = str(row.get(fco_col_hist, "")).strip().upper()
                    if co_val in ["", "NAN", "INPR", "HOLD", "BANK"]:
                        wip_row_idx = idx
                        if co_val == "HOLD":
                            wip_is_hold = True
                        break

            target_cols_order = [
                "step", "stage owner", "step description", "process tool", "recipe", 
                "check point", "spc data", "result", "check out time", "q time", 
                "spc group", "target", "ucl", "lcl", "spc result", "hold note"
            ]
            
            final_cols = []
            for tgt in target_cols_order:
                for c in display_route.columns:
                    if str(c).strip().lower() == tgt:
                        final_cols.append(c)
                        break
                        
            display_route_show = display_route[final_cols]
            
            col_cfg = {
                "Result": st.column_config.ImageColumn("Result (預覽圖片)", help="上傳的檢驗圖片")
            }
            for col_name in display_route_show.columns:
                c_lower = str(col_name).lower().strip()
                if c_lower in ["step description", "recipe", "hold note"]:
                    col_cfg[col_name] = st.column_config.TextColumn(width="large")

            def highlight_wip_row(row):
                if row.name == wip_row_idx and not has_scrap:
                    if wip_is_hold:
                        return ['background-color: #fff3cd; color: #856404; font-weight: bold;'] * len(row)
                    return ['background-color: #d4edda; color: #155724; font-weight: bold;'] * len(row)
                return [''] * len(row)
            
            styled_display_route = display_route_show.style.apply(highlight_wip_row, axis=1)

            selected_route_row = st.dataframe(
                styled_display_route, 
                use_container_width=True, 
                hide_index=True, 
                on_select="rerun", 
                selection_mode="single-row", 
                key="history_route_table", 
                column_config=col_cfg
            )
            
            if selected_route_row and selected_route_row.get("selection", {}).get("rows"):
                selected_idx = selected_route_row["selection"]["rows"][0]
                target_step_no = clean_step(original_display_route.iloc[selected_idx].get("Step", ""))
                target_row_data = original_display_route.iloc[selected_idx].to_dict()
                if hn_col_main and not str(target_row_data.get(hn_col_main, "")).strip():
                    filled_hn = str(display_route.iloc[selected_idx].get(hn_col_main, "")).strip()
                    if filled_hn:
                        target_row_data[hn_col_main] = filled_hn
                
                st.markdown("---")
                
                hc1, hc2 = st.columns([4, 1], vertical_alignment="center")
                hc1.markdown(f"<div style='font-size: 20px; font-weight: bold;'>Step {target_step_no} Action History</div>", unsafe_allow_html=True)
                if hc2.button("Edit Data", use_container_width=True, type="secondary"):
                    show_history_edit_dialog(search_id, target_step_no, target_row_data)
                
                log_wafer_col = [c for c in df_logs.columns if "Wafer" in c or "晶圓" in c][0]
                clean_log_steps = df_logs["Step"].apply(clean_step)
                step_logs = df_logs[(df_logs[log_wafer_col].astype(str).str.upper() == search_id.upper()) & (clean_log_steps == target_step_no)]
                
                mother_result_val = str(original_display_route.iloc[selected_idx].get("Result", "")).strip()
                result_html = ""
                if mother_result_val.startswith("http"):
                    result_html = f'<a href="{mother_result_val}" target="_blank"><img src="{mother_result_val}" style="max-height: 80px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); cursor: zoom-in;"></a>'
                else:
                    result_html = mother_result_val

                mother_spc_val = str(original_display_route.iloc[selected_idx].get("SPC data", "")).strip()
                if not mother_spc_val: mother_spc_val = str(original_display_route.iloc[selected_idx].get("Comments", "")).strip()
                if not mother_spc_val: mother_spc_val = str(original_display_route.iloc[selected_idx].get("備註", "")).strip()

                if not step_logs.empty:
                    html_parts = ['<div class="rwd-table-scroll" style="font-size: 14px;"><table style="width: 100%; min-width: 650px; border-collapse: collapse; border: 1px solid #ddd;">']
                    html_parts.append('<tr style="background-color: #f8f9fa; color: #333;"><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 12%;">動作 (Action)</th><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 20%;">日期與時間</th><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 26%;">Action Record</th><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 22%;">SPC data</th><th style="padding: 10px; border: 1px solid #ddd; text-align: center; width: 20%;">Result (檢驗圖片)</th></tr>')
                    
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
                        
                        html_parts.append(f'<tr style="background-color: {bg_color};"><td style="padding: 10px; border: 1px solid #ddd; text-align: center; font-weight: bold;">{action_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: center; white-space: nowrap;">{time_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: center; color: {text_color}; font-weight: bold;">{hold_note_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{spc_val}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: center;">{result_html}</td></tr>')
                    html_parts.append('</table></div>')
                    st.markdown("".join(html_parts), unsafe_allow_html=True)
                
                else:
                    st.info("No Record")
                    if mother_result_val.startswith("http"):
                        st.markdown("---")
                        st.markdown("**Uploaded Result Image:**")
                        st.markdown(f"<a href='{mother_result_val}' target='_blank'><img src='{mother_result_val}' style='max-width: 100%; max-height: 250px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); cursor: zoom-in;'></a>", unsafe_allow_html=True)
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
                
                rep_owner = ""
                rep_team = ""
                for _, r in w_group.iterrows():
                    raw_s = clean_step(r.get(step_col, ""))
                    if raw_s == "1":
                        rep_owner = str(r.get(owner_col, ""))
                        rep_team = str(r.get(team_col, ""))
                        break
                if not rep_owner and not w_group.empty:
                    rep_owner = str(w_group.iloc[0].get(owner_col, ""))
                    rep_team = str(w_group.iloc[0].get(team_col, ""))
                
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
                                bank_step_no = clean_step(row.get(step_col, ""))
                                bank_comment = str(row.get(comment_col, ""))
                            break
                            
                if is_banked:
                    first_row = w_group.iloc[0]
                    banked_wafers.append({
                        "Select": False, 
                        "Shuttle Name": str(first_row.get(shuttle_col, "")), 
                        "Owner": rep_owner, 
                        "團隊": rep_team, 
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
                            enc_s = requests.utils.quote(gas_safe_step(s))
                            urls_to_send.append(f"{MY_ORGANIZATION_GAS_URL}?wafer_id={requests.utils.quote(str(w))}&step_no={enc_s}&action=Kick%20off&comment={enc_comment}&time={enc_time}")
                            
                        with st.spinner(f"Syncing Kick off for {len(selected_wids)} wafers..."):
                            has_err = False
                            
                            def send_req(url):
                                try:
                                    return requests.get(url, timeout=15, allow_redirects=False)
                                except:
                                    return None
                                    
                            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                                results = executor.map(send_req, urls_to_send)
                                
                            for res in results:
                                if res and res.status_code not in [200, 302] and "Error" in res.text:
                                    st.error(f"Cloud Error: {res.text}")
                                    has_err = True
                                    
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
                match = re.search(r'lot(\d+)', str(wid).lower())
                return int(match.group(1)) if match else 999999
                
            df_route_bank['_lot_num'] = df_route_bank[wafer_col].apply(get_lot_number)
            df_route_bank = df_route_bank.sort_values(by=['_lot_num', wafer_col])
            
            for shuttle, s_group in df_route_bank.groupby(shuttle_col, sort=False):
                if str(shuttle).strip() == "": continue
                
                rep_owner = ""
                rep_team = ""
                for _, r in s_group.iterrows():
                    raw_s = clean_step(r.get(step_col, ""))
                    if raw_s == "1":
                        rep_owner = str(r.get(owner_col, ""))
                        rep_team = str(r.get(team_col, ""))
                        break
                if not rep_owner and not s_group.empty:
                    rep_owner = str(s_group.iloc[0].get(owner_col, ""))
                    rep_team = str(s_group.iloc[0].get(team_col, ""))
                
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
                        "Owner": rep_owner,
                        "團隊": rep_team,
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
    st.markdown("<div style='font-size: 20px; font-weight: bold; padding-bottom: 0.5rem;'>Active Interposer Wafer Status</div>", unsafe_allow_html=True)
    st.markdown("<div class='mobile-swipe-hint'>📱 手機檢視可左右滑動表格以維持最佳比例</div>", unsafe_allow_html=True)
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
            html_table = (
                '<style>'
                '.overview-table { width: 100%; min-width: 860px; border-collapse: collapse; font-family: sans-serif; font-size: 14px; }'
                '.overview-table th { background-color: #f8f9fa; padding: 12px 10px; border: 1px solid #dee2e6; text-align: left; font-weight: bold; color: #495057; white-space: nowrap; }'
                '.overview-table td { padding: 10px; border: 1px solid #dee2e6; text-align: left; vertical-align: middle; color: #212529; }'
                '.overview-table .merged-cell { text-align: center; vertical-align: middle; font-weight: bold; background-color: #ffffff; color: #0d6efd; white-space: nowrap; }'
                '.overview-table .owner-team-cell { text-align: center; vertical-align: middle; background-color: #ffffff; }'
                '.prog-wrapper { display: flex; align-items: center; width: 100%; min-width: 180px; }'
                '.prog-container { background-color: #e9ecef; border-radius: 4px; flex-grow: 1; height: 16px; overflow: hidden; }'
                '.prog-bar { background-color: #28a745; height: 100%; border-radius: 4px; transition: width 0.4s ease; }'
                '.prog-text { margin-left: 10px; font-size: 13px; font-weight: 500; min-width: 45px; text-align: right; }'
                '.status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }'
                '</style>'
                '<div class="rwd-table-scroll"><table class="overview-table">'
                '<tr><th>Shuttle Name</th><th>Owner</th><th>團隊</th><th style="width: 75px; text-align: center;">已出貨</th><th>ID (Wafer)</th><th>Step</th><th>Status</th><th style="width: 220px;">進度條</th></tr>'
            )
            df_route[shuttle_col] = df_route[shuttle_col].fillna("")
            df_route[team_col] = df_route[team_col].fillna("")
            
            def get_lot_number(wid):
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
                    
                    for idx, row in w_group.iterrows():
                        fco = str(row.get(fco_col, "")).strip().upper()
                        if fco == "SCRP":
                            has_scrap, wip_idx = True, idx
                            break
                            
                    if not has_scrap:
                        for idx, row in w_group.iterrows():
                            fco = str(row.get(fco_col, "")).strip().upper()
                            if fco in ["", "NAN", "INPR", "HOLD", "BANK"]:
                                wip_idx = idx
                                if fco == "BANK": is_banked = True
                                break
                                
                    if is_banked: continue
                    is_shipped = True if (wip_idx == total_steps and not has_scrap) else False
                    
                    if wip_idx < total_steps:
                        active_row = w_group.iloc[wip_idx]
                        raw_step = clean_step(active_row.get(step_col, ""))
                        fco_val = str(active_row.get(fco_col, "")).strip().upper()
                        if fco_val == "SCRP":
                            status_html = f'<span class="status-dot" style="background-color: #dc3545;"></span> SCRAPPED: {active_row.get(desc_col, "")}'
                        elif fco_val == "HOLD":
                            status_html = f'<span class="status-dot" style="background-color: #ffc107;"></span> HOLD: {active_row.get(desc_col, "")}'
                        else:
                            status_html = f'<span class="status-dot" style="background-color: #198754;"></span> INPR: {active_row.get(desc_col, "")}'
                    else:
                        raw_step = clean_step(w_group.iloc[-1].get(step_col, ""))
                        status_html = '<span class="status-dot" style="background-color: #0d6efd;"></span> Shipped (已出貨)'
                        
                    wip_step_no = str(wip_idx + 1) if raw_step in ["", "nan", "NaN", "None"] else raw_step
                    
                    sub_steps = [clean_step(x) for x in w_group[step_col] if "." in clean_step(x)]
                    has_sub_route = len(sub_steps) > 0
                    
                    curr_main_val = 0
                    curr_sub_val = 0
                    
                    if "." in wip_step_no:
                        parts = wip_step_no.split(".")
                        curr_main_val = int(re.findall(r'\d+', parts[0])[0]) if re.findall(r'\d+', parts[0]) else 0
                        curr_sub_val = int(re.findall(r'\d+', parts[1])[0]) if re.findall(r'\d+', parts[1]) else 0
                        
                        sub_total = sum(1 for s in w_group[step_col] if str(s).strip().startswith(f"{curr_main_val}."))
                        if sub_total == 0: sub_total = 24 
                        
                        main_pct = min(int((curr_main_val / 92) * 100), 100)
                        sub_pct = min(int((curr_sub_val / sub_total) * 100), 100)
                        
                        step_display = f"{curr_main_val}/92<br><span style='color: #17a2b8; font-weight: bold;'>{curr_sub_val}/{sub_total}</span>"
                        prog_display = f'<div class="prog-wrapper" style="margin-bottom: 4px;"><div class="prog-container"><div class="prog-bar" style="width: {main_pct}%;"></div></div><div class="prog-text">{main_pct}%</div></div><div class="prog-wrapper"><div class="prog-container"><div class="prog-bar" style="width: {sub_pct}%; background-color: #17a2b8;"></div></div><div class="prog-text" style="color: #17a2b8;">{sub_pct}%</div></div>'
                    else:
                        curr_main_val = int(re.findall(r'\d+', wip_step_no)[0]) if re.findall(r'\d+', wip_step_no) else 0
                        main_pct = min(int((curr_main_val / 92) * 100), 100)
                        
                        if has_sub_route:
                            sub_main_str = sub_steps[0].split(".")[0]
                            sub_main_val = int(re.findall(r'\d+', sub_main_str)[0]) if re.findall(r'\d+', sub_main_str) else 0
                            
                            sub_total = len(sub_steps)
                            if curr_main_val > sub_main_val:
                                curr_sub_val = sub_total
                                sub_pct = 100
                            else:
                                curr_sub_val = 0
                                sub_pct = 0
                                
                            step_display = f"{curr_main_val}/92<br><span style='color: #17a2b8; font-weight: bold;'>{curr_sub_val}/{sub_total}</span>"
                            prog_display = f'<div class="prog-wrapper" style="margin-bottom: 4px;"><div class="prog-container"><div class="prog-bar" style="width: {main_pct}%;"></div></div><div class="prog-text">{main_pct}%</div></div><div class="prog-wrapper"><div class="prog-container"><div class="prog-bar" style="width: {sub_pct}%; background-color: #17a2b8;"></div></div><div class="prog-text" style="color: #17a2b8;">{sub_pct}%</div></div>'
                        else:
                            step_display = f"{curr_main_val}/92"
                            prog_display = f'<div class="prog-wrapper"><div class="prog-container"><div class="prog-bar" style="width: {main_pct}%;"></div></div><div class="prog-text">{main_pct}%</div></div>'
                    
                    team_valid_wafers.append({
                        "id": wid, 
                        "step": step_display, 
                        "status": status_html, 
                        "is_shipped": is_shipped, 
                        "prog_display": prog_display
                    })
                    
                    if is_shipped:
                        all_shipped_data.append({
                            "Shuttle Name": shuttle,
                            "Owner": rep_owner,
                            "團隊": rep_team,
                            "ID (Wafer)": wid,
                            "Step": step_display.split("<br>")[0],
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

                    for w_data in inpr_wafers:
                        html_table += "<tr>"
                        if is_first_in_shuttle:
                            html_table += f'<td class="merged-cell" rowspan="{shuttle_inpr_count}">{shuttle}</td><td class="owner-team-cell" rowspan="{shuttle_inpr_count}">{s_data["owner"]}</td>'
                            is_first_in_shuttle = False
                        
                        if is_first_in_team:
                            html_table += f'<td class="owner-team-cell" rowspan="{team_rowspan}">{t_data["team_name"]}</td><td class="merged-cell" rowspan="{team_rowspan}">{shipped_count}</td>'
                            is_first_in_team = False
                        
                        html_table += f"<td style='white-space: nowrap;'>{w_data['id']}</td><td style='white-space: nowrap;'>{w_data['step']}</td><td>{w_data['status']}</td>"
                        html_table += f"<td>{w_data['prog_display']}</td>"
                        html_table += "</tr>"
                        
            html_table += "</table></div>"
            
            if has_inpr_wafers:
                st.markdown(html_table, unsafe_allow_html=True)
            else:
                st.info("目前產線上沒有任何進行中 (INPR) 的晶圓。")
                
            st.markdown("---")
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

# =========================================================================
# 📈 頁籤 6: Key Stage Report (KSR) - 點擊區間名稱直接顯示無背景無標題 Process Flow
# =========================================================================
with all_tabs[5]:
    st.markdown(
        '<div class="ksr-header">'
        '<div class="ksr-legend">'
        '<span style="color: #009944;">■ 綠: Normal Run</span><br>'
        '<span style="color: #92278f;">■ 紫: Hold Wafer</span><br>'
        '<span style="color: #d9534f;">■ 紅: 報廢 (SCRP)</span>'
        '</div>'
        '<div class="ksr-title">Wafer in Process by Stage</div>'
        '<div class="ksr-spacer"></div>'
        '</div>',
        unsafe_allow_html=True
    )

    df_ksr, _ = fetch_route_data_via_csv("route_template")
    df_ksr_logs, _ = fetch_route_data_via_csv("wafer_status")
    
    if not df_ksr.empty:
        wafer_col = next((c for c in df_ksr.columns if str(c).strip().lower() in ["wafer id", "id", "wafer"]), "Wafer ID")
        step_col = next((c for c in df_ksr.columns if str(c).strip().lower() in ["step", "step no.", "step no"]), "Step")
        shuttle_col = next((c for c in df_ksr.columns if "shuttle" in str(c).lower()), "Shuttle Name")
        fco_col = next((c for c in df_ksr.columns if "check out" in str(c).lower()), "Check out Time")
        desc_col = next((c for c in df_ksr.columns if "description" in str(c).lower()), "Step description")
        hold_note_col = next((c for c in df_ksr.columns if "hold note" in str(c).lower() or "hold_note" in str(c).lower()), "Hold Note")

        log_hold_map = build_log_hold_note_map(df_ksr_logs)

        B_POS = {
            1: 0.0,
            27: 15.5,
            37: 25.0,
            61: 45.5,
            68: 56.0,
            69: 71.0,
            88: 88.5,
            92: 100.0
        }

        def step_to_x_pos(step_str):
            if "." in step_str:
                parts = step_str.split(".")
                s_val = int(re.findall(r'\d+', parts[1])[0]) if re.findall(r'\d+', parts[1]) else 1
                s_val = max(1, min(s_val, 24))
                span = B_POS[69] - B_POS[68]
                return B_POS[68] + (s_val / 25.0) * span
            else:
                m_val = int(re.findall(r'\d+', step_str)[0]) if re.findall(r'\d+', step_str) else 1
                m_val = max(1, min(m_val, 92))
                if m_val <= 27:
                    return B_POS[1] + ((m_val - 1) / 26.0) * (B_POS[27] - B_POS[1])
                elif m_val <= 37:
                    return B_POS[27] + ((m_val - 27) / 10.0) * (B_POS[37] - B_POS[27])
                elif m_val <= 61:
                    return B_POS[37] + ((m_val - 37) / 24.0) * (B_POS[61] - B_POS[37])
                elif m_val <= 68:
                    return B_POS[61] + ((m_val - 61) / 7.0) * (B_POS[68] - B_POS[61])
                elif m_val == 69:
                    return B_POS[69]
                elif m_val <= 88:
                    return B_POS[69] + ((m_val - 69) / 19.0) * (B_POS[88] - B_POS[69])
                else:
                    return B_POS[88] + ((m_val - 88) / 4.0) * (B_POS[92] - B_POS[88])

        def format_step_label(step_str):
            if "." in step_str:
                parts = step_str.split(".")
                s_val = int(re.findall(r'\d+', parts[1])[0]) if re.findall(r'\d+', parts[1]) else 1
                return f"C{s_val}"
            return step_str

        def get_section_name(step_str):
            if "." in step_str:
                return "Cu Pad (RDL)"
            m_val = int(re.findall(r'\d+', step_str)[0]) if re.findall(r'\d+', step_str) else 1
            if m_val < 27: return "W2W Bonding"
            elif m_val < 37: return "Grinding"
            elif m_val < 61: return "TSV Etch Section"
            elif m_val <= 68: return "TSV Cu ECP"
            elif m_val < 88: return "Bumping Section"
            else: return "Dicing"

        if wafer_col in df_ksr.columns:
            ksr_records = []
            
            for wid, w_group in df_ksr.groupby(wafer_col, sort=False):
                if not str(wid).strip():
                    continue
                w_group = w_group.reset_index(drop=True)
                total_steps = len(w_group)
                has_scrap, is_banked = False, False
                wip_idx = total_steps
                active_row = None
                
                shuttle_val = ""
                for _, r in w_group.iterrows():
                    sv = str(r.get(shuttle_col, "")).strip()
                    if sv:
                        shuttle_val = sv
                        break
                if not shuttle_val:
                    shuttle_val = "No Shuttle"

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

                if is_banked or (wip_idx == total_steps and not has_scrap):
                    continue

                if active_row is not None:
                    raw_step = clean_step(active_row.get(step_col, ""))
                    step_str = str(wip_idx + 1) if raw_step in ["", "nan", "NaN", "None"] else raw_step
                    axis_lbl = format_step_label(step_str)
                    fco_status = str(active_row.get(fco_col, "")).strip().upper()
                    
                    hold_note_str = str(active_row.get(hold_note_col, "")).strip()
                    if not hold_note_str:
                        hold_note_str = log_hold_map.get((str(wid).strip().upper(), step_str), "")

                    if fco_status == "SCRP":
                        status_cat = "Scrap (報廢)"
                        bar_color = "#d9534f"
                    elif fco_status == "HOLD":
                        status_cat = "Hold Wafer"
                        bar_color = "#92278f"
                    else:
                        status_cat = "Normal Run"
                        bar_color = "#009944"

                    ksr_records.append({
                        "Wafer ID": str(wid).strip(),
                        "Shuttle": shuttle_val,
                        "Step": step_str,
                        "Step_Label": axis_lbl,
                        "Section": get_section_name(step_str),
                        "Status": status_cat,
                        "Color": bar_color,
                        "Hold_Note": hold_note_str,
                        "Step Description": str(active_row.get(desc_col, "")).strip(),
                        "x_pos": step_to_x_pos(step_str)
                    })

            if ksr_records:
                df_items = pd.DataFrame(ksr_records)

                step_totals = []
                for (step_s, step_lbl, x_p, sec_s), grp in df_items.groupby(["Step", "Step_Label", "x_pos", "Section"], sort=False):
                    desc_sample = grp["Step Description"].iloc[0] if not grp.empty else ""
                    display_full_step = f"{step_lbl} ({step_s})" if step_lbl != step_s else step_s
                    step_totals.append({
                        "Step": step_s,
                        "Step_Label": step_lbl,
                        "Display_Step": display_full_step,
                        "Section": sec_s,
                        "Total": len(grp),
                        "Desc": desc_sample,
                        "x_pos": x_p,
                        "items": grp.to_dict("records")
                    })
                df_totals = pd.DataFrame(step_totals).sort_values("x_pos")

                svg_w = 1200.0
                svg_h = 340.0
                pad_l = 35.0
                pad_r = 75.0
                base_y = 265.0
                sec_y = 52.0
                max_bar_area_h = 165.0

                def to_px_x(vx):
                    return pad_l + (vx / 100.0) * (svg_w - pad_l - pad_r)

                max_cnt = max(int(df_totals["Total"].max()), 5)
                unit_h = max_bar_area_h / float(max_cnt)

                sections_meta = [
                    ("sec_w2w", "W2W Bonding", B_POS[1], B_POS[27]),
                    ("sec_grinding", "Grinding", B_POS[27], B_POS[37]),
                    ("sec_etch", "TSV Etch Section", B_POS[37], B_POS[61]),
                    ("sec_cu_ecp", "TSV Cu ECP", B_POS[61], B_POS[68]),
                    ("sec_cu_pad", "Cu Pad (RDL)", B_POS[68], B_POS[69]),
                    ("sec_bump", "Bumping Section", B_POS[69], B_POS[88]),
                    ("sec_dicing", "Dicing", B_POS[88], B_POS[92]),
                ]
                boundaries = [
                    ("1", B_POS[1]),
                    ("27", B_POS[27]),
                    ("37", B_POS[37]),
                    ("61", B_POS[61]),
                    ("68", B_POS[68]),
                    ("69", B_POS[69]),
                    ("88", B_POS[88]),
                    ("92", B_POS[92]),
                ]

                svg_parts = []
                svg_parts.append(
                    f'<svg viewBox="0 0 {svg_w} {svg_h}" style="width: 100%; height: auto; display: block; overflow: visible;">'
                    '<defs>'
                    '<marker id="ksr-arr-r" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 1 L 10 5 L 0 9 z" fill="#666666"/></marker>'
                    '<marker id="ksr-arr-l" viewBox="0 0 10 10" refX="2" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 10 1 L 0 5 L 10 9 z" fill="#666666"/></marker>'
                    '<marker id="ksr-axis-r" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 1 L 10 5 L 0 9 z" fill="#000000"/></marker>'
                    '</defs>'
                )

                active_px_list = [to_px_x(r["x_pos"]) for _, r in df_totals.iterrows()]
                for b_lbl, bx in boundaries:
                    px = to_px_x(bx)
                    svg_parts.append(f'<line x1="{px:.1f}" y1="15" x2="{px:.1f}" y2="{base_y + 42:.1f}" stroke="#dcdcdc" stroke-width="1.5" stroke-dasharray="5,4" />')
                    if all(abs(px - apx) > 10.0 for apx in active_px_list):
                        svg_parts.append(f'<line x1="{px:.1f}" y1="{base_y - 6:.1f}" x2="{px:.1f}" y2="{base_y + 6:.1f}" stroke="#999999" stroke-width="1.5" />')
                        svg_parts.append(f'<text x="{px:.1f}" y="{base_y + 24:.1f}" text-anchor="middle" font-size="13" fill="#999999" font-family="sans-serif">{b_lbl}</text>')

                # 頂部各區間雙向箭頭 + 可點擊透明感應區 (綁定純 CSS Radio 切換下方 Process Flow)
                sec_click_labels = []
                for s_id, s_name, sx1, sx2 in sections_meta:
                    px1 = to_px_x(sx1) + 4.0
                    px2 = to_px_x(sx2) - 4.0
                    pmid = (px1 + px2) / 2.0
                    svg_parts.append(f'<line x1="{px1:.1f}" y1="{sec_y:.1f}" x2="{px2:.1f}" y2="{sec_y:.1f}" stroke="#666666" stroke-width="1.5" marker-start="url(#ksr-arr-l)" marker-end="url(#ksr-arr-r)" />')
                    svg_parts.append(f'<text class="sec-svg-txt-{s_id}" x="{pmid:.1f}" y="{sec_y - 8:.1f}" text-anchor="middle" font-size="13.5" fill="#777777" font-family="sans-serif">{html_lib.escape(s_name)}</text>')
                    l_pct = (px1 / svg_w) * 100.0
                    w_pct = ((px2 - px1) / svg_w) * 100.0
                    # 點擊區間時開啟對應 Process Flow；若已選取時還提供重設透明鈕收合
                    sec_click_labels.append(
                        f'<label for="pf_rad_{s_id}" class="ksr-sec-hit hit-open-{s_id}" title="點擊顯示 {html_lib.escape(s_name)} Process Flow" '
                        f'style="left: {l_pct:.2f}%; width: {w_pct:.2f}%;"></label>'
                        f'<label for="pf_rad_none" class="ksr-sec-hit hit-close-{s_id}" title="點擊收合 Process Flow" '
                        f'style="left: {l_pct:.2f}%; width: {w_pct:.2f}%;"></label>'
                    )

                axis_end_x = svg_w - pad_r + 18.0
                svg_parts.append(f'<line x1="{pad_l - 15:.1f}" y1="{base_y:.1f}" x2="{axis_end_x:.1f}" y2="{base_y:.1f}" stroke="#000000" stroke-width="2" marker-end="url(#ksr-axis-r)" />')
                svg_parts.append(f'<text x="{axis_end_x + 8:.1f}" y="{base_y - 10:.1f}" text-anchor="start" font-size="14" font-weight="bold" fill="#000000" font-family="sans-serif">片數</text>')
                svg_parts.append(f'<text x="{axis_end_x + 8:.1f}" y="{base_y + 24:.1f}" text-anchor="start" font-size="14" font-weight="bold" fill="#000000" font-family="sans-serif">Step</text>')

                bar_w = 10.0
                overlay_divs = []
                status_order = {"Normal Run": 0, "Hold Wafer": 1, "Scrap (報廢)": 2}

                for _, s_row in df_totals.iterrows():
                    px = to_px_x(s_row["x_pos"])
                    items_sorted = sorted(s_row["items"], key=lambda x: status_order.get(x["Status"], 9))
                    
                    curr_bottom_y = base_y
                    for st_cat in ["Normal Run", "Hold Wafer", "Scrap (報廢)"]:
                        sub_items = [it for it in items_sorted if it["Status"] == st_cat]
                        if not sub_items:
                            continue
                        seg_h = len(sub_items) * unit_h
                        rect_y = curr_bottom_y - seg_h
                        color_hex = sub_items[0]["Color"]
                        svg_parts.append(
                            f'<rect x="{px - bar_w/2.0:.1f}" y="{rect_y:.1f}" width="{bar_w:.1f}" height="{seg_h:.1f}" '
                            f'fill="{color_hex}" stroke="#000000" stroke-width="1.2" />'
                        )
                        curr_bottom_y = rect_y

                    total_cnt = int(s_row["Total"])
                    top_bar_y = base_y - total_cnt * unit_h

                    svg_parts.append(f'<text x="{px:.1f}" y="{top_bar_y - 8:.1f}" text-anchor="middle" font-size="15" font-weight="bold" fill="#000000" font-family="sans-serif">{total_cnt}</text>')
                    svg_parts.append(f'<line x1="{px:.1f}" y1="{base_y:.1f}" x2="{px:.1f}" y2="{base_y + 7:.1f}" stroke="#000000" stroke-width="2" />')
                    svg_parts.append(f'<text x="{px:.1f}" y="{base_y + 24:.1f}" text-anchor="middle" font-size="13" font-weight="bold" fill="#000000" font-family="sans-serif">{html_lib.escape(s_row["Step_Label"])}</text>')

                    left_pct = (px / svg_w) * 100.0
                    top_pct = ((top_bar_y - 18.0) / svg_h) * 100.0
                    height_pct = (((base_y + 28.0) - (top_bar_y - 18.0)) / svg_h) * 100.0
                    tip_pos_style = "right: 0; transform: translateX(0);" if left_pct > 80 else ("left: 0; transform: translateX(0);" if left_pct < 20 else "left: 50%; transform: translateX(-50%);")

                    wafer_lines_list = []
                    for it in items_sorted:
                        line_str = f'<div style="margin-top: 4px;"><span style="color: {it["Color"]};">●</span> {html_lib.escape(it["Shuttle"])} <b>({html_lib.escape(it["Wafer ID"])})</b>'
                        if it["Status"] == "Hold Wafer":
                            h_txt = html_lib.escape(it["Hold_Note"]) if it["Hold_Note"] else "無備註 (No Hold Note)"
                            line_str += f'<div style="color: #e599f7; font-size: 11.5px; margin-left: 14px; white-space: normal;">↳ Hold Note: {h_txt}</div>'
                        elif it["Status"] == "Scrap (報廢)" and it["Hold_Note"]:
                            s_txt = html_lib.escape(it["Hold_Note"])
                            line_str += f'<div style="color: #ffa8a8; font-size: 11.5px; margin-left: 14px; white-space: normal;">↳ Scrap Note: {s_txt}</div>'
                        line_str += '</div>'
                        wafer_lines_list.append(line_str)

                    wafer_lines_html = "".join(wafer_lines_list)
                    desc_txt = html_lib.escape(s_row["Desc"])

                    overlay_divs.append(
                        f'<div class="ksr-hit" tabindex="0" style="left: calc({left_pct:.2f}% - 14px); top: {top_pct:.2f}%; height: {height_pct:.2f}%;">'
                        f'<div class="ksr-tip" style="{tip_pos_style}">'
                        f'<div style="font-weight: bold; font-size: 13px; color: #ffd43b; border-bottom: 1px solid #495057; padding-bottom: 4px; margin-bottom: 4px;">'
                        f'Step {html_lib.escape(s_row["Display_Step"])} ｜ {html_lib.escape(s_row["Section"])} ({total_cnt} 片)'
                        f'</div>'
                        f'<div style="font-size: 12px; color: #ced4da; margin-bottom: 4px;">{desc_txt}</div>'
                        f'{wafer_lines_html}'
                        f'</div></div>'
                    )

                svg_parts.append('</svg>')

                # Hold Lots 摘要 HTML (維持顯示在 KSR 圖表下方)
                hold_summary_html = ""
                df_holds = df_items[df_items["Status"] == "Hold Wafer"]
                if not df_holds.empty:
                    hold_cards = []
                    for _, hrow in df_holds.iterrows():
                        st_disp = f"{hrow['Step_Label']} ({hrow['Step']})" if hrow['Step_Label'] != hrow['Step'] else hrow['Step']
                        h_note = html_lib.escape(hrow["Hold_Note"]) if hrow["Hold_Note"] else "無備註"
                        hold_cards.append(
                            f'<div style="margin: 4px 0; font-size: 14px; line-height: 1.5;">'
                            f'<span style="color: #92278f; font-weight: bold;">● Step {html_lib.escape(st_disp)}</span> ｜ '
                            f'<b>{html_lib.escape(hrow["Shuttle"])} ({html_lib.escape(hrow["Wafer ID"])})</b> — '
                            f'<span style="color: #c92a2a; font-weight: bold;">Hold Note: {h_note}</span>'
                            f'</div>'
                        )
                    hold_summary_html = (
                        '<div style="background-color: #f8f0fc; border-left: 4px solid #92278f; padding: 10px 16px; border-radius: 4px; margin: 10px 0 14px 0;">'
                        '<div style="font-weight: bold; color: #92278f; font-size: 15px; margin-bottom: 4px;">⚠️ Current Hold Lots (暫停在製清單)</div>'
                        f'{"".join(hold_cards)}'
                        '</div>'
                    )

                # 載入 6 組無背景、無標題的純向量 Process Flow 圖
                pf_svgs = build_process_flow_svgs()

                ksr_interactive_html = (
                    '<style>'
                    '.pf-rad { display: none !important; }'
                    '.ksr-wrap { position: relative; width: 100%; background: #ffffff; border: 1px solid #e9ecef; border-radius: 8px; padding: 14px 10px 18px 10px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }'
                    '.ksr-stage { position: relative; width: 100%; min-width: 880px; }'
                    '.ksr-sec-hit { position: absolute; top: 3%; height: 17%; cursor: pointer; z-index: 15; border-radius: 6px; transition: background 0.15s ease; }'
                    '.ksr-sec-hit:hover { background: rgba(13, 110, 253, 0.09); }'
                    '.hit-close-sec_w2w, .hit-close-sec_grinding, .hit-close-sec_etch, .hit-close-sec_cu_ecp, .hit-close-sec_cu_pad, .hit-close-sec_bump, .hit-close-sec_dicing { display: none; }'
                    '#pf_rad_sec_w2w:checked ~ .ksr-wrap .hit-open-sec_w2w { display: none; }'
                    '#pf_rad_sec_w2w:checked ~ .ksr-wrap .hit-close-sec_w2w { display: block; background: rgba(13, 110, 253, 0.12); }'
                    '#pf_rad_sec_w2w:checked ~ .ksr-wrap .sec-svg-txt-sec_w2w { fill: #0d6efd !important; font-weight: bold; }'
                    '#pf_rad_sec_grinding:checked ~ .ksr-wrap .hit-open-sec_grinding { display: none; }'
                    '#pf_rad_sec_grinding:checked ~ .ksr-wrap .hit-close-sec_grinding { display: block; background: rgba(13, 110, 253, 0.12); }'
                    '#pf_rad_sec_grinding:checked ~ .ksr-wrap .sec-svg-txt-sec_grinding { fill: #0d6efd !important; font-weight: bold; }'
                    '#pf_rad_sec_etch:checked ~ .ksr-wrap .hit-open-sec_etch { display: none; }'
                    '#pf_rad_sec_etch:checked ~ .ksr-wrap .hit-close-sec_etch { display: block; background: rgba(13, 110, 253, 0.12); }'
                    '#pf_rad_sec_etch:checked ~ .ksr-wrap .sec-svg-txt-sec_etch { fill: #0d6efd !important; font-weight: bold; }'
                    '#pf_rad_sec_cu_ecp:checked ~ .ksr-wrap .hit-open-sec_cu_ecp { display: none; }'
                    '#pf_rad_sec_cu_ecp:checked ~ .ksr-wrap .hit-close-sec_cu_ecp { display: block; background: rgba(13, 110, 253, 0.12); }'
                    '#pf_rad_sec_cu_ecp:checked ~ .ksr-wrap .sec-svg-txt-sec_cu_ecp { fill: #0d6efd !important; font-weight: bold; }'
                    '#pf_rad_sec_cu_pad:checked ~ .ksr-wrap .hit-open-sec_cu_pad { display: none; }'
                    '#pf_rad_sec_cu_pad:checked ~ .ksr-wrap .hit-close-sec_cu_pad { display: block; background: rgba(13, 110, 253, 0.12); }'
                    '#pf_rad_sec_cu_pad:checked ~ .ksr-wrap .sec-svg-txt-sec_cu_pad { fill: #0d6efd !important; font-weight: bold; }'
                    '#pf_rad_sec_bump:checked ~ .ksr-wrap .hit-open-sec_bump { display: none; }'
                    '#pf_rad_sec_bump:checked ~ .ksr-wrap .hit-close-sec_bump { display: block; background: rgba(13, 110, 253, 0.12); }'
                    '#pf_rad_sec_bump:checked ~ .ksr-wrap .sec-svg-txt-sec_bump { fill: #0d6efd !important; font-weight: bold; }'
                    '#pf_rad_sec_dicing:checked ~ .ksr-wrap .hit-open-sec_dicing { display: none; }'
                    '#pf_rad_sec_dicing:checked ~ .ksr-wrap .hit-close-sec_dicing { display: block; background: rgba(13, 110, 253, 0.12); }'
                    '#pf_rad_sec_dicing:checked ~ .ksr-wrap .sec-svg-txt-sec_dicing { fill: #0d6efd !important; font-weight: bold; }'
                    '.ksr-hit { position: absolute; width: 28px; cursor: pointer; z-index: 10; outline: none; -webkit-tap-highlight-color: transparent; }'
                    '.ksr-hit:hover, .ksr-hit:focus, .ksr-hit:active { background: rgba(13, 110, 253, 0.1); border-radius: 4px; }'
                    '.ksr-tip { display: none; position: absolute; bottom: 102%; min-width: 220px; max-width: 340px; background: rgba(33, 37, 41, 0.96); color: #ffffff; padding: 10px 14px; border-radius: 6px; font-size: 12.5px; white-space: nowrap; z-index: 999; box-shadow: 0 4px 14px rgba(0,0,0,0.25); pointer-events: none; line-height: 1.45; }'
                    '.ksr-hit:hover .ksr-tip, .ksr-hit:focus .ksr-tip, .ksr-hit:active .ksr-tip { display: block; }'
                    /* 下方無背景無標題 Process Flow 面板 */
                    '.pf-flow-panel { display: none; width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; padding: 16px 4px 8px 4px; margin-top: 6px; background: transparent; border: none; }'
                    '#pf_rad_sec_w2w:checked ~ .pf-panel-bonding, #pf_rad_sec_grinding:checked ~ .pf-panel-bonding { display: block; }'
                    '#pf_rad_sec_etch:checked ~ .pf-panel-etch { display: block; }'
                    '#pf_rad_sec_cu_ecp:checked ~ .pf-panel-cu_ecp { display: block; }'
                    '#pf_rad_sec_cu_pad:checked ~ .pf-panel-cu_pad { display: block; }'
                    '#pf_rad_sec_bump:checked ~ .pf-panel-bump { display: block; }'
                    '#pf_rad_sec_dicing:checked ~ .pf-panel-dicing { display: block; }'
                    '@media screen and (max-width: 920px) {'
                    '  .ksr-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; padding-top: 75px; }'
                    '}'
                    '</style>'
                    '<div>'
                    '<input type="radio" name="ksr_pf_sel" id="pf_rad_none" class="pf-rad" checked>'
                    '<input type="radio" name="ksr_pf_sel" id="pf_rad_sec_w2w" class="pf-rad">'
                    '<input type="radio" name="ksr_pf_sel" id="pf_rad_sec_grinding" class="pf-rad">'
                    '<input type="radio" name="ksr_pf_sel" id="pf_rad_sec_etch" class="pf-rad">'
                    '<input type="radio" name="ksr_pf_sel" id="pf_rad_sec_cu_ecp" class="pf-rad">'
                    '<input type="radio" name="ksr_pf_sel" id="pf_rad_sec_cu_pad" class="pf-rad">'
                    '<input type="radio" name="ksr_pf_sel" id="pf_rad_sec_bump" class="pf-rad">'
                    '<input type="radio" name="ksr_pf_sel" id="pf_rad_sec_dicing" class="pf-rad">'
                    '<div class="mobile-swipe-hint">📱 手機可左右滑動圖表；輕點長條看 Wafer 明細，輕點上方區間名稱顯示 Process Flow</div>'
                    f'<div class="ksr-wrap"><div class="ksr-stage">{"".join(svg_parts)}{"".join(sec_click_labels)}{"".join(overlay_divs)}</div></div>'
                    '<div style="font-size: 12.5px; color: #6c757d; margin-bottom: 8px;">'
                    '💡 提示：滑鼠移至長條上可檢視 Shuttle / Wafer ID；<b>直接點擊圖表上方的區間名稱（如 W2W Bonding、TSV Etch Section 等）</b>即可在下方展開對應 Process Flow（再次點擊可收合）。'
                    '</div>'
                    f'{hold_summary_html}'
                    f'<div class="pf-flow-panel pf-panel-bonding">{pf_svgs["bonding"]}</div>'
                    f'<div class="pf-flow-panel pf-panel-etch">{pf_svgs["etch"]}</div>'
                    f'<div class="pf-flow-panel pf-panel-cu_ecp">{pf_svgs["cu_ecp"]}</div>'
                    f'<div class="pf-flow-panel pf-panel-cu_pad">{pf_svgs["cu_pad"]}</div>'
                    f'<div class="pf-flow-panel pf-panel-bump">{pf_svgs["bump"]}</div>'
                    f'<div class="pf-flow-panel pf-panel-dicing">{pf_svgs["dicing"]}</div>'
                    '</div>'
                )

                st.markdown(ksr_interactive_html, unsafe_allow_html=True)
            else:
                st.info("目前產線上沒有任何在製中 (WIP) 的晶圓可供繪製圖表。")
        else:
            st.warning("⚠️ 母表中找不到 Wafer ID 欄位。")
    else:
        st.info("💡 目前雲端母表尚無資料。")
