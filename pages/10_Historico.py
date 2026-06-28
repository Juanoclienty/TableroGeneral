"""
10_Historico.py — Histórico de bajas por cohorte
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import io
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import urllib.request
from datetime import date

st.set_page_config(page_title="Histórico", page_icon="📅", layout="wide", initial_sidebar_state="expanded")

# ── Config Monday ─────────────────────────────────────────────────────────────

_MONDAY_TOKEN = (
    "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjY2Nzg4MzU5OSwiYWFpIjoxMSwidWlkIjo3N"
    "DQ5MjMwMiwiaWFkIjoiMjAyNi0wNi0wN1QxNzozMTowMi4wMDBaIiwicGVyIjoibWU6"
    "d3JpdGUiLCJhY3RpZCI6MjQxNjExNjcsInJnbiI6InVzZTEifQ.L41MQVmopJ880Q2m"
    "uX6S6erxUv23uOSvppD9fmsoaMQ"
)
_BOARD_ID      = "6967792411"
_GROUP_ACTIVOS = "grupo_nuevo28466"
_COLS          = ["id8__1", "fecha5", "fecha1", "status0", "rubro_mkmttagz", "pain__1"]

_MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _monday_request(query: str) -> dict:
    payload = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.monday.com/v2",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": _MONDAY_TOKEN,
            "API-Version":   "2024-01",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _inferir_fecha_grupo(titulo: str) -> pd.Timestamp:
    t = titulo.lower()
    for mes_str, mes_num in _MESES_ES.items():
        if mes_str in t:
            m = re.search(r"\b(20\d{2})\b", titulo)
            if m:
                return pd.Timestamp(year=int(m.group(1)), month=mes_num, day=1)
    return pd.NaT


def _fmt_fecha(ts) -> str:
    return ts.strftime("%d/%m/%Y") if pd.notna(ts) else "–"


def _norm_id_cs(v) -> str:
    s = str(v).strip()
    if s.endswith(".0") and s[:-2].lstrip("-").isdigit():
        s = s[:-2]
    return s if s not in ("nan", "None", "") else ""


def _cat(m):
    if pd.isna(m): return None
    m = float(m)
    if m <= 0:  return "0"
    if m <= 3:  return "0-3"
    if m <= 6:  return "+3"
    if m <= 12: return "+6"
    return "+12"


_ID_HIST = "1Gx8D17EGw4Lwoo82F11PBQ9fl6aC8dQDPdurxWxSOP4"
_URL_HIST = f"https://docs.google.com/spreadsheets/d/{_ID_HIST}/edit?usp=sharing"

@st.cache_data(ttl=3600)
def _cargar_tabla_hist() -> dict:
    """Devuelve {(year, month): {ventas, publicidad, cpv}} desde el sheet Histórico."""
    import os
    _cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache", "historico.parquet")
    if os.path.exists(_cache_path):
        df = pd.read_parquet(_cache_path)
    else:
        url = f"https://docs.google.com/spreadsheets/d/{_ID_HIST}/gviz/tq?tqx=out:csv"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        df  = pd.read_csv(io.StringIO(urllib.request.urlopen(req, timeout=15).read().decode("utf-8")))
    # parse "MM/YYYY" → (year, month)
    out = {}
    for _, row in df.iterrows():
        mes_str = str(row.get("Mes", "")).strip()
        if "/" not in mes_str: continue
        parts = mes_str.split("/")
        try: m, yr = int(parts[0]), int(parts[1])
        except: continue
        def _n(col):
            v = str(row.get(col, "")).replace(",", ".").strip()
            try: return float(v)
            except: return None
        out[(yr, m)] = {"ventas": _n("Ventas"), "publicidad": _n("Publicidad"), "cpv": _n("CPV")}
    return out


# ── Carga datos Monday ────────────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def _descubrir_col_b2b() -> str:
    q = f'{{ boards(ids: [{_BOARD_ID}]) {{ columns {{ id title }} }} }}'
    r = _monday_request(q)
    cols = r["data"]["boards"][0]["columns"]
    for c in cols:
        if "b2b" in c["title"].lower() or "b2c" in c["title"].lower():
            return c["id"]
    return ""


@st.cache_data(ttl=3600)
def _cargar_monday() -> pd.DataFrame:
    _col_b2b  = _descubrir_col_b2b()
    _cols_use = list(_COLS) + ([_col_b2b] if _col_b2b else [])
    cols_gql  = ", ".join(f'"{c}"' for c in _cols_use)
    item_fragment = f"""
      id name
      group {{ id title }}
      column_values(ids: [{cols_gql}]) {{ id text }}
    """
    q = f'{{ boards(ids: [{_BOARD_ID}]) {{ items_page(limit: 500) {{ cursor items {{ {item_fragment} }} }} }} }}'
    r      = _monday_request(q)
    page   = r["data"]["boards"][0]["items_page"]
    items  = list(page["items"])
    cursor = page.get("cursor")

    while cursor:
        q2 = f'{{ next_items_page(limit: 500, cursor: "{cursor}") {{ cursor items {{ {item_fragment} }} }} }}'
        r2     = _monday_request(q2)
        page   = r2["data"]["next_items_page"]
        items.extend(page["items"])
        cursor = page.get("cursor")

    rows = []
    for item in items:
        cv = {c["id"]: (c["text"] or "") for c in item["column_values"]}
        rows.append({
            "monday_id":      item["id"],
            "ID CRM":         cv.get("id8__1", ""),
            "Nombre":         item["name"],
            "grupo_id":       item["group"]["id"],
            "grupo_titulo":   item["group"]["title"],
            "_fecha_ingreso": cv.get("fecha5", ""),
            "_fecha_baja":    cv.get("fecha1", ""),
            "Rubro":          cv.get("rubro_mkmttagz", ""),
            "B2B - B2C":      cv.get(_col_b2b, "") if _col_b2b else "",
        })

    df = pd.DataFrame(rows)
    df["_fecha_ingreso"] = pd.to_datetime(df["_fecha_ingreso"], errors="coerce")
    df["_fecha_baja"]    = pd.to_datetime(df["_fecha_baja"],    errors="coerce")
    return df


# ── CSS / JS ──────────────────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; margin: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #fff; padding: 4px 2px; }
.wrap { overflow-x: auto; border: 1px solid #c8ccd0; border-radius: 4px; }
table { border-collapse: collapse; min-width: 860px; width: 100%; font-size: 0.78rem; table-layout: fixed; }
thead th { position: sticky; z-index: 2; border: 1px dotted #9ab; }
thead tr:first-child  th { top: 0px; }
thead tr:nth-child(2) th { top: 34px; }
.h-n { background:#1a3a5c; color:#fff; font-weight:bold; padding:6px 4px; text-align:center; }
.h-p { background:#7b341e; color:#fff; font-weight:bold; padding:6px 4px; text-align:center; }
.h-a { background:#145a32; color:#fff; font-weight:bold; padding:6px 4px; text-align:center; }
.sh   { padding:4px 4px; font-weight:bold; text-align:center; border:2px solid #8aabb8; }
.sh-n { background:#a9cce3; }
.sh-p { background:#f5cba7; }
.sh-a { background:#a9dfbf; }
td { border:1px dotted #bbb; padding:4px 4px; text-align:center; }
.c-l { text-align:center; white-space:nowrap; }
.c-n { background:#d6eaf8; }
.c-p { background:#fdebd0; color:#333; }
.c-a { background:#d5f5e3; color:#333; }
.yr-row td   { font-weight:bold; }
.yr-row .c-l { background:#dde1e6; }
.p-row .c-l  { padding-left:16px !important; }
.tbtn { background:none; border:none; cursor:pointer; font-size:0.65rem; padding:0 3px 0 0; color:#444; vertical-align:middle; }
.tbtn:hover { color:#0055cc; }
td[onclick] { cursor: pointer; }
td[onclick]:hover { filter: brightness(0.82); outline: 1px solid rgba(0,0,0,0.25); }
"""

