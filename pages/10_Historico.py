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

_BOARD_OB_IMPL  = "18390960078"
_COL_OB_RIESGO  = "color_mkyxb835"
_COL_OB_ID_CRM  = "bbdd"

@st.cache_data(ttl=86400)
def _cargar_ob_riesgo_lookup() -> dict:
    """Retorna {nombre_lower: riesgo_str} desde el board de implementación OB."""
    cols_ids = [_COL_OB_RIESGO]
    fragment = f'name column_values(ids: {json.dumps(cols_ids)}) {{ id text }}'
    q = (
        f'{{ boards(ids: [{_BOARD_OB_IMPL}]) {{'
        f'  items_page(limit: 500) {{ cursor items {{ {fragment} }} }}'
        f'}}}}'
    )
    r      = _monday_request(q)
    page   = r["data"]["boards"][0]["items_page"]
    items  = list(page["items"])
    cursor = page.get("cursor")
    while cursor:
        q2 = f'{{ next_items_page(limit: 500, cursor: "{cursor}") {{ cursor items {{ {fragment} }} }} }}'
        r2 = _monday_request(q2)
        page = r2["data"]["next_items_page"]
        items.extend(page["items"])
        cursor = page.get("cursor")
    lookup = {}
    for item in items:
        nombre = (item.get("name") or "").strip().lower()
        cv     = {c["id"]: (c["text"] or "") for c in item["column_values"]}
        riesgo = cv.get(_COL_OB_RIESGO, "").strip()
        if nombre:
            lookup[nombre] = riesgo
    return lookup


_SHEET_SINDATA_URL = "https://docs.google.com/spreadsheets/d/1pputir93lb57bmFawlAiUMMK--758jRVCWSMOVX9tm0/export?format=csv&gid=0"

