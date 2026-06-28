"""
5_VGF.py — Leads VGF (Very Good Fit).
Fuente: leads con etiqueta CRM "Proceso VGF" (API Clienty).
Datos enriquecidos con BBDD_CRM_Clienty (Notas + Fecha 1ra reunión).
Conclusiones individuales guardadas localmente en cache/vgf_conclusiones.json.
"""
import sys, os, io, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date
import urllib.request
import streamlit as st
import pandas as pd
import datos_crm
import graficos

st.set_page_config(page_title="VGF", page_icon="🌟", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.5rem; }
</style>
""", unsafe_allow_html=True)

_ID_BBDD_CRM  = "1BHzXgiDqYcnz7_kVASPCc65KXz4v6oqSeVCJlN48_J8"
_URL_BBDD_CRM = f"https://docs.google.com/spreadsheets/d/{_ID_BBDD_CRM}/edit?usp=sharing"
_CACHE_DIR    = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
_CONCLUS_FILE = os.path.join(_CACHE_DIR, "vgf_conclusiones.json")


# ── Persistencia de conclusiones ──────────────────────────────
def _load_conclusiones() -> dict:
    if os.path.exists(_CONCLUS_FILE):
        with open(_CONCLUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_conclusion(lead_id: str, texto: str):
    os.makedirs(_CACHE_DIR, exist_ok=True)
    data = _load_conclusiones()
    data[str(lead_id)] = texto
    with open(_CONCLUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Carga de datos ────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Cargando datos CRM...")
def _cargar_crm():
    return datos_crm.cargar_crm()

@st.cache_data(ttl=3600)
def _cargar_bbdd_crm() -> pd.DataFrame:
    url = (f"https://docs.google.com/spreadsheets/d/{_ID_BBDD_CRM}"
           f"/gviz/tq?tqx=out:csv&sheet=BBDD_CRM_Clienty")
    with urllib.request.urlopen(url, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="replace")
    df = pd.read_csv(io.StringIO(raw), dtype=str)
    df.columns = df.columns.str.strip()
    df["ID"] = df["ID"].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    col_fecha = "Dato interno hora 1ra reunion efectiva"
    df["_fecha_reunion"] = (
        pd.to_datetime(df[col_fecha], errors="coerce").dt.strftime("%d/%m/%Y %H:%M").fillna("")
        if col_fecha in df.columns else ""
    )
    df["_notas"] = df["Notas"].fillna("") if "Notas" in df.columns else ""
    return df[["ID", "_fecha_reunion", "_notas"]]


try:
    df_crm = _cargar_crm()
except Exception as e:
    st.error(f"Error al cargar CRM: {e}")
    st.stop()

try:
    df_bbdd = _cargar_bbdd_crm()
except Exception as e:
    df_bbdd = pd.DataFrame()
    st.warning(f"No se pudo cargar BBDD_CRM_Clienty: {e}")

# Dataset base: leads con etiqueta "Proceso VGF"
def _limpiar_id(df):
    df = df.copy()
    df["id"] = df["id"].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    return df

df_vgf = _limpiar_id(
    df_crm[df_crm["Etiquetas"].astype(str).str.contains("Proceso VGF", case=False, na=False)]
) if "Etiquetas" in df_crm.columns else pd.DataFrame(columns=df_crm.columns)


# ── Session state ─────────────────────────────────────────────
for _k, _v in [("vgf_sel_id", None), ("vgf_sel_nombre", ""), ("vgf_sel_estado", "")]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Sets para el embudo ───────────────────────────────────────
R1_PLUS = {
    "2 - R1", "3 - Filtrado en R1", "4 - Follow podcast",
    "5.2 - Filtrado pre R2", "5.3 - Reagendar R2", "5.1 - R2 confirmada",
    "2 Reunión", "Buyer Sin interés", "Coordinando reunión", "Irrelevante",
    "SDR - Irrelevante", "Contactar a Futuro", "Dijo que no", "Follow 2",
    "Follow Clienty", "Stand By", "Últimos detalles", "Venta ganada",
}
FOLLOW_PLUS = {
    "4 - Follow podcast",
    "5.2 - Filtrado pre R2", "5.3 - Reagendar R2", "5.1 - R2 confirmada",
    "2 Reunión", "Buyer Sin interés", "Coordinando reunión", "Irrelevante",
    "SDR - Irrelevante", "Contactar a Futuro", "Dijo que no", "Follow 2",
    "Follow Clienty", "Stand By", "Últimos detalles", "Venta ganada",
}
R2_PLUS = {
    "5.1 - R2 confirmada", "2 Reunión", "Coordinando reunión",
    "Buyer Sin interés", "Irrelevante", "SDR - Irrelevante",
    "Contactar a Futuro", "Dijo que no", "Follow 2", "Follow Clienty",
    "Stand By", "Últimos detalles", "Venta ganada",
}
PRESU_PLUS = {
    "Contactar a Futuro", "Dijo que no", "Follow 2", "Follow Clienty",
    "Stand By", "Últimos detalles", "Venta ganada",
}


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.title("🌟 VGF")

    st.markdown(f"""