_JS = """
function tog(yr) {
    var rows = document.querySelectorAll('.yr-' + yr);
    var btn  = document.getElementById('btn-' + yr);
    var open = btn.dataset.open === '1';
    rows.forEach(function(r) { r.style.display = open ? 'none' : ''; });
    btn.dataset.open = open ? '0' : '1';
    btn.innerHTML    = open ? '&#9654;' : '&#9660;';
}
"""

_DET_DIV = (
    "<div id='det' onclick='closeDet()'"
    " style='display:none;position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:100;padding:18px 10px;overflow-y:auto'>"
    "<div onclick='event.stopPropagation()'"
    " style='background:#fff;border-radius:6px;max-width:860px;margin:0 auto;box-shadow:0 4px 24px rgba(0,0,0,0.25)'>"
    "<div style='display:flex;justify-content:space-between;align-items:center;"
    "padding:9px 14px;background:#1a3a5c;border-radius:6px 6px 0 0'>"
    "<span style='color:#fff;font-size:0.82rem;font-weight:bold'>Detalle: <span id='det-title'></span></span>"
    "<button onclick='closeDet()' style='background:#c0392b;color:#fff;border:none;"
    "border-radius:4px;padding:3px 10px;cursor:pointer;font-size:0.72rem'>&#10005; Cerrar</button>"
    "</div>"
    "<div id='det-body' style='max-height:72vh;overflow-y:auto'></div>"
    "</div></div>"
)

