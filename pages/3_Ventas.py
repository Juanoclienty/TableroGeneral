"""
3_Ventas.py — Dashboard de Ventas (embudo CRM).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import datos
import datos_crm
import graficos

st.set_page_config(page_title="Ventas", page_icon="💼", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.5rem; }
    .section-title {
        font-size: 0.95rem; font-weight: 700; color: #1e293b;
        border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────

def _fmt_pct(n, total):
    if total == 0:
        return f"{n} (–)"
    return f"{n} ({round(n / total * 100)}%)"

def _semanas_cerradas_rango(n=8, excluir=0):
    hoy = date.today()
    dias = (hoy.weekday() + 1) % 7 or 7
    ultimo_dom = hoy - timedelta(days=dias)
    fin   = ultimo_dom - timedelta(weeks=excluir)
    inicio = fin - timedelta(weeks=n) + timedelta(days=1)
    return inicio, fin

def _meses_rango(n=1):
    hoy = date.today()
    mes_ini = hoy.month - (n - 1)
    año_ini = hoy.year
    while mes_ini <= 0:
        mes_ini += 12
        año_ini -= 1
    return date(año_ini, mes_ini, 1), hoy


# ── Session state ─────────────────────────────────────────────
if "vt_fecha_desde" not in st.session_state:
    ini, fin = _semanas_cerradas_rango(8, 0)
    st.session_state.vt_fecha_desde = ini
    st.session_state.vt_fecha_hasta = fin


# ── Carga de datos (caché: se renueva a la 1 AM hora Argentina) ──
@st.cache_resource(show_spinner="Cargando datos CRM...")
def _cargar_todo():
    df_crm  = datos_crm.cargar_crm()
    df_ads  = datos.cargar_ads()
    obj     = datos.cargar_objetivos()
    df_sem  = datos_crm.calcular_semanas_crm(df_crm, df_ads)
    df_men  = datos_crm.calcular_meses_crm(df_crm, df_ads)
    return df_crm, df_ads, obj, df_sem, df_men

try:
    df_crm, df_ads, obj, df_sem, df_men = _cargar_todo()
except Exception as e:
    st.error(f"Error al cargar datos: {e}")
    st.stop()


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.title("💼 Ventas")
    st.markdown("---")

    vista = st.radio("", ["Mes", "Sem", "Día"], horizontal=True, label_visibility="collapsed")
    st.markdown("")

    fecha_min = df_sem["fecha_ini"].min().date()
    fecha_max = df_sem["fecha_fin"].max().date()

    if vista == "Día":
        st.caption("Vista Día: últimos 15 días desde ayer.")
        fecha_desde = fecha_min
        fecha_hasta = date.today() - timedelta(days=1)
    else:
        col_d1, col_d2 = st.columns(2)
        _clamp = lambda v, lo, hi: max(lo, min(hi, v))
        fecha_desde = col_d1.date_input("Desde",
                                         value=_clamp(st.session_state.vt_fecha_desde, fecha_min, fecha_max),
                                         min_value=fecha_min, max_value=fecha_max, format="DD/MM/YYYY")
        fecha_hasta = col_d2.date_input("Hasta",
                                         value=_clamp(st.session_state.vt_fecha_hasta, fecha_min, fecha_max),
                                         min_value=fecha_min, max_value=fecha_max, format="DD/MM/YYYY")
        st.session_state.vt_fecha_desde = fecha_desde
        st.session_state.vt_fecha_hasta = fecha_hasta

        if vista == "Sem":
            c1, c2 = st.columns(2)
            if c1.button("📅 8 sem.", use_container_width=True):
                ini, fin = _semanas_cerradas_rango(8, 0)
                st.session_state.vt_fecha_desde = ini
                st.session_state.vt_fecha_hasta = fin
                st.rerun()
            if c2.button("📅 6 sem.", use_container_width=True):
                ini, fin = _semanas_cerradas_rango(6, 2)
                st.session_state.vt_fecha_desde = ini
                st.session_state.vt_fecha_hasta = fin
                st.rerun()
        elif vista == "Mes":
            c1, c2 = st.columns(2)
            if c1.button("📅 1 mes", use_container_width=True):
                ini, fin = _meses_rango(1)
                st.session_state.vt_fecha_desde = ini
                st.session_state.vt_fecha_hasta = fin
                st.rerun()
            if c2.button("📅 3 meses", use_container_width=True):
                ini, fin = _meses_rango(3)
                st.session_state.vt_fecha_desde = ini
                st.session_state.vt_fecha_hasta = fin
                st.rerun()

    st.markdown("---")
    filtro_calidad = st.radio("", ["Todos", "GF", "BF", "PF"],
                               horizontal=True, label_visibility="collapsed")

    st.markdown("---")
    EXTRA_FILTROS = [
        ("Tipo cliente",         "Tipo cliente"),
        ("Ticket",               "Ticket"),
        ("Equipo comercial",     "Equipo comercial"),
        ("Consultas",            "Consultas"),
        ("Inversión Publicidad", "Inv. Publicidad"),
    ]
    filtros_extra = {}
    for col, label in EXTRA_FILTROS:
        opciones = []
        if col in df_crm.columns:
            vals = sorted(df_crm[col].dropna().astype(str).unique().tolist())
            opciones = [v for v in vals if v not in ("", "nan")]
            if df_crm[col].isna().any() or df_crm[col].eq("").any():
                opciones.append("Sin datos")
        st.markdown(
            f'<span style="font-size:0.75rem;color:#64748b">{label}</span>',
            unsafe_allow_html=True,
        )
        filtros_extra[col] = st.multiselect(
            "", opciones, key=f"fil_{col}", label_visibility="collapsed"
        )

    # Etiquetas — último filtro (valores multi-tag, separados por coma en el CRM)
    opciones_et = []
    if "Etiquetas" in df_crm.columns:
        all_tags = set()
        for v in df_crm["Etiquetas"].dropna().astype(str):
            for t in v.split(","):
                t = t.strip()
                if t and t not in ("", "nan"):
                    all_tags.add(t)
        opciones_et = sorted(all_tags)
        et_col = df_crm["Etiquetas"].fillna("").astype(str).str.strip()
        if et_col.eq("").any() or et_col.eq("nan").any():
            opciones_et.append("Sin etiquetas")
    st.markdown(
        '<span style="font-size:0.75rem;color:#64748b">Etiquetas</span>',
        unsafe_allow_html=True,
    )
    filtro_etiquetas = st.multiselect("", opciones_et, key="fil_etiquetas",
                                      label_visibility="collapsed")

    st.markdown("---")
    if st.button("📊 Actualizar tablas", use_container_width=True,
                 help="Recarga solo los Google Sheets (ventas, presupuestos, ads). Rápido."):
        st.cache_data.clear()
        st.rerun()
    if st.button("🔄 Recargar todo (API)", use_container_width=True,
                 help="Recarga también el CRM Clienty. Puede tardar varios minutos."):
        datos_crm.limpiar_cache()
        _cargar_todo.clear()
        st.cache_data.clear()
        st.rerun()
    st.caption("Fuente: CRM Clienty · Ads")


# ── Preparar datos según vista y filtro ───────────────────────
calidad_map = {"GF": "R1F", "BF": "R1BF", "PF": "R1PBF"}

def _filtrar_crm(filtro):
    df_f = df_crm
    if filtro != "Todos":
        df_f = df_f[df_f["calidad"] == calidad_map[filtro]]
    for col, vals in filtros_extra.items():
        if vals and col in df_f.columns:
            reg  = [v for v in vals if v != "Sin datos"]
            nulo = "Sin datos" in vals
            col_str = df_f[col].astype(str).replace("nan", "")
            if reg and nulo:
                df_f = df_f[col_str.isin(reg) | df_f[col].isna() | col_str.eq("")]
            elif reg:
                df_f = df_f[col_str.isin(reg)]
            else:
                df_f = df_f[df_f[col].isna() | col_str.eq("")]
    if filtro_etiquetas and "Etiquetas" in df_f.columns:
        sin_et   = "Sin etiquetas" in filtro_etiquetas
        tags_sel = [v for v in filtro_etiquetas if v != "Sin etiquetas"]
        et_col   = df_f["Etiquetas"].fillna("").astype(str)
        mask     = pd.Series(False, index=df_f.index)
        for tag in tags_sel:
            mask |= et_col.str.contains(tag, na=False, regex=False)
        if sin_et:
            mask |= et_col.str.strip().eq("") | et_col.str.strip().eq("nan")
        df_f = df_f[mask]
    return df_f

_hay_filtro = filtro_calidad != "Todos" or any(v for v in filtros_extra.values()) or bool(filtro_etiquetas)

if vista == "Día":
    df_vista = datos_crm.calcular_dias_crm(_filtrar_crm(filtro_calidad), df_ads)

elif vista == "Mes":
    base = datos_crm.calcular_meses_crm(_filtrar_crm(filtro_calidad), df_ads) if _hay_filtro else df_men
    mask = (base["fecha_ini"] >= pd.Timestamp(fecha_desde)) & (base["fecha_ini"] <= pd.Timestamp(fecha_hasta))
    df_vista = base[mask].copy()

else:  # Semana
    base = datos_crm.calcular_semanas_crm(_filtrar_crm(filtro_calidad), df_ads) if _hay_filtro else df_sem
    mask = (base["fecha_ini"] >= pd.Timestamp(fecha_desde)) & (base["fecha_fin"] <= pd.Timestamp(fecha_hasta))
    df_vista = base[mask].copy()


# ── Título principal ──────────────────────────────────────────
st.markdown("# Ventas")

# ── Tarjetas de ventas recientes (fuente: BBDD_Ventas sheet) ─
_ID_BBDD     = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"
_ID_LTV      = "1TGVc9zgYc0siaouIOi8xTOiFopgXuW8AXIB_dqYZ7Ps"
_ID_REPORTES = "1b2LzEE8T5yQERP934C4kNQJbUiVZcNdR7aBjB9R2kHM"

@st.cache_data(ttl=3600)
def _cargar_links_ventas() -> dict:
    """Devuelve dict {"2026-06-09": url} leyendo la pestaña Ventas semanales."""
    try:
        url = (f"https://docs.google.com/spreadsheets/d/{_ID_REPORTES}"
               f"/gviz/tq?tqx=out:csv&sheet=Ventas%20semanales")
        df  = pd.read_csv(url, dtype=str)
        out = {}
        for _, row in df.iterrows():
            fecha_raw = str(row.iloc[0]).strip()
            link      = str(row.iloc[1]).strip()
            if not fecha_raw or fecha_raw in ("nan", "Fecha ini sem"):
                continue
            try:
                ts = pd.to_datetime(fecha_raw, errors="coerce")
                if pd.isna(ts):
                    continue
                import re as _re
                m = _re.search(r'/d/([a-zA-Z0-9_-]+)', link)
                if m:
                    link = f"https://drive.google.com/uc?export=view&id={m.group(1)}"
                out[ts.strftime("%Y-%m-%d")] = link
            except Exception:
                pass
        return out
    except Exception:
        return {}


def _norm_id_ltv(v) -> str:
    s = str(v).strip()
    if s in ("", "nan", "None"):
        return ""
    try:
        return str(int(float(s)))
    except (ValueError, OverflowError):
        return ""


def _leer_sheet_ltv(url: str) -> pd.DataFrame:
    import io, urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        contenido = resp.read().decode("utf-8")
    df = pd.read_csv(io.StringIO(contenido), dtype=str)
    df.columns = df.columns.str.strip()
    return df


@st.cache_data(ttl=86400)
def _cargar_ltv_lookup() -> dict:
    """Retorna {id_crm: {"rec": float, "impl": float}} — misma lógica que 6_LTV.py."""
    # LTV Real (Finnegans) — export URL (sin límite de filas, a diferencia de gviz)
    try:
        url_r = (f"https://docs.google.com/spreadsheets/d/{_ID_LTV}"
                 f"/export?format=csv&sheet=LTV%20Real")
        df_r = _leer_sheet_ltv(url_r)
        _id_col  = next((c for c in df_r.columns if c.upper() == "ID CRM"), None)
        _usd_col = next((c for c in df_r.columns if "SECUNDARIA" in c.upper()), None)
        df_r["_id"]  = df_r[_id_col].apply(_norm_id_ltv) if _id_col else pd.Series("", index=df_r.index)
        _usd_raw = (df_r[_usd_col] if _usd_col else pd.Series(dtype=str)).astype(str).str.replace(",", ".", regex=False)
        df_r["_usd"] = pd.to_numeric(_usd_raw, errors="coerce").fillna(0)
        df_r["_impl"] = df_r.get("Producto", pd.Series(dtype=str)).astype(str).str.lower().str.contains("implementa", na=False)
        df_r = df_r[df_r["_id"] != ""]
        real_rec  = df_r[~df_r["_impl"]].groupby("_id")["_usd"].sum()
        real_impl = df_r[df_r["_impl"]].groupby("_id")["_usd"].sum()
    except Exception:
        real_rec = real_impl = pd.Series(dtype=float)

    # LTV Prom pre-Finnegans — xlsx completo (gviz trunca, export ignora nombre de sheet)
    try:
        import io as _io
        url_xlsx = f"https://docs.google.com/spreadsheets/d/{_ID_LTV}/export?format=xlsx"
        _req = __import__("urllib.request", fromlist=["request"]).Request(
            url_xlsx, headers={"User-Agent": "Mozilla/5.0"}
        )
        with __import__("urllib.request", fromlist=["request"]).urlopen(_req, timeout=60) as _resp:
            _xdata = _resp.read()
        _xl = pd.ExcelFile(_io.BytesIO(_xdata))
        df_p = _xl.parse("LTV Prom - 2024.08", dtype=str)
        df_p.columns = df_p.columns.str.strip()
        _id_col_p  = next((c for c in df_p.columns if c.upper() == "ID CRM"), None)
        _usd_col_p = next((c for c in df_p.columns if "SECUNDARIA" in c.upper()), None)
        df_p["_id"]  = df_p[_id_col_p].apply(_norm_id_ltv) if _id_col_p else pd.Series("", index=df_p.index)
        _usd_raw_p = (df_p[_usd_col_p] if _usd_col_p else pd.Series(dtype=str)).astype(str).str.replace(",", ".", regex=False)
        df_p["_usd"] = pd.to_numeric(_usd_raw_p, errors="coerce").fillna(0)
        prom_rec = df_p[df_p["_id"] != ""].groupby("_id")["_usd"].sum()
    except Exception:
        prom_rec = pd.Series(dtype=float)

    todos_ids = set(real_rec.index) | set(real_impl.index) | set(prom_rec.index)
    lookup = {}
    for idk in todos_ids:
        if not idk:
            continue
        lookup[idk] = {
            "rec":  float(real_rec.get(idk, 0)) + float(prom_rec.get(idk, 0)),
            "impl": float(real_impl.get(idk, 0)),
        }
    return lookup


@st.cache_data(ttl=3600)
def _cargar_bbdd_ventas():
    url = (f"https://docs.google.com/spreadsheets/d/{_ID_BBDD}"
           f"/gviz/tq?tqx=out:csv&sheet=BBDD_Ventas")
    df = pd.read_csv(url, dtype=str)
    df.columns = df.columns.str.strip()
    df["Fecha"]               = pd.to_datetime(df.get("Fecha", ""),              dayfirst=True, errors="coerce")
    df["Fecha lead"]          = pd.to_datetime(df.get("Fecha lead", ""),         dayfirst=True, errors="coerce")
    df["Monto de venta"]      = pd.to_numeric(df.get("Monto de venta", ""),      errors="coerce").fillna(0)
    df["Venta cierre (días)"] = pd.to_numeric(df.get("Venta cierre (días)", ""), errors="coerce")
    df["ID prospecto"]        = df["ID prospecto"].astype(str).str.strip()
    return df

@st.cache_data(ttl=3600)
def _cargar_bbdd_presupuesto():
    """Carga bbdd_presupuestos: fecha de envío para contar presupuestos por período."""
    url = (f"https://docs.google.com/spreadsheets/d/{_ID_BBDD}"
           f"/gviz/tq?tqx=out:csv&sheet=bbdd_presupuestos")
    df = pd.read_csv(url, dtype=str)
    df.columns = df.columns.str.strip()
    df["_fecha"] = pd.to_datetime(df["FECHA DE ENVIO"], dayfirst=True, errors="coerce")
    return df.dropna(subset=["_fecha"])

try:
    df_bbdd = _cargar_bbdd_ventas()
except Exception:
    df_bbdd = pd.DataFrame()

try:
    _ltv_lookup = _cargar_ltv_lookup()
except Exception:
    _ltv_lookup = {}

try:
    df_presu = _cargar_bbdd_presupuesto()
except Exception:
    df_presu = pd.DataFrame()

# Enriquecer BBDD con datos del CRM (nombre, email, tel) donde el ID matchee.
# Se muestran TODAS las ventas del sheet — leads viejos fuera del cache CRM incluidos.
_crm_fil = _filtrar_crm(filtro_calidad)

if not df_bbdd.empty:
    df_vtas = df_bbdd.copy()
    _enrich_cols = ["id"] + [c for c in ["Nombre", "Emails", "Telefono", "Empresa", "Etiquetas"] if c in _crm_fil.columns]
    _enrich = (_crm_fil[_enrich_cols]
               .copy()
               .assign(id=lambda d: d["id"].astype(str).str.strip()))
    df_vtas = df_vtas.merge(_enrich, left_on="ID prospecto", right_on="id", how="left")
    df_vtas["fecha_venta"] = df_vtas["Fecha"]
    df_vtas["monto_num"]   = df_vtas["Monto de venta"]
else:
    df_vtas = pd.DataFrame()

# Agrupar según la vista activa
_MESES_ES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
_DIAS_ES  = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]

def _semana_de(ts):
    if pd.isna(ts): return pd.NaT
    t = pd.Timestamp(ts).normalize()
    return t - pd.Timedelta(days=t.dayofweek)

def _ultimos_dias_lab(n=4):
    """Retorna los últimos n días laborables (lun-vie) incluyendo hoy si es laborable."""
    dias, d = [], pd.Timestamp.today().normalize()
    while len(dias) < n:
        if d.weekday() < 5:
            dias.append(d)
        d -= pd.Timedelta(days=1)
    return list(reversed(dias))  # más antiguo primero

if not df_vtas.empty:
    if vista == "Mes":
        df_vtas["_periodo"] = df_vtas["fecha_venta"].dt.to_period("M")
        def _lbl(p):
            try: return f"{_MESES_ES[p.month - 1]} {p.year}"
            except: return str(p)
    elif vista == "Sem":
        df_vtas["_periodo"] = df_vtas["fecha_venta"].apply(_semana_de)
        def _lbl(p):
            try: return f"Sem. {pd.Timestamp(p).strftime('%d/%m')}"
            except: return str(p)
    else:  # Día
        df_vtas["_periodo"] = df_vtas["fecha_venta"].dt.normalize()
        def _lbl(p):
            try:
                t = pd.Timestamp(p)
                return f"{_DIAS_ES[t.weekday()]} {t.strftime('%d/%m')}"
            except: return str(p)
else:
    def _lbl(p): return str(p)

# Últimos 4 períodos: siempre incluye el período actual (aunque no tenga ventas aún)
if vista == "Día":
    ultimos_4 = _ultimos_dias_lab(4)
elif vista == "Mes":
    _periodo_actual = pd.Timestamp.today().to_period("M")
    _all_periodos   = set(df_vtas["_periodo"].dropna().unique()) if not df_vtas.empty else set()
    _all_periodos.add(_periodo_actual)
    ultimos_4 = sorted(_all_periodos)[-4:]
else:  # Semana
    _periodo_actual = _semana_de(pd.Timestamp.today())
    _all_periodos   = set(df_vtas["_periodo"].dropna().unique()) if not df_vtas.empty else set()
    _all_periodos.add(_periodo_actual)
    ultimos_4 = sorted(_all_periodos)[-4:]

# ── CPV mensual (inversión / ventas del mes) ─────────────────
_cpv_mes_lookup: dict = {}
try:
    if not df_ads.empty and not df_bbdd.empty:
        _ads_m = df_ads.copy()
        _ads_m["_p"] = pd.to_datetime(_ads_m["fecha"], errors="coerce").dt.to_period("M")
        _inv_m = _ads_m.groupby("_p")["inversion"].sum()

        _vtas_m_df = df_bbdd.copy()
        _vtas_m_df["_p"] = pd.to_datetime(
            _vtas_m_df.get("Fecha", ""), dayfirst=True, errors="coerce"
        ).dt.to_period("M")
        _vtas_m = _vtas_m_df.groupby("_p").size()

        for _p in _inv_m.index:
            _inv = float(_inv_m.get(_p, 0))
            _nv  = int(_vtas_m.get(_p, 0))
            if _inv > 0 and _nv > 0:
                _cpv_mes_lookup[_p] = round(_inv / _nv)
except Exception:
    pass


# ── Modal de detalle ─────────────────────────────────────────
def _clean_v(v):
    s = str(v or "").strip()
    return s if s not in ("", "nan") else ""

def _build_filas(grp_sel):
    # Lookup canal de adquisicion por ID desde BBDD_Ventas
    _canal_lookup = {}
    if not df_bbdd.empty and "Canal de adquisicion" in df_bbdd.columns:
        _tmp = df_bbdd[["ID prospecto", "Canal de adquisicion"]].copy()
        _tmp["_id_norm"] = _tmp["ID prospecto"].apply(_norm_id_ltv)
        _canal_lookup = _tmp.set_index("_id_norm")["Canal de adquisicion"].to_dict()

    filas = []
    for _, r in grp_sel.sort_values("fecha_venta", ascending=False).iterrows():
        fv = r["fecha_venta"]
        fl = r.get("Fecha lead")
        fl = fl if pd.notna(fl) else pd.NaT

        fecha_str      = fv.strftime("%d/%m/%Y") if pd.notna(fv) else "–"
        fecha_lead_str = pd.Timestamp(fl).strftime("%d/%m/%Y") if pd.notna(fl) else "–"

        dias_raw = r.get("Venta cierre (días)")
        if pd.notna(dias_raw):
            ventana_str = str(int(dias_raw))
        elif pd.notna(fv) and pd.notna(fl):
            ventana_str = str((fv.normalize() - pd.Timestamp(fl).normalize()).days)
        else:
            ventana_str = "–"

        empresa_str = _clean_v(r.get("Empresa")) or "–"

        vendedor_raw = _clean_v(r.get("Vendedor"))
        vendedor_str = vendedor_raw.split()[0] if vendedor_raw else "–"

        monto = r["monto_num"]

        # CPV del mes de la venta
        _cpv = None
        if pd.notna(fv):
            _p_mes = pd.Timestamp(fv).to_period("M")
            _cpv   = _cpv_mes_lookup.get(_p_mes)

        _idk  = _norm_id_ltv(r["ID prospecto"])
        _ltv  = _ltv_lookup.get(_idk, {})
        _rec  = _ltv.get("rec",  0)
        _impl = _ltv.get("impl", 0)
        _total = _rec + _impl

        _ltv_cpv = round(_total / _cpv, 1) if _cpv and _cpv > 0 and _total > 0 else None

        _ets = str(r.get("Etiquetas", "") or "").lower()
        _id_str = _norm_id_ltv(r.get("ID prospecto", ""))
        _canal = str(_canal_lookup.get(_id_str, "") or "").strip().lower()
        if "proc" in _ets and "vgf" in _ets:
            _tipo = "VGF"
        elif "referido" in _canal:
            _tipo = "Referido"
        else:
            _tipo = ""

        filas.append({
            "Fecha": fecha_str,
            "Tipo":  _tipo,
            "ID":         _idk or r["ID prospecto"],
            "Empresa":    empresa_str,
            "Vendedor":   vendedor_str,
            "Monto":      "$ {:,.0f}".format(monto) if monto > 0 else "–",
            "Fecha lead": fecha_lead_str,
            "Ventana":    ventana_str,
            "CPV":        "$ {:,.0f}".format(_cpv) if _cpv else "–",
            "LTV I":      "$ {:,.0f}".format(_impl)  if _impl  > 0 else "–",
            "LTV R":      "$ {:,.0f}".format(_rec)   if _rec   > 0 else "–",
            "LTV T":      "$ {:,.0f}".format(_total) if _total > 0 else "–",
            "LTV/CPV":    f"{_ltv_cpv:.1f}x" if _ltv_cpv is not None else "–",
        })
    return filas

@st.dialog("Detalle de ventas", width="large")
def _modal_detalle(label, filas):
    st.markdown(f"**{label} — {len(filas)} ventas**")
    st.dataframe(
        pd.DataFrame(filas),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tipo":    st.column_config.TextColumn("Tipo",    width=80),
            "Empresa": st.column_config.TextColumn("Empresa", width="medium"),
        },
    )

st.markdown("### Resumen")

if ultimos_4:
    # ── Lookup presupuestos por período ──────────────────────
    _presu_por_periodo = {}
    if not df_presu.empty:
        if vista == "Mes":
            df_presu["_p"] = df_presu["_fecha"].dt.to_period("M")
        elif vista == "Sem":
            df_presu["_p"] = df_presu["_fecha"].apply(_semana_de)
        else:
            df_presu["_p"] = df_presu["_fecha"].dt.normalize()
        _presu_por_periodo = df_presu.groupby("_p").size().to_dict()

    # ── Lookup leads/gf/inversión sin filtro de fechas ───────
    # Recalculamos sobre el CRM filtrado (calidad+etiquetas) pero sin restricción de rango
    _crm_cards = _filtrar_crm(filtro_calidad)
    if vista == "Mes":
        _dv_full = datos_crm.calcular_meses_crm(_crm_cards, df_ads)
        _dv_full["_vp"] = _dv_full["fecha_ini"].dt.to_period("M")
    elif vista == "Sem":
        _dv_full = datos_crm.calcular_semanas_crm(_crm_cards, df_ads)
        _dv_full["_vp"] = _dv_full["fecha_ini"].dt.normalize()
    else:
        _dv_full = datos_crm.calcular_dias_crm(_crm_cards, df_ads, dias=30)
        _dv_full["_vp"] = _dv_full["fecha_ini"].dt.normalize()
    _vista_por_periodo = _dv_full.set_index("_vp").to_dict("index") if not _dv_full.empty else {}

    def _fmt_m(v): return "$ {:,.0f}".format(v) if v > 0 else "–"
    def _fmt_n(v): return str(int(v)) if v > 0 else "–"

    _canal_lookup = {}
    if not df_bbdd.empty and "Canal de adquisicion" in df_bbdd.columns:
        _tmp = df_bbdd[["ID prospecto", "Canal de adquisicion"]].copy()
        _tmp["_id_norm"] = _tmp["ID prospecto"].apply(_norm_id_ltv)
        _canal_lookup = _tmp.set_index("_id_norm")["Canal de adquisicion"].to_dict()

    _links_ventas = _cargar_links_ventas()

    cols_cards = st.columns(len(ultimos_4))
    for i, (col, periodo) in enumerate(zip(cols_cards, reversed(ultimos_4))):
        grp    = df_vtas[df_vtas["_periodo"] == periodo]
        total  = grp["monto_num"].sum()
        n_v    = len(grp)
        label  = _lbl(periodo)

        # $ Imp.: suma de LTV I; los sin dato usan $600 como estimado
        _LTV_I_DEFAULT = 600
        imp_total = sum(
            _ltv_lookup.get(_norm_id_ltv(str(r.get("ID prospecto",""))), {}).get("impl", 0) or _LTV_I_DEFAULT
            for _, r in grp.iterrows()
        )

        # Fila 1
        n_pre  = int(_presu_por_periodo.get(periodo, 0) or 0)

        # Fila 2: Leads / %GF / Inversión
        vrow   = _vista_por_periodo.get(periodo, {})
        leads  = int(vrow.get("leads", 0))
        gf     = int(vrow.get("gf", 0))
        inv    = float(vrow.get("inversion", 0))
        pct_gf = (str(round(gf / leads * 100)) + "%") if leads > 0 else "–"

        # Fila 3: CPL / CPL GF / CPE / CPV / CPV Meta
        cpl    = round(inv / leads) if leads > 0 else 0
        cpl_gf = round(inv / gf)    if gf    > 0 else 0
        cpe    = round(inv / n_pre) if n_pre > 0 else 0
        cpv    = round(inv / n_v)   if n_v   > 0 else 0
        tc_real = (str(round(n_v / n_pre * 100)) + "%") if n_pre > 0 else "–"
        n_ref  = sum(
            1 for _, r in grp.iterrows()
            if "referido" in str(_canal_lookup.get(_norm_id_ltv(str(r.get("ID prospecto",""))), "")).lower()
        )
        n_v_meta = n_v - n_ref
        cpv_meta = round(inv / n_v_meta) if n_v_meta > 0 and inv > 0 else 0

        ventas_txt  = "venta" if n_v == 1 else "ventas"
        total_str   = _fmt_m(total)
        imp_str     = _fmt_m(imp_total)
        n_pre_str   = _fmt_n(n_pre)
        leads_str   = _fmt_n(leads)
        inv_str     = _fmt_m(inv)
        cpl_str     = _fmt_m(cpl)
        cpl_gf_str  = _fmt_m(cpl_gf)
        cpe_str     = _fmt_m(cpe)
        cpv_str      = _fmt_m(cpv)
        cpv_meta_str = _fmt_m(cpv_meta)

        html = (
            '<div style="background:linear-gradient(135deg,#2196F3,#1565C0);'
            'border-radius:12px;padding:20px 16px 14px;text-align:center;color:white;margin-bottom:6px">'
            f'<div style="font-size:1rem;font-weight:600;margin-bottom:8px">{label}</div>'
            f'<div style="font-size:2rem;font-weight:700;line-height:1.1">{n_v}</div>'
            f'<div style="font-size:0.78rem;opacity:.85;margin-bottom:6px">{ventas_txt}</div>'
            '<div style="display:flex;justify-content:space-around;font-size:0.75rem;'
            'border-top:1px solid rgba(255,255,255,.25);padding-top:7px;margin-top:4px">'
            f'<div><div style="opacity:.7">Presupuestos</div><div style="font-weight:600">{n_pre_str}</div></div>'
            f'<div><div style="opacity:.7">TC Real</div><div style="font-weight:600">{tc_real}</div></div>'
            f'<div><div style="opacity:.7">$ recu.</div><div style="font-weight:600">{total_str}</div></div>'
            f'<div><div style="opacity:.7">$ Imp.</div><div style="font-weight:600">{imp_str}</div></div>'
            '</div>'
            '<div style="display:flex;justify-content:space-around;font-size:0.75rem;'
            'border-top:1px solid rgba(255,255,255,.25);padding-top:7px;margin-top:4px">'
            f'<div><div style="opacity:.7">Leads</div><div style="font-weight:600">{leads_str}</div></div>'
            f'<div><div style="opacity:.7">%GF</div><div style="font-weight:600">{pct_gf}</div></div>'
            f'<div><div style="opacity:.7">Inversión</div><div style="font-weight:600">{inv_str}</div></div>'
            '</div>'
            '<div style="display:flex;justify-content:space-around;font-size:0.75rem;'
            'border-top:1px solid rgba(255,255,255,.25);padding-top:7px;margin-top:4px">'
            f'<div><div style="opacity:.7">CPL</div><div style="font-weight:600">{cpl_str}</div></div>'
            f'<div><div style="opacity:.7">CPL GF</div><div style="font-weight:600">{cpl_gf_str}</div></div>'
            f'<div><div style="opacity:.7">CPE</div><div style="font-weight:600">{cpe_str}</div></div>'
            f'<div><div style="opacity:.7">CPV</div><div style="font-weight:600">{cpv_str}</div></div>'
            f'<div><div style="opacity:.7">CPV Meta</div><div style="font-weight:600">{cpv_meta_str}</div></div>'
            '</div>'
            '</div>'
        )

        with col:
            st.markdown(html, unsafe_allow_html=True)
            # Buscar link de reporte para este período
            _periodo_key = None
            if isinstance(periodo, pd.Timestamp):
                _periodo_key = periodo.strftime("%Y-%m-%d")
            elif hasattr(periodo, 'start_time'):
                _periodo_key = pd.Timestamp(periodo.start_time).strftime("%Y-%m-%d")
            _rep_url = None
            if _periodo_key:
                _ts_base = pd.Timestamp(_periodo_key)
                for _delta in range(3):  # 0, 1, 2 días de tolerancia
                    _k = (_ts_base + pd.Timedelta(days=_delta)).strftime("%Y-%m-%d")
                    if _k in _links_ventas:
                        _rep_url = _links_ventas[_k]
                        break

            if _rep_url:
                _c1, _c2 = st.columns([4, 1])
                if _c1.button("Ver detalle", key=f"vt_card_{i}", use_container_width=True):
                    grp_sel = df_vtas[df_vtas["_periodo"] == periodo].copy()
                    _modal_detalle(label, _build_filas(grp_sel))
                _c2.markdown(
                    f'<a href="{_rep_url}" target="_blank" style="display:flex;align-items:center;'
                    f'justify-content:center;height:38px;background:#f1f5f9;border-radius:6px;'
                    f'border:1px solid #e2e8f0;font-size:1rem;text-decoration:none">📄</a>',
                    unsafe_allow_html=True,
                )
            else:
                if st.button("Ver detalle", key=f"vt_card_{i}", use_container_width=True):
                    grp_sel = df_vtas[df_vtas["_periodo"] == periodo].copy()
                    _modal_detalle(label, _build_filas(grp_sel))

_col_src, _col_exp = st.columns([3, 1])
_col_src.markdown(
    '<div style="font-size:0.68rem;color:#94a3b8;margin-top:8px;line-height:1.8">'
    f'Ventas reales, presupuestos reales e Inversión en pauta provienen del '
    f'<a href="https://docs.google.com/spreadsheets/d/{_ID_BBDD}" target="_blank" '
    f'style="color:#94a3b8;text-decoration:underline">tablero de marketing</a>.<br>'
    f'Canal de adquisición (referidos) proviene de la '
    f'<a href="https://docs.google.com/spreadsheets/d/{_ID_BBDD}/edit#gid=0" target="_blank" '
    f'style="color:#94a3b8;text-decoration:underline">BBDD Ventas</a>.<br>'
    f'$ Imp. = suma de LTV Implementación por venta; ventas sin factura cargada se estiman en $ 600.'
    '</div>',
    unsafe_allow_html=True,
)

if not df_vtas.empty and ultimos_4:
    def _exportar_detalle() -> bytes:
        import io
        frames = []
        for periodo in ultimos_4:
            grp = df_vtas[df_vtas["_periodo"] == periodo].copy()
            if grp.empty:
                continue
            filas = _build_filas(grp)
            df_p  = pd.DataFrame(filas)
            df_p.insert(0, "Período", _lbl(periodo))
            frames.append(df_p)
        if not frames:
            return b""
        df_export = pd.concat(frames, ignore_index=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="Detalle ventas")
        return buf.getvalue()

    with _col_exp:
        import base64
        _xlsx_bytes = _exportar_detalle()
        _b64 = base64.b64encode(_xlsx_bytes).decode()
        st.markdown(
            f'<div style="text-align:right;margin-top:6px">'
            f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{_b64}" '
            f'download="detalle_ventas.xlsx" '
            f'style="font-size:0.72rem;color:#64748b;text-decoration:none;'
            f'border:1px solid #cbd5e1;border-radius:4px;padding:3px 8px;">'
            f'⬇ Exportar detalle</a></div>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Conjuntos del embudo ──────────────────────────────────────
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

FUNNEL_COLS = [
    ("fR1",     "R1"),
    ("fFollow", "Follow podcast"),
    ("fR2",     "R2"),
    ("fPresu",  "Presupuesto"),
    ("fVenta",  "Venta"),
]

# Calcular columnas del embudo por período desde CRM raw
if not df_vista.empty:
    fd_all = df_vista["fecha_ini"].min()
    fh_all = df_vista["fecha_fin"].max()
    df_crm_fil = _filtrar_crm(filtro_calidad)
    df_crm_fil = df_crm_fil[
        (df_crm_fil["fecha_lead"] >= fd_all) &
        (df_crm_fil["fecha_lead"] <= fh_all)
    ].copy()

    if vista == "Sem":
        df_crm_fil["_pkey"] = df_crm_fil["semana_inicio"]
        df_vista["_pkey"]   = df_vista["semana_inicio"]
    elif vista == "Mes":
        df_crm_fil["_pkey"] = df_crm_fil["fecha_lead"].dt.to_period("M").dt.start_time.dt.normalize()
        df_vista["_pkey"]   = df_vista["fecha_ini"]
    else:
        df_crm_fil["_pkey"] = df_crm_fil["fecha_lead"].dt.normalize()
        df_vista["_pkey"]   = df_vista["fecha_ini"]

    rows_fc = []
    for pkey, grp in df_crm_fil.groupby("_pkey"):
        e = grp["Estado"].dropna()
        rows_fc.append({
            "_pkey":  pkey,
            "fR1":    int(e.isin(R1_PLUS).sum()),
            "fFollow":int(e.isin(FOLLOW_PLUS).sum()),
            "fR2":    int(e.isin(R2_PLUS).sum()),
            "fPresu": int(e.isin(PRESU_PLUS).sum()),
            "fVenta": int((e == "Venta ganada").sum()),
        })
    df_fc = pd.DataFrame(rows_fc) if rows_fc else pd.DataFrame(
        columns=["_pkey", "fR1", "fFollow", "fR2", "fPresu", "fVenta"])
    df_vista = df_vista.merge(df_fc, on="_pkey", how="left")
    for c, _ in FUNNEL_COLS:
        df_vista[c] = df_vista[c].fillna(0).astype(int)
else:
    df_crm_fil = pd.DataFrame()


# ── Header ────────────────────────────────────────────────────
n_filas   = len(df_vista)
leads_tot = int(df_vista["leads"].sum()) if not df_vista.empty else 0
sufijo    = {"Sem": f"{n_filas} semanas", "Mes": f"{n_filas} meses", "Día": f"{n_filas} días"}
st.caption(f"Vista: **{vista}** · {sufijo.get(vista,'')} · {leads_tot:,} leads")


# ── KPI Cards ─────────────────────────────────────────────────
if not df_vista.empty:
    gf_tot   = int(df_vista["gf"].sum())
    ventas   = int(df_vista["5. Venta"].sum())
    inv_tot  = df_vista["inversion"].sum()
    mes_ref  = df_vista["fecha_ini"].iloc[-1].month

    obj_leads = obj["leads"].get(mes_ref, 300)
    obj_gf    = obj["gf"].get(mes_ref, 141)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Leads",   f"{leads_tot:,}",
              f"{leads_tot - obj_leads:+,.0f} vs obj {obj_leads:,.0f}")
    k2.metric("GF",      f"{gf_tot:,}",
              f"{gf_tot - obj_gf:+,.0f} vs obj {obj_gf:,.0f} · {round(gf_tot/leads_tot*100) if leads_tot else 0}%")
    k3.metric("Ventas",  f"{ventas:,}")
    k4.metric("Conv. Lead→Venta",
              f"{round(ventas/leads_tot*100)}%" if leads_tot > 0 else "–")

st.markdown("---")


# ── Tabla de embudo ───────────────────────────────────────────
titulo_tabla = {"Sem": "Embudo por semana", "Mes": "Embudo por mes", "Día": "Embudo por día"}
st.markdown(f'<p class="section-title">{titulo_tabla[vista]}</p>', unsafe_allow_html=True)

if df_vista.empty:
    st.info("No hay datos para el período seleccionado.")
else:
    df_d = df_vista.copy()

    # Formato fechas
    if vista == "Día":
        df_d["Fecha"] = df_d["fecha_ini"].dt.strftime("%d/%m/%y")
        col_per = ["Fecha"]
    elif vista == "Mes":
        df_d["Período"] = df_d["fecha_ini"].dt.strftime("%m/%Y")
        col_per = ["Período"]
    else:
        df_d["Ini-Fin"] = (df_d["fecha_ini"].dt.strftime("%d/%m") + " – " +
                           df_d["fecha_fin"].dt.strftime("%d/%m"))
        col_per = ["Ini-Fin"]

    # Calidad con %
    for col in ["gf", "bf", "pf", "sin_data"]:
        df_d[col] = df_d.apply(
            lambda r: _fmt_pct(int(r[col]) if pd.notna(r[col]) else 0,
                               int(r["leads"]) if pd.notna(r["leads"]) else 0), axis=1)

    # Inversión
    df_d["Inversión"] = df_d["inversion"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "–")

    # Columnas del embudo: N (X% de leads)
    for col, lbl in FUNNEL_COLS:
        fmt_col = col + "_fmt"
        df_d[fmt_col] = df_d.apply(
            lambda r, c=col: _fmt_pct(int(r[c]) if pd.notna(r[c]) else 0,
                                      int(r["leads"]) if pd.notna(r["leads"]) else 0), axis=1)

    cols_show = (col_per +
                 ["leads", "gf", "Inversión"] +
                 [c + "_fmt" for c, _ in FUNNEL_COLS])

    rename = {"leads": "Leads", "gf": "GF"}
    for col, lbl in FUNNEL_COLS:
        rename[col + "_fmt"] = lbl

    df_show = df_d[cols_show].rename(columns=rename)

    # Column config: ancho ajustado al contenido de cada columna
    _per_col = col_per[0]   # "Fecha" / "Período" / "Ini-Fin"
    _col_cfg = {
        _per_col      : st.column_config.TextColumn(_per_col,      width="small"),
        "Leads"       : st.column_config.NumberColumn("Leads",     width="small"),
        "GF"          : st.column_config.TextColumn("GF",          width="small"),
        "Inversión"   : st.column_config.TextColumn("Inversión",   width="small"),
        "R1"          : st.column_config.TextColumn("R1",          width="small"),
        "Follow podcast": st.column_config.TextColumn("Follow podcast", width="small"),
        "R2"          : st.column_config.TextColumn("R2",          width="small"),
        "Presupuesto" : st.column_config.TextColumn("Presupuesto", width="small"),
        "Venta"       : st.column_config.TextColumn("Venta",       width="small"),
    }

    evento = st.dataframe(
        df_show.style.set_properties(subset=["Leads"], **{"text-align": "center"}),
        column_config=_col_cfg,
        selection_mode="multi-row",
        on_select="rerun",
        use_container_width=True,
        hide_index=True,
    )
    filas_sel = evento.selection.rows if evento.selection else []

    # ── Totalizador ───────────────────────────────────────────
    def _total_row(df_raw, label):
        leads = int(df_raw["leads"].sum())
        gf    = int(df_raw["gf"].sum())
        inv   = df_raw["inversion"].sum()
        row   = {
            _per_col   : label,
            "Leads"    : leads,
            "GF"       : _fmt_pct(gf, leads),
            "Inversión": f"${inv:,.0f}",
        }
        for col, lbl in FUNNEL_COLS:
            n = int(df_raw[col].sum())
            row[lbl] = _fmt_pct(n, leads)
        return row

    rows_tot = [_total_row(df_vista, "📊 TOTAL período")]
    if filas_sel:
        rows_tot.append(_total_row(df_vista.iloc[filas_sel], "📌 SELECCIÓN"))

    def _style_tot(row):
        bg = "#f1f5f9" if "TOTAL" in str(row.iloc[0]) else "#e0f2fe"
        return [f"background-color: {bg}; font-weight: bold"] * len(row)

    st.dataframe(
        pd.DataFrame(rows_tot).style
            .apply(_style_tot, axis=1)
            .set_properties(subset=["Leads"], **{"text-align": "center"}),
        column_config=_col_cfg,
        use_container_width=True,
        hide_index=True,
    )
    st.caption("💡 Hacé click en filas para ver el detalle →")

    # ── Embudo gráfico ────────────────────────────────────────
    st.markdown("---")
    st.markdown('<p class="section-title">Embudo visual</p>', unsafe_allow_html=True)

    # Reutiliza df_crm_fil (ya filtrado por calidad y período completo)
    df_raw_periodo = df_crm_fil.copy()

    # Si hay filas seleccionadas, filtrar solo esos períodos
    if filas_sel:
        df_sel_periods = df_vista.iloc[filas_sel]
        mask = pd.Series(False, index=df_raw_periodo.index)
        for _, row in df_sel_periods.iterrows():
            mask |= (
                (df_raw_periodo["fecha_lead"] >= row["fecha_ini"]) &
                (df_raw_periodo["fecha_lead"] <= row["fecha_fin"])
            )
        df_raw_periodo = df_raw_periodo[mask]

    estados = df_raw_periodo["Estado"].dropna()

    data_embudo = {
        "capas" : [
            len(estados),
            int(estados.isin(R1_PLUS).sum()),
            int(estados.isin(FOLLOW_PLUS).sum()),
            int(estados.isin(R2_PLUS).sum()),
            int(estados.isin(PRESU_PLUS).sum()),
            int((estados == "Venta ganada").sum()),
        ],
        "labels": ["Leads", "R1", "Follow podcast", "R2", "Presupuesto", "Venta"],
        "fuga_leads": [
            ("Llamado cancelado",  int((estados == "0 - Llamado cancelado").sum())),
            ("Reagendar R1",       int((estados == "1.2 - Reagendar R1").sum())),
            ("Filtrado pre R1",    int((estados == "1.1 - Filtrado pre R1").sum())),
            ("Contacto inicial",   int((estados == "0.1 - Contacto inicial pre R1").sum())),
            ("Duplicados",         int((estados == "Duplicados").sum())),
            ("Nuevo",              int((estados == "Nuevo").sum())),
        ],
        "fuga_r1": [
            ("En R1",       int((estados == "2 - R1").sum())),
            ("Filtrado R1", int((estados == "3 - Filtrado en R1").sum())),
        ],
        "fuga_follow": [
            ("Follow podcast", int((estados == "4 - Follow podcast").sum())),
            ("Filtrado R2",    int((estados == "5.2 - Filtrado pre R2").sum())),
            ("Reagendar R2",   int((estados == "5.3 - Reagendar R2").sum())),
        ],
        "fuga_r2": [
            ("Irrelevante", int(estados.isin(["Irrelevante", "SDR - Irrelevante"]).sum())),
            ("BSI",         int((estados == "Buyer Sin interés").sum())),
        ],
        "fuga_presu": [
            ("Contactar a Futuro", int((estados == "Contactar a Futuro").sum())),
            ("Dijo que no",        int((estados == "Dijo que no").sum())),
            ("Follow Clienty",     int((estados == "Follow Clienty").sum())),
            ("Follow 2",           int((estados == "Follow 2").sum())),
            ("Stand By",           int((estados == "Stand By").sum())),
            ("Últimos detalles",   int((estados == "Últimos detalles").sum())),
        ],
    }

    _, col_emb, _ = st.columns([1, 4, 1])
    with col_emb:
        st.plotly_chart(graficos.embudo_ventas(data_embudo), use_container_width=True)


# ── Comparativa de embudos ────────────────────────────────────
st.divider()
st.subheader("🔀 Comparativa de embudos")
st.caption(f"Usa el mismo período del filtro principal · {fecha_desde.strftime('%d/%m/%Y')} → {fecha_hasta.strftime('%d/%m/%Y')}")

def _filtrar_crm_cmp(etiquetas_sel, calidad_sel):
    df_f = df_crm.copy()
    if calidad_sel != "Todos":
        df_f = df_f[df_f["calidad"] == calidad_map[calidad_sel]]
    if etiquetas_sel and "Etiquetas" in df_f.columns:
        sin_et   = "Sin etiquetas" in etiquetas_sel
        tags_sel = [v for v in etiquetas_sel if v != "Sin etiquetas"]
        et_col   = df_f["Etiquetas"].fillna("").astype(str)
        mask     = pd.Series(False, index=df_f.index)
        for tag in tags_sel:
            mask |= et_col.str.contains(tag, na=False, regex=False)
        if sin_et:
            mask |= et_col.str.strip().eq("") | et_col.str.strip().eq("nan")
        df_f = df_f[mask]
    return df_f

def _calc_funnel(df_base, fd, fh):
    df_f    = df_base[
        (df_base["fecha_lead"] >= pd.Timestamp(fd)) &
        (df_base["fecha_lead"] <= pd.Timestamp(fh))
    ].copy()
    estados = df_f["Estado"].dropna()
    return {
        "capas": [
            len(estados),
            int(estados.isin(R1_PLUS).sum()),
            int(estados.isin(FOLLOW_PLUS).sum()),
            int(estados.isin(R2_PLUS).sum()),
            int(estados.isin(PRESU_PLUS).sum()),
            int((estados == "Venta ganada").sum()),
        ],
        "labels": ["Leads", "R1", "Follow podcast", "R2", "Presupuesto", "Venta"],
        "fuga_leads": [
            ("Llamado cancelado", int((estados == "0 - Llamado cancelado").sum())),
            ("Reagendar R1",      int((estados == "1.2 - Reagendar R1").sum())),
            ("Filtrado pre R1",   int((estados == "1.1 - Filtrado pre R1").sum())),
            ("Contacto inicial",  int((estados == "0.1 - Contacto inicial pre R1").sum())),
            ("Duplicados",        int((estados == "Duplicados").sum())),
            ("Nuevo",             int((estados == "Nuevo").sum())),
        ],
        "fuga_r1": [
            ("En R1",       int((estados == "2 - R1").sum())),
            ("Filtrado R1", int((estados == "3 - Filtrado en R1").sum())),
        ],
        "fuga_follow": [
            ("Follow podcast", int((estados == "4 - Follow podcast").sum())),
            ("Filtrado R2",    int((estados == "5.2 - Filtrado pre R2").sum())),
            ("Reagendar R2",   int((estados == "5.3 - Reagendar R2").sum())),
        ],
        "fuga_r2": [
            ("Irrelevante", int(estados.isin(["Irrelevante", "SDR - Irrelevante"]).sum())),
            ("BSI",         int((estados == "Buyer Sin interés").sum())),
        ],
        "fuga_presu": [
            ("Contactar a Futuro", int((estados == "Contactar a Futuro").sum())),
            ("Dijo que no",        int((estados == "Dijo que no").sum())),
            ("Follow Clienty",     int((estados == "Follow Clienty").sum())),
            ("Follow 2",           int((estados == "Follow 2").sum())),
            ("Stand By",           int((estados == "Stand By").sum())),
            ("Últimos detalles",   int((estados == "Últimos detalles").sum())),
        ],
    }

col_cmp_a, col_cmp_b = st.columns(2)

with col_cmp_a:
    st.markdown("##### Embudo A")
    nombre_a = st.text_input("Nombre", value="Embudo A", key="cmp_nom_a",
                              label_visibility="collapsed")
    cal_a    = st.selectbox("Calidad A", ["Todos", "GF", "BF", "PF"],
                             key="cmp_cal_a", label_visibility="collapsed")
    et_a     = st.multiselect("Etiquetas A", opciones_et,
                               key="cmp_et_a", placeholder="Etiquetas…",
                               label_visibility="collapsed")
    df_cmp_a  = _filtrar_crm_cmp(et_a, cal_a)
    data_a    = _calc_funnel(df_cmp_a, fecha_desde, fecha_hasta)
    leads_a   = data_a["capas"][0]
    st.caption(f"**{nombre_a}** · {leads_a:,} leads")
    st.plotly_chart(graficos.embudo_ventas(data_a), use_container_width=True, key="chart_cmp_a")

with col_cmp_b:
    st.markdown("##### Embudo B")
    nombre_b = st.text_input("Nombre", value="Embudo B", key="cmp_nom_b",
                              label_visibility="collapsed")
    cal_b    = st.selectbox("Calidad B", ["Todos", "GF", "BF", "PF"],
                             key="cmp_cal_b", label_visibility="collapsed")
    et_b     = st.multiselect("Etiquetas B", opciones_et,
                               key="cmp_et_b", placeholder="Etiquetas…",
                               label_visibility="collapsed")
    df_cmp_b  = _filtrar_crm_cmp(et_b, cal_b)
    data_b    = _calc_funnel(df_cmp_b, fecha_desde, fecha_hasta)
    leads_b   = data_b["capas"][0]
    st.caption(f"**{nombre_b}** · {leads_b:,} leads")
    st.plotly_chart(graficos.embudo_ventas(data_b), use_container_width=True, key="chart_cmp_b")

# Tabla comparativa de tasas
if leads_a > 0 or leads_b > 0:
    _etapas = ["Leads", "R1", "Follow podcast", "R2", "Presupuesto", "Venta"]
    def _pct(n, tot): return f"{round(n/tot*100)}%" if tot > 0 else "–"
    rows_cmp = []
    for i, etapa in enumerate(_etapas):
        na = data_a["capas"][i]
        nb = data_b["capas"][i]
        rows_cmp.append({
            "Etapa"          : etapa,
            f"{nombre_a} (n)": na,
            f"{nombre_a} (%)" : _pct(na, leads_a),
            f"{nombre_b} (n)": nb,
            f"{nombre_b} (%)" : _pct(nb, leads_b),
        })
    st.markdown("**Comparativa de tasas**")
    _cmp_l, _cmp_m, _cmp_r = st.columns([1, 2, 1])
    with _cmp_m:
        _df_cmp = pd.DataFrame(rows_cmp)
        _html_cmp = _df_cmp.to_html(index=False, border=0)
        _html_cmp = (
            "<style>.cmp-tbl{width:100%;border-collapse:collapse;font-size:14px}"
            ".cmp-tbl th,.cmp-tbl td{padding:6px 10px;text-align:center;border-bottom:1px solid #e5e7eb}"
            ".cmp-tbl th{background:#f8fafc;font-weight:600;color:#6b7280}"
            ".cmp-tbl td:first-child,.cmp-tbl th:first-child{text-align:left}</style>"
            + _html_cmp.replace("<table", "<table class='cmp-tbl'")
        )
        st.markdown(_html_cmp, unsafe_allow_html=True)