@st.cache_data(ttl=86400)
def _cargar_sindata_riesgo_lookup() -> dict:
    """Retorna {id_crm: riesgo, nombre_lower: riesgo} desde el sheet manual de sin data."""
    import requests, io
    r = requests.get(_SHEET_SINDATA_URL, timeout=15)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    lookup = {}
    _RIESGOS = ["Alto", "Medio", "Bajo"]
    for _, row in df.iterrows():
        riesgo = str(row.get("RIESGO") or "").strip()
        if riesgo not in _RIESGOS:
            continue
        id_crm = str(row.get("ID CRM") or "").strip()
        nombre = str(row.get("Nombre") or "").strip().lower()
        if id_crm and id_crm != "-" and id_crm != "nan":
            lookup[id_crm] = riesgo
        if nombre:
            lookup[nombre] = riesgo
    return lookup


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
table { border-collapse: collapse; width: 100%; font-size: 0.78rem; table-layout: fixed; }
thead { position: sticky; top: 0; z-index: 2; }
thead th { border: 1px dotted #9ab; }
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


def _cohorte_ingreso_html(df_all: pd.DataFrame, granularity: str, hist_map: dict = None, ltv_lookup: dict = None, ob_riesgo: dict = None, sindata_riesgo: dict = None) -> tuple[str, int]:
    """Tabla de cohortes por fecha de ingreso (fecha de venta).
    Ventas = todos los ingresados ese mes; Activos = sin baja; Bajas = con baja.
    Intervalos = meses entre ingreso y baja."""
    IVLS = ["0-3", "+3", "+6", "+12"]
    _hoy = pd.Timestamp(date.today())

    df_fi = df_all[df_all["_fecha_ingreso"].notna()].copy()
    # Solo 2025 y 2026
    df_fi = df_fi[df_fi["_fecha_ingreso"].dt.year.isin([2025, 2026])].copy()
    # Deduplicar por (ID CRM + Nombre)
    df_fi = df_fi[~df_fi.duplicated(subset=["ID CRM", "Nombre"], keep="first")].reset_index(drop=True)

    if df_fi.empty:
        return "<p style='padding:12px;color:#666'>Sin datos.</p>", 60

    df_fi["_y"] = df_fi["_fecha_ingreso"].dt.year
    df_fi["_m"] = df_fi["_fecha_ingreso"].dt.month
    df_fi["_es_baja"] = df_fi["grupo_id"] != _GROUP_ACTIVOS

    # Meses activos para bajas
    df_fi["_meses_r"] = None
    _mb = df_fi["_es_baja"] & df_fi["_fecha_baja"].notna()
    df_fi.loc[_mb, "_meses_r"] = (
        (df_fi.loc[_mb, "_fecha_baja"] - df_fi.loc[_mb, "_fecha_ingreso"]).dt.days / 30
    )
    df_fi["_iv"] = df_fi["_meses_r"].apply(_cat).replace("0", "0-3")

    if granularity == "trimestre":
        df_fi["_p"] = ((df_fi["_m"] - 1) // 3 + 1)
        def fmt_p(p): return f"Q{int(p)}"
    else:
        df_fi["_p"] = df_fi["_m"]
        def fmt_p(p): return str(int(p))

    # Pivots
    ventas_piv = df_fi.groupby(["_y", "_p"]).size()
    ventas_yr  = df_fi.groupby("_y").size()
    activos_piv = df_fi[~df_fi["_es_baja"]].groupby(["_y", "_p"]).size()
    activos_yr  = df_fi[~df_fi["_es_baja"]].groupby("_y").size()
    df_baj = df_fi[df_fi["_es_baja"] & df_fi["_iv"].notna()].copy()
    bajas_piv   = df_fi[df_fi["_es_baja"]].groupby(["_y", "_p"]).size()
    bajas_yr    = df_fi[df_fi["_es_baja"]].groupby("_y").size()
    iv_piv = (
        df_baj.groupby(["_y", "_p", "_iv"]).size()
        .unstack(fill_value=0).reindex(columns=IVLS, fill_value=0)
    )
    iv_yr = (
        df_baj.groupby(["_y", "_iv"]).size()
        .unstack(fill_value=0).reindex(columns=IVLS, fill_value=0)
    )
    years = sorted(df_fi["_y"].unique())

    # Pivot riesgo: activos y bajas 2026, usando lookup del board OB
    _RIESGOS = ["Alto", "Medio", "Bajo"]
    if ob_riesgo:
        _sd = sindata_riesgo or {}
        def _norm_riesgo(row):
            nombre = str(row.get("Nombre") or "").strip()
            id_crm = str(row.get("ID CRM") or "").strip()
            v = ob_riesgo.get(nombre.lower(), "")
            if v not in _RIESGOS and _sd:
                v = _sd.get(id_crm, "") or _sd.get(nombre.lower(), "")
            return v if v in _RIESGOS else "Sin data"
        df_act_riesgo = df_fi[(~df_fi["_es_baja"]) & (df_fi["_y"] == 2026)].copy()
        df_act_riesgo["_riesgo_n"] = df_act_riesgo.apply(_norm_riesgo, axis=1)
        _riesgo_yr  = df_act_riesgo.groupby(["_y", "_riesgo_n"]).size().unstack(fill_value=0)
        _riesgo_piv = df_act_riesgo.groupby(["_y", "_p", "_riesgo_n"]).size().unstack(fill_value=0)
        df_baj_riesgo = df_fi[df_fi["_es_baja"] & (df_fi["_y"] == 2026)].copy()
        df_baj_riesgo["_riesgo_n"] = df_baj_riesgo.apply(_norm_riesgo, axis=1)
        _riesgo_baj_yr  = df_baj_riesgo.groupby(["_y", "_riesgo_n"]).size().unstack(fill_value=0)
        _riesgo_baj_piv = df_baj_riesgo.groupby(["_y", "_p", "_riesgo_n"]).size().unstack(fill_value=0)
    else:
        _riesgo_yr = _riesgo_piv = None
        _riesgo_baj_yr = _riesgo_baj_piv = None

    def _riesgo_cells(yr, p=None, months=None, act_total=0):
        """Devuelve HTML de celdas Alto/Medio/Bajo/Sin data para activos 2026."""
        if yr != 2026 or _riesgo_yr is None:
            return "".join('<td class="c-rs rs-d"></td>' for _ in range(4))
        src = (_riesgo_piv.loc[(yr, p)] if p is not None and (yr, p) in _riesgo_piv.index
               else _riesgo_yr.loc[yr] if yr in _riesgo_yr.index else None)
        if src is None:
            return "".join('<td class="c-rs rs-d"></td>' for _ in range(4))
        alto     = int(src.get("Alto", 0))
        medio    = int(src.get("Medio", 0))
        bajo     = int(src.get("Bajo", 0))
        sin_data = int(src.get("Sin data", 0))
        def _c(v, cls, riesgo_val):
            if v:
                fj  = json.dumps({"yr": int(yr), "months": months, "iv": None, "eb_filter": False, "riesgo": riesgo_val})
                pct = f"<span style='font-size:0.75em'> ({round(v/act_total*100)}%)</span>" if act_total > 0 else ""
                return f"<td class='c-rs rs-d {cls}' onclick='filterClick({fj})' style='cursor:pointer'>{v}{pct}</td>"
            return f'<td class="c-rs rs-d {cls}"></td>'
        return _c(alto, "rs-a", "Alto") + _c(medio, "rs-m", "Medio") + _c(bajo, "rs-b", "Bajo") + _c(sin_data, "rs-s", "Sin data")

    def _riesgo_baj_cells(yr, p=None, months=None, baj_total=0):
        """Devuelve HTML de celdas Riesgo Alto/Medio/Bajo/Sin data para bajas 2026."""
        if yr != 2026 or _riesgo_baj_yr is None or baj_total == 0:
            return "".join('<td class="c-rs rs-baj-d"></td>' for _ in range(4))
        src = (_riesgo_baj_piv.loc[(yr, p)] if p is not None and (yr, p) in _riesgo_baj_piv.index
               else _riesgo_baj_yr.loc[yr] if yr in _riesgo_baj_yr.index else None)
        if src is None:
            return "".join('<td class="c-rs rs-baj-d"></td>' for _ in range(4))
        alto     = int(src.get("Alto", 0))
        medio    = int(src.get("Medio", 0))
        bajo     = int(src.get("Bajo", 0))
        sin_data = int(src.get("Sin data", 0))
        def _cb(v, cls, riesgo_val):
            if v:
                fj  = json.dumps({"yr": int(yr), "months": months, "iv": None, "eb_filter": True, "riesgo": riesgo_val})
                pct = f"<span style='font-size:0.75em'> ({round(v/baj_total*100)}%)</span>" if baj_total > 0 else ""
                return f"<td class='c-rs rs-baj-d {cls}' onclick='filterClick({fj})' style='cursor:pointer'>{v}{pct}</td>"
            return f'<td class="c-rs rs-baj-d {cls}"></td>'
        return _cb(alto, "rs-a", "Alto") + _cb(medio, "rs-m", "Medio") + _cb(bajo, "rs-b", "Bajo") + _cb(sin_data, "rs-s", "Sin data")

    # Agregados LTV por cohorte
    _ltv = ltv_lookup or {}
    _ltv_yr  = {}   # {yr:  {t, i, r}}
    _ltv_piv = {}   # {(yr,p): {t, i, r}}
    for _, _r in df_fi.iterrows():
        _vid    = _norm_id_cs(str(_r.get("ID CRM") or ""))
        _le     = _ltv.get(_vid, {})
        _lt, _li, _lr = (_le.get("ltv_t") or 0), (_le.get("ltv_i") or 0), (_le.get("ltv_r") or 0)
        _ky, _kp = int(_r["_y"]), (int(_r["_y"]), int(_r["_p"]))
        _ltv_yr.setdefault(_ky, {"t": 0, "i": 0, "r": 0})
        _ltv_yr[_ky]["t"] += _lt; _ltv_yr[_ky]["i"] += _li; _ltv_yr[_ky]["r"] += _lr
        _ltv_piv.setdefault(_kp, {"t": 0, "i": 0, "r": 0})
        _ltv_piv[_kp]["t"] += _lt; _ltv_piv[_kp]["i"] += _li; _ltv_piv[_kp]["r"] += _lr

    def _fmt_usd(v): return f"<span style='font-size:0.7rem;white-space:nowrap'>$ {int(round(v)):,}</span>".replace(",", ".") if v else ""

    # Datos detalle drill-down (todos los clientes, con flag eb=es_baja)

    bdata_rows = []
    for _, r in df_fi.iterrows():
        _fi_ok = pd.notna(r["_fecha_ingreso"])
        _fb_ok = pd.notna(r.get("_fecha_baja"))
        _eb    = bool(r["_es_baja"])
        _vid   = _norm_id_cs(str(r.get("ID CRM") or ""))
        _lentry = _ltv.get(_vid, {})
        bdata_rows.append({
            "id":      _vid,
            "nom":     str(r.get("Nombre") or ""),
            "fi":      _fmt_fecha(r["_fecha_ingreso"]) if _fi_ok else "–",
            "fb":      ("Activo" if not _eb else (_fmt_fecha(r["_fecha_baja"]) if _fb_ok else "–")),
            "fis":     r["_fecha_ingreso"].strftime("%Y-%m-%d") if _fi_ok else "",
            "fbs":     r["_fecha_baja"].strftime("%Y-%m-%d")    if _fb_ok else "",
            "mr":      round(float(r["_meses_r"]), 1) if pd.notna(r.get("_meses_r")) else None,
            "yr":      int(r["_y"]),
            "mb":      int(r["_m"]),
            "eb":      _eb,
            "ltv_t":   _lentry.get("ltv_t"),
            "ltv_i":   _lentry.get("ltv_i"),
            "ltv_r":   _lentry.get("ltv_r"),
            "tkt_rec": _lentry.get("tkt_rec"),
            "riesgo":  _norm_riesgo(r) if ob_riesgo else "Sin data",
        })
    _bdata_safe = json.dumps(bdata_rows, ensure_ascii=False).replace("</", "<\\/")
    _custom_render = """
function _fmt$(v){return v!=null?'$'+v.toLocaleString():'-';}
function renderDet(rows){
  _lastRows=rows;
  document.getElementById('det-title').textContent=rows.length+' registros';
  var bdy=document.getElementById('det-body');
  if(!rows.length){
    bdy.innerHTML='<p style="padding:12px;color:#666;font-size:0.78rem">Sin registros.</p>';
    document.getElementById('det').style.display='block';
    return;
  }
  var S='padding:5px 8px;font-weight:600;background:#1a3a5c;white-space:nowrap;position:sticky;top:0;overflow:hidden;text-overflow:ellipsis;';
  var _rCol={'Alto':'#c0392b','Medio':'#e67e22','Bajo':'#27ae60','':''};
  var h='<table style="width:100%;border-collapse:collapse;font-size:0.78rem;table-layout:fixed">'
    +'<colgroup>'
    +'<col style="width:90px"><col style="width:140px"><col style="width:80px"><col style="width:80px">'
    +'<col style="width:55px"><col style="width:60px"><col style="width:70px"><col style="width:70px"><col style="width:70px">'
    +'</colgroup>'
    +'<thead><tr style="color:#fff">'
    +'<th style="'+S+'text-align:left">ID CRM</th>'
    +'<th style="'+S+'text-align:left">Nombre</th>'
    +'<th style="'+S+'text-align:center;cursor:pointer" onclick="sortDet(0)">F. ingreso'+_arr(0)+'</th>'
    +'<th style="'+S+'text-align:center;cursor:pointer" onclick="sortDet(1)">F. baja'+_arr(1)+'</th>'
    +'<th style="'+S+'text-align:center;cursor:pointer" onclick="sortDet(2)">Meses'+_arr(2)+'</th>'
    +'<th style="'+S+'text-align:center">Riesgo</th>'
    +'<th style="'+S+'text-align:right;cursor:pointer" onclick="sortDet(3)">LTV T</th>'
    +'<th style="'+S+'text-align:right;cursor:pointer" onclick="sortDet(4)">LTV I</th>'
    +'<th style="'+S+'text-align:right;cursor:pointer" onclick="sortDet(5)">LTV R</th>'
    +'</tr></thead><tbody>';
  for(var i=0;i<rows.length;i++){
    var r=rows[i],bg=i%2?'#fff':'#f8f9fa';
    var _rc=_rCol[r.riesgo||'']||'#95a5a6';
    var _rv=r.riesgo||'-';
    h+='<tr style="background:'+bg+'">'
      +'<td style="padding:4px 8px;border-bottom:1px solid #eee;max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+(r.id||'-')+'">'+(r.id||'-')+'</td>'
      +'<td style="padding:4px 8px;border-bottom:1px solid #eee;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+r.nom+'">'+r.nom+'</td>'
      +'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:center">'+r.fi+'</td>'
      +'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:center">'+r.fb+'</td>'
      +'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:center">'+(r.mr!=null?Math.round(r.mr*10)/10+'m':'-')+'</td>'
      +'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:center;font-weight:bold;color:'+_rc+'">'+_rv+'</td>'
      +'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:right">'+_fmt$(r.ltv_t)+'</td>'
      +'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:right">'+_fmt$(r.ltv_i)+'</td>'
      +'<td style="padding:4px 8px;border-bottom:1px solid #eee;text-align:right">'+_fmt$(r.ltv_r)+'</td>'
      +'</tr>';
  }
  bdy.innerHTML=h+'</tbody></table>';
  document.getElementById('det').style.display='block';
}
"""
    filter_js = (
        "var BDATA=" + _bdata_safe + ";\n"
        "var _SKEYS=['fis','fbs','mr','ltv_t','ltv_i','ltv_r'];\n"
        + _IFRAME_JS_TMPL.replace(
            "var _SKEYS=['fis','fbs','mr'];", "",
        ).replace(
            "function filterClick(p){",
            "function filterClick(p){\n  var eb_filter=p.eb_filter;",
        ).replace(
            "if(p.iv&&_ivl(r.mr)!==p.iv)return false;",
            "if(p.iv&&_ivl(r.mr)!==p.iv)return false;\n    if(eb_filter!=null&&r.eb!==eb_filter)return false;\n    if(p.riesgo&&r.riesgo!==p.riesgo)return false;",
        ).replace(
            "function renderDet(rows){", "function _renderDet_orig(rows){\n",  # neutralizar original
        )
        + _custom_render
    )

    def _fmt_hv(v):
        return f"<span style='font-size:0.7rem;white-space:nowrap'>$ {int(round(v)):,}</span>".replace(",", ".")

    def _hv_yr(yr, field):
        if not hist_map: return ""
        vals = [hist_map.get((int(yr), m), {}).get(field) for m in range(1, 13)]
        vals = [v for v in vals if v is not None and v == v]
        if not vals: return ""
        s = sum(vals)
        return _fmt_hv(s if field != "cpv" else s / len(vals))

    def _hv_p(yr, months_p, field):
        if not hist_map: return ""
        vals = [hist_map.get((int(yr), m), {}).get(field) for m in months_p]
        vals = [v for v in vals if v is not None and v == v]
        if not vals: return ""
        s = sum(vals)
        return _fmt_hv(s if field != "cpv" else s / len(vals))

    def _cells(cnt, ventas_total, fb):
        n_html = a_html = ""
        acum = 0.0
        for iv in IVLS:
            n   = cnt.get(iv, 0)
            frc = n / ventas_total if ventas_total > 0 else 0.0
            acum += frc
            _fj  = json.dumps({**fb, "iv": iv, "eb_filter": True})
            oc   = f" onclick='filterClick({_fj})'" if n > 0 else ""
            _pct = f"<span style='font-size:0.75em'> ({round(frc*100)}%)</span>" if n > 0 else ""
            n_html += f'<td class="c-p"{oc}>{(str(n) + _pct) if n > 0 else ""}</td>'
            _acum_pct = round(acum * 100)
            a_html += f'<td class="c-a">{str(_acum_pct) + "%" if ventas_total > 0 and _acum_pct > 0 else ""}</td>'
        return n_html, a_html

    tbody    = ""
    n_p_rows = 0

    for yr in years:
        fb_yr    = {"yr": int(yr), "months": None, "iv": None}
        vtas_yr  = int(ventas_yr.get(yr, 0))
        act_yr   = int(activos_yr.get(yr, 0))
        baj_yr   = int(bajas_yr.get(yr, 0))
        yr_iv    = {iv: int(iv_yr.loc[yr, iv]) if yr in iv_yr.index else 0 for iv in IVLS}
        _fb_yr_all  = {**fb_yr, "eb_filter": None}
        _fb_yr_act  = {**fb_yr, "eb_filter": False}
        _fb_yr_baj  = {**fb_yr, "eb_filter": True}
        _baj_yr_pct = f"<span style='font-size:0.75em'> ({round(baj_yr/vtas_yr*100)}%)</span>" if vtas_yr > 0 and baj_yr > 0 else ""
        oc_yr      = f" onclick='filterClick({json.dumps(_fb_yr_baj)})'" if baj_yr > 0 else ""
        oc_vtas_yr = f" onclick='filterClick({json.dumps(_fb_yr_all)})' style='cursor:pointer'" if vtas_yr > 0 else ""
        oc_act_yr  = f" onclick='filterClick({json.dumps(_fb_yr_act)})' style='cursor:pointer'" if act_yr > 0 else ""
        nh, ah = _cells(yr_iv, vtas_yr, fb_yr)
        _act_yr_pct = f"<span style='font-size:0.75em'> ({round(act_yr/vtas_yr*100)}%)</span>" if vtas_yr > 0 and act_yr > 0 else ""
        _lyr = _ltv_yr.get(yr, {"t": 0, "i": 0, "r": 0})
        _ltv_prom_yr = _fmt_usd(_lyr["t"] / vtas_yr) if vtas_yr > 0 and _lyr["t"] else ""
        tbody += (
            f'<tr class="yr-row">'
            f'<td class="c-l"><button class="tbtn" id="btn-{yr}" data-open="0"'
            f' onclick="tog(\'{yr}\')">&#9654;</button>{yr}</td>'
            f'<td class="c-n"{oc_vtas_yr}>{vtas_yr or ""}</td>'
            f'<td class="c-n" style="white-space:nowrap">{_hv_yr(yr, "publicidad")}</td>'
            f'<td class="c-n" style="white-space:nowrap">{_hv_yr(yr, "cpv")}</td>'
            f'<td class="c-n ing-t" style="white-space:nowrap">{_fmt_usd(_lyr["t"])}</td>'
            f'<td class="c-rs ing-d" style="white-space:nowrap">{_fmt_usd(_lyr["r"])}</td>'
            f'<td class="c-rs ing-d" style="white-space:nowrap">{_fmt_usd(_lyr["i"])}</td>'
            f'<td class="c-n" style="white-space:nowrap">{_ltv_prom_yr}</td>'
            f'<td class="c-n"{oc_act_yr}>{(str(act_yr) + _act_yr_pct) if act_yr else ""}</td>'
            f'{_riesgo_cells(yr, months=None, act_total=act_yr)}'
            f'<td class="c-n"{oc_yr}>{(str(baj_yr) + _baj_yr_pct) if baj_yr else ""}</td>'
            f'{nh}{ah}'
            f'{_riesgo_baj_cells(yr, months=None, baj_total=baj_yr)}</tr>'
        )
        periods_yr = sorted(df_fi[df_fi["_y"] == yr]["_p"].unique())
        for p in periods_yr:
            n_p_rows += 1
            months_p   = list(range((int(p)-1)*3+1, int(p)*3+1)) if granularity == "trimestre" else [int(p)]
            fb_p       = {"yr": int(yr), "months": months_p, "iv": None}
            vtas_p     = int(ventas_piv.get((yr, p), 0))
            act_p      = int(activos_piv.get((yr, p), 0))
            baj_p      = int(bajas_piv.get((yr, p), 0))
            p_iv       = ({iv: int(iv_piv.loc[(yr, p), iv]) for iv in IVLS}
                          if (yr, p) in iv_piv.index else {iv: 0 for iv in IVLS})
            _fb_p_all  = {**fb_p, "eb_filter": None}
            _fb_p_act  = {**fb_p, "eb_filter": False}
            _fb_p_baj  = {**fb_p, "eb_filter": True}
            _baj_p_pct = f"<span style='font-size:0.75em'> ({round(baj_p/vtas_p*100)}%)</span>" if vtas_p > 0 and baj_p > 0 else ""
            oc_p       = f" onclick='filterClick({json.dumps(_fb_p_baj)})'" if baj_p > 0 else ""
            oc_vtas_p  = f" onclick='filterClick({json.dumps(_fb_p_all)})' style='cursor:pointer'" if vtas_p > 0 else ""
            oc_act_p   = f" onclick='filterClick({json.dumps(_fb_p_act)})' style='cursor:pointer'" if act_p > 0 else ""
            nh_p, ah_p = _cells(p_iv, vtas_p, fb_p)
            _act_p_pct = f"<span style='font-size:0.75em'> ({round(act_p/vtas_p*100)}%)</span>" if vtas_p > 0 and act_p > 0 else ""
            _lp = _ltv_piv.get((yr, int(p)), {"t": 0, "i": 0, "r": 0})
            _ltv_prom_p = _fmt_usd(_lp["t"] / vtas_p) if vtas_p > 0 and _lp["t"] else ""
            tbody += (
                f'<tr class="p-row yr-{yr}" style="display:none">'
                f'<td class="c-l">{yr}&nbsp;{fmt_p(p)}</td>'
                f'<td class="c-n"{oc_vtas_p}>{vtas_p or ""}</td>'
                f'<td class="c-n" style="white-space:nowrap">{_hv_p(yr, months_p, "publicidad")}</td>'
                f'<td class="c-n" style="white-space:nowrap">{_hv_p(yr, months_p, "cpv")}</td>'
                f'<td class="c-n ing-t" style="white-space:nowrap">{_fmt_usd(_lp["t"])}</td>'
                f'<td class="c-rs ing-d" style="white-space:nowrap">{_fmt_usd(_lp["r"])}</td>'
                f'<td class="c-rs ing-d" style="white-space:nowrap">{_fmt_usd(_lp["i"])}</td>'
                f'<td class="c-n" style="white-space:nowrap">{_ltv_prom_p}</td>'
                f'<td class="c-n"{oc_act_p}>{(str(act_p) + _act_p_pct) if act_p else ""}</td>'
                f'{_riesgo_cells(yr, p, months=months_p, act_total=act_p)}'
                f'<td class="c-n"{oc_p}>{(str(baj_p) + _baj_p_pct) if baj_p else ""}</td>'
                f'{nh_p}{ah_p}'
                f'{_riesgo_baj_cells(yr, p, months=months_p, baj_total=baj_p)}</tr>'
            )

    sub_n = "".join(f'<th class="sh sh-p">{iv}</th>' for iv in IVLS)
    sub_a = "".join(f'<th class="sh sh-a">{iv}</th>' for iv in IVLS)
    height = (len(years) + n_p_rows) * 28 + 130

    _W_MAIN = "65"  # px para columnas principales
    _W_IV   = "52"  # px para columnas de intervalo
    _W_RS   = "64"  # px para columnas de riesgo
    _colgroup = (
        "<colgroup>"
        "<col style='width:80px'>"
        f"<col class='col-main' style='width:{_W_MAIN}px'>"
        f"<col class='col-main' style='width:{_W_MAIN}px'>"
        f"<col class='col-main' style='width:{_W_MAIN}px'>"
        f"<col class='col-main' style='width:{_W_MAIN}px'>"
        f"<col class='col-ing-d' style='width:0;overflow:hidden'>"
        f"<col class='col-ing-d' style='width:0;overflow:hidden'>"
        f"<col class='col-main' style='width:{_W_MAIN}px'>"
        f"<col class='col-main' style='width:{_W_MAIN}px'>"
        + "".join(f"<col class='col-rs-d' style='width:0;overflow:hidden'>" for _ in range(4))
        + f"<col class='col-main' style='width:{_W_MAIN}px'>"
        + "".join(f"<col style='width:{_W_IV}px'>" for _ in range(8))
        + "".join(f"<col class='col-rs-baj-d' style='width:0;overflow:hidden'>" for _ in range(4))
        + "</colgroup>"
    )

    _toggle_js = f"""
var _desglose=false;
function toggleDesglose(){{
  _desglose=!_desglose;
  document.querySelectorAll('.ing-d,.th-ing-d').forEach(function(c){{
    c.style.padding=_desglose?'':'0';
    c.style.borderWidth=_desglose?'':'0';
    c.style.overflow=_desglose?'':'hidden';
    c.style.fontSize=_desglose?'':'0';
    c.style.lineHeight=_desglose?'':'0';
  }});
  document.querySelectorAll('.col-ing-d').forEach(function(c){{
    c.style.width=_desglose?'{_W_MAIN}px':'0';
  }});
  document.querySelectorAll('.rs-d,.th-rs-d').forEach(function(c){{
    c.style.padding=_desglose?'':'0';
    c.style.borderWidth=_desglose?'':'0';
    c.style.overflow=_desglose?'':'hidden';
    c.style.fontSize=_desglose?'':'0';
    c.style.lineHeight=_desglose?'':'0';
  }});
  document.querySelectorAll('.col-rs-d').forEach(function(c){{
    c.style.width=_desglose?'{_W_RS}px':'0';
  }});
  document.querySelectorAll('.rs-baj-d,.th-rs-baj-d').forEach(function(c){{
    c.style.padding=_desglose?'':'0';
    c.style.borderWidth=_desglose?'':'0';
    c.style.overflow=_desglose?'':'hidden';
    c.style.fontSize=_desglose?'':'0';
    c.style.lineHeight=_desglose?'':'0';
  }});
  document.querySelectorAll('.col-rs-baj-d').forEach(function(c){{
    c.style.width=_desglose?'{_W_RS}px':'0';
  }});
  document.getElementById('btn-desglose').textContent=_desglose?'Ocultar desglose':'Mostrar desglose';
}}
document.addEventListener('DOMContentLoaded',function(){{
  var sel='.ing-d,.th-ing-d,.rs-d,.th-rs-d,.rs-baj-d,.th-rs-baj-d';
  document.querySelectorAll(sel).forEach(function(c){{
    c.style.padding='0';c.style.borderWidth='0';
    c.style.overflow='hidden';c.style.fontSize='0';c.style.lineHeight='0';
  }});
}});
"""
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_CSS}table{{table-layout:fixed}}"
        ".ing-d,.th-ing-d,.rs-d,.th-rs-d,.rs-baj-d,.th-rs-baj-d{overflow:hidden}"
        ".h-g{background:#5a5f63;color:#fff;font-weight:bold;padding:6px 4px;text-align:center;border:1px dotted #9ab}"
        ".c-g{background:#e2e5e8;color:#333}"
        ".h-rs{background:#2c3e50;color:#fff;font-weight:bold;padding:6px 4px;text-align:center;border:1px dotted #9ab}"
        ".sh-rs{background:#aab7c4;font-weight:bold;padding:4px;text-align:center;border:2px solid #8aabb8}"
        ".c-rs{border:1px dotted #bbb;padding:4px;text-align:center;background:#f4f6f8}"
        ".rs-a{color:#c0392b;font-weight:bold}"
        ".rs-m{color:#e67e22;font-weight:bold}"
        ".rs-b{color:#27ae60;font-weight:bold}"
        ".rs-s{color:#95a5a6}"
        "</style></head><body>"
        "<div style='text-align:right;margin-bottom:6px'>"
        "<button id='btn-desglose' onclick='toggleDesglose()'"
        " style='font-size:0.75rem;padding:3px 10px;border:1px solid #ccc;"
        "border-radius:4px;cursor:pointer;background:#f8f9fa'>Mostrar desglose</button>"
        "</div>"
        f"<div class='wrap'><table>{_colgroup}<thead>"
        "<tr>"
        "<th rowspan='2' class='h-n'>Cohorte</th>"
        "<th rowspan='2' class='h-n'>Ventas</th>"
        "<th rowspan='2' class='h-n'>Publicidad</th>"
        "<th rowspan='2' class='h-n'>CPV</th>"
        "<th rowspan='2' class='h-n' style='font-size:0.78rem'>Ingresos<br>totales</th>"
        "<th rowspan='2' class='h-rs th-ing-d' style='font-size:0.78rem'>Ing.<br>Recu.</th>"
        "<th rowspan='2' class='h-rs th-ing-d' style='font-size:0.78rem'>Ing.<br>Impl.</th>"
        "<th rowspan='2' class='h-n' style='font-size:0.78rem'>LTV<br>Prom.</th>"
        "<th rowspan='2' class='h-n'>Activos</th>"
        "<th colspan='4' class='h-rs th-rs-d'>Riesgo (2026)</th>"
        "<th rowspan='2' class='h-n'>Bajas</th>"
        "<th colspan='4' class='h-p'>Bajas por meses activos</th>"
        "<th colspan='4' class='h-a'>% acumulado</th>"
        "<th colspan='4' class='h-rs th-rs-baj-d' style='font-size:0.78rem'>Riesgo Bajas<br>(2026)</th>"
        "</tr>"
        f"<tr>"
        "<th class='sh sh-rs rs-d'>Alto</th><th class='sh sh-rs rs-d'>Medio</th>"
        "<th class='sh sh-rs rs-d'>Bajo</th><th class='sh sh-rs rs-d'>Sin data</th>"
        f"{sub_n}{sub_a}"
        "<th class='sh sh-rs rs-baj-d'>Alto</th><th class='sh sh-rs rs-baj-d'>Medio</th>"
        "<th class='sh sh-rs rs-baj-d'>Bajo</th><th class='sh sh-rs rs-baj-d'>Sin data</th>"
        "</tr>"
        "</thead>"
        f"<tbody>{tbody}</tbody>"
        "</table></div>"
        + _DET_DIV
        + f"<script>{_JS}</script>"
        + f"<script>{filter_js}</script>"
        + f"<script>{_toggle_js}</script>"
        + "</body></html>"
    )
    return html, height


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
        n_html = p_html = a_html = ""
        acum = 0.0
        for iv in IVLS:
            n   = cnt.get(iv, 0)
            frc = n / total if total > 0 else 0.0
            acum += frc
            _fj = json.dumps({**fb, "iv": iv})
            oc  = f" onclick='filterClick({_fj})'" if n > 0 else ""
            n_html += f'<td class="c-n"{oc}>{n if n > 0 else ""}</td>'
            p_html += f'<td class="c-p">{str(round(frc * 100)) + "%" if n > 0 else ""}</td>'
            a_html += f'<td class="c-a">{str(round(acum * 100)) + "%" if total > 0 else ""}</td>'
        return total, n_html, p_html, a_html

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
        tot, nh, ph, ah = _cells(yr_cnt, fb_yr)
        oc_yr = f" onclick='filterClick({json.dumps(fb_yr)})'" if tot > 0 else ""
        tbody += (
            f'<tr class="yr-row">'
            f'<td class="c-l"><button class="tbtn" id="btn-{yr}" data-open="0"'
            f' onclick="tog(\'{yr}\')">&#9654;</button>{yr}</td>'
            f'<td class="c-n">{_hvals_yr(yr, "ventas")}</td>'
            f'<td class="c-n">{_hvals_yr(yr, "publicidad")}</td>'
            f'<td class="c-n">{_hvals_yr(yr, "cpv")}</td>'
            f'<td class="c-n"{oc_yr}>{tot if tot > 0 else ""}</td>'
            f'{nh}{ph}{ah}</tr>'
        )
        if yr in piv.index.get_level_values(0):
            for p in sorted(piv.loc[yr].index):
                n_p_rows += 1
                months_p = list(range((int(p) - 1) * 3 + 1, int(p) * 3 + 1)) if granularity == "trimestre" else [int(p)]
                fb_p  = {"yr": int(yr), "months": months_p, "iv": None}
                p_cnt = {iv: int(piv.loc[(yr, p), iv]) for iv in IVLS}
                tot_p, nh_p, ph_p, ah_p = _cells(p_cnt, fb_p)
                oc_p = f" onclick='filterClick({json.dumps(fb_p)})'" if tot_p > 0 else ""
                tbody += (
                    f'<tr class="p-row yr-{yr}" style="display:none">'
                    f'<td class="c-l">{yr}&nbsp;{fmt_p(p)}</td>'
                    f'<td class="c-n">{_hvals_p(yr, months_p, "ventas")}</td>'
                    f'<td class="c-n">{_hvals_p(yr, months_p, "publicidad")}</td>'
                    f'<td class="c-n">{_hvals_p(yr, months_p, "cpv")}</td>'
                    f'<td class="c-n"{oc_p}>{tot_p if tot_p > 0 else ""}</td>'
                    f'{nh_p}{ph_p}{ah_p}</tr>'
                )

    sub_n = "".join(f'<th class="sh sh-n">{iv}</th>' for iv in IVLS)
    sub_p = "".join(f'<th class="sh sh-p">{iv}</th>' for iv in IVLS)
    sub_a = "".join(f'<th class="sh sh-a">{iv}</th>' for iv in IVLS)
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
        "<th colspan='5' class='h-a'>% acumulado</th>"
        "</tr>"
        f"<tr>{sub_n}{sub_p}{sub_a}</tr>"
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