_IFRAME_JS_TMPL = """
var _SKEYS=['fis','fbs','mr'];
var _lastRows=[], _sortIdx=-1, _sortDir=1;
function _ivl(m){
  if(m==null)return null;
  if(m<=0)return'0';if(m<=3)return'0-3';if(m<=6)return'+3';if(m<=12)return'+6';
  return'+12';
}
function _arr(i){ return _sortIdx===i?(_sortDir>0?' [^]':' [v]'):' [-]'; }
function filterClick(p){
  var rows=BDATA.filter(function(r){
    if(r.yr!==p.yr)return false;
    if(p.months&&p.months.indexOf(r.mb)<0)return false;
    if(p.iv&&_ivl(r.mr)!==p.iv)return false;
    return true;
  });
  _sortIdx=-1;_sortDir=1;
  renderDet(rows);
}
function closeDet(){document.getElementById('det').style.display='none';}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeDet();});
function sortDet(i){
  if(_sortIdx===i){_sortDir*=-1;}else{_sortIdx=i;_sortDir=1;}
  var key=_SKEYS[i];
  var s=_lastRows.slice().sort(function(a,b){
    var av=a[key],bv=b[key];
    var an=(av==null||av===''),bn=(bv==null||bv==='');
    if(an&&bn)return 0;if(an)return 1;if(bn)return -1;
    return(av<bv?-1:av>bv?1:0)*_sortDir;
  });
  renderDet(s);
}
function renderDet(rows){
  _lastRows=rows;
  document.getElementById('det-title').textContent=rows.length+' registros';
  var bdy=document.getElementById('det-body');
  if(!rows.length){
    bdy.innerHTML='<p style="padding:12px;color:#666;font-size:0.78rem">Sin registros.</p>';
  } else {
    var S='padding:5px 8px;font-weight:600;background:#1a3a5c;white-space:nowrap;position:sticky;top:0;';
    var h='<table style="width:100%;border-collapse:collapse;font-size:0.78rem">'
      +'<thead><tr style="color:#fff">'
      +'<th style="'+S+'text-align:left">ID CRM</th>'
      +'<th style="'+S+'text-align:left">Nombre</th>'
      +'<th style="'+S+'text-align:center;cursor:pointer" onclick="sortDet(0)">F. ingreso'+_arr(0)+'</th>'
      +'<th style="'+S+'text-align:center;cursor:pointer" onclick="sortDet(1)">F. baja'+_arr(1)+'</th>'
      +'<th style="'+S+'text-align:center;cursor:pointer" onclick="sortDet(2)">Meses'+_arr(2)+'</th>'
      +'</tr></thead><tbody>';
    for(var i=0;i<rows.length;i++){
      var r=rows[i],bg=i%2?'#fff':'#f8f9fa';
      h+='<tr style="background:'+bg+'">'
        +'<td style="padding:4px 8px;border-bottom:1px solid #eee">'+(r.id||'-')+'</td>'
        +'<td style="padding:4px 8px;border-bottom:1px solid #eee">'+r.nom+'</td>'
        +'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:center">'+r.fi+'</td>'
        +'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:center">'+r.fb+'</td>'
        +'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:center">'+(r.mr!=null?Math.round(r.mr*10)/10+'m':'-')+'</td>'
        +'</tr>';
    }
    bdy.innerHTML=h+'</tbody></table>';
  }
  document.getElementById('det').style.display='block';
}
"""

def _make_filter_js(bdata_json: str) -> str:
    safe = bdata_json.replace("</", "<\\/")
    return "var BDATA=" + safe + ";\n" + _IFRAME_JS_TMPL


# ── Tabla cohorte de baja ─────────────────────────────────────────────────────

