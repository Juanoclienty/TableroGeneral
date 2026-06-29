"""
4_Trazabilidad.py — Semáforos diarios, semanales y mensuales vs objetivos.
"""
import sys, os, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date, timedelta
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import urllib.request

st.set_page_config(page_title="Trazabilidad", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

ID_SHEET     = "1eGCO6821Dy7j591fShFAkezDHoaRUvTXgAWJt8eDZus"
ID_FORECAST  = "1YqA-KxXDdWK6Xj0ftQ6Z5MUEDWpJq9rLzoa_KvqIBdk"
ID_REPORTES  = "1b2LzEE8T5yQERP934C4kNQJbUiVZcNdR7aBjB9R2kHM"

OBJ = {
    "Día":    {"Leads": 19, "R1": 15, "Follow": 9, "R2": 7, "Presupuesto": 6},
    "Semana": {"Leads": 80, "R1": 64, "Follow": 38, "R2": 30, "Presupuesto": 26},
    "Mes":    {"Leads": 313, "R1": 250, "Follow": 150, "R2": 117, "Presupuesto": 100},
}


# ── Carga sheets ─────────────────────────────────────────────────

def _fetch_csv(sheet_name: str) -> pd.DataFrame:
    import os
    cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache", f"traz_{sheet_name}.parquet")
    if os.path.exists(cache_path):
        return pd.read_parquet(cache_path)
    url = (
        f"https://docs.google.com/spreadsheets/d/{ID_SHEET}"
        f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(sheet_name)}"
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        return pd.read_csv(r, header=0)


def _fetch_external_csv(sheet_id: str, sheet_name: str) -> pd.DataFrame:
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(sheet_name)}"
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        return pd.read_csv(r, header=0)


_ID_BBDD_MARKETING = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"

def _detectar_chance_traz(et):
    s = str(et).lower() if pd.notna(et) else ""
    if "chance de venta media-alta" in s: return "Media-Alta"
    if "chance de venta alta"       in s: return "Alta"
    if "chance de venta media"      in s: return "Media"
    if "chance de venta baja"       in s: return "Baja"
    return None

@st.cache_data(ttl=3600)
def cargar_presupuestos_con_chance() -> pd.DataFrame:
    """Presupuestos con fecha + chance de venta + Nombre, Mail, Closer del CRM."""
    try:
        df_presu = _fetch_external_csv(_ID_BBDD_MARKETING, "bbdd_presupuestos")
        # Columnas base siempre presentes
        cols_presu = {"FECHA DE ENVIO": "fecha", "ID DE PROSPECTO": "id"}
        # Columna "asignado a" puede existir o no
        _col_closer = next((c for c in df_presu.columns
                            if "asignado" in c.lower()), None)
        keep = list(cols_presu.keys())
        if _col_closer:
            keep.append(_col_closer)
        df_presu = df_presu[keep].copy()
        df_presu = df_presu.rename(columns=cols_presu)
        if _col_closer:
            df_presu = df_presu.rename(columns={_col_closer: "closer"})
        else:
            df_presu["closer"] = ""
        df_presu["id"]    = df_presu["id"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        df_presu["fecha"] = pd.to_datetime(df_presu["fecha"], dayfirst=True, errors="coerce")
        df_presu = df_presu.dropna(subset=["fecha", "id"])
        df_presu = df_presu[df_presu["id"] != ""]

        import datos_crm as _crm
        df_crm = _crm.cargar_crm()[["id", "Etiquetas", "Nombre", "Emails", "Estado"]].copy()
        df_crm["id"] = df_crm["id"].astype(str).str.strip()

        df = df_presu.merge(df_crm, on="id", how="left")
        df["chance"] = df["Etiquetas"].apply(_detectar_chance_traz)
        df["semana"] = df["fecha"].dt.isocalendar().week.astype(int)
        df["mes"]    = df["fecha"].dt.to_period("M")
        df["Nombre"] = df["Nombre"].fillna("–")
        df["Emails"] = df["Emails"].fillna("–")
        df["closer"] = df["closer"].fillna("–")
        df["Estado"] = df["Estado"].fillna("–")
        return df
    except Exception:
        return pd.DataFrame(columns=["fecha","id","Etiquetas","chance","semana","mes",
                                     "Nombre","Emails","closer","Estado"])


@st.cache_data(ttl=1800)
def cargar_links_reportes() -> dict:
    """Devuelve dict {"16/06": {"r1": url, "r2": url}, ...} leyendo el Sheet de reportes."""
    links = {}
    for tipo in ("R1", "R2"):
        try:
            df = _fetch_external_csv(ID_REPORTES, tipo)
            fecha_col = df.columns[0]
            link_col  = df.columns[1]
            for _, row in df.iterrows():
                fecha_raw = str(row[fecha_col]).strip()
                url       = str(row[link_col]).strip()
                if not fecha_raw or fecha_raw in ("nan", ""):
                    continue
                try:
                    ts  = pd.to_datetime(fecha_raw, errors="coerce")
                    key = ts.strftime("%d/%m")   # "16/06"
                    if key not in links:
                        links[key] = {}
                    # Convertir URL de visor Drive a URL de render directo
                    import re as _re
                    m = _re.search(r'/d/([a-zA-Z0-9_-]+)', url)
                    if m:
                        url = f"https://drive.google.com/uc?export=view&id={m.group(1)}"
                    links[key][tipo.lower()] = url
                except Exception:
                    pass
        except Exception:
            pass
    return links


@st.cache_data(ttl=3600)
def cargar_forecast_sheet() -> pd.DataFrame:
    """Lee Prob. cierre y Observación de Forecast Seba + Forecast Ro, matchea por ID."""
    frames = []
    for tab in ["Forecast Seba", "Forecast Ro"]:
        try:
            df_tab = _fetch_external_csv(ID_FORECAST, tab)
            # Buscar columna ID (nombre exacto o primera columna)
            id_col = next(
                (c for c in df_tab.columns if str(c).strip().upper() in ("ID", "LEAD ID", "ID LEAD")),
                df_tab.columns[0],
            )
            row = {"_id": df_tab[id_col].astype(str).str.strip()}
            if len(df_tab.columns) > 7:
                row["Prob. cierre"] = df_tab.iloc[:, 7]
            if len(df_tab.columns) > 8:
                row["Observación"] = df_tab.iloc[:, 8]
            frames.append(pd.DataFrame(row))
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(columns=["_id", "Prob. cierre", "Observación"])
    df = pd.concat(frames, ignore_index=True)
    df["_id"] = df["_id"].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    return df.dropna(subset=["_id"]).drop_duplicates(subset=["_id"])


@st.cache_data(ttl=3600)
def cargar_alta_forecast() -> pd.DataFrame:
    """Filas con Tipo='Alta' (col B) de ambas pestañas del sheet de Forecast."""
    frames = []
    for tab in ["Forecast Seba", "Forecast Ro"]:
        try:
            df_tab = _fetch_external_csv(ID_FORECAST, tab)
            if len(df_tab.columns) < 2:
                continue
            mask = df_tab.iloc[:, 1].astype(str).str.strip().str.lower() == "alta"
            df_tab = df_tab[mask].copy()
            if df_tab.empty:
                continue
            row = {"_id": df_tab.iloc[:, 0].astype(str).str.strip()}
            if len(df_tab.columns) > 7:
                row["Prob. cierre"] = df_tab.iloc[:, 7].values
            if len(df_tab.columns) > 8:
                row["Observación"] = df_tab.iloc[:, 8].values
            frames.append(pd.DataFrame(row))
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(columns=["_id", "Prob. cierre", "Observación"])
    df = pd.concat(frames, ignore_index=True)
    df["_id"] = df["_id"].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    return df.dropna(subset=["_id"])


def _parse_fecha(s) -> pd.Timestamp:
    try:
        d, m = str(s).strip().split("/")
        return pd.Timestamp(year=2026, month=int(m), day=int(d))
    except Exception:
        return pd.NaT


@st.cache_data(ttl=3600)
def cargar_datos():
    # Diaria_R1: col0=fecha, col2=semana, col3=leads, col10=R1, col11=FP
    r1 = _fetch_csv("Diaria_R1")
    r1 = r1.iloc[:, [0, 2, 3, 10, 11]].copy()
    r1.columns = ["fecha_str", "semana", "leads", "r1", "fp"]
    r1["fecha"] = r1["fecha_str"].apply(_parse_fecha)
    r1 = r1.dropna(subset=["fecha"])
    for c in ["leads", "r1", "fp"]:
        r1[c] = pd.to_numeric(r1[c], errors="coerce").fillna(0).astype(int)
    r1["semana"] = pd.to_numeric(r1["semana"], errors="coerce")
    r1 = r1.sort_values("fecha").reset_index(drop=True)

    # Diaria_R2: col0=fecha, col2=semana, col3=R2agendada, col4=R2cancelada,
    #            col5=R2reagendar, col7=Presupuesto, col8=FollowClienty,
    #            col9=R2efectiva, col26=Alta, col27=Media-Alta, col28=Media, col29=Baja
    r2_raw = _fetch_csv("Diaria_R2")
    def _sc(idx):
        return r2_raw.iloc[:, idx] if idx < len(r2_raw.columns) else pd.Series(0, index=r2_raw.index)

    r2 = pd.DataFrame({
        "fecha_str":    r2_raw.iloc[:, 0],
        "semana":       r2_raw.iloc[:, 2],
        "r2_agendada":  r2_raw.iloc[:, 3],
        "r2_cancelada": _sc(4),
        "r2_reagendar": _sc(5),
        "presupuesto":  _sc(7),
        "fc_clienty":   _sc(8),
        "r2_efectiva":  _sc(9),
        "alta":         _sc(26),
        "media_alta":   _sc(27),
        "media":        _sc(28),
        "baja":         _sc(29),
    })
    r2["fecha"] = r2["fecha_str"].apply(_parse_fecha)
    r2 = r2.dropna(subset=["fecha"])
    _R2_COLS = ["r2_agendada", "r2_cancelada", "r2_reagendar", "presupuesto",
                "fc_clienty", "r2_efectiva", "alta", "media_alta", "media", "baja"]
    for c in _R2_COLS:
        r2[c] = pd.to_numeric(r2[c], errors="coerce").fillna(0).astype(int)
    r2["semana"] = pd.to_numeric(r2["semana"], errors="coerce")
    r2 = r2.sort_values("fecha").reset_index(drop=True)

    df = pd.merge(
        r1[["fecha", "semana", "leads", "r1", "fp"]],
        r2[["fecha"] + _R2_COLS],
        on="fecha", how="outer",
    ).sort_values("fecha").reset_index(drop=True)

    df["semana"] = pd.to_numeric(df["semana"], errors="coerce")
    for c in ["leads", "r1", "fp"] + _R2_COLS:
        df[c] = df[c].fillna(0).astype(int)

    sem_dates = (
        df.dropna(subset=["semana"])
        .groupby("semana")["fecha"].min()
        .reset_index()
        .rename(columns={"fecha": "lunes"})
    )
    return df, sem_dates


@st.cache_data(ttl=3600)
def obj_ventas_mes() -> int | None:
    """Lee el objetivo mensual de Ventas del sheet Objetivos (busca fila 'Venta' en sección mensual)."""
    try:
        df_obj = _fetch_csv("Objetivos")
        in_monthly = False
        for _, row in df_obj.iterrows():
            cell = str(row.iloc[1]).strip().lower()
            if "por mes" in cell:
                in_monthly = True
                continue
            if in_monthly and "venta" in cell:
                val = pd.to_numeric(row.iloc[2], errors="coerce")
                if pd.notna(val):
                    return int(val)
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600)
def cargar_ventas_crm() -> pd.DataFrame:
    """Ventas ganadas del CRM agrupadas por fecha de lead."""
    try:
        import datos_crm as _crm
        df_crm = _crm.cargar_crm()
        v = df_crm[df_crm["estado_resumen"] == "5. Venta"][["fecha_lead"]].copy()
        v["ventas"] = 1
        return v.groupby("fecha_lead")["ventas"].sum().reset_index()
    except Exception:
        return pd.DataFrame(columns=["fecha_lead", "ventas"])



@st.cache_data(ttl=3600)
def cargar_gf_trazabilidad() -> pd.DataFrame:
    """Retorna df diario con fecha_ini, leads, gf, vgf del CRM (sin datos de ads)."""
    try:
        import datos_crm as _crm
        _df_c  = _crm.cargar_crm()
        _df_ads = pd.DataFrame({
            "fecha":     pd.Series(dtype="datetime64[ns]"),
            "inversion": pd.Series(dtype=float),
        })
        return _crm.calcular_dias_crm(_df_c, _df_ads, dias=180)
    except Exception:
        return pd.DataFrame()


# ID del mismo Google Sheet que usa la página de Ventas
_ID_VENTAS_BBDD = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"


@st.cache_data(ttl=3600)
def cargar_bbdd_ventas_traz() -> pd.DataFrame:
    """Carga BBDD_Ventas — misma fuente que la página de Ventas."""
    try:
        url = (f"https://docs.google.com/spreadsheets/d/{_ID_VENTAS_BBDD}"
               f"/gviz/tq?tqx=out:csv&sheet=BBDD_Ventas")
        df = pd.read_csv(url, dtype=str)
        df.columns = df.columns.str.strip()
        df["_fecha_venta"]       = pd.to_datetime(df.get("Fecha", ""),              dayfirst=True, errors="coerce")
        df["_fecha_lead"]        = pd.to_datetime(df.get("Fecha lead", ""),         dayfirst=True, errors="coerce")
        df["_monto"]             = pd.to_numeric(df.get("Monto de venta", ""),      errors="coerce").fillna(0)
        df["_ventana"]           = pd.to_numeric(df.get("Venta cierre (días)", ""), errors="coerce")
        df["ID prospecto"]       = df.get("ID prospecto", pd.Series(dtype=str)).astype(str).str.strip()
        df["_canal_adq"]         = df.get("Canal de adquisicion", pd.Series(dtype=str)).fillna("")
        return df.dropna(subset=["_fecha_venta"])
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def cargar_bbdd_presu_traz() -> pd.DataFrame:
    """Carga bbdd_presupuestos — misma fuente que la página de Ventas."""
    try:
        url = (f"https://docs.google.com/spreadsheets/d/{_ID_VENTAS_BBDD}"
               f"/gviz/tq?tqx=out:csv&sheet=bbdd_presupuestos")
        df = pd.read_csv(url, dtype=str)
        df.columns = df.columns.str.strip()
        df["_fecha"] = pd.to_datetime(df.get("FECHA DE ENVIO", ""), dayfirst=True, errors="coerce")
        return df.dropna(subset=["_fecha"])
    except Exception:
        return pd.DataFrame()


# ── Helpers ──────────────────────────────────────────────────────

def _icon(actual, obj, ok=0.85, warn=0.65):
    if obj == 0 or pd.isna(actual):
        return "⚪"
    return "🟢" if actual / obj >= ok else ("🟡" if actual / obj >= warn else "🔴")


def _tarjeta(col, nombre, actual, objetivo):
    col.metric(
        label=f"{_icon(actual, objetivo)} {nombre}",
        value=actual,
        delta=f"{actual - objetivo:+d}  (obj {objetivo})",
        delta_color="normal",
    )


def _semana_de_traz(ts):
    """Retorna el lunes de la semana del timestamp dado (igual que _semana_de en Ventas)."""
    if pd.isna(ts):
        return pd.NaT
    t = pd.Timestamp(ts).normalize()
    return t - pd.Timedelta(days=t.dayofweek)


def _semanas_cerradas_rango(n=8, excluir=0):
    hoy = date.today()
    dias = (hoy.weekday() + 1) % 7 or 7
    ultimo_dom = hoy - timedelta(days=dias)
    fin    = ultimo_dom - timedelta(weeks=excluir)
    inicio = fin - timedelta(weeks=n) + timedelta(days=1)
    return inicio, fin


def _meses_rango(n=1):
    hoy = date.today()
    m, y = hoy.month - (n - 1), hoy.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1), hoy


def _ventas_en_rango(df_v: pd.DataFrame, desde: pd.Timestamp, hasta: pd.Timestamp) -> int:
    if df_v.empty:
        return 0
    mask = (df_v["fecha_lead"] >= desde) & (df_v["fecha_lead"] < hasta)
    return int(df_v.loc[mask, "ventas"].sum())


def _ventas_en_mes(df_v: pd.DataFrame, periodo) -> int:
    if df_v.empty:
        return 0
    return int(df_v[df_v["fecha_lead"].dt.to_period("M") == periodo]["ventas"].sum())