import datos_ltv as _datos_ltv
try:
    _ltv_lookup_hist = _datos_ltv.cargar_ltv_lookup()
except Exception:
    _ltv_lookup_hist = {}

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

_tab_venta, _tab_baja = st.tabs(["Histórico por fecha de venta", "Histórico por fecha de baja"])

# ── Tab 1: Histórico por fecha de baja ───────────────────────────────────────
with _tab_baja:
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

# ── Tab 2: Histórico por fecha de venta ──────────────────────────────────────
with _tab_venta:
    _col_lbl2, _col_rad2, _ = st.columns([1, 2, 6])
    with _col_lbl2:
        st.markdown('<div style="padding-top:8px;font-size:0.85rem;color:#444">Agrupar por:</div>', unsafe_allow_html=True)
    with _col_rad2:
        _gran2 = st.radio("", ["Mes", "Trimestre"], horizontal=True, key="gran_hist2", label_visibility="collapsed")

    _hist_map2 = _cargar_tabla_hist()
    try:
        _ob_riesgo = _cargar_ob_riesgo_lookup()
    except Exception:
        _ob_riesgo = {}
    try:
        _sindata_riesgo = _cargar_sindata_riesgo_lookup()
    except Exception:
        _sindata_riesgo = {}
    _html2, _h2 = _cohorte_ingreso_html(df_all, granularity="trimestre" if _gran2 == "Trimestre" else "mes", hist_map=_hist_map2, ltv_lookup=_ltv_lookup_hist, ob_riesgo=_ob_riesgo, sindata_riesgo=_sindata_riesgo)
    components.html(_html2, height=_h2, scrolling=False)
