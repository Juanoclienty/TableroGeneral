"""
6_LTV.py — LTV por cliente (USD).
Los datos se leen del caché local (data/ltv_cache.pkl).
Para actualizar: Actualizar BD → Actualizar LTV.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datos_ltv

st.set_page_config(page_title="LTV", page_icon="💰", layout="wide", initial_sidebar_state="expanded")

# ── Carga desde caché ─────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _cargar_cache():
    return datos_ltv.cargar_ltv()

try:
    _data   = _cargar_cache()
    df_real = _data["real"]
    df_prom = _data["prom"]
    df_vtas = _data["ventas"]
    df_ads  = _data["ads"]
    _estado_lookup = _data["monday"]
except FileNotFoundError as _e:
    st.title("💰 LTV")
    st.warning(str(_e))
    st.info("Andá a **Actualizar BD → Actualizar LTV** para cargar los datos por primera vez.")
    st.stop()
except Exception as _e:
    st.title("💰 LTV")
    st.error(f"Error cargando caché LTV: {_e}")
    st.stop()


# ── Helpers ───────────────────────────────────────────────────────

_MESES_ES = {1:"ene",2:"feb",3:"mar",4:"abr",5:"may",6:"jun",
             7:"jul",8:"ago",9:"sep",10:"oct",11:"nov",12:"dic"}

def _mes_es(ts) -> str:
    return f"{_MESES_ES[ts.month]}-{ts.strftime('%y')}"


# ── CPV mensual ───────────────────────────────────────────────────

_inv_por_mes: dict = {}
try:
    if not df_ads.empty and "fecha" in df_ads.columns and "inversion" in df_ads.columns:
        _ads_m = df_ads.copy()
        _ads_m["_p"] = pd.to_datetime(_ads_m["fecha"], errors="coerce").dt.to_period("M")
        _inv_por_mes = _ads_m.groupby("_p")["inversion"].sum().to_dict()
except Exception:
    pass

_vtas_por_mes: dict = {}
try:
    if not df_vtas.empty:
        _vm = df_vtas.dropna(subset=["_fecha"]).copy()
        _vm["_p"] = _vm["_fecha"].dt.to_period("M")
        _vtas_por_mes = _vm.groupby("_p").size().to_dict()
except Exception:
    pass


def _cpv_mes(periodo) -> float | None:
    inv = float(_inv_por_mes.get(periodo, 0))
    n   = int(_vtas_por_mes.get(periodo, 0))
    return round(inv / n) if n > 0 and inv > 0 else None


# ── Lookup ID → primera fecha de venta ───────────────────────────

_fecha_por_id: dict = {}
if not df_vtas.empty:
    for _, row in df_vtas.dropna(subset=["_fecha"]).sort_values("_fecha").iterrows():
        idk = row["_id"]
        if idk and idk not in _fecha_por_id:
            _fecha_por_id[idk] = row["_fecha"]


# ── Agregar LTV por cliente ───────────────────────────────────────

_real_rec  = df_real[~df_real["_es_impl"]].groupby("_id")["_usd"].sum()
_real_impl = df_real[df_real["_es_impl"]].groupby("_id")["_usd"].sum()
_real_cli  = df_real.groupby("_id")["_cliente"].first()

_prom_rec = df_prom.groupby("_id")["_usd"].sum()
_prom_cli = df_prom.groupby("_id")["_cliente"].first()

_todos_ids = sorted(
    set(_real_rec.index) | set(_real_impl.index) | set(_prom_rec.index),
    key=lambda x: (not x.lstrip("-").isdigit(), x),
)

_FINNEGANS = pd.Timestamp("2024-09-01")

filas = []
for idk in _todos_ids:
    if not idk:
        continue
    _fv = _fecha_por_id.get(idk)
    _pre_finnegans = (_fv is not None and pd.notna(_fv) and pd.Timestamp(_fv) < _FINNEGANS)
    rec  = float(_real_rec.get(idk, 0)) + (float(_prom_rec.get(idk, 0)) if _pre_finnegans else 0.0)
    impl = float(_real_impl.get(idk, 0))

    _c = _real_cli.get(idk)
    if _c is None or (isinstance(_c, float) and pd.isna(_c)):
        _c = _prom_cli.get(idk)
    cli = str(_c).strip() if _c is not None else "–"
    if cli in ("nan", "None", ""):
        cli = "–"

    fecha_ts = _fecha_por_id.get(idk)
    if fecha_ts is not None and pd.notna(fecha_ts):
        _p        = pd.Timestamp(fecha_ts).to_period("M")
        cpv       = _cpv_mes(_p)
        fecha_str = pd.Timestamp(fecha_ts).strftime("%d/%m/%Y")
    else:
        cpv       = None
        fecha_str = "–"

    _fecha_baja = _estado_lookup.get(idk, pd.NaT)
    _es_baja    = pd.notna(_fecha_baja)
    filas.append({
        "ID CRM":    idk,
        "Cliente":   cli,
        "Mes venta": _mes_es(pd.Timestamp(fecha_ts)) if fecha_ts is not None and pd.notna(fecha_ts) else None,
        "Estado":    "Baja" if _es_baja else "Activo",
        "Mes baja":  _mes_es(_fecha_baja) if _es_baja else None,
        "CPV":       float(cpv) if cpv is not None else float("nan"),
        "LTV R":     rec,
        "LTV I":     impl,
        "LTV T":     rec + impl,
    })

df_ltv = pd.DataFrame(filas)

if df_ltv.empty:
    st.warning("Sin datos en las fuentes LTV.")
    st.stop()


# ── Sidebar ───────────────────────────────────────────────────────

with st.sidebar:
    st.title("💰 LTV")
    st.markdown("---")
    _fecha_cache = datos_ltv.cache_fecha()
    if _fecha_cache:
        st.caption(f"Datos al: {_fecha_cache}")
    st.markdown("---")


# ── Tabla ─────────────────────────────────────────────────────────

st.title("💰 LTV")

df_show = df_ltv.copy().sort_values("LTV T", ascending=False)

_MESES_ES_NUM = {v: k for k, v in _MESES_ES.items()}

def _mes_sort_key(s):
    try:
        m, a = s.split("-")
        return (2000 + int(a)) * 100 + _MESES_ES_NUM.get(m, 0)
    except Exception:
        return 0

def _anios_de(col):
    vals = df_show[col].dropna()
    return sorted({2000 + int(s.split("-")[1]) for s in vals if "-" in s}, reverse=True)

def _meses_de(col, anio_str):
    vals = df_show[col].dropna().unique().tolist()
    if anio_str != "Todos":
        sfx = anio_str[-2:]
        vals = [v for v in vals if v.endswith(sfx)]
    return sorted(vals, key=_mes_sort_key)

_fa1, _fa2, _fa3, _fa4, _fa5 = st.columns([1, 1, 1, 1, 2])
_anios_v_opts  = ["Todos"] + [str(a) for a in _anios_de("Mes venta")]
_filtro_anio_v = _fa1.selectbox("Año venta", _anios_v_opts)
_filtro_mv     = _fa2.selectbox("Mes venta", ["Todos"] + _meses_de("Mes venta", _filtro_anio_v))
_anios_b_opts  = ["Todos"] + [str(a) for a in _anios_de("Mes baja")]
_filtro_anio_b = _fa3.selectbox("Año baja",  _anios_b_opts)
_filtro_mb     = _fa4.selectbox("Mes baja",  ["Todos"] + _meses_de("Mes baja",  _filtro_anio_b))
_buscar_id     = _fa5.text_input("🔍 Buscar por ID o nombre", "", placeholder="Ej: 13281959 o Vargas")

if _filtro_anio_v != "Todos":
    df_show = df_show[df_show["Mes venta"].fillna("").str.endswith(_filtro_anio_v[-2:])]
if _filtro_mv != "Todos":
    df_show = df_show[df_show["Mes venta"] == _filtro_mv]
if _filtro_anio_b != "Todos":
    df_show = df_show[df_show["Mes baja"].fillna("").str.endswith(_filtro_anio_b[-2:])]
if _filtro_mb != "Todos":
    df_show = df_show[df_show["Mes baja"] == _filtro_mb]
if _buscar_id:
    _q = _buscar_id.strip()
    df_show = df_show[
        df_show["ID CRM"].str.contains(_q, case=False, na=False)
        | df_show["Cliente"].str.contains(_q, case=False, na=False)
    ]

st.markdown(f"**{len(df_show):,} clientes**")

st.dataframe(
    df_show,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Mes venta": st.column_config.TextColumn("Mes venta"),
        "CPV": st.column_config.NumberColumn(
            "CPV (USD)", format="$ %.0f",
            help="Costo por venta del mes en que se cerró la venta",
        ),
        "LTV R": st.column_config.NumberColumn("LTV R (USD)", format="$ %.0f",
            help="Facturación acumulada (excluye Implementación)"),
        "LTV I": st.column_config.NumberColumn("LTV I (USD)", format="$ %.0f"),
        "LTV T": st.column_config.NumberColumn("LTV T (USD)", format="$ %.0f"),
    },
)

st.markdown(
    '<div style="text-align:right;font-size:0.68rem;color:#94a3b8;margin-top:4px">'
    'LTV Real (Finnegans) + LTV Prom pre-Finnegans · '
    'Fecha de venta y CPV: BBDD_Ventas · Moneda: USD'
    '</div>',
    unsafe_allow_html=True,
)


# ── Tabla cohorte ─────────────────────────────────────────────────

st.markdown("---")
st.subheader("Cohortes de venta")

_df_coh = df_ltv[df_ltv["Mes venta"].notna()].copy()

def _mes_a_period(s):
    try:
        m, a = s.split("-")
        return pd.Period(year=2000+int(a), month=_MESES_ES_NUM[m], freq="M")
    except Exception:
        return None

_df_coh["_periodo"] = _df_coh["Mes venta"].apply(_mes_a_period)
_df_coh = _df_coh[_df_coh["_periodo"].apply(lambda p: p is not None and p.year >= 2025)]

_coh_rows = []
for _p, _grp in _df_coh.dropna(subset=["_periodo"]).groupby("_periodo"):
    _tot  = len(_grp)
    _ltv  = float(_grp["LTV T"].sum())
    _actv = int((_grp["Estado"] == "Activo").sum())
    _baj  = int((_grp["Estado"] == "Baja").sum())
    _cpv_vals = _grp["CPV"].dropna()
    _cpv_prom = float(_cpv_vals.mean()) if not _cpv_vals.empty else 0.0
    _ltv_prom = _ltv / _tot if _tot > 0 else 0.0
    _coh_rows.append({
        "_anio":    _p.year,
        "_mes":     _p.month,
        "_label":   f"{_p.year} {_p.month}",
        "total":    _tot,
        "activos":  _actv,
        "bajas":    _baj,
        "inv":      float(_inv_por_mes.get(_p, 0)),
        "ltv":      _ltv,
        "cpv_prom": _cpv_prom,
        "ltv_prom": _ltv_prom,
    })

df_coh = pd.DataFrame(_coh_rows).sort_values(["_anio", "_mes"])

_CSS_COH = """
* { box-sizing:border-box; margin:0; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       background:#fff; padding:4px 2px; }
.wrap { overflow:auto; border:1px solid #c8ccd0; border-radius:4px; }
table { border-collapse:collapse; width:100%; font-size:0.78rem; table-layout:fixed; }
thead th { position:sticky; top:0; z-index:2; border:1px dotted #9ab; }
.h-n { background:#1a3a5c; color:#fff; font-weight:bold; padding:8px 6px; text-align:center; }
td   { border:1px dotted #bbb; padding:5px 6px; text-align:center; }
.c-l { text-align:left; white-space:nowrap; }
.c-n { background:#d6eaf8; }
.c-p { background:#fdebd0; }
.c-a { background:#d5f5e3; }
.yr-row td  { font-weight:bold; }
.yr-row .c-l { background:#dde1e6; }
.p-row .c-l  { padding-left:20px !important; }
.tbtn { background:none; border:none; cursor:pointer; font-size:0.65rem;
        padding:0 3px 0 0; color:#444; vertical-align:middle; }
.tbtn:hover { color:#0055cc; }
"""

_JS_COH = """
function togc(yr) {
    var rows = document.querySelectorAll('.yrc-' + yr);
    var btn  = document.getElementById('btnc-' + yr);
    var open = btn.dataset.open === '1';
    rows.forEach(function(r){ r.style.display = open ? 'none' : ''; });
    btn.dataset.open = open ? '0' : '1';
    btn.innerHTML    = open ? '&#9654;' : '&#9660;';
}
"""

def _fmt_usd(v):
    return f"$ {v:,.0f}" if v else ""

_tbody = ""
_years = sorted(df_coh["_anio"].unique())
for _yr in _years:
    _grp_yr = df_coh[df_coh["_anio"] == _yr]
    _tv     = int(_grp_yr["total"].sum())
    _tact   = int(_grp_yr["activos"].sum())
    _tbaj   = int(_grp_yr["bajas"].sum())
    _ti     = float(_grp_yr["inv"].sum())
    _tl     = float(_grp_yr["ltv"].sum())
    _tcpv   = float(_grp_yr["cpv_prom"].mean()) if _tv > 0 else 0.0
    _tltv   = _tl / _tv if _tv > 0 else 0.0
    _tbody += (
        f'<tr class="yr-row">'
        f'<td class="c-l"><button class="tbtn" id="btnc-{_yr}" data-open="0"'
        f' onclick="togc(\'{_yr}\')">&#9654;</button>{_yr}</td>'
        f'<td class="c-n">{_tv}</td>'
        f'<td class="c-n">{_tact}</td>'
        f'<td class="c-n" style="color:#c0392b">{_tbaj}</td>'
        f'<td class="c-p">{_fmt_usd(_ti)}</td>'
        f'<td class="c-a">{_fmt_usd(_tl)}</td>'
        f'<td class="c-p">{_fmt_usd(_tcpv)}</td>'
        f'<td class="c-a">{_fmt_usd(_tltv)}</td>'
        f'</tr>'
    )
    for _, _row in _grp_yr.iterrows():
        _tbody += (
            f'<tr class="p-row yrc-{_yr}" style="display:none">'
            f'<td class="c-l">{_row["_label"]}</td>'
            f'<td class="c-n">{int(_row["total"])}</td>'
            f'<td class="c-n">{int(_row["activos"])}</td>'
            f'<td class="c-n" style="color:#c0392b">{int(_row["bajas"]) if _row["bajas"] > 0 else ""}</td>'
            f'<td class="c-p">{_fmt_usd(_row["inv"])}</td>'
            f'<td class="c-a">{_fmt_usd(_row["ltv"])}</td>'
            f'<td class="c-p">{_fmt_usd(_row["cpv_prom"])}</td>'
            f'<td class="c-a">{_fmt_usd(_row["ltv_prom"])}</td>'
            f'</tr>'
        )

_n_rows = len(df_coh) + len(_years)
_height = min(max(_n_rows * 28 + 70, 120), 520)

_html_coh = (
    "<!DOCTYPE html><html><head><meta charset='utf-8'>"
    f"<style>{_CSS_COH}</style></head><body>"
    "<div class='wrap'><table><thead><tr>"
    "<th class='h-n' style='width:120px'>Cohorte</th>"
    "<th class='h-n' style='width:65px'>Total</th>"
    "<th class='h-n' style='width:75px'>Activos</th>"
    "<th class='h-n' style='width:65px'>Bajas</th>"
    "<th class='h-n'>Inversión MKT</th>"
    "<th class='h-n'>Ingresos totales</th>"
    "<th class='h-n'>CPV Prom</th>"
    "<th class='h-n'>LTV Prom</th>"
    f"</tr></thead><tbody>{_tbody}</tbody></table></div>"
    f"<script>{_JS_COH}</script>"
    "</body></html>"
)

components.html(_html_coh, height=_height, scrolling=False)