# ── UI ───────────────────────────────────────────────────────────

st.title("🔍 Trazabilidad")

try:
    df, sem_dates = cargar_datos()
except Exception as e:
    st.error(f"Error cargando datos: {e}")
    st.stop()

# Objetivos de ventas: del sheet (mensual) y derivado para semana
_obj_v_mes = obj_ventas_mes()
_obj_v_sem = round(_obj_v_mes / 4.2) if _obj_v_mes else None

# Datos reales de ventas del CRM (para semáforo actual)
df_ventas = cargar_ventas_crm()

# Mismas fuentes que la página de Ventas (para las tarjetas Resumen)
try:
    df_bbdd_res  = cargar_bbdd_ventas_traz()
except Exception:
    df_bbdd_res  = pd.DataFrame()

try:
    df_presu_res = cargar_bbdd_presu_traz()
except Exception:
    df_presu_res = pd.DataFrame()

try:
    import datos as _datos_mod
    df_ads_res = _datos_mod.cargar_ads()
except Exception:
    df_ads_res = pd.DataFrame()

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 Trazabilidad")
    st.markdown("---")

    _vista_raw = st.radio("", ["Día", "Sem", "Mes"], horizontal=True, label_visibility="collapsed")
    vista = "Semana" if _vista_raw == "Sem" else _vista_raw
    st.markdown("")

    hoy = date.today()
    if vista == "Día":
        fecha_desde = hoy - timedelta(days=60)
        fecha_hasta = hoy
    elif vista == "Semana":
        fecha_desde = hoy - timedelta(weeks=24)
        fecha_hasta = hoy
    else:  # Mes
        fecha_desde = hoy - timedelta(days=365)
        fecha_hasta = hoy


    st.markdown("---")
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

obj = OBJ[vista]

@st.dialog("Detalle de ventas", width="large")
def _modal_detalle_traz(label, filas):
    st.markdown(f"**{label} — {len(filas)} ventas**")
    st.dataframe(
        pd.DataFrame(filas),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Empresa": st.column_config.TextColumn("Empresa", width="medium"),
        },
    )

def _build_filas_traz(df_v):
    import datos_crm as _dcrm_t
    # Enriquecer con CRM para Empresa y Etiquetas (igual que Ventas)
    try:
        _crm_t = _dcrm_t.cargar_crm()
        _enrich_cols = ["id"] + [c for c in ["Nombre","Emails","Empresa","Etiquetas"] if c in _crm_t.columns]
        _enrich_t = _crm_t[_enrich_cols].copy()
        _enrich_t["id"] = _enrich_t["id"].astype(str).str.strip()
        _empresa_lkp = _enrich_t.set_index("id")["Empresa"].to_dict() if "Empresa" in _enrich_t.columns else {}
        _etiq_lkp    = _enrich_t.set_index("id")["Etiquetas"].to_dict() if "Etiquetas" in _enrich_t.columns else {}
    except Exception:
        _empresa_lkp = {}; _etiq_lkp = {}
    # CPV mensual desde df_ads_res
    try:
        _ads_cpv = df_ads_res.copy()
        _ads_cpv["_pm"] = pd.to_datetime(_ads_cpv["fecha"], errors="coerce").dt.to_period("M")
        _inv_m   = _ads_cpv.groupby("_pm")["inversion"].sum()
        # ventas por mes desde df_bbdd_res
        _vtas_m  = df_v.groupby(df_v["_fecha_venta"].dt.to_period("M")).size()
        _cpv_lkp = {p: round(_inv_m[p] / _vtas_m[p]) for p in _inv_m.index if p in _vtas_m.index and _vtas_m[p] > 0}
    except Exception:
        _cpv_lkp = {}

    filas = []
    for _, r in df_v.sort_values("_fecha_venta", ascending=False).iterrows():
        fv  = r["_fecha_venta"]
        _id = str(r.get("ID prospecto", "") or "").strip()
        monto     = float(r.get("_monto", 0) or 0)
        empresa   = str(_empresa_lkp.get(_id, "") or r.get("Empresa", "") or "").strip() or "–"
        vendedor  = str(r.get("Vendedor", "") or "").strip()
        vendedor  = vendedor.split()[0] if vendedor else "–"
        fecha_str = fv.strftime("%d/%m/%Y") if pd.notna(fv) else "–"
        fl        = r.get("_fecha_lead", pd.NaT)
        fecha_lead_str = pd.Timestamp(fl).strftime("%d/%m/%Y") if pd.notna(fl) else "–"
        ventana_raw = r.get("_ventana")
        if pd.notna(ventana_raw):
            ventana = str(int(ventana_raw))
        elif pd.notna(fv) and pd.notna(fl):
            ventana = str((fv.normalize() - pd.Timestamp(fl).normalize()).days)
        else:
            ventana = "–"
        # CPV
        _cpv = _cpv_lkp.get(fv.to_period("M")) if pd.notna(fv) else None
        # LTV
        # Tipo
        _ets   = str(_etiq_lkp.get(_id, "") or "").lower()
        _canal = str(r.get("_canal_adq", "") or "").strip().lower()
        if "proc" in _ets and "vgf" in _ets:
            _tipo = "VGF"
        elif "referido" in _canal:
            _tipo = "Referido"
        else:
            _tipo = ""
        filas.append({
            "Fecha":      fecha_str,
            "Tipo":       _tipo,
            "ID":         _id,
            "Empresa":    empresa,
            "Vendedor":   vendedor,
            "Monto":      "$ {:,.0f}".format(monto) if monto > 0 else "–",
            "Fecha lead": fecha_lead_str,
            "Ventana":    ventana,
            "CPV":        "$ {:,.0f}".format(_cpv) if _cpv else "–",
        })
    return filas