def _cohorte_html(df_b: pd.DataFrame, granularity: str, hist_map: dict = None) -> tuple[str, int]:
    IVLS = ["0", "0-3", "+3", "+6", "+12"]

    df = df_b.dropna(subset=["_fecha_baja", "_fecha_ingreso"]).copy()
    df["_y"]       = df["_fecha_baja"].dt.year
    df["_m"]       = df["_fecha_baja"].dt.month
    df["_meses_r"] = (df["_fecha_baja"] - df["_fecha_ingreso"]).dt.days / 30
    df["_iv"]      = df["_meses_r"].apply(_cat)
    df = df.dropna(subset=["_iv"])
    df = df[df["_y"] >= 2021]

    if df.empty:
        return "<p style='padding:12px;color:#666'>Sin datos.</p>", 60

    if granularity == "trimestre":
        df["_p"] = ((df["_m"] - 1) // 3 + 1)
        def fmt_p(p): return f"Q{int(p)}"
    else:
        df["_p"] = df["_m"]
        def fmt_p(p): return str(int(p))

    piv = (
        df.groupby(["_y", "_p", "_iv"])
        .size().unstack(fill_value=0)
        .reindex(columns=IVLS, fill_value=0)
    )
    yr_piv = (
        df.groupby(["_y", "_iv"])
        .size().unstack(fill_value=0)
        .reindex(columns=IVLS, fill_value=0)
    )
    years = sorted(df["_y"].unique())

    # Detalle drill-down
    bdata_rows = []
    for _, r in df.iterrows():
        bdata_rows.append({
            "id":  _norm_id_cs(str(r.get("ID CRM") or "")),
            "nom": str(r.get("Nombre") or ""),
            "fi":  _fmt_fecha(r["_fecha_ingreso"]) if pd.notna(r["_fecha_ingreso"]) else "–",
            "fb":  _fmt_fecha(r["_fecha_baja"])    if pd.notna(r["_fecha_baja"])    else "–",
            "fis": r["_fecha_ingreso"].strftime("%Y-%m-%d") if pd.notna(r["_fecha_ingreso"]) else "",
            "fbs": r["_fecha_baja"].strftime("%Y-%m-%d")    if pd.notna(r["_fecha_baja"])    else "",
            "mr":  round(float(r["_meses_r"]), 1) if pd.notna(r["_meses_r"]) else None,
            "yr":  int(r["_y"]),
            "mb":  int(r["_m"]),
        })
    filter_js = _make_filter_js(json.dumps(bdata_rows, ensure_ascii=False))

    def _cells(cnt, fb):
        total = sum(cnt.get(iv, 0) for iv in IVLS)
        n_html = p_html = ""
        for iv in IVLS:
            n   = cnt.get(iv, 0)
            frc = n / total if total > 0 else 0.0
            _fj = json.dumps({**fb, "iv": iv})
            oc  = f" onclick='filterClick({_fj})'" if n > 0 else ""
            n_html += f'<td class="c-n"{oc}>{n if n > 0 else ""}</td>'
            p_html += f'<td class="c-p">{str(round(frc * 100)) + "%" if n > 0 else ""}</td>'
        return total, n_html, p_html

    tbody    = ""
    n_p_rows = 0

    def _hvals_yr(yr, field):
        if not hist_map: return ""
        vals = [hist_map.get((int(yr), m), {}).get(field) for m in range(1, 13)]
        vals = [v for v in vals if v is not None and v == v]  # drop None and NaN
        if not vals: return ""
        s = sum(vals)
        return str(int(round(s))) if field != "cpv" else str(int(round(s / len(vals))))

    def _hvals_p(yr, months_p, field):
        if not hist_map: return ""
        vals = [hist_map.get((int(yr), m), {}).get(field) for m in months_p]
        vals = [v for v in vals if v is not None and v == v]
        if not vals: return ""
        s = sum(vals)
        return str(int(round(s))) if field != "cpv" else str(int(round(s / len(vals))))

    for yr in years:
        fb_yr  = {"yr": int(yr), "months": None, "iv": None}
        yr_cnt = {iv: int(yr_piv.loc[yr, iv]) if yr in yr_piv.index else 0 for iv in IVLS}
        tot, nh, ph = _cells(yr_cnt, fb_yr)
        oc_yr = f" onclick='filterClick({json.dumps(fb_yr)})'" if tot > 0 else ""
        tbody += (
            f'<tr class="yr-row">'
            f'<td class="c-l"><button class="tbtn" id="btn-{yr}" data-open="0"'
            f' onclick="tog(\'{yr}\')">&#9654;</button>{yr}</td>'
            f'<td class="c-n">{_hvals_yr(yr, "ventas")}</td>'
            f'<td class="c-n">{_hvals_yr(yr, "publicidad")}</td>'
            f'<td class="c-n">{_hvals_yr(yr, "cpv")}</td>'
            f'<td class="c-n"{oc_yr}>{tot if tot > 0 else ""}</td>'
            f'{nh}{ph}</tr>'
        )
        if yr in piv.index.get_level_values(0):
            for p in sorted(piv.loc[yr].index):
                n_p_rows += 1
                months_p = list(range((int(p) - 1) * 3 + 1, int(p) * 3 + 1)) if granularity == "trimestre" else [int(p)]
                fb_p  = {"yr": int(yr), "months": months_p, "iv": None}
                p_cnt = {iv: int(piv.loc[(yr, p), iv]) for iv in IVLS}
                tot_p, nh_p, ph_p = _cells(p_cnt, fb_p)
                oc_p = f" onclick='filterClick({json.dumps(fb_p)})'" if tot_p > 0 else ""
                tbody += (
                    f'<tr class="p-row yr-{yr}" style="display:none">'
                    f'<td class="c-l">{yr}&nbsp;{fmt_p(p)}</td>'
                    f'<td class="c-n">{_hvals_p(yr, months_p, "ventas")}</td>'
                    f'<td class="c-n">{_hvals_p(yr, months_p, "publicidad")}</td>'
                    f'<td class="c-n">{_hvals_p(yr, months_p, "cpv")}</td>'
                    f'<td class="c-n"{oc_p}>{tot_p if tot_p > 0 else ""}</td>'
                    f'{nh_p}{ph_p}</tr>'
                )

    sub_n = "".join(f'<th class="sh sh-n">{iv}</th>' for iv in IVLS)
    sub_p = "".join(f'<th class="sh sh-p">{iv}</th>' for iv in IVLS)
    height = (len(years) + n_p_rows) * 28 + 130

    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_CSS}</style></head><body>"
        "<div class='wrap'><table><thead>"
        "<tr>"
        "<th rowspan='2' class='h-n'>Cohorte</th>"
        "<th rowspan='2' class='h-n'>Total ventas</th>"
        "<th rowspan='2' class='h-n'>Publicidad</th>"
        "<th rowspan='2' class='h-n'>CPV</th>"
        "<th rowspan='2' class='h-n'>Total bajas</th>"
        "<th colspan='5' class='h-n'>Bajas por fecha de baja</th>"
        "<th colspan='5' class='h-p'>%</th>"
        "</tr>"
        f"<tr>{sub_n}{sub_p}</tr>"
        "</thead>"
        f"<tbody>{tbody}</tbody>"
        "</table></div>"
        + _DET_DIV
        + f"<script>{_JS}</script>"
        + f"<script>{filter_js}</script>"
        + "</body></html>"
    )
    return html, height