<small style="color:#888;line-height:1.8">
📌 <b>Pendientes:</b><br>
• Completar fechas 1ra reunión<br>
• Cargar notas por lead<br>
• Actualizar conclusiones VGF<br>
• <a href="{_URL_BBDD_CRM}" target="_blank" style="color:#888">Abrir BBDD_CRM_Clienty →</a>
</small>
""", unsafe_allow_html=True)

    st.markdown("---")

    _all_estados = set(df_vgf["Estado"].dropna().unique()) if not df_vgf.empty else set()
    filtro_estado = st.selectbox("Estado CRM", ["Todos"] + sorted(_all_estados), key="vgf_estado")

    _all_usuarios = set()
    if "Usuario" in df_vgf.columns:
        _all_usuarios = set(df_vgf["Usuario"].dropna().unique())
    filtro_usuario = st.selectbox("Vendedor", ["Todos"] + sorted(_all_usuarios), key="vgf_usuario")

    st.markdown("---")
    st.caption("Filtrar por Fecha 1ra reunión (opcional)")
    _col_sd, _col_sh = st.columns(2)
    fecha_desde = _col_sd.date_input("Desde", value=date(2026, 5, 27), format="DD/MM/YYYY", key="vgf_fecha_desde")
    fecha_hasta = _col_sh.date_input("Hasta", value=None, format="DD/MM/YYYY", key="vgf_fecha_hasta")

    st.markdown("---")

    if st.button("🔄 Recargar datos", use_container_width=True):
        datos_crm.limpiar_cache()
        _cargar_crm.clear()
        _cargar_bbdd_crm.clear()
        st.cache_data.clear()
        st.rerun()

    st.caption("Fuente: CRM Clienty · BBDD_CRM_Clienty")


# ── Título ────────────────────────────────────────────────────
st.markdown("# 🌟 VGF")
st.markdown("Leads **Very Good Fit** — etiqueta CRM: *Proceso VGF*.")


# ── Preparar df ───────────────────────────────────────────────
df = df_vgf.copy()

if filtro_estado != "Todos":
    df = df[df["Estado"] == filtro_estado]
if filtro_usuario != "Todos" and "Usuario" in df.columns:
    df = df[df["Usuario"] == filtro_usuario]

# Enriquecer con BBDD_CRM (fecha reunion + notas)
if not df_bbdd.empty:
    df = df.merge(df_bbdd, left_on="id", right_on="ID", how="left")
df["_fecha_reunion"] = df.get("_fecha_reunion", pd.Series("", index=df.index)).fillna("")
df["_notas"]         = df.get("_notas",         pd.Series("", index=df.index)).fillna("")

# Conclusiones individuales
_conclus_dict = _load_conclusiones()
df["_conclusion"] = df["id"].astype(str).map(_conclus_dict).fillna("")

# Filtro de fecha reunión — solo aplica si el usuario seleccionó alguna fecha
if fecha_desde or fecha_hasta:
    _fechas_dt = pd.to_datetime(df["_fecha_reunion"], format="%d/%m/%Y %H:%M", errors="coerce")
    _mask = pd.Series(True, index=df.index)
    if fecha_desde:
        _mask &= _fechas_dt >= pd.Timestamp(fecha_desde)
    if fecha_hasta:
        _mask &= _fechas_dt <= pd.Timestamp(fecha_hasta) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    df = df[_mask].reset_index(drop=True)


# ── KPIs ──────────────────────────────────────────────────────
_total     = len(df)
_r1_cnt    = int(df["Estado"].isin(R1_PLUS).sum())
_r2_cnt    = int(df["Estado"].isin(R2_PLUS).sum())
_presu_cnt = int(df["Estado"].isin(PRESU_PLUS).sum())

def _pct_lbl(n, tot):
    return f"{round(n / tot * 100, 1)}% de leads" if tot > 0 else "–"

_card = (
    '<div style="flex:1;background:{bg};border:1px solid #e2e8f0;border-radius:10px;'
    'padding:20px 16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.06)">'
    '<div style="font-size:2rem;font-weight:700;color:{tc}">{val}</div>'
    '<div style="font-size:0.82rem;color:{sc};margin-top:5px">{lbl}</div>'
    '{pct_div}'
    '</div>'
)

def _make_card(val, lbl, pct_lbl="", highlight=False):
    bg  = "#4F46E5" if highlight else "white"
    tc  = "white"   if highlight else "#1e293b"
    sc  = "rgba(255,255,255,0.85)" if highlight else "#64748b"
    pc  = "rgba(255,255,255,0.9)"  if highlight else "#3b82f6"
    pct = (f'<div style="font-size:0.8rem;color:{pc};margin-top:3px;font-weight:500">{pct_lbl}</div>'
           if pct_lbl else "")
    return _card.format(bg=bg, tc=tc, sc=sc, val=val, lbl=lbl, pct_div=pct)

st.markdown(
    '<div style="display:flex;gap:12px;margin-bottom:16px">'
    + _make_card(_total,     "Total VGF")
    + _make_card(_r1_cnt,    "R1 efectiva",          _pct_lbl(_r1_cnt,    _total))
    + _make_card(_r2_cnt,    "R2 efectiva",          _pct_lbl(_r2_cnt,    _total))
    + _make_card(_presu_cnt, "Presupuesto enviado",  _pct_lbl(_presu_cnt, _total))
    + '</div>',
    unsafe_allow_html=True,
)

st.markdown("---")

# ── Detalle por semana VGF ────────────────────────────────────
_df_sem = df_vgf.copy()
_df_sem["_sem"] = pd.to_datetime(_df_sem.get("semana_inicio", pd.Series(dtype="datetime64[ns]")), errors="coerce")
_df_sem = _df_sem.dropna(subset=["_sem"])

if not _df_sem.empty:
    _todas_sems = sorted(_df_sem["_sem"].unique())
    _n_max_vgf  = len(_todas_sems)
    _col_sl, _ = st.columns([2, 5])
    _n_mostrar_vgf = _col_sl.slider(
        "Semanas a mostrar", min_value=min(3, _n_max_vgf), max_value=_n_max_vgf,
        value=min(6, _n_max_vgf), key="vgf_sem_slider"
    )
    _semanas = _todas_sems[-_n_mostrar_vgf:]

    _FILAS_VGF = [
        ("Leads VGF",      lambda e: pd.Series([True] * len(e), index=e.index)),
        ("R1",             lambda e: e.isin(R1_PLUS)),
        ("Follow podcast", lambda e: e.isin(FOLLOW_PLUS)),
        ("R2",             lambda e: e.isin(R2_PLUS)),
        ("Presupuesto",    lambda e: e.isin(PRESU_PLUS)),
    ]
    _S = "border:1px solid #e2e8f0"
    _BASE_TH = f"font-size:0.78rem;font-weight:600;padding:6px 8px;{_S};overflow:hidden"
    _BASE_TD = f"font-size:0.83rem;padding:5px 8px;{_S};overflow:hidden"
    _WM = "width:130px;min-width:130px"
    _WP = "width:105px;min-width:105px"
    _WS = "width:88px;min-width:88px"

    _hdr = f'<th style="text-align:left;color:#fff;background:#1a3a5c;{_WM};{_BASE_TH}">Métrica</th>'
    for _s in _semanas:
        _lbl = f"Sem · {pd.Timestamp(_s).strftime('%d/%m')}"
        _hdr += f'<th style="text-align:center;color:#fff;background:#1a3a5c;{_WP};{_BASE_TH}">{_lbl}</th>'
    _hdr += f'<th style="text-align:center;color:#fff;background:#1a3a5c;{_WS};{_BASE_TH}">Promedio</th>'

    # leads por semana (denominador tabla azul)
    _leads_por_sem = {_s: int(pd.Series([True] * len(_df_sem[_df_sem["_sem"] == _s])).sum()) for _s in _semanas}
    # presupuestos por semana (denominador tablas verdes)
    _presu_por_sem = {_s: int(_df_sem[_df_sem["_sem"] == _s]["Estado"].isin(PRESU_PLUS).sum()) for _s in _semanas}

    def _pct_lbl(n, denom):
        if not denom: return ""
        return f'<span style="font-size:0.65rem;color:#475569;margin-left:3px">({round(n*100/denom)}%)</span>'

    _body = ""
    for _ri, (_label, _mask_fn) in enumerate(_FILAS_VGF):
        _bg  = "#d6eaf8" if _ri % 2 == 0 else "#eef6fc"
        _bgs = "#a9cce3" if _ri % 2 == 0 else "#bcd9ec"
        _is_leads = _ri == 0
        _vals = []
        _cells = f'<td style="text-align:left;font-weight:600;color:#1e293b;{_WM};{_BASE_TD};background:{_bg}">{_label}</td>'
        for _s in _semanas:
            _sub = _df_sem[_df_sem["_sem"] == _s]
            _n = int(_mask_fn(_sub["Estado"]).sum())
            _vals.append(_n)
            _pct = "" if _is_leads else _pct_lbl(_n, _leads_por_sem[_s])
            _cells += f'<td style="text-align:center;{_WP};{_BASE_TD};background:{_bg}">{_n if _n else ""}{_pct}</td>'
        _prom = round(sum(_vals) / len(_vals)) if _vals else 0
        _prom_leads = round(sum(_leads_por_sem.values()) / len(_semanas)) if _semanas else 0
        _pct_prom = "" if _is_leads else _pct_lbl(_prom, _prom_leads)
        _cells += f'<td style="text-align:center;font-weight:500;{_WS};{_BASE_TD};background:{_bgs}">{_prom if _prom else ""}{_pct_prom}</td>'
        _body += f"<tr>{_cells}</tr>"

    def _tabla_sem_secundaria(filas_config, tema_bg0, tema_bg1, tema_bgs0, tema_bgs1, denom_por_sem):
        _BASE_TD_SM = f"font-size:0.70rem;padding:3px 8px;{_S};overflow:hidden"
        _body_s = ""
        for _ri, (_label, _cat_fn) in enumerate(filas_config):
            _bg  = tema_bg0 if _ri % 2 == 0 else tema_bg1
            _bgs = tema_bgs0 if _ri % 2 == 0 else tema_bgs1
            _vals = []
            _cells = f'<td style="text-align:left;font-weight:600;color:#1e293b;{_WM};{_BASE_TD_SM};background:{_bg}">{_label}</td>'
            for _s in _semanas:
                _sub = _df_sem[_df_sem["_sem"] == _s]
                _n = int(_cat_fn(_sub).sum())
                _vals.append(_n)
                _pct = _pct_lbl(_n, denom_por_sem[_s])
                _cells += f'<td style="text-align:center;{_WP};{_BASE_TD_SM};background:{_bg}">{_n if _n else ""}{_pct}</td>'
            _prom = round(sum(_vals) / len(_vals)) if _vals else 0
            _prom_denom = round(sum(denom_por_sem.values()) / len(_semanas)) if _semanas else 0
            _pct_prom = _pct_lbl(_prom, _prom_denom)
            _cells += f'<td style="text-align:center;font-weight:500;{_WS};{_BASE_TD_SM};background:{_bgs}">{_prom if _prom else ""}{_pct_prom}</td>'
            _body_s += f"<tr>{_cells}</tr>"
        return _body_s

    def _chance_fn(cat):
        return lambda sub: sub["Etiquetas"].astype(str).str.lower().str.contains(f"chance de venta {cat.lower()}", na=False)

    def _podcast_fn(cat):
        if cat == "Escuchado":
            return lambda sub: (
                sub["Etiquetas"].astype(str).str.lower().str.contains("podcast escuchado", na=False) &
                ~sub["Etiquetas"].astype(str).str.lower().str.contains("no escuchado", na=False)
            )
        return lambda sub: sub["Etiquetas"].astype(str).str.lower().str.contains("podcast no escuchado", na=False)

    _filas_chance = [
        ("Alta",       lambda sub: (
            sub["Etiquetas"].astype(str).str.lower().str.contains("chance de venta alta", na=False) &
            ~sub["Etiquetas"].astype(str).str.lower().str.contains("chance de venta media-alta", na=False)
        )),
        ("Media-Alta", lambda sub: sub["Etiquetas"].astype(str).str.lower().str.contains("chance de venta media-alta", na=False)),
        ("Media",      lambda sub: (
            sub["Etiquetas"].astype(str).str.lower().str.contains("chance de venta media", na=False) &
            ~sub["Etiquetas"].astype(str).str.lower().str.contains("chance de venta media-alta", na=False)
        )),
        ("Baja",       _chance_fn("baja")),
    ]
    _filas_podcast = [
        ("Escuchado",    _podcast_fn("Escuchado")),
        ("No escuchado", _podcast_fn("No escuchado")),
    ]

    _body_chance  = _tabla_sem_secundaria(_filas_chance,  "#d7f0e3", "#eef9f3", "#a3d9bd", "#bdeace", _presu_por_sem)
    _body_podcast = _tabla_sem_secundaria(_filas_podcast, "#d7f0e3", "#eef9f3", "#a3d9bd", "#bdeace", _presu_por_sem)

    st.markdown(
        '<table style="table-layout:fixed;width:100%;border-collapse:collapse;margin-bottom:0px">'
        f'<thead><tr>{_hdr}</tr></thead><tbody>{_body}</tbody></table>'
        '<table style="table-layout:fixed;width:100%;border-collapse:collapse;margin-top:10px;margin-bottom:0px">'
        f'<tbody>{_body_chance}</tbody></table>'
        '<table style="table-layout:fixed;width:100%;border-collapse:collapse;margin-top:10px;margin-bottom:16px">'
        f'<tbody>{_body_podcast}</tbody></table>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

if st.session_state.vgf_sel_id:
    st.info(
        f"✏️ Editando conclusión de **{st.session_state.vgf_sel_nombre}** "
        f"(`{st.session_state.vgf_sel_id}`) — panel en el sidebar →",
        icon="📝",
    )

# ── Tabla ─────────────────────────────────────────────────────
df_show = df[["id", "Nombre", "Emails", "_fecha_reunion",
              "Estado", "_notas", "_conclusion"]].copy()
df_show.rename(columns={
    "id"            : "ID",
    "Emails"        : "Mail",
    "_fecha_reunion": "Fecha 1ra reunión",
    "_conclusion"   : "Conclusiones VGF",
    "_notas"        : "Notas",
}, inplace=True)
for col in df_show.select_dtypes(include="object").columns:
    df_show[col] = df_show[col].replace({"nan": "", "None": ""}).fillna("")

# ── Embudo visual ─────────────────────────────────────────────
st.markdown("### Embudo visual VGF")

_estados_emb = df["Estado"].dropna()
_data_emb = {
    "capas": [
        len(_estados_emb),
        int(_estados_emb.isin(R1_PLUS).sum()),
        int(_estados_emb.isin(FOLLOW_PLUS).sum()),
        int(_estados_emb.isin(R2_PLUS).sum()),
        int(_estados_emb.isin(PRESU_PLUS).sum()),
        int((_estados_emb == "Venta ganada").sum()),
    ],
    "labels": ["Leads VGF", "R1", "Follow podcast", "R2", "Presupuesto", "Venta"],
    "fuga_leads": [
        ("Llamado cancelado",  int((_estados_emb == "0 - Llamado cancelado").sum())),
        ("Reagendar R1",       int((_estados_emb == "1.2 - Reagendar R1").sum())),
        ("Filtrado pre R1",    int((_estados_emb == "1.1 - Filtrado pre R1").sum())),
        ("Contacto inicial",   int((_estados_emb == "0.1 - Contacto inicial pre R1").sum())),
        ("Nuevo",              int((_estados_emb == "Nuevo").sum())),
    ],
    "fuga_r1": [
        ("En R1",       int((_estados_emb == "2 - R1").sum())),
        ("Filtrado R1", int((_estados_emb == "3 - Filtrado en R1").sum())),
    ],
    "fuga_follow": [
        ("Follow podcast", int((_estados_emb == "4 - Follow podcast").sum())),
        ("Filtrado R2",    int((_estados_emb == "5.2 - Filtrado pre R2").sum())),
        ("Reagendar R2",   int((_estados_emb == "5.3 - Reagendar R2").sum())),
    ],
    "fuga_r2": [
        ("Irrelevante", int(_estados_emb.isin(["Irrelevante", "SDR - Irrelevante"]).sum())),
        ("BSI",         int((_estados_emb == "Buyer Sin interés").sum())),
    ],
    "fuga_presu": [
        ("Contactar a Futuro", int((_estados_emb == "Contactar a Futuro").sum())),
        ("Dijo que no",        int((_estados_emb == "Dijo que no").sum())),
        ("Follow Clienty",     int((_estados_emb == "Follow Clienty").sum())),
        ("Follow 2",           int((_estados_emb == "Follow 2").sum())),
        ("Stand By",           int((_estados_emb == "Stand By").sum())),
        ("Últimos detalles",   int((_estados_emb == "Últimos detalles").sum())),
    ],
}

_, _col_emb, _ = st.columns([1, 4, 1])
with _col_emb:
    st.plotly_chart(graficos.embudo_ventas(_data_emb), use_container_width=True)


# ── Desglose Presupuestos por Chance de venta ─────────────────
_df_presu_ch    = df[df["Estado"].isin(PRESU_PLUS)].copy()
_total_presu_ch = len(_df_presu_ch)

if _total_presu_ch > 0 and "Etiquetas" in df.columns:
    def _detectar_chance(et):
        s = str(et).lower() if pd.notna(et) else ""
        if "chance de venta media-alta" in s: return "Media-Alta"
        if "chance de venta alta"       in s: return "Alta"
        if "chance de venta media"      in s: return "Media"
        if "chance de venta baja"       in s: return "Baja"
        return "Sin dato"

    def _detectar_podcast(et):
        s = str(et).lower() if pd.notna(et) else ""
        if "podcast no escuchado" in s: return "No escuchado"
        if "podcast escuchado"    in s: return "Escuchado"
        return "Sin dato"

    _df_presu_ch["_chance"]  = _df_presu_ch["Etiquetas"].apply(_detectar_chance)
    _df_presu_ch["_podcast"] = _df_presu_ch["Etiquetas"].apply(_detectar_podcast)

    def _tabla_desglose(titulo, conteos, orden, colores):
        filas = ""
        for cat in orden:
            n   = int(conteos.get(cat, 0))
            pct = f"{round(n / _total_presu_ch * 100)}%" if _total_presu_ch > 0 else "–"
            c   = colores.get(cat, "#64748b")
            filas += (
                f'<tr>'
                f'<td style="padding:7px 14px;font-size:0.85rem;font-weight:600;color:{c}">{cat}</td>'
                f'<td style="padding:7px 14px;text-align:center;font-size:0.85rem">{n}</td>'
                f'<td style="padding:7px 14px;text-align:center;font-size:0.85rem;color:#64748b">{pct}</td>'
                f'</tr>'
            )
        return (
            f'<div style="flex:1;min-width:0">'
            f'<p style="font-size:0.82rem;font-weight:600;color:#475569;margin-bottom:6px;text-align:center">'
            f'{titulo}</p>'
            f'<table style="width:100%;border-collapse:collapse;background:white;'
            f'border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08)">'
            f'<thead><tr style="background:#f8fafc">'
            f'<th style="padding:6px 14px;text-align:left;font-size:0.78rem;color:#64748b;font-weight:600">Categoría</th>'
            f'<th style="padding:6px 14px;text-align:center;font-size:0.78rem;color:#64748b;font-weight:600">Leads</th>'
            f'<th style="padding:6px 14px;text-align:center;font-size:0.78rem;color:#64748b;font-weight:600">%</th>'
            f'</tr></thead>'
            f'<tbody>{filas}</tbody>'
            f'</table>'
            f'</div>'
        )

    _t1 = _tabla_desglose(
        "Chance de venta",
        _df_presu_ch["_chance"].value_counts(),
        ["Alta", "Media-Alta", "Media", "Baja", "Sin dato"],
        {"Alta": "#16a34a", "Media-Alta": "#65a30d", "Media": "#d97706", "Baja": "#dc2626", "Sin dato": "#94a3b8"},
    )
    _t2 = _tabla_desglose(
        "Podcast",
        _df_presu_ch["_podcast"].value_counts(),
        ["Escuchado", "No escuchado", "Sin dato"],
        {"Escuchado": "#2563eb", "No escuchado": "#7c3aed", "Sin dato": "#94a3b8"},
    )

    st.markdown(
        f'<p style="font-size:0.82rem;color:#475569;text-align:center;margin-bottom:8px">'
        f'Presupuestos enviados — {_total_presu_ch} leads</p>'
        f'<div style="display:flex;gap:24px;max-width:720px;margin:0 auto 16px">'
        f'{_t1}{_t2}'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Tabla detalle leads VGF ───────────────────────────────────
st.markdown(f"**{len(df_show):,} leads VGF** · Hacé click en una fila para editar su conclusión")

_cfg = {
    "ID"               : st.column_config.TextColumn("ID",                width=80),
    "Nombre"           : st.column_config.TextColumn("Nombre",            width=130),
    "Mail"             : st.column_config.TextColumn("Mail",              width=230),
    "Fecha 1ra reunión": st.column_config.TextColumn("Fecha 1ra reunión", width=145),
    "Estado"           : st.column_config.TextColumn("Estado",            width=150),
    "Conclusiones VGF" : st.column_config.TextColumn("Conclusiones VGF", width=220),
    "Notas"            : st.column_config.TextColumn("Notas",             width=300),
}

evento = st.dataframe(
    df_show,
    column_config=_cfg,
    selection_mode="single-row",
    on_select="rerun",
    use_container_width=True,
    hide_index=True,
    key="tbl_vgf",
)

filas_sel = evento.selection.rows if evento.selection else []
if filas_sel:
    _row = df_show.iloc[filas_sel[0]]
    st.session_state.vgf_sel_id     = str(_row["ID"])
    st.session_state.vgf_sel_nombre = str(_row["Nombre"])
    st.session_state.vgf_sel_estado = str(_row["Estado"])

    _nota_id     = str(_row["ID"])
    _nota_mail   = str(_row["Mail"])
    _nota_nombre = str(_row["Nombre"])
    _notas_txt   = str(_row.get("Notas", "")).strip()
    _concl_txt   = str(_row.get("Conclusiones VGF", "")).strip()
    _notas_txt   = "" if _notas_txt in ("nan", "None") else _notas_txt
    _concl_txt   = "" if _concl_txt  in ("nan", "None") else _concl_txt

    if _notas_txt or _concl_txt:
        @st.dialog(f"{_nota_nombre} · ID {_nota_id}", width="large")
        def _popup_nota():
            st.markdown(
                f'<div style="font-size:0.82rem;color:#475569;margin-bottom:12px">'
                f'📧 {_nota_mail}</div>',
                unsafe_allow_html=True,
            )
            if _notas_txt:
                import re as _re
                # split on "., " or ".," — reliable note boundary in Clienty
                _partes = [p.strip() for p in _re.split(r'\.,\s*', _notas_txt) if p.strip()]
                _bloques_html = ""
                for _i, _parte in enumerate(_partes):
                    _sep = 'border-top:1px solid #a9cce3;' if _i > 0 else ''
                    _bloques_html += (
                        f'<div style="{_sep}padding:12px 16px;font-size:0.87rem;'
                        f'color:#1e293b;line-height:1.65;white-space:pre-wrap">{_parte}</div>'
                    )
                st.markdown(
                    f'<div style="background:#d6eaf8;border-radius:6px;overflow:hidden">'
                    f'{_bloques_html}</div>',
                    unsafe_allow_html=True,
                )
            if _concl_txt:
                st.markdown(
                    f'<div style="margin-top:10px;background:#eef9f3;border-radius:6px;'
                    f'padding:14px 18px;font-size:0.88rem;color:#1e293b;line-height:1.7;white-space:pre-wrap">'
                    f'<span style="font-size:0.75rem;font-weight:600;color:#1a5c3a;display:block;margin-bottom:4px">'
                    f'Conclusión VGF</span>{_concl_txt}</div>',
                    unsafe_allow_html=True,
                )
        _popup_nota()

st.caption(
    "📋 Notas y Fecha 1ra reunión provienen de BBDD_CRM_Clienty. "
    "Las Conclusiones VGF se guardan localmente en el servidor del dashboard."
)


# ── Panel de conclusión individual (sidebar) ──────────────────
@st.fragment
def _panel_conclusion():
    st.markdown("---")
    if st.session_state.vgf_sel_id:
        _sid = st.session_state.vgf_sel_id
        st.markdown("### ✏️ Conclusión VGF")
        st.markdown(f"**{st.session_state.vgf_sel_nombre}** · `{_sid}`")
        st.caption(st.session_state.vgf_sel_estado)
        _conclus_actual = _load_conclusiones().get(str(_sid), "")
        _nuevo_texto = st.text_area(
            "Conclusión",
            value=_conclus_actual,
            height=280,
            key=f"vgf_txt_{_sid}",
            placeholder="Escribí tu conclusión aquí...",
        )
        col_g, col_c = st.columns(2)
        if col_g.button("💾 Guardar", use_container_width=True, key="vgf_guardar"):
            _save_conclusion(_sid, _nuevo_texto)
            st.success("✅ Guardado")
        if col_c.button("✖ Cerrar", use_container_width=True, key="vgf_cerrar"):
            st.session_state.vgf_sel_id = None
            st.rerun()
    else:
        st.info("Hacé click en una fila de la tabla para editar su conclusión.", icon="👆")

with st.sidebar:
    _panel_conclusion()