tab_gral, tab_cc, tab_closer = st.tabs(["Gral", "Perfo. CC", "Perfo. Closer"])
with tab_gral:
    
    # ── Resumen (últimos 4 períodos) — mismas fuentes que página Ventas ─
    st.markdown("### Resumen")
    
    _dv_gf_raw = cargar_gf_trazabilidad()
    
    def _fmt_n_res(v):
        return str(int(v)) if v and int(v) > 0 else "–"
    
    # ── Pre-computar dicts por período según vista ────────────────────
    if vista == "Mes":
        _p_act_res = pd.Timestamp.today().to_period("M")
    
        # Ventas — BBDD_Ventas sheet (misma fuente que Ventas)
        _vtas_dict = (
            df_bbdd_res["_fecha_venta"].dt.to_period("M").value_counts().to_dict()
            if not df_bbdd_res.empty else {}
        )
        # Presupuestos — bbdd_presupuestos sheet (misma fuente que Ventas)
        _presu_dict = (
            df_presu_res["_fecha"].dt.to_period("M").value_counts().to_dict()
            if not df_presu_res.empty else {}
        )
        # Leads + GF — CRM (misma fuente que Ventas)
        if not _dv_gf_raw.empty:
            _dv_g = _dv_gf_raw.copy()
            _dv_g["_vp_res"] = _dv_g["fecha_ini"].dt.to_period("M")
            _gf_cols_res = [c for c in ["leads", "gf"] if c in _dv_g.columns]
            _gf_dict = _dv_g.groupby("_vp_res")[_gf_cols_res].sum().to_dict("index") if _gf_cols_res else {}
        else:
            _gf_dict = {}
    
        if not df_ads_res.empty:
            _ads_g = df_ads_res.copy()
            _ads_g["_vp_res"] = pd.to_datetime(_ads_g["fecha"], errors="coerce").dt.to_period("M")
            _inv_dict = _ads_g.groupby("_vp_res")["inversion"].sum().to_dict()
        else:
            _inv_dict = {}

        _all_p_res  = set(_vtas_dict) | set(_presu_dict) | set(_gf_dict)
        _all_p_res.add(_p_act_res)
        _ult4_res   = sorted(_all_p_res)[-4:]

        def _lbl_res(p):
            return pd.Timestamp(p.start_time).strftime("%b %Y").capitalize()

        def _metrics_res(p):
            n_v   = int(_vtas_dict.get(p, 0))
            n_pr  = int(_presu_dict.get(p, 0))
            row   = _gf_dict.get(p, {})
            leads = int(row.get("leads", 0) or 0)
            gf    = int(row.get("gf",    0) or 0)
            pct   = (str(round(gf / leads * 100)) + "%") if leads > 0 else "–"
            inv   = float(_inv_dict.get(p, 0) or 0)
            return n_v, n_pr, leads, pct, inv
    
    elif vista == "Semana":
        _hoy_res = pd.Timestamp.today()
        _lun_act = (_hoy_res - pd.Timedelta(days=_hoy_res.dayofweek)).normalize()
    
        # Ventas
        _vtas_dict = (
            df_bbdd_res.groupby(df_bbdd_res["_fecha_venta"].apply(_semana_de_traz)).size().to_dict()
            if not df_bbdd_res.empty else {}
        )
        # Presupuestos
        _presu_dict = (
            df_presu_res.groupby(df_presu_res["_fecha"].apply(_semana_de_traz)).size().to_dict()
            if not df_presu_res.empty else {}
        )
        # Leads + GF
        if not _dv_gf_raw.empty:
            _dv_g = _dv_gf_raw.copy()
            _dv_g["_vp_res"] = (
                _dv_g["fecha_ini"] - pd.to_timedelta(_dv_g["fecha_ini"].dt.dayofweek, unit="D")
            ).dt.normalize()
            _gf_cols_res = [c for c in ["leads", "gf"] if c in _dv_g.columns]
            _gf_dict = _dv_g.groupby("_vp_res")[_gf_cols_res].sum().to_dict("index") if _gf_cols_res else {}
        else:
            _gf_dict = {}
    
        if not df_ads_res.empty:
            _ads_g = df_ads_res.copy()
            _ads_g["_vp_res"] = (
                pd.to_datetime(_ads_g["semana_inicio"], errors="coerce")
            ).dt.normalize()
            _inv_dict = _ads_g.groupby("_vp_res")["inversion"].sum().to_dict()
        else:
            _inv_dict = {}

        _all_p_res = {k for k in (set(_vtas_dict) | set(_presu_dict) | set(_gf_dict)) if pd.notna(k)}
        _all_p_res.add(_lun_act)
        _ult4_res  = sorted(_all_p_res)[-4:]

        def _lbl_res(p):
            return f"Sem. {pd.Timestamp(p).strftime('%d/%m')}"

        def _metrics_res(p):
            _k    = pd.Timestamp(p)
            n_v   = int(_vtas_dict.get(_k, 0))
            n_pr  = int(_presu_dict.get(_k, 0))
            row   = _gf_dict.get(_k, {})
            leads = int(row.get("leads", 0) or 0)
            gf    = int(row.get("gf",    0) or 0)
            pct   = (str(round(gf / leads * 100)) + "%") if leads > 0 else "–"
            inv   = float(_inv_dict.get(_k, 0) or 0)
            return n_v, n_pr, leads, pct, inv
    
    else:  # Día
        _hoy_res = pd.Timestamp.today().normalize()
    
        # Ventas
        _vtas_dict = (
            df_bbdd_res.groupby(df_bbdd_res["_fecha_venta"].dt.normalize()).size().to_dict()
            if not df_bbdd_res.empty else {}
        )
        # Presupuestos
        _presu_dict = (
            df_presu_res.groupby(df_presu_res["_fecha"].dt.normalize()).size().to_dict()
            if not df_presu_res.empty else {}
        )
        # Leads + GF
        if not _dv_gf_raw.empty:
            _dv_g = _dv_gf_raw.copy()
            _dv_g["_vp_res"] = _dv_g["fecha_ini"].dt.normalize()
            _gf_cols_res = [c for c in ["leads", "gf"] if c in _dv_g.columns]
            _gf_dict = _dv_g.groupby("_vp_res")[_gf_cols_res].sum().to_dict("index") if _gf_cols_res else {}
        else:
            _gf_dict = {}
    
        if not df_ads_res.empty:
            _ads_g = df_ads_res.copy()
            _ads_g["_lun"] = pd.to_datetime(_ads_g["semana_inicio"], errors="coerce").dt.normalize()
            _inv_sem_dict = _ads_g.groupby("_lun")["inversion"].sum().to_dict()
        else:
            _inv_sem_dict = {}

        def _inv_para_dia(d):
            _ts = pd.Timestamp(d)
            _lun = (_ts - pd.Timedelta(days=_ts.dayofweek)).normalize()
            return float(_inv_sem_dict.get(_lun, 0) or 0)

        _all_p_res = {k for k in (set(_vtas_dict) | set(_presu_dict) | set(_gf_dict)) if pd.notna(k)}
        _all_p_res.add(_hoy_res)
        _ult4_res  = sorted(_all_p_res)[-4:]

        def _lbl_res(p):
            return pd.Timestamp(p).strftime("%d/%m")

        def _metrics_res(p):
            _k    = pd.Timestamp(p)
            n_v   = int(_vtas_dict.get(_k, 0))
            n_pr  = int(_presu_dict.get(_k, 0))
            row   = _gf_dict.get(_k, {})
            leads = int(row.get("leads", 0) or 0)
            gf    = int(row.get("gf",    0) or 0)
            pct   = (str(round(gf / leads * 100)) + "%") if leads > 0 else "–"
            inv   = _inv_para_dia(_k)
            return n_v, n_pr, leads, pct, inv
    
    # ── Renderizar tarjetas (más reciente a la izquierda, igual que Ventas) ──
    if _ult4_res:
        _cols_res = st.columns(len(_ult4_res))
        for _i_res, (_col_res, _periodo_res) in enumerate(zip(_cols_res, reversed(_ult4_res))):
            _lbl_str_r                                   = _lbl_res(_periodo_res)
            _n_v_r, _n_pre_r, _leads_r, _pct_gf_r, _inv_r = _metrics_res(_periodo_res)
            _vtas_lbl_r = "venta" if _n_v_r == 1 else "ventas"

            def _fmt_inv(v):
                if not v: return "–"
                return f"${v:,.0f}"
            def _fmt_cp(inv, denom):
                if not inv or not denom: return "–"
                return f"${round(inv/denom):,}"

            _cpl_r  = _fmt_cp(_inv_r, _leads_r)
            _cpe_r  = _fmt_cp(_inv_r, _n_pre_r)
            _cpv_r  = _fmt_cp(_inv_r, _n_v_r)
            _tc_real_r = (str(round(_n_v_r / _n_pre_r * 100)) + "%") if _n_pre_r > 0 else "–"
            _has_inv = bool(_inv_r)

            _html_res = (
                '<div style="background:linear-gradient(135deg,#2196F3,#1565C0);'
                'border-radius:12px;padding:20px 16px 14px;text-align:center;color:white;margin-bottom:6px">'
                f'<div style="font-size:1rem;font-weight:600;margin-bottom:8px">{_lbl_str_r}</div>'
                f'<div style="font-size:2rem;font-weight:700;line-height:1.1">{_n_v_r}</div>'
                f'<div style="font-size:0.78rem;opacity:.85;margin-bottom:6px">{_vtas_lbl_r}</div>'
                '<div style="display:flex;justify-content:space-around;font-size:0.75rem;'
                'border-top:1px solid rgba(255,255,255,.25);padding-top:7px;margin-top:4px">'
                f'<div><div style="opacity:.7">Presupuestos</div><div style="font-weight:600">{_fmt_n_res(_n_pre_r)}</div></div>'
                f'<div><div style="opacity:.7">TC Real</div><div style="font-weight:600">{_tc_real_r}</div></div>'
                f'<div><div style="opacity:.7">Leads</div><div style="font-weight:600">{_fmt_n_res(_leads_r)}</div></div>'
                f'<div><div style="opacity:.7">%GF</div><div style="font-weight:600">{_pct_gf_r}</div></div>'
                '</div>'
            )
            if _has_inv:
                _html_res += (
                    '<div style="display:flex;justify-content:space-around;font-size:0.75rem;'
                    'border-top:1px solid rgba(255,255,255,.15);padding-top:6px;margin-top:4px">'
                    f'<div><div style="opacity:.7">Inv.</div><div style="font-weight:600">{_fmt_inv(_inv_r)}</div></div>'
                    f'<div><div style="opacity:.7">CPL</div><div style="font-weight:600">{_cpl_r}</div></div>'
                    f'<div><div style="opacity:.7">CPE</div><div style="font-weight:600">{_cpe_r}</div></div>'
                    f'<div><div style="opacity:.7">CPV</div><div style="font-weight:600">{_cpv_r}</div></div>'
                    '</div>'
                )
            _html_res += '</div>'

            with _col_res:
                st.markdown(_html_res, unsafe_allow_html=True)
                # Filtrar ventas del período para el modal
                if not df_bbdd_res.empty:
                    if vista == "Mes":
                        _mask_v = df_bbdd_res["_fecha_venta"].dt.to_period("M") == _periodo_res
                    elif vista == "Semana":
                        _mask_v = df_bbdd_res["_fecha_venta"].apply(_semana_de_traz) == pd.Timestamp(_periodo_res)
                    else:
                        _mask_v = df_bbdd_res["_fecha_venta"].dt.normalize() == pd.Timestamp(_periodo_res)
                    _grp_v = df_bbdd_res[_mask_v]
                else:
                    _grp_v = pd.DataFrame()
                if st.button("Ver detalle", key=f"traz_card_{_i_res}", use_container_width=True):
                    _modal_detalle_traz(_lbl_str_r, _build_filas_traz(_grp_v))

    # ── Exportar detalle ──────────────────────────────────────────
    if not df_bbdd_res.empty and _ult4_res:
        import io, base64
        def _exportar_traz() -> bytes:
            frames = []
            for _p in _ult4_res:
                if vista == "Mes":
                    _m = df_bbdd_res["_fecha_venta"].dt.to_period("M") == _p
                elif vista == "Semana":
                    _m = df_bbdd_res["_fecha_venta"].apply(_semana_de_traz) == pd.Timestamp(_p)
                else:
                    _m = df_bbdd_res["_fecha_venta"].dt.normalize() == pd.Timestamp(_p)
                _grp = df_bbdd_res[_m]
                if _grp.empty: continue
                _df_p = pd.DataFrame(_build_filas_traz(_grp))
                _df_p.insert(0, "Período", _lbl_res(_p))
                frames.append(_df_p)
            if not frames: return b""
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                pd.concat(frames, ignore_index=True).to_excel(w, index=False, sheet_name="Detalle ventas")
            return buf.getvalue()
        _xlsx = _exportar_traz()
        _b64  = base64.b64encode(_xlsx).decode()
        _col_src_t, _col_exp_t = st.columns([3, 1])
        _col_src_t.markdown(
            '<div style="text-align:right;font-size:0.68rem;color:#94a3b8;margin-top:8px">'
            f'Ventas reales, presupuestos reales e Inversión en pauta provienen del '
            f'<a href="https://docs.google.com/spreadsheets/d/{_ID_VENTAS_BBDD}" target="_blank" '
            f'style="color:#94a3b8;text-decoration:underline">tablero de marketing</a>.'
            '</div>',
            unsafe_allow_html=True,
        )
        _col_exp_t.markdown(
            f'<div style="text-align:right;margin-top:6px">'
            f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{_b64}" '
            f'download="detalle_ventas_traz.xlsx" '
            f'style="font-size:0.72rem;color:#64748b;text-decoration:none;'
            f'border:1px solid #cbd5e1;border-radius:4px;padding:3px 8px;">'
            f'⬇ Exportar detalle</a></div>',
            unsafe_allow_html=True,
        )

    st.divider()
    
    # ── Semáforo del período actual ──────────────────────────────────
    if vista == "Día":
        st.subheader("Último día con datos")
        ult = df[df["leads"] > 0]
        if not ult.empty:
            row = ult.iloc[-1]
            st.caption(f"**{row['fecha'].strftime('%d/%m')}**  ·  Semana {int(row['semana'])}")
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            _tarjeta(c1, "Leads",         int(row["leads"]),         obj["Leads"])
            _tarjeta(c2, "R1",            int(row["r1"]),            obj["R1"])
            _tarjeta(c3, "Follow",        int(row["fp"]),            obj["Follow"])
            _tarjeta(c4, "R2 agendada",   int(row["r2_agendada"]),   obj["R2"])
            _tarjeta(c5, "R2 efectiva",   int(row["r2_efectiva"]),   obj["R2"])
            _tarjeta(c6, "Presupuesto",   int(row["presupuesto"]),   obj["Presupuesto"])
    
    elif vista == "Semana":
        sem_act = df["semana"].max()
        if pd.notna(sem_act):
            sem_r = df[df["semana"] == sem_act]
            lunes_row = sem_dates.loc[sem_dates["semana"] == sem_act, "lunes"]
            lunes_ts  = lunes_row.values[0] if not lunes_row.empty else None
            lunes_str = pd.Timestamp(lunes_ts).strftime("%d/%m") if lunes_ts is not None else "?"
            domingo_str = (
                (pd.Timestamp(lunes_ts) + timedelta(days=6)).strftime("%d/%m")
                if lunes_ts is not None else "?"
            )
            st.subheader(f"Semana {lunes_str} - {domingo_str}")
            n_dias = int((sem_r["leads"] > 0).sum())
            st.caption(f"Semana {int(sem_act)} · desde el {lunes_str} · {n_dias} días con datos")
    
            ncols = 7 if _obj_v_sem else 6
            cols = st.columns(ncols)
            _tarjeta(cols[0], "Leads",       int(sem_r["leads"].sum()),         obj["Leads"])
            _tarjeta(cols[1], "R1",          int(sem_r["r1"].sum()),            obj["R1"])
            _tarjeta(cols[2], "Follow",      int(sem_r["fp"].sum()),            obj["Follow"])
            _tarjeta(cols[3], "R2 agendada", int(sem_r["r2_agendada"].sum()),   obj["R2"])
            _tarjeta(cols[4], "R2 efectiva", int(sem_r["r2_efectiva"].sum()),   obj["R2"])
            _tarjeta(cols[5], "Presupuesto", int(sem_r["presupuesto"].sum()),   obj["Presupuesto"])
            if _obj_v_sem and lunes_ts is not None:
                v = _ventas_en_rango(df_ventas, pd.Timestamp(lunes_ts), pd.Timestamp(lunes_ts) + pd.Timedelta(days=7))
                _tarjeta(cols[6], "Ventas", v, _obj_v_sem)
    
    elif vista == "Mes":
        st.subheader("Mes actual")
        mes_act = pd.Timestamp(date.today()).to_period("M")
        mes_r = df[df["fecha"].dt.to_period("M") == mes_act]
        if not mes_r.empty:
            st.caption(f"{pd.Timestamp(date.today()).strftime('%B %Y').capitalize()} · hasta hoy")
    
            ncols = 7 if _obj_v_mes else 6
            cols = st.columns(ncols)
            _tarjeta(cols[0], "Leads",       int(mes_r["leads"].sum()),         obj["Leads"])
            _tarjeta(cols[1], "R1",          int(mes_r["r1"].sum()),            obj["R1"])
            _tarjeta(cols[2], "Follow",      int(mes_r["fp"].sum()),            obj["Follow"])
            _tarjeta(cols[3], "R2 agendada", int(mes_r["r2_agendada"].sum()),   obj["R2"])
            _tarjeta(cols[4], "R2 efectiva", int(mes_r["r2_efectiva"].sum()),   obj["R2"])
            _tarjeta(cols[5], "Presupuesto", int(mes_r["presupuesto"].sum()),   obj["Presupuesto"])
            if _obj_v_mes:
                v = _ventas_en_mes(df_ventas, mes_act)
                _tarjeta(cols[6], "Ventas", v, _obj_v_mes)
    
    st.divider()
    
    # ── Agregar por período ──────────────────────────────────────────
    df_filt = df[
        (df["fecha"] >= pd.Timestamp(fecha_desde)) &
        (df["fecha"] <= pd.Timestamp(fecha_hasta))
    ].copy()
    
    _DIAS_ES = {"Monday": "Lu", "Tuesday": "Ma", "Wednesday": "Mi",
                "Thursday": "Ju", "Friday": "Vi", "Saturday": "Sá", "Sunday": "Do"}
    if vista == "Día":
        df_agg = df_filt.copy()
        df_agg["periodo_lbl"] = df_agg["fecha"].apply(
            lambda d: f"{_DIAS_ES.get(d.strftime('%A'), d.strftime('%A')[:2])} {d.strftime('%d/%m')}"
        )
    
    elif vista == "Semana":
        _AGG = ["leads","r1","fp","r2_agendada","r2_cancelada","r2_reagendar",
                "presupuesto","fc_clienty","r2_efectiva","alta","media_alta","media","baja"]
        df_w = df_filt.dropna(subset=["semana"]).copy()
        df_w["semana"] = df_w["semana"].astype(int)
        df_agg = df_w.groupby("semana")[[c for c in _AGG if c in df_w.columns]].sum().reset_index()
        df_agg = df_agg.merge(sem_dates, on="semana", how="left")
        df_agg["periodo_lbl"] = df_agg.apply(
            lambda r: (
                f"Sem {int(r['semana'])} · {pd.Timestamp(r['lunes']).strftime('%d/%m')}"
                if pd.notna(r.get("lunes")) else f"Sem {int(r['semana'])}"
            ), axis=1
        )
    
    elif vista == "Mes":
        _AGG = ["leads","r1","fp","r2_agendada","r2_cancelada","r2_reagendar",
                "presupuesto","fc_clienty","r2_efectiva","alta","media_alta","media","baja"]
        df_m = df_filt.copy()
        df_m["mes"] = df_m["fecha"].dt.to_period("M")
        df_agg = df_m.groupby("mes")[[c for c in _AGG if c in df_m.columns]].sum().reset_index()
        df_agg["periodo_lbl"] = df_agg["mes"].apply(
            lambda p: pd.Timestamp(str(p.start_time)).strftime("%b %Y").capitalize()
        )
    
    # ── Chances de venta desde bbdd_presupuestos + CRM ──────────────
    _df_ch = cargar_presupuestos_con_chance()
    _df_ch_filt = _df_ch[
        (_df_ch["fecha"] >= pd.Timestamp(fecha_desde)) &
        (_df_ch["fecha"] <= pd.Timestamp(fecha_hasta))
    ].copy()

    _CHANCE_CATS = ["Alta", "Media-Alta", "Media", "Baja"]
    _CHANCE_COLS = {"Alta": "ch_alta", "Media-Alta": "ch_media_alta",
                    "Media": "ch_media", "Baja": "ch_baja"}

    if not _df_ch_filt.empty:
        if vista == "Día":
            _df_ch_filt["_key"] = _df_ch_filt["fecha"].dt.strftime("%d/%m")
            df_agg["_ch_key"] = df_agg["fecha"].dt.strftime("%d/%m")
            _key_col = "_ch_key"
        elif vista == "Semana":
            _df_ch_filt["semana"] = _df_ch_filt["semana"].astype(int)
            _df_ch_filt["_key"] = _df_ch_filt["semana"]
            _key_col = "semana"
        else:
            _df_ch_filt["_key"] = _df_ch_filt["mes"]
            _key_col = "mes"

        for _cat, _col in _CHANCE_COLS.items():
            _grp = (_df_ch_filt[_df_ch_filt["chance"] == _cat]
                    .groupby("_key").size().reset_index(name=_col))
            _grp["_key"] = _grp["_key"].astype(str)
            df_agg["_key_str"] = df_agg[_key_col].astype(str)
            df_agg = df_agg.merge(_grp.rename(columns={"_key": "_key_str"}),
                                  on="_key_str", how="left")
            df_agg[_col] = df_agg[_col].fillna(0).astype(int)
        df_agg = df_agg.drop(columns=["_key_str", "_ch_key"], errors="ignore")
    else:
        for _col in _CHANCE_COLS.values():
            df_agg[_col] = 0

    # ── Tabla de semáforos ───────────────────────────────────────────
    if df_agg.empty:
        st.info("Sin datos en el rango seleccionado.")
    else:
        n_max = len(df_agg)
        labels   = {"Día": "Días a mostrar", "Semana": "Semanas a mostrar", "Mes": "Meses a mostrar"}
        defaults = {"Día": min(7, n_max), "Semana": min(6, n_max), "Mes": min(4, n_max)}
        mins     = {"Día": min(3, n_max),  "Semana": min(4, n_max),  "Mes": 1}
    
        col_tit2, col_slider, col_modo = st.columns([3, 3, 2])

        if n_max > mins[vista]:
            n_mostrar = col_slider.slider(
                labels[vista], min_value=mins[vista], max_value=n_max, value=defaults[vista],
            )
        else:
            n_mostrar = n_max

        _lbl_ult = {"Día": "Últ. día", "Semana": "Últ. semana", "Mes": "Últ. mes"}[vista]
        with col_modo:
            st.markdown(
                '<style>'
                'div[data-testid="column"]:last-child div[data-testid="stRadio"]{'
                '  display:flex;justify-content:flex-end;margin-top:-4px'
                '}'
                'div[data-testid="column"]:last-child div[data-testid="stRadio"] > div{'
                '  gap:2px'
                '}'
                'div[data-testid="column"]:last-child div[data-testid="stRadio"] label p{'
                '  font-size:0.72rem!important'
                '}'
                '</style>',
                unsafe_allow_html=True,
            )
            _modo_resumen = st.radio(
                "Resumen", ["Prom.", _lbl_ult],
                horizontal=False, label_visibility="collapsed", key="modo_resumen"
            )
        _modo_resumen = "Promedio" if _modo_resumen == "Prom." else _lbl_ult
    
        df_show = df_agg.tail(n_mostrar).copy()

        # Agregar ventas por período para Tasa cierre
        if not df_ventas.empty:
            _dv = df_ventas.copy()
            if vista == "Día":
                _dv["_vkey"] = _dv["fecha_lead"].dt.normalize().astype(str)
                df_show["_vkey"] = pd.to_datetime(df_show["fecha"]).dt.normalize().astype(str)
            elif vista == "Semana":
                _dv["_vkey"] = _dv["fecha_lead"].dt.isocalendar().week.astype(int).astype(str)
                df_show["_vkey"] = df_show["semana"].astype(int).astype(str)
            else:
                _dv["_vkey"] = _dv["fecha_lead"].dt.to_period("M").astype(str)
                df_show["_vkey"] = df_show["mes"].astype(str)
            _vgrp = _dv.groupby("_vkey")["ventas"].sum().reset_index(name="_ventas_p")
            df_show = df_show.merge(_vgrp, on="_vkey", how="left")
            df_show["_ventas_p"] = df_show["_ventas_p"].fillna(0).astype(int)
            df_show = df_show.drop(columns=["_vkey"], errors="ignore")
        else:
            df_show["_ventas_p"] = 0

        period_lbls = list(df_show["periodo_lbl"])
        # ── Helpers HTML ─────────────────────────────────────────────
        _S   = "border:1px solid #e2e8f0"
        # Anchos fijos para que todas las tablas de la página queden alineadas
        _WM  = "width:120px;min-width:120px;max-width:120px"   # Métrica
        _WP  = "width:105px;min-width:105px;max-width:105px"   # Período
        _WS  = "width:88px;min-width:88px;max-width:88px"      # Resumen (Promedio/Obj/%)
        _BASE_TH = f"font-size:0.78rem;font-weight:600;padding:6px 8px;{_S};overflow:hidden"
        _BASE_TD = f"font-size:0.83rem;padding:5px 8px;{_S};overflow:hidden"
    
        # CSS compartido para tooltips (ch-cell / ch-tip) usado en semáforo y chances
        st.markdown(
            '<style>'
            '.ch-cell{cursor:default;position:relative}'
            '.ch-tip{display:none;position:absolute;z-index:9999;top:50%;right:calc(100% + 8px);'
            'transform:translateY(-50%);background:#1e293b;color:#fff;'
            'border-radius:8px;padding:10px 14px;min-width:200px;max-width:280px;'
            'box-shadow:0 4px 16px rgba(0,0,0,0.25);white-space:normal;text-align:left}'
            '.ch-tip-right .ch-tip{right:auto;left:calc(100% + 8px)}'
            '.ch-cell:hover .ch-tip{display:block}'
            '</style>',
            unsafe_allow_html=True,
        )

        # Esquemas de color: header (bg, color texto), filas body (par/impar), resumen (par/impar)
        _TEMAS = {
            "azul":  {"hdr_bg": "#1a3a5c", "hdr_fg": "#fff",
                      "bg0": "#d6eaf8", "bg1": "#eef6fc", "bgs0": "#a9cce3", "bgs1": "#bcd9ec",
                      "label_fg": "#1e293b"},
            "verde": {"hdr_bg": "#1a5c3a", "hdr_fg": "#fff",
                      "bg0": "#d7f0e3", "bg1": "#eef9f3", "bgs0": "#a3d9bd", "bgs1": "#bdeace",
                      "label_fg": "#1e293b"},
            "plano": {"hdr_bg": "#f8fafc", "hdr_fg": "#64748b",
                      "bg0": "#fff", "bg1": "#f8fafc", "bgs0": "#eef2f7", "bgs1": "#e8edf4",
                      "label_fg": "#334155"},
        }
    
        def _estilos_tema(tema, compacto=False):
            t = _TEMAS[tema]
            base_td = (
                f"font-size:0.70rem;padding:3px 8px;{_S};overflow:hidden" if compacto else _BASE_TD
            )
            thl = f"text-align:left;color:{t['hdr_fg']};background:{t['hdr_bg']};{_WM};{_BASE_TH}"
            th  = f"text-align:center;color:{t['hdr_fg']};background:{t['hdr_bg']};{_WP};{_BASE_TH}"
            ths = f"text-align:center;color:{t['hdr_fg']};background:{t['hdr_bg']};{_WS};{_BASE_TH}"
            tdl = f"text-align:left;font-weight:600;color:{t['label_fg']};{_WM};{base_td}"
            td  = f"text-align:center;{_WP};{base_td}"
            tds = f"text-align:center;font-weight:500;{_WS};{base_td}"
            return t, thl, th, ths, tdl, td, tds
    
        def _render_par(t1, t2, tema="azul", col_links=None):
            """Une t1 (períodos) y t2 (resumen) en una sola tabla HTML con anchos fijos."""
            t, thl, th, ths, tdl, td, tds = _estilos_tema(tema)
            period_cols  = list(t1.columns)
            summary_cols = list(t2.columns)
            _badge = (
                'font-size:0.60rem;font-weight:600;padding:1px 5px;border-radius:3px;'
                'text-decoration:none;margin-left:4px;color:#fff'
            )
    
            def _col_hdr(c):
                if not col_links:
                    return c
                reps = col_links.get(c, {})
                badges = ""
                if "r1" in reps:
                    badges += f'<a href="{reps["r1"]}" target="_blank" style="{_badge};background:#1a3a5c">R1</a>'
                if "r2" in reps:
                    badges += f'<a href="{reps["r2"]}" target="_blank" style="{_badge};background:#1a5c3a">R2</a>'
                return f'{c}{badges}'
    
            # Cabecera
            hdr  = f'<th style="{thl}">Métrica</th>'
            hdr += "".join(f'<th style="{th}">{_col_hdr(c)}</th>' for c in period_cols)
            hdr += "".join(f'<th style="{ths}">{c}</th>' for c in summary_cols)
    
            # Filas
            body = ""
            for i, (metric, row1) in enumerate(t1.iterrows()):
                bg  = t["bg0"] if i % 2 == 0 else t["bg1"]
                bgs = t["bgs0"] if i % 2 == 0 else t["bgs1"]
                row2   = t2.iloc[i]
                cells  = f'<td style="{tdl};background:{bg}">{metric}</td>'
                cells += "".join(f'<td style="{td};background:{bg}">{v}</td>'  for v in row1)
                cells += "".join(f'<td style="{tds};background:{bgs}">{v}</td>' for v in row2)
                body  += f"<tr>{cells}</tr>"
    
            st.markdown(
                '<table style="table-layout:fixed;width:100%;border-collapse:collapse;margin-bottom:6px">'
                f'<thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table>',
                unsafe_allow_html=True,
            )
    
        _lbl_resumen = "Promedio" if _modo_resumen == "Promedio" else _lbl_ult
        _es_ult = (_modo_resumen != "Promedio")

        def _tabla_metricas(metricas):
            filas1, filas2 = [], []
            for label, col_key, objetivo in metricas:
                row1 = {"Métrica": label}
                row2 = {}
                vals = []
                for _, r in df_show.iterrows():
                    val = int(r[col_key]) if col_key in r.index and pd.notna(r[col_key]) else 0
                    vals.append(val)
                    row1[r["periodo_lbl"]] = "" if val == 0 else f"{_icon(val, objetivo)} {val}"
                resumen = vals[-1] if _es_ult and vals else (round(sum(vals) / len(vals)) if vals else 0)
                pct     = round(resumen / objetivo * 100) if objetivo > 0 else 0
                row2[_lbl_resumen] = "" if resumen == 0 else f"{_icon(resumen, objetivo)} {resumen}"
                row2["Objetivo"]   = str(objetivo)
                row2["% Cumpl."]   = f"{pct}%" if pct else ""
                filas1.append(row1)
                filas2.append(row2)
            return pd.DataFrame(filas1).set_index("Métrica"), pd.DataFrame(filas2)
    
        def _tabla_ratios(ratios):
            filas1, filas2 = [], []
            for label, num_col, den_col, obj_num, obj_den in ratios:
                row1 = {"Métrica": label}
                row2 = {}
                ratio_vals = []
                for _, r in df_show.iterrows():
                    num = r[num_col] if num_col in r.index and pd.notna(r[num_col]) else 0
                    den = r[den_col] if den_col in r.index and pd.notna(r[den_col]) else 0
                    ratio = round(num / den * 100) if den > 0 else 0
                    ratio_vals.append(ratio)
                    row1[r["periodo_lbl"]] = "" if ratio == 0 else f"{ratio}%"
                res_ratio  = ratio_vals[-1] if _es_ult and ratio_vals else (round(sum(ratio_vals) / len(ratio_vals)) if ratio_vals else 0)
                obj_ratio  = round(obj_num / obj_den * 100) if obj_den > 0 else 0
                pct_ratio  = round(res_ratio / obj_ratio * 100) if obj_ratio > 0 else 0
                row2[_lbl_resumen] = "" if res_ratio == 0 else f"{res_ratio}%"
                row2["Objetivo"]   = f"{obj_ratio}%" if obj_ratio else ""
                row2["% Cumpl."]   = f"{pct_ratio}%" if obj_ratio else ""
                filas1.append(row1)
                filas2.append(row2)
            return pd.DataFrame(filas1).set_index("Métrica"), pd.DataFrame(filas2)
    
        def _tabla_counts(items):
            """items: [(label, col_key), ...] — conteos sin semáforo ni objetivo."""
            filas1, filas2 = [], []
            for label, col_key in items:
                row1 = {"Métrica": label}
                row2 = {}
                vals = []
                for _, r in df_show.iterrows():
                    val = int(r[col_key]) if col_key in r.index and pd.notna(r[col_key]) else 0
                    vals.append(val)
                    row1[r["periodo_lbl"]] = "" if val == 0 else str(val)
                resumen = vals[-1] if _es_ult and vals else (round(sum(vals) / len(vals)) if vals else 0)
                row2[_lbl_resumen] = "" if resumen == 0 else str(resumen)
                row2["Objetivo"]   = ""
                row2["% Cumpl."]   = ""
                filas1.append(row1)
                filas2.append(row2)
            return pd.DataFrame(filas1).set_index("Métrica"), pd.DataFrame(filas2)
    
        _URL_DIARIA = f"https://docs.google.com/spreadsheets/d/{ID_SHEET}"
        _URL_FORECAST_SH = f"https://docs.google.com/spreadsheets/d/{ID_FORECAST}"
    
        def _titulo_fuente(titulo, tab_nombre, url):
            st.markdown(
                f'<h3 style="margin-bottom:2px;line-height:1.2">{titulo}</h3>'
                f'<div style="margin-bottom:6px">'
                f'<a href="{url}" target="_blank" '
                f'style="font-size:0.68rem;color:#94a3b8;font-weight:normal;text-decoration:none">'
                f'· {tab_nombre} →</a></div>',
                unsafe_allow_html=True,
            )
    
        def _render_combo(grupos, tema="azul", header=True, compacto=False, margin_top=0, margin_bottom=6, col_links=None):
            """Une varios pares (t1, t2) en una sola tabla, con una fila espaciadora entre grupos."""
            t, thl, th, ths, tdl, td, tds = _estilos_tema(tema, compacto=compacto)
            period_cols  = list(grupos[0][0].columns)
            summary_cols = list(grupos[0][1].columns)
    
            _badge = (
                'font-size:0.60rem;font-weight:600;padding:1px 5px;border-radius:3px;'
                'text-decoration:none;margin-left:4px;color:#fff'
            )
            def _col_hdr(c):
                if not col_links:
                    return c
                reps = col_links.get(c, {})
                badges = ""
                if "r1" in reps:
                    badges += f'<a href="{reps["r1"]}" target="_blank" style="{_badge};background:#2563eb">R1</a>'
                if "r2" in reps:
                    badges += f'<a href="{reps["r2"]}" target="_blank" style="{_badge};background:#16a34a">R2</a>'
                if badges:
                    return f'<div style="line-height:1.3">{c}<br>{badges}</div>'
                return c
    
            thead_html = ""
            if header:
                hdr  = f'<th style="{thl}">Métrica</th>'
                hdr += "".join(f'<th style="{th}">{_col_hdr(c)}</th>' for c in period_cols)
                hdr += "".join(f'<th style="{ths}">{c}</th>'          for c in summary_cols)
                thead_html = f"<thead><tr>{hdr}</tr></thead>"
    
            body = ""
            for gi, (t1, t2) in enumerate(grupos):
                if gi > 0:
                    ncols = 1 + len(period_cols) + len(summary_cols)
                    body += f'<tr><td colspan="{ncols}" style="height:10px;border:none;background:#fff"></td></tr>'
                for i, (metric, row1) in enumerate(t1.iterrows()):
                    bg  = t["bg0"] if i % 2 == 0 else t["bg1"]
                    bgs = t["bgs0"] if i % 2 == 0 else t["bgs1"]
                    row2  = t2.iloc[i]
                    cells = f'<td style="{tdl};background:{bg}">{metric}</td>'
                    cells += "".join(f'<td style="{td};background:{bg}">{v}</td>'  for v in row1)
                    cells += "".join(f'<td style="{tds};background:{bgs}">{v}</td>' for v in row2)
                    body  += f"<tr>{cells}</tr>"
    
            st.markdown(
                f'<table style="table-layout:fixed;width:100%;border-collapse:collapse;'
                f'margin-top:{margin_top}px;margin-bottom:{margin_bottom}px">'
                f'{thead_html}<tbody>{body}</tbody></table>',
                unsafe_allow_html=True,
            )
    
        metricas_r1 = [
            ("Leads",  "leads", obj["Leads"]),
            ("R1",     "r1",    obj["R1"]),
            ("Follow", "fp",    obj["Follow"]),
        ]
        ratios_r1 = [
            ("%R1/Lead", "r1", "leads", obj["R1"],     obj["Leads"]),
            ("%FP/Lead", "fp", "leads", obj["Follow"], obj["Leads"]),
        ]
    
        metricas_r2 = [
            ("R2 agendada", "r2_agendada", obj["R2"]),
            ("R2 efectiva", "r2_efectiva", obj["R2"]),
            ("Presupuesto (Co)", "presupuesto", obj["Presupuesto"]),
            ("Venta (Co)",       "_ventas_p",   0),
        ]
        # (label, num_col, den_col, obj_num, obj_den) — sin objetivo definido
        ratios_r2 = [
            ("% Canc. /R2A", "r2_cancelada", "r2_agendada", 0, 0),
            ("% Reag. /R2A", "r2_reagendar", "r2_agendada", 0, 0),
            ("% PE /R2A",    "presupuesto",  "r2_agendada", 0, 0),
        ]
        chances_r2 = [
            ("Alta",       "ch_alta"),
            ("Media-Alta", "ch_media_alta"),
            ("Media",      "ch_media"),
            ("Baja",       "ch_baja"),
        ]
    
        _links_rep = cargar_links_reportes() if vista == "Día" else {}
    
        with col_tit2:
            _titulo_fuente(f"Detalle por {vista.lower()}", "Trazabilidad", _URL_DIARIA)
        _render_combo([_tabla_metricas(metricas_r1), _tabla_metricas(metricas_r2)], tema="azul", margin_bottom=10, col_links=_links_rep)
    
        _render_combo(
            [_tabla_ratios(ratios_r1), _tabla_ratios(ratios_r2)],
            tema="verde", header=False, compacto=True, margin_top=0,
        )

        if vista != "Día":
            ratios_conv = [("% PE/Leads", "presupuesto", "leads", 0, 0)]
            if vista == "Mes":
                ratios_conv.append(("Tasa cierre (Co)", "_ventas_p", "presupuesto", 0, 0))
            _render_combo(
                [_tabla_ratios(ratios_conv)],
                tema="verde", header=False, compacto=True, margin_top=0,
            )

        st.markdown('<div style="margin-bottom:2px;font-weight:600">Chances de venta</div>', unsafe_allow_html=True)

        # ── Tooltips con Nombre / Mail / Closer ──────────────────────
        _ch_rows = _df_ch_filt.copy() if not _df_ch_filt.empty else pd.DataFrame()

        def _ch_tooltip_html(prospectos: list) -> str:
            if not prospectos:
                return ""
            items = "".join(
                f'<div style="padding:5px 0;border-top:1px solid rgba(255,255,255,0.15)'
                f'{";margin-top:0" if i==0 else ""}">'
                f'<div style="font-weight:600;font-size:0.78rem">{p["nombre"]}</div>'
                f'<div style="font-size:0.72rem;opacity:0.85">{p["mail"]}</div>'
                f'<div style="font-size:0.72rem;opacity:0.75;font-style:italic">{p["closer"]}</div>'
                f'<div style="font-size:0.72rem;opacity:0.7;color:#94d4b8">{p["estado"]}</div>'
                f'</div>'
                for i, p in enumerate(prospectos)
            )
            return (
                f'<div class="ch-tip">{items}</div>'
            )

        def _get_prospectos(cat, key_col, key_val):
            if _ch_rows.empty:
                return []
            mask = _ch_rows["chance"] == cat
            if key_col == "periodo_lbl":
                _kv = key_val[-5:] if len(key_val) > 5 else key_val  # extrae "dd/mm" de "Mi dd/mm"
                mask &= _ch_rows["fecha"].dt.strftime("%d/%m") == _kv
            elif key_col == "semana":
                mask &= _ch_rows["semana"].astype(str) == str(key_val)
            else:
                mask &= _ch_rows["mes"].astype(str) == str(key_val)
            sub = _ch_rows[mask]
            return [{"nombre": r["Nombre"], "mail": r["Emails"], "closer": r["closer"], "estado": r.get("Estado", "–")}
                    for _, r in sub.iterrows()]

        _key_col_ch = "periodo_lbl" if vista == "Día" else ("semana" if vista == "Semana" else "mes")
        _period_keys = list(df_show[_key_col_ch])

        _S_ch = "border:1px solid #e2e8f0"
        _BASE_TH_ch = f"font-size:0.78rem;font-weight:600;padding:6px 8px;{_S_ch}"
        _BASE_TD_ch = f"font-size:0.83rem;padding:5px 8px;{_S_ch}"

        _WO  = "width:78px;min-width:78px;max-width:78px"   # Objetivo
        _WC  = "width:78px;min-width:78px;max-width:78px"   # % Cumpl.
        _hdr_ch = f'<th style="text-align:left;background:#f8fafc;color:#64748b;{_WM};{_BASE_TH_ch}">Chance</th>'
        for _lbl in list(df_show["periodo_lbl"]):
            _hdr_ch += f'<th style="text-align:center;background:#f8fafc;color:#64748b;{_WP};{_BASE_TH_ch}">{_lbl}</th>'
        _hdr_ch += (
            f'<th style="text-align:center;background:#f8fafc;color:#64748b;{_WS};{_BASE_TH_ch}">Total</th>'
            f'<th style="text-align:center;background:#f8fafc;color:#64748b;{_WO};{_BASE_TH_ch}">Objetivo</th>'
            f'<th style="text-align:center;background:#f8fafc;color:#64748b;{_WC};{_BASE_TH_ch}">% Cumpl.</th>'
        )

        _body_ch = ""
        for _ri, (_cat, _col) in enumerate(zip(_CHANCE_CATS, _CHANCE_COLS.values())):
            _bg  = "#fff"      if _ri % 2 == 0 else "#f8fafc"
            _bgs = "#eef2f7"   if _ri % 2 == 0 else "#e8edf4"
            _vals_ch = []
            _cells_ch = f'<td style="text-align:left;font-weight:600;color:#1e293b;{_WM};{_BASE_TD_ch};background:{_bg}">{_cat}</td>'
            for _ri2, (_row_agg, _key_val) in enumerate(zip(df_show.itertuples(), _period_keys)):
                _n = int(getattr(_row_agg, _col, 0))
                _vals_ch.append(_n)
                _prosp = _get_prospectos(_cat, _key_col_ch, _key_val)
                _tip   = _ch_tooltip_html(_prosp) if _n else ""
                _cell_style = f"text-align:center;{_WP};{_BASE_TD_ch};background:{_bg};position:relative"
                _n_cols = len(list(df_show["periodo_lbl"]))
                _tip_cls = "ch-cell ch-tip-right" if _ri2 < _n_cols // 2 else "ch-cell"
                if _tip:
                    _cells_ch += (
                        f'<td style="{_cell_style}" class="{_tip_cls}">'
                        f'{_n}{_tip}</td>'
                    )
                else:
                    _cells_ch += f'<td style="{_cell_style}">{_n if _n else ""}</td>'
            _total_ch = sum(_vals_ch)
            _cells_ch += (
                f'<td style="text-align:center;font-weight:500;{_WS};{_BASE_TD_ch};background:{_bgs}">{_total_ch if _total_ch else ""}</td>'
                f'<td style="text-align:center;{_WO};{_BASE_TD_ch};background:{_bg}"></td>'
                f'<td style="text-align:center;{_WC};{_BASE_TD_ch};background:{_bg}"></td>'
            )
            _body_ch += f"<tr>{_cells_ch}</tr>"

        # ── Fila "Proy. ventas" (solo Día o Semana) ──────────────────
        if vista in ("Día", "Semana"):
            _pesos = {"ch_alta": 0.38, "ch_media_alta": 0.20, "ch_media": 0.13, "ch_baja": 0.06}
            _proy_vals = []
            _proy_cells = (
                f'<td style="text-align:left;font-weight:600;color:#1e293b;{_WM};{_BASE_TD_ch};'
                f'background:#f0f4ff;border-top:2px solid #cbd5e1">Proy. ventas</td>'
            )
            for _row_agg in df_show.itertuples():
                _proy = sum(int(getattr(_row_agg, col, 0)) * peso for col, peso in _pesos.items())
                _proy_r = round(_proy, 1)
                _proy_vals.append(_proy_r)
                _proy_cells += (
                    f'<td style="text-align:center;{_WP};{_BASE_TD_ch};'
                    f'background:#f0f4ff;border-top:2px solid #cbd5e1">'
                    f'{_proy_r if _proy_r else ""}</td>'
                )
            _total_proy = round(sum(_proy_vals), 1)
            _proy_cells += (
                f'<td style="text-align:center;font-weight:500;{_WS};{_BASE_TD_ch};'
                f'background:#e8ecf8;border-top:2px solid #cbd5e1">{_total_proy if _total_proy else ""}</td>'
                f'<td style="text-align:center;{_WO};{_BASE_TD_ch};background:#f0f4ff;border-top:2px solid #cbd5e1"></td>'
                f'<td style="text-align:center;{_WC};{_BASE_TD_ch};background:#f0f4ff;border-top:2px solid #cbd5e1"></td>'
            )
            _body_ch += f"<tr>{_proy_cells}</tr>"

        st.markdown(
            '<table style="table-layout:fixed;width:100%;border-collapse:collapse;margin-bottom:4px">'
            f'<thead><tr>{_hdr_ch}</tr></thead><tbody>{_body_ch}</tbody></table>'
            '<div style="font-size:0.68rem;color:#94a3b8;margin-top:2px">'
            'Proy. ventas = Alta×0.38 + Media-Alta×0.20 + Media×0.13 + Baja×0.06</div>',
            unsafe_allow_html=True,
        )
    
    st.divider()
    
    # ── Forecast ─────────────────────────────────────────────────────
    st.markdown(
        f'<h3 style="margin-bottom:4px">🔮 Forecast '
        f'<a href="https://docs.google.com/spreadsheets/d/{ID_FORECAST}" target="_blank" '
        f'style="font-size:0.68rem;color:#94a3b8;font-weight:normal">'
        f'· Forecast Seba + Forecast Ro →</a></h3>',
        unsafe_allow_html=True,
    )
    
    @st.cache_data(ttl=3600)
    def cargar_comentarios_forecast() -> pd.DataFrame:
        """Lee la pestaña 'Comentarios forecast' (Fecha, Closer, Comentarios)."""
        try:
            df = _fetch_external_csv(ID_FORECAST, "Comentarios forecast")
        except Exception:
            return pd.DataFrame(columns=["Fecha", "Closer", "Comentarios"])
        if df.empty:
            return df
        df.columns = [str(c).strip() for c in df.columns]
    
        hoy = date.today()
    
        def _parse_fecha(s):
            s = str(s).strip()
            try:
                d, m = s.split("/")[:2]
                d, m = int(d), int(m)
                f = date(hoy.year, m, d)
                if f > hoy + timedelta(days=2):
                    f = date(hoy.year - 1, m, d)
                return f
            except Exception:
                return None
    
        df["_fecha_dt"] = df["Fecha"].apply(_parse_fecha)
        return df.dropna(subset=["_fecha_dt"])
    
    
    def _ultimos_comentarios(df: pd.DataFrame, closer: str, n: int = 3):
        """Devuelve lista de (fecha, comentario) de las últimas n entradas para ese closer."""
        if df.empty or "Closer" not in df.columns:
            return []
        sub = df[df["Closer"].astype(str).str.strip().str.lower() == closer.lower()]
        if sub.empty:
            return []
        sub = sub.sort_values("_fecha_dt").tail(n)
        return [(row["_fecha_dt"], row.get("Comentarios", "")) for _, row in sub.iterrows()]
    
    
    try:
        df_comentarios_fc = cargar_comentarios_forecast()
        _com_cols = st.columns(2)
        for _col, _closer, _label in zip(_com_cols, ["Sebastian", "Rocio"], ["Sebastian", "Ro"]):
            _entradas = _ultimos_comentarios(df_comentarios_fc, _closer, n=3)
            with _col:
                if not _entradas:
                    st.info(f"Sin comentarios de {_label}.")
                else:
                    bloques = ""
                    for i, (_fecha_c, _texto_c) in enumerate(reversed(_entradas)):
                        sep = "border-top:1px solid #a9cce3;" if i > 0 else ""
                        bloques += (
                            f'<div style="{sep}padding:10px 14px">'
                            f'<div style="font-size:0.72rem;color:#5a7a9a;margin-bottom:4px">'
                            f'{_fecha_c.strftime("%d/%m/%Y")}</div>'
                            f'<div style="font-size:0.82rem;white-space:pre-wrap;color:#1e293b">'
                            f'{_texto_c}</div></div>'
                        )
                    st.markdown(
                        f'<div style="border:1px solid #c8ccd0;border-radius:6px;overflow:hidden">'
                        f'<div style="background:#1a3a5c;color:#fff;font-weight:bold;'
                        f'padding:9px 14px;font-size:0.85rem">{_label}</div>'
                        f'<div style="background:#d6eaf8;max-height:320px;overflow-y:auto">'
                        f'{bloques}</div></div>',
                        unsafe_allow_html=True,
                    )
    except Exception as _e_com:
        st.warning(f"No se pudieron cargar los comentarios del forecast: {_e_com}")
    
    st.markdown("")
    
    
    def _cargar_forecast():
        import datos_crm as _crm
        df_c = _crm.cargar_crm()
        cols = ["id", "fecha_ingreso", "Estado", "Empresa", "Usuario"]
        cols_presentes = [c for c in cols if c in df_c.columns]
        df_f = df_c[cols_presentes].copy()
        df_f = df_f.rename(columns={
            "id":            "ID",
            "fecha_ingreso": "Fecha ingreso",
            "Estado":        "Estado CRM",
            "Empresa":       "Empresa",
            "Usuario":       "Usuario",
        })
        if "Fecha ingreso" in df_f.columns:
            df_f["Fecha ingreso"] = pd.to_datetime(df_f["Fecha ingreso"], errors="coerce").dt.strftime("%d/%m/%Y")
        df_f = df_f[df_f["Estado CRM"] == "Últimos detalles"].reset_index(drop=True)
    
        # Enriquecer con Prob. cierre y Observación del sheet de Forecast
        try:
            df_fc_extra = cargar_forecast_sheet()
            if not df_fc_extra.empty:
                df_f["_id"] = df_f["ID"].astype(str).str.strip()
                df_f = df_f.merge(df_fc_extra, on="_id", how="left")
                df_f.drop(columns=["_id"], inplace=True)
        except Exception:
            pass
    
        return df_f
    
    try:
        df_fc = _cargar_forecast()
    
        # Filtros compartidos por ambas tablas
        df_alta_raw = cargar_alta_forecast()
    
        _filt_c1, _filt_c2 = st.columns(2)
    
        usuarios = ["Todos"] + sorted(df_fc["Usuario"].dropna().unique().tolist()) if "Usuario" in df_fc.columns else ["Todos"]
        filtro_usuario = _filt_c1.selectbox("Vendedor", usuarios)
    
        # Prob. cierre: valores únicos de ambas tablas
        _probs_tz = set()
        for _dfp in [df_fc, df_alta_raw]:
            if "Prob. cierre" in _dfp.columns:
                _probs_tz |= set(
                    _dfp["Prob. cierre"].dropna().astype(str).str.strip()
                    .replace("", pd.NA).dropna().unique()
                )
        _probs_opciones_tz = ["Todos"] + sorted(_probs_tz - {"nan", "None", ""})
        filtro_prob_tz = _filt_c2.selectbox("Prob. cierre", _probs_opciones_tz, key="tz_prob")
    
        # ── Tabla 1: Últimos detalles ─────────────────────────────
        df_vista = df_fc.copy()
        if filtro_usuario != "Todos" and "Usuario" in df_vista.columns:
            df_vista = df_vista[df_vista["Usuario"] == filtro_usuario]
        if filtro_prob_tz != "Todos" and "Prob. cierre" in df_vista.columns:
            df_vista = df_vista[df_vista["Prob. cierre"].astype(str).str.strip() == filtro_prob_tz]
    
        st.markdown(f"**{len(df_vista):,} registros · Estado CRM: Últimos detalles**")
        st.dataframe(df_vista, use_container_width=True, hide_index=True)
    
        # ── Tabla 2: Alta (del sheet Forecast) ────────────────────
        st.markdown("---")
    
        if df_alta_raw.empty:
            st.info("Sin oportunidades de tipo Alta registradas en el Forecast.")
        else:
            # Enriquecer con datos del CRM (mismas columnas que tabla 1)
            import datos_crm as _crm
            df_crm_raw = _crm.cargar_crm()
            cols_crm = [c for c in ["id", "fecha_ingreso", "Estado", "Empresa", "Usuario"] if c in df_crm_raw.columns]
            df_crm_sub = df_crm_raw[cols_crm].copy().rename(columns={
                "id":            "ID",
                "fecha_ingreso": "Fecha ingreso",
                "Estado":        "Estado CRM",
                "Empresa":       "Empresa",
                "Usuario":       "Usuario",
            })
            if "Fecha ingreso" in df_crm_sub.columns:
                df_crm_sub["Fecha ingreso"] = pd.to_datetime(
                    df_crm_sub["Fecha ingreso"], errors="coerce"
                ).dt.strftime("%d/%m/%Y")
            df_crm_sub["_id"] = df_crm_sub["ID"].astype(str).str.strip()
    
            df_alta = df_alta_raw.merge(df_crm_sub.drop(columns=["ID"]), on="_id", how="left")
            df_alta.rename(columns={"_id": "ID"}, inplace=True)
    
            col_order = ["ID", "Fecha ingreso", "Estado CRM", "Empresa", "Usuario", "Prob. cierre", "Observación"]
            df_alta = df_alta[[c for c in col_order if c in df_alta.columns]].reset_index(drop=True)
    
            if filtro_usuario != "Todos" and "Usuario" in df_alta.columns:
                df_alta = df_alta[df_alta["Usuario"] == filtro_usuario]
            if filtro_prob_tz != "Todos" and "Prob. cierre" in df_alta.columns:
                df_alta = df_alta[df_alta["Prob. cierre"].astype(str).str.strip() == filtro_prob_tz]
    
            # Excluir ventas ya ganadas y las que ya están en "Últimos detalles" (tabla 1)
            _estado_col = df_alta.get("Estado CRM", pd.Series(dtype=str)).astype(str).str.strip()
            _prob_col   = df_alta.get("Prob. cierre", pd.Series(dtype=str)).astype(str).str.strip().str.lower()
            _ganadas    = (_estado_col == "Venta ganada") | (_prob_col.isin(["venta ganada", "ganada"]))
            _ult_det    = _estado_col == "Últimos detalles"
            _contac_fut = _estado_col == "Contactar a Futuro"
            _baja       = _prob_col == "baja"
            df_alta     = df_alta[~(_ganadas | _ult_det | _contac_fut | _baja)].reset_index(drop=True)
    
            st.markdown(f"**{len(df_alta):,} oportunidades · Tipo: Alta · Forecast Seba + Ro**")
            st.dataframe(df_alta, use_container_width=True, hide_index=True)
    
    except Exception as e:
        st.error(f"Error cargando datos del CRM: {e}")