# ── Main ──────────────────────────────────────────────────────────────────────

st.markdown("## Histórico")

with st.sidebar:
    st.title("📅 Histórico")
    st.markdown("---")
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    df_all = _cargar_monday()
except Exception as e:
    st.error(f"Error cargando datos de Monday: {e}")
    st.stop()

df_all   = df_all.drop_duplicates(subset=["monday_id"]).copy()
df_bajas = df_all[df_all["grupo_id"] != _GROUP_ACTIVOS].copy()

# Completar fecha_baja desde nombre del grupo cuando está vacía
_mask = df_bajas["_fecha_baja"].isna()
if _mask.any():
    df_bajas.loc[_mask, "_fecha_baja"] = (
        df_bajas.loc[_mask, "grupo_titulo"].apply(_inferir_fecha_grupo)
    )

# Deduplicar por ID CRM
_con_id = df_bajas[df_bajas["ID CRM"] != ""].copy()
_sin_id = df_bajas[df_bajas["ID CRM"] == ""].copy()
_con_id = (
    _con_id.sort_values("_fecha_baja", ascending=False, na_position="last")
    .drop_duplicates(subset=["ID CRM"], keep="first")
)
df_bajas = pd.concat([_con_id, _sin_id], ignore_index=True)

_col_lbl, _col_rad, _ = st.columns([1, 2, 6])
with _col_lbl:
    st.markdown('<div style="padding-top:8px;font-size:0.85rem;color:#444">Agrupar por:</div>', unsafe_allow_html=True)
with _col_rad:
    _gran = st.radio("", ["Mes", "Trimestre"], horizontal=True, key="gran_hist", label_visibility="collapsed")

st.markdown(
    '<div style="font-size:0.7rem;color:#999;margin-bottom:4px">'
    f'⚠️ Completar datos de Ventas/Publicidad/CPV en <a href="{_URL_HIST}" target="_blank" style="color:#999">esta tabla</a>'
    "</div>",
    unsafe_allow_html=True,
)

_hist_map = _cargar_tabla_hist()
_html, _h = _cohorte_html(df_bajas, granularity="trimestre" if _gran == "Trimestre" else "mes", hist_map=_hist_map)
components.html(_html, height=_h, scrolling=False)