with tab_cc:
    _ID_SOL = "1Oto16BeUmohfjWlzGeH-Nj0d3RMmZLG17ZSPd93ePA8"
    _ID_FER = "1EDbB-LMLeXFaCJeAifbV9zLNh9R4piO0GYuAeMBupo8"

    @st.cache_data(ttl=3600)
    def _cargar_bbdd_r1(sheet_id, hoja="BBDD_R1"):
        df = _fetch_external_csv(sheet_id, hoja)
        # Normalizar headers para buscar por nombre
        _hdr = [str(c).strip().lower() for c in df.columns]
        def _find_col(candidates):
            for cand in candidates:
                for i, h in enumerate(_hdr):
                    if cand in h:
                        return df.columns[i]
            return None
        _col_id    = _find_col(["id"]) or df.columns[0]
        _col_mail  = _find_col(["mail", "email", "correo"]) or df.columns[1]
        _col_fecha = _find_col(["fecha r1", "fecha_r1", "fecha"]) or df.columns[2]
        _col_nom   = _find_col(["nombre", "name"]) or df.columns[3]
        _col_est   = _find_col(["estado r1", "estado_r1", "estado"]) or df.columns[4]
        _col_exp   = _find_col(["explic", "explicacion", "explicación"])
        _col_fat   = _find_col(["fathom", "grabacion", "grabación"])
        _col_emp   = _find_col(["empresa", "web", "pagina"])
        _col_obj   = _find_col(["objecion", "objeciones", "pregunta"])
        # Fallback por índice si no se encuentra por nombre
        if _col_exp is None and len(df.columns) > 6: _col_exp = df.columns[6]
        if _col_fat is None and len(df.columns) > 7: _col_fat = df.columns[7]
        if _col_emp is None and len(df.columns) > 8: _col_emp = df.columns[8]
        if _col_obj is None and len(df.columns) > 9: _col_obj = df.columns[9]
        out = pd.DataFrame()
        out["ID"]        = df[_col_id].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        out["Mail"]      = df[_col_mail].astype(str)
        out["Fecha R1"]  = df[_col_fecha].astype(str)
        out["Nombre"]    = df[_col_nom].astype(str)
        out["Estado R1"] = df[_col_est].astype(str)
        out["Explicacion"] = df[_col_exp].astype(str) if _col_exp is not None else ""
        out["Fathom"]      = df[_col_fat].astype(str) if _col_fat is not None else ""
        out["Empresa"]     = df[_col_emp].astype(str) if _col_emp is not None else ""
        out["Objeciones"]  = df[_col_obj].astype(str) if _col_obj is not None else ""
        out = out[out["ID"].notna() & (out["ID"] != "") & (out["ID"] != "nan")]
        hoy = pd.Timestamp.today()
        def _parse_r1(s):
            s = str(s).strip()
            if not s or s == "nan": return pd.NaT
            if len(s) <= 5:
                for yr in [hoy.year, hoy.year - 1]:
                    try:
                        t = pd.to_datetime(f"{s}/{yr}", dayfirst=True)
                        if t <= hoy + pd.Timedelta(days=1): return t
                    except Exception: pass
                return pd.NaT
            return pd.to_datetime(s, dayfirst=True, errors="coerce")
        out["_fecha"] = out["Fecha R1"].apply(_parse_r1)
        return out[["ID", "Mail", "Fecha R1", "_fecha", "Nombre", "Estado R1", "Explicacion", "Fathom", "Empresa", "Objeciones"]].copy()

    @st.cache_data(ttl=3600)
    def _cargar_consultas_crm():
        _ID_CRM_CONSULTAS = "1BHzXgiDqYcnz7_kVASPCc65KXz4v6oqSeVCJlN48_J8"
        df = _fetch_external_csv(_ID_CRM_CONSULTAS, "Sheet1")
        # Col A = ID prospecto, Col M (índice 12) = Consultas
        if df.shape[1] < 13:
            return {}
        df = df.iloc[:, [0, 12]].copy()
        df.columns = ["ID", "Consultas"]
        df["ID"] = df["ID"].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df = df[df["ID"].notna() & (df["ID"] != "") & (df["ID"] != "nan")]
        return df.set_index("ID")["Consultas"].to_dict()

    def _cargar_bbdd_sol():
        return _cargar_bbdd_r1(_ID_SOL)

    @st.cache_data(ttl=3600)
    def _cargar_bbdd_fer():
        return _cargar_bbdd_r1(_ID_FER)

    def _render_perfo_cc(df_bbdd, nombre_cc):
        import json as _json
        _consultas_map = _cargar_consultas_crm()
        df_bbdd = df_bbdd.dropna(subset=["_fecha"]).copy()
        df_bbdd = df_bbdd[
            (df_bbdd["_fecha"] >= pd.Timestamp(fecha_desde)) &
            (df_bbdd["_fecha"] <= pd.Timestamp(fecha_hasta))
        ]

        if df_bbdd.empty:
            st.info("Sin datos en el rango seleccionado.")
            return

        _DIAS_ES_CC = {"Monday": "Lu", "Tuesday": "Ma", "Wednesday": "Mi",
                       "Thursday": "Ju", "Friday": "Vi", "Saturday": "Sá", "Sunday": "Do"}

        if vista == "Día":
            df_bbdd["_periodo"] = df_bbdd["_fecha"].dt.date
            df_bbdd["_lbl"] = df_bbdd["_fecha"].apply(
                lambda d: f"{_DIAS_ES_CC.get(d.strftime('%A'), d.strftime('%A')[:2])} {d.strftime('%d/%m')}"
            )
            grp_col = "_periodo"
        elif vista == "Semana":
            df_bbdd["_semana"] = df_bbdd["_fecha"].dt.isocalendar().week.astype(int)
            df_bbdd["_lunes"]  = df_bbdd["_fecha"] - pd.to_timedelta(df_bbdd["_fecha"].dt.weekday, unit="D")
            df_bbdd["_periodo"] = df_bbdd["_semana"]
            df_bbdd["_lbl"] = df_bbdd.apply(
                lambda r: f"Sem {int(r['_semana'])} · {r['_lunes'].strftime('%d/%m')}", axis=1
            )
            grp_col = "_semana"
        else:
            df_bbdd["_mes"] = df_bbdd["_fecha"].dt.to_period("M")
            df_bbdd["_periodo"] = df_bbdd["_mes"]
            df_bbdd["_lbl"] = df_bbdd["_mes"].apply(
                lambda p: pd.Timestamp(str(p.start_time)).strftime("%b %Y").capitalize()
            )
            grp_col = "_mes"

        import datos_crm as _crm_cc
        _df_crm_cc = _crm_cc.cargar_crm()[["id", "Estado"]].copy()
        _df_crm_cc["id"] = _df_crm_cc["id"].astype(str).str.strip()
        _crm_estado_lookup = _df_crm_cc.set_index("id")["Estado"].to_dict()
        df_bbdd["_estado_crm"] = df_bbdd["ID"].map(_crm_estado_lookup).fillna("")

        _R2A_PEND  = {"5.3 - Reagendar R2", "5.2 - Filtrado pre R2",
                      "1.2 - Reagendar R1", "4 - Follow podcast",
                      "5.1 - R2 confirmada"}
        _R2_EFECT  = {"Buyer Sin interés"}
        _PRESU     = {"Stand By", "Contactar a Futuro", "Venta ganada",
                      "Dijo que no", "Follow 2", "Follow Clienty"}

        def _bucket_crm(estado):
            if estado in _R2A_PEND: return "r2a_pend"
            if estado in _R2_EFECT: return "r2_efectiva"
            if estado in _PRESU:    return "presupuesto"
            return "otros"

        df_bbdd["_bucket"] = df_bbdd["_estado_crm"].apply(_bucket_crm)
        df_bbdd["_periodo_str"] = df_bbdd["_periodo"].astype(str)

        _lbl_map = df_bbdd.drop_duplicates(subset=[grp_col]).set_index(grp_col)["_lbl"].to_dict()
        _ESTADOS_CC = ["Llamado Cancelado", "Reagendar R1", "Filtrado en R1", "Follow podcast"]
        periodos = sorted(df_bbdd[grp_col].unique())

        rows_agg = []
        for p in periodos:
            sub = df_bbdd[df_bbdd[grp_col] == p]
            sub_fp = sub[sub["Estado R1"] == "Follow podcast"]
            row = {"_periodo": p, "_periodo_str": str(p), "_lbl": _lbl_map.get(p, str(p)), "leads": len(sub)}
            for est in _ESTADOS_CC:
                col = est.lower().replace(" ", "_").replace("-", "_")
                row[col] = int((sub["Estado R1"] == est).sum())
            row["r2a_pend"]    = int((sub_fp["_bucket"] == "r2a_pend").sum())
            row["r2_efectiva"] = int((sub_fp["_bucket"] == "r2_efectiva").sum())
            row["presupuesto"] = int((sub_fp["_bucket"] == "presupuesto").sum())
            row["otros"]       = int((sub_fp["_bucket"] == "otros").sum())
            rows_agg.append(row)

        df_agg_cc = pd.DataFrame(rows_agg)

        n_max_cc = len(df_agg_cc)
        _labels_cc   = {"Día": "Días a mostrar", "Semana": "Semanas a mostrar", "Mes": "Meses a mostrar"}
        _defaults_cc = {"Día": min(7, n_max_cc), "Semana": min(6, n_max_cc), "Mes": n_max_cc}
        _mins_cc     = {"Día": min(3, n_max_cc), "Semana": min(4, n_max_cc), "Mes": 1}

        _col_tit_cc, _col_sl_cc, _col_modo_cc = st.columns([2, 3, 1])
        _LINKS_CC = {
            "Sol": "https://docs.google.com/spreadsheets/d/1Oto16BeUmohfjWlzGeH-Nj0d3RMmZLG17ZSPd93ePA8/edit?usp=sharing",
            "Fer": "https://docs.google.com/spreadsheets/d/1EDbB-LMLeXFaCJeAifbV9zLNh9R4piO0GYuAeMBupo8/edit?usp=sharing",
        }
        with _col_tit_cc:
            if nombre_cc == "CC":
                _links_html = (
                    "<a href='https://docs.google.com/spreadsheets/d/1Oto16BeUmohfjWlzGeH-Nj0d3RMmZLG17ZSPd93ePA8/edit?usp=sharing' target='_blank'>Sol</a>"
                    " · "
                    "<a href='https://docs.google.com/spreadsheets/d/1EDbB-LMLeXFaCJeAifbV9zLNh9R4piO0GYuAeMBupo8/edit?usp=sharing' target='_blank'>Fer</a>"
                )
                st.markdown(
                    f"<div style='padding-top:28px;font-weight:600'>Detalle por {vista.lower()} · CC (Sol + Fer)</div>"
                    f"<div style='font-size:0.75rem;margin-top:2px'>{_links_html}</div>",
                    unsafe_allow_html=True
                )
            else:
                _link_cc = _LINKS_CC.get(nombre_cc, "")
                st.markdown(
                    f"<div style='padding-top:28px;font-weight:600'>Detalle por {vista.lower()} · {nombre_cc}</div>"
                    + (f"<div style='font-size:0.75rem;margin-top:2px'><a href='{_link_cc}' target='_blank'>Sheets Seguimiento leads R1 - {nombre_cc}</a></div>" if _link_cc else ""),
                    unsafe_allow_html=True
                )
        with _col_sl_cc:
            if n_max_cc > _mins_cc[vista]:
                st.caption(_labels_cc[vista])
                n_mostrar_cc = st.slider(
                    _labels_cc[vista], min_value=_mins_cc[vista],
                    max_value=n_max_cc, value=_defaults_cc[vista],
                    key=f"sl_{nombre_cc}_{vista}",
                    label_visibility="collapsed"
                )
            else:
                n_mostrar_cc = n_max_cc

        _lbl_ult_cc = {"Día": "Últ. día", "Semana": "Últ. semana", "Mes": "Últ. mes"}[vista]
        with _col_modo_cc:
            st.markdown(
                '<style>'
                'div[data-testid="column"]:last-child div[data-testid="stRadio"]{'
                '  display:flex;justify-content:flex-end;margin-top:-4px'
                '}'
                'div[data-testid="column"]:last-child div[data-testid="stRadio"] > div{'
                '  gap:2px'
                '}'
                'div[data-testid="column"]:last-child div[data-testid="stRadio"] label p{'
                '  font-size:0.72rem!important'
                '}'
                '</style>',
                unsafe_allow_html=True,
            )
            _modo_cc = st.radio(
                "ResumenCC", ["Prom.", _lbl_ult_cc],
                horizontal=False, label_visibility="collapsed", key=f"modo_cc_{nombre_cc}_{vista}"
            )
        _es_ult_cc    = (_modo_cc != "Prom.")
        _lbl_res_cc   = "Promedio" if not _es_ult_cc else _lbl_ult_cc

        df_show_cc = df_agg_cc.tail(n_mostrar_cc)
        _shown_periodos = set(df_show_cc["_periodo_str"].tolist())

        # ── JSON para tabla detalle ─────────────────────────────────
        _det_rows = []
        for _, r in df_bbdd[df_bbdd["_periodo_str"].isin(_shown_periodos)].iterrows():
            _rid = str(r.get("ID", "") or "")
            _det_rows.append({
                "id":         _rid,
                "mail":       str(r.get("Mail", "") or ""),
                "fecha":      str(r.get("Fecha R1", "") or ""),
                "nombre":     str(r.get("Nombre", "") or ""),
                "estado_r1":  str(r.get("Estado R1", "") or ""),
                "estado_crm": str(r.get("_estado_crm", "") or ""),
                "periodo":    str(r["_periodo_str"]),
                "lbl":        str(r.get("_lbl", "") or ""),
                "bucket":     str(r.get("_bucket", "") or ""),
                "explicacion": str(r.get("Explicacion", "") or ""),
                "fathom":      str(r.get("Fathom", "") or ""),
                "consultas":   str(_consultas_map.get(_rid, "") or ""),
                "cc":          str(r.get("_cc", nombre_cc) or nombre_cc),
                "empresa":     str(r.get("Empresa", "") or ""),
                "objeciones":  str(r.get("Objeciones", "") or ""),
            })
        _det_json = _json.dumps(_det_rows, ensure_ascii=False)

        # ── Construir tablas HTML ────────────────────────────────────
        _S  = "border:1px solid #e2e8f0"
        _WM = "width:160px;min-width:160px;max-width:160px"
        _WP = "width:105px;min-width:105px;max-width:105px"
        _WS = "width:88px;min-width:88px;max-width:88px"
        _TH = f"font-size:0.78rem;font-weight:600;padding:6px 8px;{_S};overflow:hidden"
        _TD = f"font-size:0.83rem;padding:2px 8px;{_S};overflow:hidden"
        _TDv= f"font-size:0.83rem;padding:2px 8px;{_S};overflow:hidden"
        _TDr= f"font-size:0.72rem;padding:2px 8px;{_S};overflow:hidden"

        _HB = "#1a3a5c"; _HF = "#fff"
        _bgs  = ["#d6eaf8", "#eef6fc"]
        _bgss = ["#a9cce3", "#bcd9ec"]

        _WO = "width:72px;min-width:72px;max-width:72px"

        def _icon_cc(v, o):
            if not o: return ""
            return "🟢" if v >= o else ("🟡" if v >= o * 0.7 else "🔴")

        # Encabezado compartido
        def _build_hdr(hdr_bg, hdr_fg):
            h = f'<th style="text-align:left;color:{hdr_fg};background:{hdr_bg};{_WM};{_TH}">Métrica</th>'
            for _, r in df_show_cc.iterrows():
                h += f'<th style="text-align:center;color:{hdr_fg};background:{hdr_bg};{_WP};{_TH}">{r["_lbl"]}</th>'
            h += (f'<th style="text-align:center;color:{hdr_fg};background:{hdr_bg};{_WS};{_TH}">{_lbl_res_cc}</th>'
                  f'<th style="text-align:center;color:{hdr_fg};background:{hdr_bg};{_WO};{_TH}">Objetivo</th>'
                  f'<th style="text-align:center;color:{hdr_fg};background:{hdr_bg};{_WO};{_TH}">% Cumpl.</th>')
            return h

        # Tabla azul — (lbl, col, filt_total, objetivo_o_0)
        _METRICAS_CC = [
            ("Leads",             "leads",             "metrica:leads",                obj["Leads"]),
            ("Llamado Cancelado",  "llamado_cancelado", "estado_r1:Llamado Cancelado",  0),
            ("Reagendar R1",       "reagendar_r1",      "estado_r1:Reagendar R1",       0),
            ("Filtrado en R1",     "filtrado_en_r1",    "estado_r1:Filtrado en R1",     obj["R1"]),
            ("Follow podcast",     "follow_podcast",    "estado_r1:Follow podcast",     obj["Follow"]),
        ]
        body_b = ""
        for i, (lbl, col, filt_total, obj_val) in enumerate(_METRICAS_CC):
            bg  = _bgs[i % 2]; bgs = _bgss[i % 2]
            vals = [int(r[col]) if col in df_show_cc.columns and pd.notna(r[col]) else 0
                    for _, r in df_show_cc.iterrows()]
            cells = f'<td style="text-align:left;font-weight:600;color:#1e293b;{_WM};{_TD};background:{bg}">{lbl}</td>'
            for (_, row_p), v in zip(df_show_cc.iterrows(), vals):
                p_str = str(row_p["_periodo_str"])
                filt = f"periodo:{p_str}|{filt_total}" if filt_total != "metrica:leads" else f"periodo:{p_str}"
                onclick = f' data-filter="{filt}"' if v else ""
                _icn = f"{_icon_cc(v, obj_val)} " if obj_val else ""
                cells += f'<td style="text-align:center;{_WP};{_TD};background:{bg}"{onclick}>{(_icn+str(v)) if v else ""}</td>'
            _tot = sum(vals)
            _res = vals[-1] if _es_ult_cc and vals else (round(_tot / len(vals)) if vals else 0)
            _pct = round(_res / obj_val * 100) if obj_val else 0
            _icn_res = f"{_icon_cc(_res, obj_val)} " if obj_val else ""
            tot_onclick = f' data-filter="{filt_total}"' if _tot else ""
            cells += f'<td style="text-align:center;font-weight:500;{_WS};{_TD};background:{bgs}"{tot_onclick}>{(_icn_res+str(_res)) if _res else ""}</td>'
            cells += f'<td style="text-align:center;{_WO};{_TD};background:{bgs};color:#1e293b">{obj_val if obj_val else ""}</td>'
            cells += f'<td style="text-align:center;{_WO};{_TD};background:{bgs};color:#1e293b">{"" if not _pct else str(_pct)+"%"}</td>'
            body_b += f"<tr>{cells}</tr>"

        # Tabla R2/Presupuesto — mismo color azul que tabla superior
        _METRICAS_V = [
            ("R2A Pend",    "r2a_pend"),
            ("R2 Efectiva", "r2_efectiva"),
            ("Presupuesto", "presupuesto"),
            ("Otros",       "otros"),
        ]
        body_v = ""
        for i, (lbl, col) in enumerate(_METRICAS_V):
            bg  = _bgs[i % 2]; bgs = _bgss[i % 2]
            vals = [int(row_p[col]) if col in df_show_cc.columns and pd.notna(row_p[col]) else 0
                    for _, row_p in df_show_cc.iterrows()]
            cells = f'<td style="text-align:left;font-weight:600;color:#1e293b;{_WM};{_TDv};background:{bg}">{lbl}</td>'
            for (_, row_p), v in zip(df_show_cc.iterrows(), vals):
                p_str = str(row_p["_periodo_str"])
                onclick = f' data-filter="periodo:{p_str}|bucket:{col}"' if v else ""
                cells += f'<td style="text-align:center;{_WP};{_TDv};background:{bg}"{onclick}>{v if v else ""}</td>'
            _tot = sum(vals)
            _res = vals[-1] if _es_ult_cc and vals else (round(_tot / len(vals)) if vals else 0)
            tot_onclick = f' data-filter="bucket:{col}"' if _tot else ""
            cells += f'<td style="text-align:center;font-weight:500;{_WS};{_TDv};background:{bgs}"{tot_onclick}>{_res if _res else ""}</td>'
            cells += f'<td style="text-align:center;{_WO};{_TDv};background:{bgs}"></td>'
            cells += f'<td style="text-align:center;{_WO};{_TDv};background:{bgs}"></td>'
            body_v += f"<tr>{cells}</tr>"

        # Ratios — fila separadora + filas en verde
        _bg_ratio  = ["#d7f0e3", "#eef9f3"]
        _bgs_ratio = ["#a3d9bd", "#bdeace"]
        _n_cols = len(df_show_cc) + 5  # métrica + períodos + Resumen + Objetivo + % Cumpl.
        _sep_row = f'<tr><td colspan="{_n_cols}" style="padding:2px 0;background:#fff;border:none"></td></tr>'
        body_v += _sep_row

        def _pct(num, den):
            return f"{round(num/den*100)}%" if den else ""

        _RATIOS = [
            ("%R1/Lead",  "follow_podcast", "filtrado_en_r1", "leads"),
            ("%FP/Lead",  "follow_podcast",  None,            "leads"),
        ]
        for i, ratio_def in enumerate(_RATIOS):
            lbl   = ratio_def[0]
            bg    = _bg_ratio[i % 2]; bgs = _bgs_ratio[i % 2]
            vals_str = []
            nums_sum = 0; dens_sum = 0
            cells = f'<td style="text-align:left;font-weight:600;color:#1e293b;{_WM};{_TDr};background:{bg}">{lbl}</td>'
            for _, row_p in df_show_cc.iterrows():
                if ratio_def[0] == "%R1/Lead":
                    num = int(row_p.get("follow_podcast", 0) or 0) + int(row_p.get("filtrado_en_r1", 0) or 0)
                else:
                    num = int(row_p.get("follow_podcast", 0) or 0)
                den = int(row_p.get("leads", 0) or 0)
                nums_sum += num; dens_sum += den
                v = _pct(num, den)
                cells += f'<td style="text-align:center;{_WP};{_TDr};background:{bg}">{v}</td>'
            tot_v = _pct(nums_sum, dens_sum)
            cells += (f'<td style="text-align:center;font-weight:500;{_WS};{_TDr};background:{bgs}">{tot_v}</td>'
                      f'<td style="text-align:center;{_WO};{_TDr};background:{bgs}"></td>'
                      f'<td style="text-align:center;{_WO};{_TDr};background:{bgs}"></td>')
            body_v += f"<tr>{cells}</tr>"

        # Insertar el mismo separador entre tabla azul y R2/ratios
        _sep_row_top = f'<tr><td colspan="{_n_cols}" style="padding:2px 0;background:#fff;border:none"></td></tr>'
        body_combined = body_b + _sep_row_top + body_v

        _hdr_b = _build_hdr(_HB, _HF)

        _n_det = len(_det_rows)
        _height = 34 + 5 * 34 + 16 + (4 + 2) * 30 + 40 + 50 + _n_det * 31 + 80

        _html_cc = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<style>
*{{box-sizing:border-box;margin:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#fff;padding:4px 0;font-size:0.78rem}}
table{{border-collapse:collapse;table-layout:fixed;width:100%}}
td[data-filter]:hover{{filter:brightness(0.88);outline:1px solid rgba(0,0,0,0.2);cursor:pointer}}
.det-wrap{{border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;margin-top:14px}}
.det-tbl{{width:100%;border-collapse:collapse;font-size:0.8rem;table-layout:auto}}
.det-th{{padding:6px 12px;font-weight:600;background:#f1f5f9;color:#475569;border-bottom:2px solid #e2e8f0;cursor:pointer;white-space:nowrap;text-align:left}}
.det-th:hover{{background:#e2e8f0}}
.det-td{{padding:6px 12px;border-bottom:1px solid #f1f5f9;color:#1e293b;cursor:pointer}}
.det-td-c{{padding:6px 12px;border-bottom:1px solid #f1f5f9;color:#1e293b;text-align:center;cursor:pointer}}
.det-tr:hover .det-td,.det-tr:hover .det-td-c{{background:#f0f4f8}}
.det-tr.active .det-td,.det-tr.active .det-td-c{{background:#e8f0f8;border-bottom:none}}
.exp-tr td{{background:#f0f4f8;border-left:3px solid #1a3a5c;border-bottom:1px solid #e2e8f0;padding:12px 16px;cursor:default}}
.exp-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.exp-full{{grid-column:1/-1}}
.exp-label{{font-size:0.68rem;text-transform:uppercase;letter-spacing:0.05em;color:#64748b;margin-bottom:3px;font-weight:600}}
.exp-val{{color:#1e293b;line-height:1.5;font-size:0.78rem}}
.exp-link{{color:#1a3a5c;font-size:0.78rem;text-decoration:none}}
.exp-link:hover{{text-decoration:underline}}
.exp-empty{{color:#94a3b8;font-style:italic;font-size:0.75rem}}
.count{{font-size:0.78rem;color:#64748b;margin:10px 0 4px;display:inline-block}}
</style>
</head><body>
<table style="margin-bottom:12px;width:100%;table-layout:auto"><thead><tr>{_hdr_b}</tr></thead><tbody>{body_combined}</tbody></table>
<div style="display:flex;align-items:center;margin:10px 0 4px">
<div class="count" id="det-count"></div>
</div>
<div class="det-wrap">
<table class="det-tbl">
<thead><tr>
<th class="det-th" style="text-align:center" onclick="sortDet(0)">ID <span id="arr0"></span></th>
<th class="det-th" style="text-align:center" onclick="sortDet(1)">Mail <span id="arr1"></span></th>
<th class="det-th" style="text-align:center" onclick="sortDet(2)">Fecha R1 <span id="arr2"></span></th>
<th class="det-th" style="text-align:center" onclick="sortDet(3)">Nombre <span id="arr3"></span></th>
<th class="det-th" style="text-align:center" onclick="sortDet(4)">Estado R1 <span id="arr4"></span></th>
<th class="det-th" style="text-align:center" onclick="sortDet(5)">Estado CRM <span id="arr5"></span></th>
<th class="det-th" style="text-align:center" onclick="sortDet(6)">CC <span id="arr6"></span></th>
</tr></thead>
<tbody id="det-body"></tbody>
</table>
</div>
<script>
var _all={_det_json};
var _cur=_all.slice();
var _sort=-1,_dir=1;
var _openIdx=-1;
var _KEYS=['id','mail','fecha','nombre','estado_r1','estado_crm','cc'];

function filterClick(filter){{
  var parts={{}};
  if(filter&&filter!=='all')filter.split('|').forEach(function(p){{
var i=p.indexOf(':'),k=p.slice(0,i),v=p.slice(i+1);parts[k]=v;
  }});
  _cur=_all.filter(function(r){{
if(parts.periodo&&r.periodo!==parts.periodo)return false;
if(parts.estado_r1&&r.estado_r1!==parts.estado_r1)return false;
if(parts.bucket){{if(r.estado_r1!=='Follow podcast'||r.bucket!==parts.bucket)return false;}}
return true;
  }});
  _sort=-1;_dir=1;_openIdx=-1;renderDet(_cur);
}}

function sortDet(i){{
  if(_sort===i){{_dir*=-1;}}else{{_sort=i;_dir=1;}}
  var k=_KEYS[i];
  _cur=_cur.slice().sort(function(a,b){{
var av=a[k]||'',bv=b[k]||'';
return(av<bv?-1:av>bv?1:0)*_dir;
  }});
  _openIdx=-1;renderDet(_cur);
}}

function toggleRow(idx){{
  _openIdx=(_openIdx===idx)?-1:idx;
  renderDet(_cur);
}}

function _esc(s){{return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}}

function _fmtConsultas(s){{
  var parts=s.split('¿').filter(function(p){{return p.trim();}});
  if(parts.length<=1)return '<div class="exp-val">'+_esc(s)+'</div>';
  return parts.map(function(p){{
return '<div class="exp-val" style="margin-bottom:4px">¿'+_esc(p.trim())+'</div>';
  }}).join('');
}}

function _expandHtml(r){{
  var hasExp=r.explicacion&&r.explicacion!=='nan'&&r.explicacion.trim();
  var hasFat=r.fathom&&r.fathom!=='nan'&&r.fathom.trim()&&r.fathom.startsWith('http');
  var hasCon=r.consultas&&r.consultas!=='nan'&&r.consultas.trim();
  var hasEmp=r.empresa&&r.empresa!=='nan'&&r.empresa.trim();
  var hasObj=r.objeciones&&r.objeciones!=='nan'&&r.objeciones.trim();
  var h='<div class="exp-grid">';
  h+='<div><div class="exp-label">Explicación call confirmer</div>';
  h+=hasExp?'<div class="exp-val">'+_esc(r.explicacion)+'</div>'
        :'<div class="exp-empty">Sin explicación</div>';
  h+='</div>';
  h+='<div><div class="exp-label">Consultas (Calendly)</div>';
  h+=hasCon?_fmtConsultas(r.consultas)
        :'<div class="exp-empty">Sin consultas registradas</div>';
  h+='</div>';
  h+='<div><div class="exp-label">Empresa (página web)</div>';
  h+=hasEmp?'<div class="exp-val">'+_esc(r.empresa)+'</div>'
        :'<div class="exp-empty">Sin datos</div>';
  h+='</div>';
  h+='<div></div>';
  h+='<div><div class="exp-label">Objeciones o preguntas en R1</div>';
  h+=hasObj?'<div class="exp-val">'+_esc(r.objeciones)+'</div>'
        :'<div class="exp-empty">Sin datos</div>';
  h+='</div>';
  h+='<div></div>';
  if(hasFat){{
h+='<div><div class="exp-label">Grabación Fathom</div>';
h+='<a class="exp-link" href="'+r.fathom+'" target="_blank">▶ Ver grabación →</a></div>';
  }}
  h+='</div>';
  return h;
}}

function renderDet(rows){{
  document.getElementById('det-count').textContent=rows.length+' registros · BBDD R1 {nombre_cc}';
  for(var i=0;i<7;i++)document.getElementById('arr'+i).textContent=_sort===i?(_dir>0?' ↑':' ↓'):'';
  var h='';
  if(!rows.length){{
h='<tr><td colspan="8" style="padding:14px;color:#94a3b8;text-align:center">Sin registros.</td></tr>';
  }}else{{
rows.forEach(function(r,idx){{
  var open=(_openIdx===idx);
  var cls='det-tr'+(open?' active':'');
  h+='<tr class="'+cls+'" onclick="toggleRow('+idx+')">'
    +'<td class="det-td" style="text-align:center">'+_esc(r.id)+'</td>'
    +'<td class="det-td">'+_esc(r.mail)+'</td>'
    +'<td class="det-td-c" style="text-align:center">'+_esc(r.fecha)+'</td>'
    +'<td class="det-td" style="text-align:center">'+_esc(r.nombre)+'</td>'
    +'<td class="det-td-c" style="text-align:center">'+_esc(r.estado_r1)+'</td>'
    +'<td class="det-td-c" style="text-align:center">'+_esc(r.estado_crm)+'</td>'
    +'<td class="det-td-c" style="text-align:center">'+_esc(r.cc)+'</td>'
    +'</tr>';
  if(open){{
    h+='<tr class="exp-tr"><td colspan="7">'+_expandHtml(r)+'</td></tr>';
  }}
}});
  }}
  document.getElementById('det-body').innerHTML=h;
}}


document.querySelectorAll('td[data-filter]').forEach(function(td){{
  td.onclick=function(){{filterClick(this.dataset.filter);}};
}});

renderDet(_all);
</script>
</body></html>"""

        components.html(_html_cc, height=_height, scrolling=True)

    tab_cc_total, tab_sol, tab_fer = st.tabs(["Perfo CC", "Perfo Sol", "Perfo Fer"])

    try:
        _df_sol = _cargar_bbdd_sol()
        _df_sol["_cc"] = "Sol"
    except Exception:
        _df_sol = pd.DataFrame()
    try:
        _df_fer = _cargar_bbdd_fer()
        _df_fer["_cc"] = "Fer"
    except Exception:
        _df_fer = pd.DataFrame()

    with tab_cc_total:
        try:
            _df_cc_total = pd.concat([_df_sol, _df_fer], ignore_index=True)
            _render_perfo_cc(_df_cc_total, "CC")
        except Exception as _e_cc:
            st.error(f"Error cargando datos de CC: {_e_cc}")
    with tab_sol:
        if _df_sol.empty:
            st.error("Error cargando datos de Sol.")
        else:
            _render_perfo_cc(_df_sol, "Sol")
    with tab_fer:
        if _df_fer.empty:
            st.error("Error cargando datos de Fer.")
        else:
            _render_perfo_cc(_df_fer, "Fer")

with tab_closer:
    _ID_SEBA = "17IGWY-VvK8pB_0cN2gSNHrzyTMhndhRS8cWtJDNbBEQ"
    _ID_RO   = "1PsGJ4DBwjfOaSV7icHLUbSmP8kDQ6gGLjztUD4_HNvs"

    _LINKS_CLO = {
        "Seba": "https://docs.google.com/spreadsheets/d/17IGWY-VvK8pB_0cN2gSNHrzyTMhndhRS8cWtJDNbBEQ/edit?usp=sharing",
        "Ro":   "https://docs.google.com/spreadsheets/d/1PsGJ4DBwjfOaSV7icHLUbSmP8kDQ6gGLjztUD4_HNvs/edit?usp=sharing",
    }

    @st.cache_data(ttl=3600)
    def _cargar_bbdd_closer(sheet_id, hoja="BBDD_FINAL"):
        df = _fetch_external_csv(sheet_id, hoja)
        _hdr = [str(c).strip().lower() for c in df.columns]
        def _fc(candidates):
            for cand in candidates:
                for i, h in enumerate(_hdr):
                    if cand in h: return df.columns[i]
            return None
        _col_id    = _fc(["id"]) or df.columns[0]
        _col_nom   = _fc(["nombre"]) or df.columns[2]
        _col_ape   = _fc(["apellido"]) or df.columns[3]
        _col_emp   = _fc(["empresa"]) or df.columns[5]
        _col_est   = _fc(["estado del dia"]) or df.columns[7]
        _col_fec   = _fc(["fecha r2", "fecha_r2"]) or df.columns[8]
        _col_por   = _fc(["porque", "porqué"])
        out = pd.DataFrame()
        out["ID"]       = df[_col_id].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        out["Nombre"]   = df[_col_nom].astype(str)
        out["Apellido"] = df[_col_ape].astype(str) if _col_ape else ""
        out["Empresa"]  = df[_col_emp].astype(str) if _col_emp else ""
        out["Estado"]   = df[_col_est].astype(str)
        out["Fecha R2"] = df[_col_fec].astype(str)
        out["Porque"]   = df[_col_por].astype(str) if _col_por else ""
        out = out[out["ID"].notna() & (out["ID"] != "") & (out["ID"] != "nan")]
        hoy = pd.Timestamp.today()
        def _parse_r2(s):
            s = str(s).strip()
            if not s or s == "nan": return pd.NaT
            parts = s.split("/")
            if len(parts) == 2:
                for yr in [hoy.year, hoy.year - 1]:
                    try:
                        t = pd.to_datetime(f"{parts[0]}/{parts[1]}/{yr}", dayfirst=True)
                        if t <= hoy + pd.Timedelta(days=30): return t
                    except Exception: pass
            return pd.to_datetime(s, dayfirst=True, errors="coerce")
        out["_fecha"] = out["Fecha R2"].apply(_parse_r2)
        return out

    def _cargar_bbdd_seba():
        return _cargar_bbdd_closer(_ID_SEBA)

    @st.cache_data(ttl=3600)
    def _cargar_bbdd_ro():
        return _cargar_bbdd_closer(_ID_RO)

    @st.cache_data(ttl=3600)
    def _cargar_cc_lookup(id_sol, id_fer):
        """Construye {id: 'Sol'/'Fer'} buscando en las BBDD_R1 de cada CC. Se cachea."""
        lkp = {}
        for sheet_id, nombre in [(id_sol, "Sol"), (id_fer, "Fer")]:
            try:
                df = _fetch_external_csv(sheet_id, "BBDD_R1")
                ids = df.iloc[:, 0].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                for _id in ids:
                    if _id and _id not in ("nan", "ID", ""):
                        lkp[_id] = nombre
            except Exception:
                pass
        return lkp

    def _render_perfo_closer(df_bbdd, nombre_closer):
        import datos_crm as _crm_cl
        _cc_lkp = _cargar_cc_lookup(_ID_SOL, _ID_FER)
        _df_crm_cl = _crm_cl.cargar_crm()[["id", "Estado"]].copy()
        _df_crm_cl["id"] = _df_crm_cl["id"].astype(str).str.strip()
        _crm_estado_cl = _df_crm_cl.set_index("id")["Estado"].to_dict()
        df_bbdd = df_bbdd.dropna(subset=["_fecha"]).copy()
        df_bbdd = df_bbdd[
            (df_bbdd["_fecha"] >= pd.Timestamp(fecha_desde)) &
            (df_bbdd["_fecha"] <= pd.Timestamp(fecha_hasta))
        ]
        if df_bbdd.empty:
            st.info("Sin datos en el rango seleccionado.")
            return

        _DIAS_ES = {"Monday":"Lu","Tuesday":"Ma","Wednesday":"Mi",
                    "Thursday":"Ju","Friday":"Vi","Saturday":"Sá","Sunday":"Do"}

        if vista == "Día":
            df_bbdd["_periodo"] = df_bbdd["_fecha"].dt.date
            df_bbdd["_lbl"] = df_bbdd["_fecha"].apply(
                lambda d: f"{_DIAS_ES.get(d.strftime('%A'),d.strftime('%A')[:2])} {d.strftime('%d/%m')}"
            )
            grp_col = "_periodo"
        elif vista == "Semana":
            df_bbdd["_semana"] = df_bbdd["_fecha"].dt.isocalendar().week.astype(int)
            df_bbdd["_lunes"]  = df_bbdd["_fecha"] - pd.to_timedelta(df_bbdd["_fecha"].dt.weekday, unit="D")
            df_bbdd["_periodo"] = df_bbdd["_semana"]
            df_bbdd["_lbl"] = df_bbdd.apply(
                lambda r: f"Sem {int(r['_semana'])} · {r['_lunes'].strftime('%d/%m')}", axis=1
            )
            grp_col = "_semana"
        else:
            df_bbdd["_mes"] = df_bbdd["_fecha"].dt.to_period("M")
            df_bbdd["_periodo"] = df_bbdd["_mes"]
            df_bbdd["_lbl"] = df_bbdd["_mes"].apply(
                lambda p: pd.Timestamp(str(p.start_time)).strftime("%b %Y").capitalize()
            )
            grp_col = "_mes"

        def _map_bucket(s):
            s = str(s).strip().lower()
            if "cancelad" in s:  return "r2_cancelada"
            if "reagend" in s:   return "r2_reagendada"
            if "buyer" in s or "sin inter" in s: return "bsi"
            if "follow" in s:    return "follow_clienty"
            return "otros"
        df_bbdd["_bucket"] = df_bbdd["Estado"].apply(_map_bucket)

        _periodos_all = sorted(df_bbdd[grp_col].unique())
        _lbl_map_all  = df_bbdd.groupby(grp_col)["_lbl"].first().to_dict()

        n_max_cl    = len(_periodos_all)
        _labels_cl  = {"Día": "Días a mostrar", "Semana": "Semanas a mostrar", "Mes": "Meses a mostrar"}
        _defaults_cl = {"Día": min(7, n_max_cl), "Semana": min(6, n_max_cl), "Mes": n_max_cl}
        _mins_cl    = {"Día": min(3, n_max_cl), "Semana": min(4, n_max_cl), "Mes": 1}

        _col_tit_cl, _col_sl_cl = st.columns([2, 4])
        with _col_tit_cl:
            _link_cl = _LINKS_CLO.get(nombre_closer, "")
            st.markdown(
                f"<div style='padding-top:28px;font-weight:600'>Detalle por {vista.lower()} · {nombre_closer}</div>"
                + (f"<div style='font-size:0.75rem;margin-top:2px'><a href='{_link_cl}' target='_blank'>Sheets Seguimiento R2 - {nombre_closer}</a></div>" if _link_cl else ""),
                unsafe_allow_html=True
            )
        with _col_sl_cl:
            if n_max_cl > _mins_cl[vista]:
                st.caption(_labels_cl[vista])
                n_mostrar_cl = st.slider(
                    _labels_cl[vista], min_value=_mins_cl[vista],
                    max_value=n_max_cl, value=_defaults_cl[vista],
                    key=f"sl_closer_{nombre_closer}_{vista}",
                    label_visibility="collapsed"
                )
            else:
                n_mostrar_cl = n_max_cl

        _periodos = _periodos_all[-n_mostrar_cl:]
        _p_strs   = {p: str(_lbl_map_all[p]) for p in _periodos}

        _rows_data = []
        for p in _periodos:
            sub = df_bbdd[df_bbdd[grp_col] == p]
            rc  = int((sub["_bucket"] == "r2_cancelada").sum())
            rr  = int((sub["_bucket"] == "r2_reagendada").sum())
            rb  = int((sub["_bucket"] == "bsi").sum())
            rf  = int((sub["_bucket"] == "follow_clienty").sum())
            rt  = rc + rr + rb + rf
            _rows_data.append({"lbl": _p_strs[p],
                "r2_total": rt, "r2_cancelada": rc,
                "r2_reagendada": rr, "bsi": rb, "follow": rf})

        _n_cols = len(_periodos) + 3
        _bgs  = ["#d6eaf8", "#eef6fc"]
        _bgss = ["#a9cce3", "#bcd9ec"]
        _gbgs = ["#d7f0e3", "#eef9f3"]
        _gbgss= ["#a3d9bd", "#bdeace"]
        _TD   = "font-size:0.83rem;padding:2px 8px;border:1px solid #e2e8f0;overflow:hidden"
        _TDr  = "font-size:0.72rem;padding:2px 8px;border:1px solid #e2e8f0;overflow:hidden"

        def _hdr_td(txt, extra=""):
            return f'<td style="background:#1a3a5c;color:white;font-weight:600;font-size:0.83rem;padding:2px 8px;border:1px solid #e2e8f0;text-align:center{extra}">{txt}</td>'

        def _val_td(v, bg, align="center", onclick="", style=None):
            style = style or _TD
            _cur = "cursor:pointer;" if onclick else ""
            return f'<td style="{style};background:{bg};text-align:{align};{_cur}" {onclick}>{v if v else ""}</td>'

        header = f'<tr>{_hdr_td("Métrica", ";text-align:left")}'
        for rd in _rows_data: header += _hdr_td(rd["lbl"])
        header += f'{_hdr_td("Total")}{_hdr_td("Promedio")}</tr>'

        _METRICS = [
            ("R2 Total",          "r2_total",      None),
            ("R2 Cancelada",      "r2_cancelada",  "r2_cancelada"),
            ("R2 Reagendada",     "r2_reagendada", "r2_reagendada"),
            ("Buyer Sin Interés", "bsi",           "bsi"),
            ("Follow Clienty",    "follow",        "follow_clienty"),
        ]
        body_b = ""
        for mi, (lbl_m, key_m, bucket_m) in enumerate(_METRICS):
            bg  = _bgs[mi % 2]
            bgs = _bgss[mi % 2]
            vals = [rd[key_m] for rd in _rows_data]
            tot  = sum(vals)
            prom = round(tot / len(vals)) if vals else 0
            _fw  = "font-weight:700;" if key_m == "r2_total" else ""
            filt_total = f"bucket:{bucket_m}" if bucket_m else "metrica:r2_total"
            row = f'<tr>{_val_td(lbl_m, bg, "left", style=_TD+";"+_fw)}'
            for rd, v in zip(_rows_data, vals):
                p_str = rd["lbl"]
                if key_m == "r2_total":
                    oc = f'data-filter="periodo:{p_str}"' if v else ""
                else:
                    oc = f'data-filter="periodo:{p_str}|bucket:{bucket_m}"' if (v and bucket_m) else ""
                row += _val_td(v or "", _bgss[mi%2] if v else bg, "center", oc, _TD+";"+_fw)
            tot_oc = f'data-filter="{filt_total}"' if tot else ""
            row += _val_td(tot or "", bgs, "center", tot_oc, _TD+";"+_fw)
            row += _val_td(prom or "", bgs, "center", style=_TD+";"+_fw)
            row += "</tr>"
            body_b += row

        _SEP = f'<tr><td colspan="{_n_cols}" style="padding:2px 0;background:#fff;border:none"></td></tr>'
        _RATIOS = [
            ("% Cancelada",      "r2_cancelada"),
            ("% Reagendada",     "r2_reagendada"),
            ("% BSI",            "bsi"),
            ("% Follow Clienty", "follow"),
        ]
        body_v = ""
        for ri, (lbl_r, key_r) in enumerate(_RATIOS):
            bg  = _gbgs[ri % 2]
            bgs = _gbgss[ri % 2]
            vals   = [rd[key_r] for rd in _rows_data]
            tots   = [rd["r2_total"] for rd in _rows_data]
            tot_n  = sum(vals)
            tot_d  = sum(tots)
            def _pct(n, d): return f"{round(n/d*100)}%" if d else ""
            row = f'<tr>{_val_td(lbl_r, bg, "left", style=_TDr)}'
            for v, t in zip(vals, tots):
                row += _val_td(_pct(v, t), bg, "center", style=_TDr)
            row += _val_td(_pct(tot_n, tot_d), bgs, "center", style=_TDr)
            row += _val_td("", bgs, "center", style=_TDr)
            row += "</tr>"
            body_v += row

        # ── Tabla semáforo + detalle con filtro JS ───────────────────
        _chip_styles = {
            "r2_cancelada":   ("R2 Cancelada", "#fee2e2", "#b91c1c"),
            "r2_reagendada":  ("Reagendada",   "#fef3c7", "#92400e"),
            "bsi":            ("BSI",          "#ede9fe", "#5b21b6"),
            "follow_clienty": ("Follow",       "#d1fae5", "#065f46"),
            "otros":          ("Otros",        "#f1f5f9", "#475569"),
        }
        def _chip(bk):
            lbl, bg, fg = _chip_styles.get(bk, ("?", "#f1f5f9", "#475569"))
            return (f'<span style="display:inline-block;padding:1px 7px;border-radius:9px;'
                    f'font-size:0.72rem;font-weight:600;background:{bg};color:{fg}">{lbl}</span>')

        def _esc_html(s):
            return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

        _df_det = df_bbdd.sort_values("_fecha", ascending=False)
        _total_r = len(_df_det)
        _TH = "background:#1a3a5c;color:white;padding:4px 10px;text-align:left;font-size:0.82rem"
        _TD_det = "padding:3px 10px;border-bottom:1px solid #e2e8f0;font-size:0.82rem"
        det_hdr = (f'<tr><th style="{_TH}">ID</th><th style="{_TH}">Fecha R2</th>'
                   f'<th style="{_TH}">Nombre</th><th style="{_TH}">Empresa</th>'
                   f'<th style="{_TH}">Estado</th><th style="{_TH}">Estado CRM</th>'
                   f'<th style="{_TH}">CC</th></tr>')
        det_body = ""
        for _, r in _df_det.iterrows():
            _id   = _esc_html(r.get("ID",""))
            _nom  = _esc_html((str(r.get("Nombre","") or "") + " " + str(r.get("Apellido","") or "")).strip())
            _emp  = _esc_html(r.get("Empresa",""))
            _fec  = _esc_html(r.get("Fecha R2",""))
            _bk   = str(r.get("_bucket","") or "otros")
            _per  = _esc_html(str(_p_strs.get(r[grp_col], "") or ""))
            _ecrm = _esc_html(_crm_estado_cl.get(str(r.get("ID","") or "").strip(), ""))
            _cc   = _esc_html(_cc_lkp.get(str(r.get("ID","") or "").strip(), ""))
            det_body += (
                f'<tr class="drow" data-periodo="{_per}" data-bucket="{_bk}" style="border-bottom:1px solid #e2e8f0">'
                f'<td style="{_TD_det}">{_id}</td>'
                f'<td style="{_TD_det}">{_fec}</td>'
                f'<td style="{_TD_det}">{_nom}</td>'
                f'<td style="{_TD_det}">{_emp}</td>'
                f'<td style="{_TD_det}">{_chip(_bk)}</td>'
                f'<td style="{_TD_det};color:#475569">{_ecrm}</td>'
                f'<td style="{_TD_det};font-weight:600;color:#1a3a5c">{_cc}</td>'
                f'</tr>'
            )

        # Añadir onclick a celdas clickeables de body_b
        _body_b_click = body_b  # ya tiene data-filter desde _val_td

        _SEP_ROW = f'<tr><td colspan="{_n_cols}" style="padding:2px 0;background:#fff;border:none"></td></tr>'

        _html_cl = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
body{{margin:0;padding:0;font-family:system-ui,sans-serif;font-size:14px}}
table{{border-collapse:collapse;width:100%}}
td[data-filter]{{cursor:pointer;opacity:1;transition:opacity .15s}}
td[data-filter]:hover{{opacity:.75}}
td[data-filter].active{{outline:2px solid #2563eb}}
.drow{{transition:background .1s}}
</style></head><body>
<div style="overflow-x:auto;margin-bottom:8px">
<table style="table-layout:fixed;width:100%;border-collapse:collapse">
<thead>{header}</thead>
<tbody>{_body_b_click}{_SEP_ROW}{body_v}</tbody>
</table></div>
<div style="font-size:0.78rem;color:#64748b;margin:4px 0" id="info">{_total_r} registros · BBDD R2 {nombre_closer}</div>
<div style="overflow-x:auto">
<table style="width:100%;border-collapse:collapse">
<thead>{det_hdr}</thead>
<tbody id="det">{det_body}</tbody>
</table></div>
<script>
var _activeFilter=null;
function applyFilter(periodo,bucket){{
  var rows=document.querySelectorAll('.drow');
  var vis=0;
  rows.forEach(function(r){{
    var show=true;
    if(periodo&&r.dataset.periodo!==periodo)show=false;
    if(bucket&&r.dataset.bucket!==bucket)show=false;
    r.style.display=show?'':'none';
    if(show)vis++;
  }});
  document.getElementById('info').textContent=vis+' registros · BBDD R2 {nombre_closer}';
}}
document.querySelectorAll('td[data-filter]').forEach(function(td){{
  td.addEventListener('click',function(){{
    var f=this.dataset.filter;
    if(_activeFilter===f){{
      _activeFilter=null;
      document.querySelectorAll('td[data-filter]').forEach(function(x){{x.classList.remove('active');}});
      applyFilter(null,null);
      return;
    }}
    _activeFilter=f;
    document.querySelectorAll('td[data-filter]').forEach(function(x){{x.classList.remove('active');}});
    this.classList.add('active');
    var parts={{}};
    f.split('|').forEach(function(p){{var kv=p.split(':');parts[kv[0]]=kv.slice(1).join(':');}});
    var periodo=parts.periodo||null;
    var bucket=parts.bucket||(parts.metrica==='r2_total'?'__any__':null);
    if(bucket==='__any__'){{
      var rows=document.querySelectorAll('.drow');
      var bkts=['r2_cancelada','r2_reagendada','bsi','follow_clienty'];
      var vis=0;
      rows.forEach(function(r){{
        var show=(!periodo||r.dataset.periodo===periodo)&&bkts.indexOf(r.dataset.bucket)>=0;
        r.style.display=show?'':'none';
        if(show)vis++;
      }});
      document.getElementById('info').textContent=vis+' registros · BBDD R2 {nombre_closer}';
    }}else{{
      applyFilter(periodo,bucket);
    }}
  }});
}});
</script>
</body></html>"""

        _height = 40 + (_n_cols + 10) * 30 + _total_r * 28 + 80
        components.html(_html_cl, height=max(800, min(_height, 4000)), scrolling=True)

    tab_seba, tab_ro = st.tabs(["Perfo Seba", "Perfo Ro"])
    with tab_seba:
        try:
            _render_perfo_closer(_cargar_bbdd_seba(), "Seba")
        except Exception as _e_seba:
            st.error(f"Error cargando datos de Seba: {_e_seba}")
    with tab_ro:
        try:
            _render_perfo_closer(_cargar_bbdd_ro(), "Ro")
        except Exception as _e_ro:
            st.error(f"Error cargando datos de Ro: {_e_ro}")
