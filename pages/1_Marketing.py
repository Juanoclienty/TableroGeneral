"""
app.py — Dashboard de Marketing y Ventas (Clienty)
Para correr: streamlit run app.py
"""
import os
import calendar as _cal
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import datos
import datos_crm
import graficos

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
st.set_page_config(
    page_title="Dashboard Clienty",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.5rem; }
    .section-title {
        font-size: 0.95rem; font-weight: 700; color: #1e293b;
        border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPERS DE UI
# ============================================================

def _fmt_pct(n: int, total: int) -> str:
    if total == 0:
        return f"{n} (–)"
    return f"{n} ({round(n / total * 100)}%)"


def _fila_totalizador(df_raw: pd.DataFrame) -> dict:
    leads = int(df_raw["leads"].sum())
    gf    = int(df_raw["gf"].sum())
    bf    = int(df_raw["bf"].sum())
    pf    = int(df_raw["pf"].sum())
    sd    = int(df_raw["sin_data"].sum())
    inv   = df_raw["inversion"].sum()
    return {
        "Leads"    : leads,
        "GF"       : _fmt_pct(gf, leads),
        "BF"       : _fmt_pct(bf, leads),
        "PF"       : _fmt_pct(pf, leads),
        "s/d"      : _fmt_pct(sd, leads),
        "% GF"     : f"{round(gf/leads*100)}%" if leads > 0 else "–",
        "Inversión": f"${inv:,.0f}",
        "CPL"      : f"${inv/leads:.0f}" if leads > 0 else "–",
        "CPL GF"   : f"${inv/gf:.0f}"   if gf    > 0 else "–",
    }


def _semanas_cerradas_rango(n_semanas: int = 8, excluir_ultimas: int = 0):
    hoy = date.today()
    dias_hasta_domingo = (hoy.weekday() + 1) % 7 or 7
    ultimo_domingo = hoy - timedelta(days=dias_hasta_domingo)
    fin    = ultimo_domingo - timedelta(weeks=excluir_ultimas)
    inicio = fin - timedelta(weeks=n_semanas) + timedelta(days=1)
    return inicio, fin


def _meses_rango(n_meses: int = 1):
    """Devuelve (inicio, fin) para los últimos N meses incluyendo el actual."""
    hoy = date.today()
    mes_ini = hoy.month - (n_meses - 1)
    año_ini = hoy.year
    while mes_ini <= 0:
        mes_ini += 12
        año_ini -= 1
    return date(año_ini, mes_ini, 1), hoy


def _obj_numeros(df_vista: pd.DataFrame, obj: dict) -> dict:
    """
    Objetivos proporcionales al período mostrado, mes a mes, capando en hoy.
    Retorna valores numéricos: leads, gf, inversion, cpl, cpl_gf.
    Para el mes en curso usa (días transcurridos / días del mes) como ratio.
    """
    if df_vista.empty:
        return {"leads": 0, "gf": 0, "inversion": 0.0, "cpl": 0.0, "cpl_gf": 0.0}
    fecha_ini = df_vista["fecha_ini"].min()
    fecha_fin = df_vista["fecha_fin"].max()
    hoy = pd.Timestamp.today().normalize()

    leads_obj = inv_obj = gf_obj = 0.0
    mes = fecha_ini.to_period("M")
    fin_p = fecha_fin.to_period("M")
    while mes <= fin_p:
        y, m = mes.year, mes.month
        days_in_month = _cal.monthrange(y, m)[1]
        overlap_start = max(fecha_ini, pd.Timestamp(y, m, 1))
        # Capear en hoy para que el mes en curso no compute el mes entero
        overlap_end   = min(fecha_fin, hoy, pd.Timestamp(y, m, days_in_month))
        if overlap_end < overlap_start:
            mes += 1
            continue
        ratio = ((overlap_end - overlap_start).days + 1) / days_in_month
        leads_obj += (obj["leads"].get(m) or 0) * ratio
        gf_obj    += (obj["gf"].get(m)    or 0) * ratio
        inv_obj   += (obj["inversion"].get(m) or 0) * ratio
        mes += 1

    cpl    = inv_obj / leads_obj if leads_obj > 0 else 0.0
    cpl_gf = inv_obj / gf_obj   if gf_obj   > 0 else 0.0
    return {
        "leads": round(leads_obj), "gf": round(gf_obj),
        "inversion": inv_obj, "cpl": cpl, "cpl_gf": cpl_gf,
    }


def _obj_numeros_sin_cap(df_sel: pd.DataFrame, obj: dict) -> dict:
    """
    Igual que _obj_numeros pero SIN capear en hoy.
    Usado para el objetivo de la selección: mes completo si es un mes,
    o 7/días_del_mes si es una semana.
    """
    if df_sel.empty:
        return {"leads": 0, "gf": 0, "inversion": 0.0, "cpl": 0.0, "cpl_gf": 0.0}
    fecha_ini = df_sel["fecha_ini"].min()
    fecha_fin = df_sel["fecha_fin"].max()

    leads_obj = inv_obj = gf_obj = 0.0
    mes = fecha_ini.to_period("M")
    fin_p = fecha_fin.to_period("M")
    while mes <= fin_p:
        y, m = mes.year, mes.month
        days_in_month = _cal.monthrange(y, m)[1]
        overlap_start = max(fecha_ini, pd.Timestamp(y, m, 1))
        overlap_end   = min(fecha_fin, pd.Timestamp(y, m, days_in_month))
        if overlap_end < overlap_start:
            mes += 1
            continue
        ratio = ((overlap_end - overlap_start).days + 1) / days_in_month
        leads_obj += (obj["leads"].get(m) or 0) * ratio
        gf_obj    += (obj["gf"].get(m)    or 0) * ratio
        inv_obj   += (obj["inversion"].get(m) or 0) * ratio
        mes += 1

    cpl    = inv_obj / leads_obj if leads_obj > 0 else 0.0
    cpl_gf = inv_obj / gf_obj   if gf_obj   > 0 else 0.0
    return {
        "leads": round(leads_obj), "gf": round(gf_obj),
        "inversion": inv_obj, "cpl": cpl, "cpl_gf": cpl_gf,
    }


def _fmt_obj_fila(n: dict) -> dict:
    """Convierte dict numérico de objetivo a dict de strings para la tabla."""
    if not n["leads"]:
        return {}
    leads_r = n["leads"]
    gf_r    = n["gf"]
    return {
        "Leads"    : leads_r,
        "GF"       : _fmt_pct(gf_r, leads_r),
        "BF"       : "–", "PF": "–", "s/d": "–",
        "% GF"     : f"{round(gf_r / leads_r * 100) if leads_r else 0}%",
        "Inversión": f"${n['inversion']:,.0f}",
        "CPL"      : f"${n['cpl']:.0f}",
        "CPL GF"   : f"${n['cpl_gf']:.0f}",
    }


def _fila_objetivo(df_vista: pd.DataFrame, obj: dict) -> dict:
    """Objetivo proporcional capado en hoy (para resumen del período completo)."""
    return _fmt_obj_fila(_obj_numeros(df_vista, obj))


def _fila_objetivo_sel(df_sel: pd.DataFrame, obj: dict) -> dict:
    """Objetivo sin capear en hoy (para la fila de selección)."""
    return _fmt_obj_fila(_obj_numeros_sin_cap(df_sel, obj))


def _guardar_comentarios(comentarios: list) -> str:
    hoy    = datetime.now().strftime("%d-%m-%Y")
    nombre = f"comentarios - {hoy}.txt"
    ruta   = os.path.join(os.path.dirname(__file__), nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(f"=== Comentarios del dashboard — {hoy} ===\n\n")
        por_semana = {}
        for c in comentarios:
            por_semana.setdefault(c["semana"], []).append(c)
        for semana, items in por_semana.items():
            f.write(f"--- {semana} ---\n")
            for c in items:
                f.write(f"  [{c['ts']}] Variable: {c['variable']} | {c['texto']}\n")
            f.write("\n")
    return ruta


# ============================================================
# INICIALIZAR SESSION STATE
# ============================================================
if "comentarios" not in st.session_state:
    st.session_state.comentarios = []
if "confirmar_recarga" not in st.session_state:
    st.session_state.confirmar_recarga = False


# ============================================================
# CARGA DE DATOS (caché local Parquet, se renueva cada día)
# ============================================================
@st.cache_resource(show_spinner="Cargando datos...")
def _cargar_todo():
    df_crm = datos_crm.cargar_crm()
    df_ads = datos.cargar_ads()
    obj    = datos.cargar_objetivos()
    df_sem = datos_crm.calcular_semanas_crm(df_crm, df_ads)
    df_men = datos_crm.cargar_meses_compartido()   # caché compartido con T90
    return df_crm, df_ads, obj, df_sem, df_men

try:
    df_crm, df_ads, obj, df_sem, df_men = _cargar_todo()
except Exception as e:
    st.error(f"Error al cargar datos: {e}")
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("📊 Dashboard Clienty")
    st.markdown("---")

    vista = st.radio("", ["Sem", "Mes", "Día"], horizontal=True, label_visibility="collapsed")

    st.markdown("")

    fecha_min_data = df_sem["fecha_ini"].min().date()
    fecha_max_data = df_sem["fecha_fin"].max().date()

    # ── Chips rápidos ─────────────────────────────────────────
    _skey = f"mkt_n_{vista}"
    _sdef = {"Día": 15, "Sem": 8, "Mes": 3}
    if _skey not in st.session_state:
        st.session_state[_skey] = _sdef[vista]

    if vista == "Día":
        _cx1, _cx2 = st.columns(2)
        if _cx1.button("Ult. 7 días",  use_container_width=True):
            st.session_state[_skey] = 7;  st.rerun()
        if _cx2.button("Ult. 15 días", use_container_width=True):
            st.session_state[_skey] = 15; st.rerun()
    elif vista == "Sem":
        _cx1, _cx2 = st.columns(2)
        if _cx1.button("Esta sem.",   use_container_width=True):
            st.session_state[_skey] = 1; st.rerun()
        if _cx2.button("Ult. 8 sem.", use_container_width=True):
            st.session_state[_skey] = 8; st.rerun()
    else:
        _cx1, _cx2 = st.columns(2)
        if _cx1.button("Este mes",      use_container_width=True):
            st.session_state[_skey] = 1; st.rerun()
        if _cx2.button("Ult. 3 meses", use_container_width=True):
            st.session_state[_skey] = 3; st.rerun()

    # Calcular fechas desde session_state (el slider las refinará en main area)
    _n = st.session_state[_skey]
    if vista == "Día":
        _max_dias = min(max(1, (date.today() - timedelta(days=1) - fecha_min_data).days + 1), 60)
        _n = min(_n, _max_dias)
        fecha_hasta = date.today() - timedelta(days=1)
        fecha_desde = fecha_hasta - timedelta(days=_n - 1)
    elif vista == "Sem":
        _max_sem = min(max(1, len(df_sem)), 24)
        _n = min(_n, _max_sem)
        fecha_hasta = fecha_max_data
        fecha_desde = fecha_hasta - timedelta(weeks=_n) + timedelta(days=1)
    else:
        _max_mes = min(max(1, len(df_men)), 12)
        _n = min(_n, _max_mes)
        fecha_hasta = fecha_max_data
        fecha_desde = _meses_rango(_n)[0]

    # ── Chips Ads (pestaña Ads) ───────────────────────────────
    _akey = f"ads_n_{vista}"
    _adef = {"Día": 15, "Sem": 8, "Mes": 3}
    if _akey not in st.session_state:
        st.session_state[_akey] = _adef[vista]

    st.caption("Ads")
    if vista == "Día":
        _ax1, _ax2 = st.columns(2)
        if _ax1.button("Ult. 7 días",  key="ads_sb1", use_container_width=True):
            st.session_state[_akey] = 7;  st.rerun()
        if _ax2.button("Ult. 15 días", key="ads_sb2", use_container_width=True):
            st.session_state[_akey] = 15; st.rerun()
    elif vista == "Sem":
        _ax1, _ax2 = st.columns(2)
        if _ax1.button("Esta sem.",    key="ads_sb1", use_container_width=True):
            st.session_state[_akey] = 1;  st.rerun()
        if _ax2.button("Ult. 8 sem.", key="ads_sb2", use_container_width=True):
            st.session_state[_akey] = 8;  st.rerun()
    else:
        _ax1, _ax2 = st.columns(2)
        if _ax1.button("Este mes",      key="ads_sb1", use_container_width=True):
            st.session_state[_akey] = 1;  st.rerun()
        if _ax2.button("Ult. 3 meses", key="ads_sb2", use_container_width=True):
            st.session_state[_akey] = 3;  st.rerun()

    st.markdown("---")

    # Calidad — sin título, sin "Solo"
    filtro_calidad = st.radio("", ["Todos", "GF", "BF", "PF"],
                              horizontal=True, label_visibility="collapsed")

    st.markdown("---")

    if st.button("🔄 Recargar datos", use_container_width=True):
        if st.session_state.comentarios:
            st.session_state.confirmar_recarga = True
        else:
            datos_crm.limpiar_cache()
            _cargar_todo.clear()
            st.rerun()

    if st.session_state.confirmar_recarga:
        st.warning("Tenés comentarios sin guardar. ¿Qué hacemos?")
        c1, c2 = st.columns(2)
        if c1.button("💾 Guardar y recargar", use_container_width=True):
            ruta = _guardar_comentarios(st.session_state.comentarios)
            st.session_state.comentarios = []
            st.session_state.confirmar_recarga = False
            st.success(f"Guardado en: {ruta}")
            datos_crm.limpiar_cache()
            _cargar_todo.clear()
            st.rerun()
        if c2.button("🗑️ Descartar y recargar", use_container_width=True):
            st.session_state.comentarios = []
            st.session_state.confirmar_recarga = False
            datos_crm.limpiar_cache()
            _cargar_todo.clear()
            st.rerun()

    st.markdown("---")
    st.caption("Fuentes: CRM Clienty (API) · Ads · Objetivos")


# ============================================================
# PREPARAR DATOS SEGÚN VISTA Y FILTROS
# ============================================================
calidad_map = {"GF": "R1F", "BF": "R1BF", "PF": "R1PBF"}

if vista == "Día":
    df_crm_f = df_crm if filtro_calidad == "Todos" else df_crm[df_crm["calidad"] == calidad_map[filtro_calidad]]
    df_vista = datos_crm.calcular_dias_crm(df_crm_f, df_ads, dias=15)

elif vista == "Mes":
    base = df_men if filtro_calidad == "Todos" else datos_crm.calcular_meses_crm(
        df_crm[df_crm["calidad"] == calidad_map[filtro_calidad]], df_ads)
    mask = (base["fecha_ini"] >= pd.Timestamp(fecha_desde)) & (base["fecha_ini"] <= pd.Timestamp(fecha_hasta))
    df_vista = base[mask].copy()

else:  # Semana
    base = df_sem if filtro_calidad == "Todos" else datos_crm.calcular_semanas_crm(
        df_crm[df_crm["calidad"] == calidad_map[filtro_calidad]], df_ads)
    mask = (base["fecha_ini"] >= pd.Timestamp(fecha_desde)) & (base["fecha_fin"] <= pd.Timestamp(fecha_hasta))
    df_vista = base[mask].copy()


# ============================================================
# PREPARAR TABLA PARA MOSTRAR
# ============================================================
def _preparar_display(df_raw: pd.DataFrame, vista: str) -> pd.DataFrame:
    df = df_raw.copy()

    for col in ["gf", "bf", "pf", "sin_data"]:
        df[col] = df.apply(lambda r: _fmt_pct(int(r[col]) if pd.notna(r[col]) else 0,
                                               int(r["leads"]) if pd.notna(r["leads"]) else 0), axis=1)

    df["inversion_fmt"] = df["inversion"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "–")
    df["cpl_fmt"]       = df["cpl"].apply(lambda x: f"${x:.0f}" if pd.notna(x) else "–")
    df["cpl_gf_fmt"]    = df["cpl_gf"].apply(lambda x: f"${x:.0f}" if pd.notna(x) else "–")
    df["pct_gf_fmt"]    = df["pct_gf"].apply(lambda x: f"{x:.0f}%" if pd.notna(x) else "–")

    if vista == "Día":
        df["Fecha"] = df["fecha_ini"].dt.strftime("%d/%m/%y")
    elif vista == "Mes":
        df["Período"] = df["fecha_ini"].dt.strftime("%m/%Y")
    else:
        df["Ini-Fin"] = (df["fecha_ini"].dt.strftime("%d/%m") + " – " +
                         df["fecha_fin"].dt.strftime("%d/%m"))
    return df


# ============================================================
# HEADER
# ============================================================
st.markdown("## Marketing")

tab_resumen, tab_ads, tab_evo = st.tabs(["Resumen", "Ads", "Evolución"])

with tab_resumen:
    n_filas   = len(df_vista)
    leads_tot = int(df_vista["leads"].sum()) if not df_vista.empty else 0
    sufijo_vista = {"Sem": f"{n_filas} semanas", "Mes": f"{n_filas} meses", "Día": f"{n_filas} días"}
    _url_obj = "https://docs.google.com/spreadsheets/d/1rOa7MvHxXUiU8nEMb5cKTyv8lMvPuZzrAT8Wj0KuD40/edit"
    st.caption(f"Vista: **{vista}** · {sufijo_vista.get(vista, '')} · {leads_tot:,} leads · [Ver objetivos]({_url_obj})")

    if not df_vista.empty:
        gf_tot   = int(df_vista["gf"].sum())
        inv_tot  = df_vista["inversion"].sum()
        cpl_p    = inv_tot / leads_tot if leads_tot > 0 else 0
        cpl_gf_p = inv_tot / gf_tot   if gf_tot   > 0 else 0
        _on = _obj_numeros(df_vista, obj)

        def _metric_card(label: str, real, obj_val, prefijo: str = "", inverse: bool = False, extra: str = "") -> str:
            """Genera HTML de una métrica con formato: valor / vs obj / abs · %."""
            if obj_val and obj_val != 0:
                abs_d = real - obj_val
                pct   = real / obj_val * 100
                # Verde si mejor, rojo si peor (inverse = menor es mejor)
                bueno = (abs_d <= 0) if inverse else (abs_d >= 0)
                color = "#16a34a" if bueno else "#dc2626"
                bg    = "#f0fdf4" if bueno else "#fef2f2"
                abs_fmt = f"{prefijo}{abs_d:+,.0f}" if not prefijo else f"{'+' if abs_d >= 0 else ''}{prefijo}{abs(abs_d):,.0f}"
                obj_fmt = f"{prefijo}{obj_val:,.0f}"
                real_fmt = f"{prefijo}{real:,.0f}"
                delta_html = (
                    f"<div style='font-size:0.72rem;color:#64748b;margin-top:2px'>vs obj {obj_fmt}</div>"
                    f"<div style='font-size:0.78rem;font-weight:600;color:{color};background:{bg};"
                    f"display:inline-block;padding:1px 6px;border-radius:4px;margin-top:2px'>"
                    f"{abs_d:+,.0f} / {pct:.1f}%</div>"
                )
            else:
                real_fmt = f"{prefijo}{real:,.0f}"
                delta_html = ""
            extra_html = f"<span style='font-size:0.72rem;color:#94a3b8;margin-left:4px'>{extra}</span>" if extra else ""
            return (
                f"<div style='padding:8px 0'>"
                f"<div style='font-size:0.78rem;color:#64748b;font-weight:500'>{label}</div>"
                f"<div style='font-size:1.4rem;font-weight:700;color:#1e293b'>{real_fmt}{extra_html}</div>"
                f"{delta_html}"
                f"</div>"
            )

        _pct_gf = f"{round(gf_tot/leads_tot*100) if leads_tot else 0}%"
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.markdown(_metric_card("Leads",    leads_tot, _on["leads"]),                    unsafe_allow_html=True)
        k2.markdown(_metric_card("GF",       gf_tot,    _on["gf"],    extra=_pct_gf),     unsafe_allow_html=True)
        k3.markdown(_metric_card("Inversión",inv_tot,   _on["inversion"], prefijo="$", inverse=True), unsafe_allow_html=True)
        k4.markdown(_metric_card("CPL",      cpl_p,     _on["cpl"],   prefijo="$", inverse=True),     unsafe_allow_html=True)
        k5.markdown(_metric_card("CPL GF",   cpl_gf_p,  _on["cpl_gf"],prefijo="$", inverse=True),    unsafe_allow_html=True)

        # Aclaración del intervalo usado para los objetivos
        _MESES_ES = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                     7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
        _fi = df_vista["fecha_ini"].min()
        _ff = min(df_vista["fecha_fin"].max(), pd.Timestamp.today().normalize())
        _partes = []
        _mes = _fi.to_period("M")
        while _mes <= _ff.to_period("M"):
            _y, _m = _mes.year, _mes.month
            _dim = _cal.monthrange(_y, _m)[1]
            _os = max(_fi, pd.Timestamp(_y, _m, 1))
            _oe = min(_ff, pd.Timestamp(_y, _m, _dim))
            _dias = (_oe - _os).days + 1
            _nombre = _MESES_ES[_m]
            _partes.append(_nombre if _dias == _dim else f"{_dias} días de {_nombre}")
            _mes += 1
        st.markdown(f"<p style='font-size:0.72rem;color:#94a3b8;margin-top:12px'>Objetivo = {' + '.join(_partes)}</p>", unsafe_allow_html=True)

    st.markdown("---")

    # ── Slider + título de tabla ──────────────────────────────
    _skey = f"mkt_n_{vista}"
    _slabels = {"Día": "Días a mostrar", "Sem": "Semanas a mostrar", "Mes": "Meses a mostrar"}
    if vista == "Día":
        _max_v = min(max(1, (date.today() - timedelta(days=1) - fecha_min_data).days + 1), 60)
    elif vista == "Sem":
        _max_v = min(max(1, len(df_sem)), 24)
    else:
        _max_v = min(max(1, len(df_men)), 12)

    _col_tit_e, _col_sl_e = st.columns([2, 4])
    _col_tit_e.markdown('<p class="section-title">Embudo por período</p>', unsafe_allow_html=True)
    _n_slider = _col_sl_e.slider(
        _slabels[vista], min_value=1, max_value=_max_v,
        value=min(st.session_state[_skey], _max_v), key=_skey,
    )
    # Recalcular fechas y df_vista con el valor actual del slider
    calidad_map = {"GF": "R1F", "BF": "R1BF", "PF": "R1PBF"}
    if vista == "Día":
        fecha_hasta = date.today() - timedelta(days=1)
        fecha_desde = fecha_hasta - timedelta(days=_n_slider - 1)
        df_vista = datos_crm.calcular_dias_crm(df_crm_f, df_ads, dias=_n_slider)
    elif vista == "Sem":
        fecha_hasta = fecha_max_data
        fecha_desde = fecha_hasta - timedelta(weeks=_n_slider) + timedelta(days=1)
        _base_mkt = df_sem if filtro_calidad == "Todos" else datos_crm.calcular_semanas_crm(df_crm_f, df_ads)
        df_vista = _base_mkt[(_base_mkt["fecha_ini"] >= pd.Timestamp(fecha_desde)) & (_base_mkt["fecha_fin"] <= pd.Timestamp(fecha_hasta))].copy()
    else:
        fecha_hasta = fecha_max_data
        fecha_desde = _meses_rango(_n_slider)[0]
        _base_mkt = df_men if filtro_calidad == "Todos" else datos_crm.calcular_meses_crm(df_crm_f, df_ads)
        df_vista = _base_mkt[(_base_mkt["fecha_ini"] >= pd.Timestamp(fecha_desde)) & (_base_mkt["fecha_ini"] <= pd.Timestamp(fecha_hasta))].copy()

    col_tabla, col_graf = st.columns([3, 2], gap="medium")

    with col_tabla:
        if df_vista.empty:
            st.info("No hay datos para el período seleccionado.")
            filas_sel = []
        else:
            _exp = st.toggle("Ver BF / PF / s/d", key="mkt_embudo_expandido")

            df_disp = _preparar_display(df_vista, vista)
            _col_periodo = {"Día": "Fecha", "Mes": "Período", "Sem": "Ini-Fin"}[vista]
            _cols_base   = [_col_periodo, "leads", "gf"]
            _cols_det    = ["bf", "pf", "sin_data"]
            cols_show    = _cols_base + (_cols_det if _exp else []) + ["pct_gf_fmt", "inversion_fmt", "cpl_fmt", "cpl_gf_fmt"]

            rename_map = {"leads": "Leads", "gf": "GF", "bf": "BF", "pf": "PF", "sin_data": "s/d",
                          "pct_gf_fmt": "% GF", "inversion_fmt": "Inversión", "cpl_fmt": "CPL", "cpl_gf_fmt": "CPL GF"}

            # Columnas centradas
            _todas_cols = list(rename_map.values()) + [_col_periodo]
            _col_cfg = {c: st.column_config.TextColumn(c, width="small") for c in _todas_cols}

            df_show = df_disp[cols_show].rename(columns=rename_map)
            evento = st.dataframe(df_show, selection_mode="multi-row", on_select="rerun",
                                  use_container_width=True, hide_index=True, column_config=_col_cfg)
            filas_sel = evento.selection.rows if evento.selection else []

            # Totalizador / Objetivo — mismas columnas que la tabla
            _cols_tot_raw = ["leads", "gf"] + (_cols_det if _exp else []) + ["pct_gf_fmt", "inversion_fmt", "cpl_fmt", "cpl_gf_fmt"]
            _tot_rename   = {**rename_map}

            def _filtrar_fila_tot(fila: dict) -> dict:
                """Deja solo las columnas visibles en la tabla."""
                _claves = [""] + [rename_map.get(c, c) for c in _cols_tot_raw]
                return {k: fila.get(k, "–") for k in _claves}

            if filas_sel:
                df_sel_raw = df_vista.iloc[filas_sel]
                rows_tot = [
                    _filtrar_fila_tot({"": "📌 SELECCIÓN"}        | _fila_totalizador(df_sel_raw)),
                    _filtrar_fila_tot({"": "🎯 OBJETIVO selección"} | _fila_objetivo_sel(df_sel_raw, obj)),
                ]
            else:
                rows_tot = [
                    _filtrar_fila_tot({"": "📊 TOTAL período"}    | _fila_totalizador(df_vista)),
                    _filtrar_fila_tot({"": "🎯 OBJETIVO período"}  | _fila_objetivo(df_vista, obj)),
                ]

            df_totales = pd.DataFrame(rows_tot)
            def _style_totales(row):
                label = str(row.iloc[0])
                if "TOTAL" in label:    bg = "#f1f5f9"
                elif "OBJETIVO" in label: bg = "#fef9c3"
                else:                   bg = "#e0f2fe"
                return [f"background-color: {bg}; font-weight: bold; text-align: center"] * len(row)
            st.dataframe(df_totales.style.apply(_style_totales, axis=1), use_container_width=True, hide_index=True)
            st.caption("💡 Hacé click en una o más filas para ver el detalle →")

    with col_graf:
        st.markdown('<p class="section-title">Evolución vs Objetivo</p>', unsafe_allow_html=True)

        import plotly.graph_objects as _go

        _metrica_evo = st.radio(
            "",
            ["Leads", "GF", "Inversión", "CPL", "CPL GF"],
            horizontal=True,
            label_visibility="collapsed",
            key="mkt_evo_metrica",
        )

        _col_evo = {"Leads": "leads", "GF": "gf", "Inversión": "inversion", "CPL": "cpl", "CPL GF": "cpl_gf"}[_metrica_evo]
        _obj_key = {"Leads": "leads", "GF": "gf", "Inversión": "inversion", "CPL": "cpl", "CPL GF": "cpl_gf"}[_metrica_evo]
        _prefix  = "$" if _metrica_evo in ("Inversión", "CPL", "CPL GF") else ""
        _is_rate = _metrica_evo in ("CPL", "CPL GF")  # tasas: obj directo del mes, no proporcional

        def _obj_periodo(row) -> float:
            """Objetivo proporcional para una fila de df_vista (día, semana o mes)."""
            fi   = row["fecha_ini"]
            ff   = row["fecha_fin"]
            hoy  = pd.Timestamp.today().normalize()
            tot_leads = tot_gf = tot_inv = 0.0
            mes  = fi.to_period("M")
            finp = min(ff, hoy).to_period("M")
            while mes <= finp:
                y, m = mes.year, mes.month
                dim  = _cal.monthrange(y, m)[1]
                os_  = max(fi, pd.Timestamp(y, m, 1))
                oe_  = min(ff, hoy, pd.Timestamp(y, m, dim))
                if oe_ < os_:
                    mes += 1; continue
                ratio = ((oe_ - os_).days + 1) / dim
                tot_leads += (obj["leads"].get(m) or 0) * ratio
                tot_gf    += (obj["gf"].get(m)    or 0) * ratio
                tot_inv   += (obj["inversion"].get(m) or 0) * ratio
                mes += 1
            if _obj_key == "leads":    return tot_leads
            if _obj_key == "gf":       return tot_gf
            if _obj_key == "inversion":return tot_inv
            # CPL / CPL GF: tasa proporcional
            if _obj_key == "cpl":    return tot_inv / tot_leads if tot_leads else 0
            if _obj_key == "cpl_gf": return tot_inv / tot_gf   if tot_gf   else 0
            return 0.0

        if not df_vista.empty:
            _dm = df_vista.copy()
            # Etiqueta del eje X según vista
            if vista == "Mes":
                _dm["_lbl"] = _dm["fecha_ini"].dt.strftime("%m/%Y")
            elif vista == "Sem":
                _dm["_lbl"] = (_dm["fecha_ini"].dt.strftime("%d/%m") + "–" +
                               _dm["fecha_fin"].dt.strftime("%d/%m"))
            else:
                _dm["_lbl"] = _dm["fecha_ini"].dt.strftime("%d/%m")

            _vals  = _dm[_col_evo].tolist()
            _lbls  = _dm["_lbl"].tolist()
            _objs  = [_obj_periodo(row) for _, row in _dm.iterrows()]
            _colors = ["#16a34a" if v >= o else "#dc2626" for v, o in zip(_vals, _objs)]

            _fig_evo = _go.Figure()
            _fig_evo.add_trace(_go.Bar(
                x=_lbls, y=_vals,
                marker_color=_colors,
                text=[f"{_prefix}{v:,.0f}" for v in _vals],
                textposition="inside",
                insidetextanchor="middle",
                name=_metrica_evo,
            ))
            _fig_evo.add_trace(_go.Scatter(
                x=_lbls, y=_objs,
                mode="lines+markers+text",
                line=dict(color="#1e40af", dash="dash", width=2),
                marker=dict(size=7, color="#1e40af"),
                text=[f"{_prefix}{o:,.0f}" for o in _objs],
                textposition="top center",
                textfont=dict(size=10, color="#1e40af"),
                name="Objetivo",
            ))
            _fig_evo.update_layout(
                height=350,
                margin=dict(l=10, r=10, t=10, b=30),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                yaxis=dict(title=_metrica_evo),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(_fig_evo, use_container_width=True)

    st.markdown("---")
    with st.expander("💬 Comentarios del período", expanded=False):
        st.caption("Los comentarios se guardan en sesión.")
        with st.form("form_comentario", clear_on_submit=True):
            c_col1, c_col2 = st.columns([2, 3])
            if not df_vista.empty:
                opciones_sem = []
                for _, row in df_vista.iterrows():
                    fi = row["fecha_ini"].strftime("%d/%m/%y")
                    ff = row["fecha_fin"].strftime("%d/%m/%y") if row["fecha_fin"] != row["fecha_ini"] else fi
                    opciones_sem.append(f"{fi}–{ff}")
                semana_sel = c_col1.selectbox("Semana / período", opciones_sem)
            else:
                semana_sel = c_col1.text_input("Período (manual)")
            variable_sel = c_col2.selectbox("Variable", ["Leads", "GF", "BF", "PF", "s/d", "% GF", "Inversión", "CPL", "CPL GF", "General"])
            texto_com = st.text_area("Comentario", placeholder="Escribí tu observación acá...")
            enviado = st.form_submit_button("➕ Agregar comentario")
            if enviado and texto_com.strip():
                st.session_state.comentarios.append({"ts": datetime.now().strftime("%d/%m/%Y %H:%M"), "semana": semana_sel, "variable": variable_sel, "texto": texto_com.strip()})
                st.success("Comentario agregado.")
        if st.session_state.comentarios:
            st.markdown("**Comentarios cargados en esta sesión:**")
            for i, c in enumerate(st.session_state.comentarios):
                col_c, col_x = st.columns([10, 1])
                col_c.markdown(f"**{c['semana']}** | *{c['variable']}* · {c['ts']}  \n{c['texto']}")
                if col_x.button("✕", key=f"del_com_{i}", help="Eliminar"):
                    st.session_state.comentarios.pop(i)
                    st.rerun()
            contenido_txt = "\n".join(f"[{c['ts']}] {c['semana']} | Variable: {c['variable']} | {c['texto']}" for c in st.session_state.comentarios)
            st.download_button("⬇️ Descargar comentarios TXT", data=contenido_txt.encode("utf-8"),
                               file_name=f"comentarios - {datetime.now().strftime('%d-%m-%Y')}.txt", mime="text/plain")
        else:
            st.info("Sin comentarios en esta sesión.")


# ============================================================
# TAB ADS
# ============================================================
with tab_ads:
    # ── Carga de datos ─────────────────────────────────────────
    @st.cache_resource(show_spinner=False)
    def _cargar_ads_detalle():
        return datos.cargar_ads_detalle()

    _df_ads_sem, _df_ads_mes, _ads_ts = _cargar_ads_detalle()

    # Combinar: sem tiene prioridad por mes
    _meses_en_sem = set(_df_ads_sem["mes_num"].unique())
    _df_ads_all   = pd.concat(
        [_df_ads_sem, _df_ads_mes[~_df_ads_mes["mes_num"].isin(_meses_en_sem)]],
        ignore_index=True)

    st.markdown('<p class="section-title">Detalle de Ads por período</p>', unsafe_allow_html=True)

    # ── Slider (usa session_state seteado desde sidebar) ──────
    _akey = f"ads_n_{vista}"

    # Calcular rango de fechas para ads (independiente del slider de marketing)
    if vista == "Día":
        _a_max = min(60, (date.today() - timedelta(days=1) - _df_ads_all["fecha_ini"].min().date()).days + 1)
        _a_n   = st.slider("Días a mostrar (Ads)", 1, max(1, _a_max),
                           min(st.session_state[_akey], max(1, _a_max)), key=_akey)
        _a_hasta = pd.Timestamp(date.today() - timedelta(days=1))
        _a_desde = _a_hasta - pd.Timedelta(days=_a_n - 1)
    elif vista == "Sem":
        _a_max = min(24, _df_ads_all["fecha_ini"].nunique())
        _a_n   = st.slider("Semanas a mostrar (Ads)", 1, max(1, _a_max),
                           min(st.session_state[_akey], max(1, _a_max)), key=_akey)
        _a_hasta = _df_ads_all["fecha_ini"].max()
        _a_desde = _a_hasta - pd.Timedelta(weeks=_a_n) + pd.Timedelta(days=1)
    else:
        _a_max = 12
        _a_n   = st.slider("Meses a mostrar (Ads)", 1, _a_max,
                           min(st.session_state[_akey], _a_max), key=_akey)
        _a_hasta = _df_ads_all["fecha_ini"].max()
        _a_desde = pd.Timestamp(_meses_rango(_a_n)[0])

    # Filtrar por rango
    _df_ads_f = _df_ads_all[
        (_df_ads_all["fecha_ini"] >= _a_desde) &
        (_df_ads_all["fecha_ini"] <= _a_hasta)
    ].copy()

    st.caption(f"Última actualización Ads: **{_ads_ts}**")

    # ── Agrupar por ────────────────────────────────────────────
    _agrupar_por = st.radio("Agrupar por", ["Ad", "Tipo de contenido", "Temática"],
                            horizontal=True, key="ads_agrupar")
    _grp_col_ads = {"Ad": "nombre_ad", "Tipo de contenido": "tipo", "Temática": "tematica"}[_agrupar_por]

    if _df_ads_f.empty:
        st.info("Sin datos para el período seleccionado.")
    else:
        # ── Etiqueta de período para columnas ──────────────────
        if vista == "Mes":
            _df_ads_f["_periodo_lbl"] = _df_ads_f["fecha_ini"].dt.strftime("%Y-%m")
        elif vista == "Sem":
            _df_ads_f["_periodo_lbl"] = (_df_ads_f["fecha_ini"].dt.strftime("%d/%m") + "–" +
                                          _df_ads_f["fecha_fin"].dt.strftime("%d/%m"))
        else:
            _df_ads_f["_periodo_lbl"] = _df_ads_f["fecha_ini"].dt.strftime("%d/%m/%y")

        # ── Pivot ──────────────────────────────────────────────
        _pivot = _df_ads_f.pivot_table(
            index=_grp_col_ads,
            columns="_periodo_lbl",
            values="inversion_usd",
            aggfunc="sum",
            fill_value=0,
        )
        # Ordenar columnas cronológicamente por fecha_ini
        _col_order = (
            _df_ads_f[["_periodo_lbl", "fecha_ini"]]
            .drop_duplicates()
            .sort_values("fecha_ini")["_periodo_lbl"]
            .tolist()
        )
        _col_order = [c for c in _col_order if c in _pivot.columns]
        _pivot = _pivot[_col_order]
        _pivot["Total"] = _pivot.sum(axis=1)
        _pivot = _pivot.sort_values("Total", ascending=False).reset_index()
        _pivot.rename(columns={_grp_col_ads: _agrupar_por}, inplace=True)

        # ── CRM: leads/presupuestos/ventas por ad ─────────────
        import re as _re2
        def _num_ad(s):
            m = _re2.search(r"\d+", str(s))
            return int(m.group()) if m else -1

        _utm_col = "utm_content" if "utm_content" in df_crm.columns else None
        _crm_f = df_crm[
            (df_crm["fecha_lead"] >= _a_desde) &
            (df_crm["fecha_lead"] <= _a_hasta)
        ].copy()
        if _utm_col:
            _crm_f = _crm_f[_crm_f[_utm_col].fillna("").str.strip() != ""]
        else:
            _crm_f = _crm_f.iloc[0:0]  # vacío si no hay columna utm
        _crm_f["_num"] = _crm_f[_utm_col].apply(_num_ad) if _utm_col else -1
        _crm_f = _crm_f[_crm_f["_num"] > 0]

        # Contar por número de ad
        _crm_grp = _crm_f.groupby("_num").agg(
            _leads=("id", "count"),
            _presu=("estado_resumen", lambda x: (x == "4. Presupuesto").sum() + (x == "5. Venta").sum()),
            _ventas=("estado_resumen", lambda x: (x == "5. Venta").sum()),
        ).reset_index()

        # Mapear num_ad → num de la columna de agrupación
        # Necesitamos saber qué _num corresponde a cada fila del pivot
        _cols_map = list(dict.fromkeys(["_periodo_lbl", _grp_col_ads, "nombre_ad"]))
        _ads_num_map = (
            _df_ads_f[_cols_map]
            .drop_duplicates()
            .reset_index(drop=True)
            .copy()
        )
        _ads_num_map["_num"] = _ads_num_map["nombre_ad"].apply(_num_ad).values
        _grp_crm = (
            _ads_num_map.merge(_crm_grp, on="_num", how="left")
            .groupby(_grp_col_ads)[["_leads", "_presu", "_ventas"]]
            .sum()
            .reset_index()
        )
        _grp_crm.rename(columns={_grp_col_ads: _agrupar_por}, inplace=True)
        _pivot = _pivot.merge(_grp_crm, on=_agrupar_por, how="left")
        for _c in ["_leads", "_presu", "_ventas"]:
            _pivot[_c] = _pivot[_c].fillna(0).astype(int)

        # CPL, CPE, CPV
        _pivot["_cpl"] = (_pivot["Total"] / _pivot["_leads"]).where(_pivot["_leads"] > 0)
        _pivot["_cpe"] = (_pivot["Total"] / _pivot["_presu"]).where(_pivot["_presu"] > 0)
        _pivot["_cpv"] = (_pivot["Total"] / _pivot["_ventas"]).where(_pivot["_ventas"] > 0)

        # ── Formateo ───────────────────────────────────────────
        def _fmt_usd(v):
            try:
                v = float(v)
            except Exception:
                return "–"
            return f"${v:,.0f}" if v > 0 else "–"

        def _fmt_int(v):
            try:
                v = int(v)
                return str(v) if v > 0 else "–"
            except Exception:
                return "–"

        _cols_periodo = [c for c in _pivot.columns
                         if c not in [_agrupar_por, "Total", "_leads", "_presu", "_ventas", "_cpl", "_cpe", "_cpv"]]
        _pivot_fmt = _pivot[[_agrupar_por] + _cols_periodo + ["Total"]].copy()
        for col in _cols_periodo + ["Total"]:
            _pivot_fmt[col] = _pivot[col].apply(_fmt_usd)

        _pivot_fmt["Leads"]        = _pivot["_leads"]
        _pivot_fmt["Presupuestos"] = _pivot["_presu"]
        _pivot_fmt["Ventas"]       = _pivot["_ventas"]
        _pivot_fmt["CPL"]          = _pivot["_cpl"]
        _pivot_fmt["CPE"]          = _pivot["_cpe"]
        _pivot_fmt["CPV"]          = _pivot["_cpv"]

        # Fila TOTAL
        _tot_inv    = _pivot["Total"].sum()
        _tot_leads  = _pivot["_leads"].sum()
        _tot_presu  = _pivot["_presu"].sum()
        _tot_ventas = _pivot["_ventas"].sum()
        _tot_row    = {_agrupar_por: "📊 TOTAL período"}
        for col in _cols_periodo:
            _tot_row[col] = _fmt_usd(_pivot[col].sum())
        _tot_row["Total"]        = _fmt_usd(_tot_inv)
        _tot_row["Leads"]        = int(_tot_leads)
        _tot_row["Presupuestos"] = int(_tot_presu)
        _tot_row["Ventas"]       = int(_tot_ventas)
        _tot_row["CPL"]          = _tot_inv / _tot_leads  if _tot_leads  else None
        _tot_row["CPE"]          = _tot_inv / _tot_presu  if _tot_presu  else None
        _tot_row["CPV"]          = _tot_inv / _tot_ventas if _tot_ventas else None
        _tot_df = pd.DataFrame([_tot_row])

        # ── Estilo ─────────────────────────────────────────────
        _cols_gris = ["Leads", "Presupuestos", "Ventas", "CPL", "CPE", "CPV"]

        def _style_ads_data(row):
            return [f"background-color: #e2e8f0" if col in _cols_gris else "" for col in row.index]

        def _style_ads_total(row):
            return [f"background-color: #f1f5f9; font-weight: bold" for _ in row.index]

        _col_cfg = {
            "Leads":        st.column_config.NumberColumn("Leads",        format="%d"),
            "Presupuestos": st.column_config.NumberColumn("Presupuestos", format="%d"),
            "Ventas":       st.column_config.NumberColumn("Ventas",       format="%d"),
            "CPL":          st.column_config.NumberColumn("CPL",          format="$%.0f"),
            "CPE":          st.column_config.NumberColumn("CPE",          format="$%.0f"),
            "CPV":          st.column_config.NumberColumn("CPV",          format="$%.0f"),
        }

        st.dataframe(
            _pivot_fmt.style.apply(_style_ads_data, axis=1),
            use_container_width=True, hide_index=True,
            column_config=_col_cfg,
        )
        st.dataframe(
            _tot_df.style.apply(_style_ads_total, axis=1),
            use_container_width=True, hide_index=True,
            column_config=_col_cfg,
        )

    # ── Botón actualizar al pie ────────────────────────────────
    st.markdown("---")
    if st.button("🔄 Actualizar datos Ads", use_container_width=False):
        with st.spinner("Descargando y procesando..."):
            datos.actualizar_cache_ads()
        _cargar_ads_detalle.clear()
        st.rerun()


# ============================================================
# TAB EVOLUCIÓN
# ============================================================
import urllib.request as _urllib_req
import io as _io
import plotly.graph_objects as go

_EVO_SHEET_ID   = "15BJQ-28m5KvAcQeE0Mp76UnIyUVjMK1O"
_EVO_CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache", "evolucion_t90.parquet")

_METRICAS = ["Inversión", "Leads", "Presupuestos", "Ventas", "CPL", "CPE", "CPV", "Tasa de cierre", "Tasa Vtas/Leads"]
_FORMATOS = {
    "Inversión": ("$", "", 0), "Leads": ("", "", 0), "Presupuestos": ("", "", 0),
    "Ventas": ("", "", 0), "CPL": ("$", "", 0), "CPE": ("$", "", 0), "CPV": ("$", "", 0),
    "Tasa de cierre": ("", "%", 1), "Tasa Vtas/Leads": ("", "%", 1),
}
_COLORES_EVO = ["#3b82f6","#f59e0b","#10b981","#ef4444","#8b5cf6","#06b6d4","#f97316","#ec4899","#84cc16"]
_G_PCT = {"Tasa de cierre", "Tasa Vtas/Leads"}


_EVO_KPI_MAP = {
    "Inversión publicidad":             "Inversión",
    "Presupuestos enviados reales":     "Presupuestos",
    "Ventas totales":                   "Ventas",
    "Tasa de cierre (Vta real/Presu real)": "Tasa de cierre",
    "Tasa Vtas /Leads":                 "Tasa Vtas/Leads",
}
_MESES_NOM = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]


def _fetch_evolucion_raw() -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{_EVO_SHEET_ID}/gviz/tq?tqx=out:csv&sheet=T90%20-%20mktVtas%20(Fran)"
    req = _urllib_req.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _urllib_req.urlopen(req) as r:
        raw = pd.read_csv(_io.StringIO(r.read().decode("utf-8")), header=None)

    # Fila 0 = años, Fila 1 = Area/KPI + números de mes, Filas 2+ = datos
    anios    = raw.iloc[0].tolist()
    periodos = raw.iloc[1].tolist()

    # Identificar columnas mensuales: año numérico (2025/2026) y periodo numérico (1-12)
    mes_cols = []
    mes_labels = []
    for i, (a, p) in enumerate(zip(anios, periodos)):
        try:
            anio = int(float(str(a)))
            mes  = int(float(str(p)))
            if 2024 <= anio <= 2030 and 1 <= mes <= 12:
                mes_cols.append(i)
                mes_labels.append(f"{_MESES_NOM[mes-1]} {anio}")
        except (ValueError, TypeError):
            pass

    # Filas de datos (desde fila 2), columnas KPI (col 1) + mensuales
    df_kpi = raw.iloc[2:, [1] + mes_cols].copy()
    df_kpi.columns = ["KPI"] + mes_labels
    df_kpi = df_kpi.dropna(subset=["KPI"])
    df_kpi = df_kpi[df_kpi["KPI"].astype(str).str.strip() != ""]
    df_kpi["KPI"] = df_kpi["KPI"].astype(str).str.strip().replace(_EVO_KPI_MAP)
    df_kpi = df_kpi.drop_duplicates(subset=["KPI"]).set_index("KPI")

    # Transponer: filas=periodos, columnas=KPIs
    df_t = df_kpi.T.reset_index().rename(columns={"index": "Periodo"})
    return df_t


@st.cache_data(ttl=86400)
def _cargar_evolucion() -> tuple:
    if os.path.exists(_EVO_CACHE_PATH):
        df = pd.read_parquet(_EVO_CACHE_PATH)
        fecha_str = pd.Timestamp(os.path.getmtime(_EVO_CACHE_PATH), unit="s").strftime("%d/%m/%Y %H:%M")
        return df, fecha_str
    df = _fetch_evolucion_raw()
    try:
        df.to_parquet(_EVO_CACHE_PATH, index=False)
    except Exception:
        pass
    return df, pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")


with tab_evo:
    col_ref, _ = st.columns([1, 4])
    with col_ref:
        if st.button("🔄 Actualizar Evolución", use_container_width=True):
            if os.path.exists(_EVO_CACHE_PATH):
                os.remove(_EVO_CACHE_PATH)
            _cargar_evolucion.clear()
            st.rerun()

    df_evo_raw, _fecha_evo = _cargar_evolucion()

    if df_evo_raw is None or df_evo_raw.empty:
        st.warning("No se pudieron cargar los datos. Presioná 'Actualizar Evolución'.")
    else:
        df_evo_raw.columns = [c.strip() for c in df_evo_raw.columns]
        col_periodo = next((c for c in df_evo_raw.columns if any(k in c.lower() for k in ["periodo","período","mes","month"])), df_evo_raw.columns[0])
        df_evo = df_evo_raw.dropna(subset=[col_periodo]).copy()
        df_evo = df_evo[df_evo[col_periodo].astype(str).str.strip() != ""].rename(columns={col_periodo: "Periodo"})
        for col in df_evo.columns:
            if col == "Periodo":
                continue
            # Formato argentino: "$1.234,56" → quitar $/%/espacios, quitar punto de miles, coma→punto decimal
            s = (df_evo[col].astype(str)
                 .str.replace(r"[$%\s]", "", regex=True)
                 .str.replace(r"\.(?=\d{3})", "", regex=True)   # punto de miles (seguido de 3 dígitos)
                 .str.replace(",", ".", regex=False))
            df_evo[col] = pd.to_numeric(s, errors="coerce")

        todos_periodos = df_evo["Periodo"].tolist()
        metricas_disponibles = [m for m in _METRICAS if m in df_evo.columns]

        if not metricas_disponibles:
            st.error("No se encontraron las columnas esperadas en el sheet.")
        else:
            metricas_sel = st.pills("Métricas", options=metricas_disponibles, selection_mode="multi", default=["Leads"])

            if metricas_sel:
                tiene_pct = any(m in _G_PCT for m in metricas_sel)
                tiene_abs = any(m not in _G_PCT for m in metricas_sel)
                doble_eje = tiene_pct and tiene_abs

                fig = go.Figure()
                for i, metrica in enumerate(metricas_sel):
                    if metrica not in df_evo.columns:
                        continue
                    df_m = df_evo[["Periodo", metrica]].dropna()
                    color = _COLORES_EVO[i % len(_COLORES_EVO)]
                    prefijo, sufijo, decimales = _FORMATOS.get(metrica, ("", "", 0))
                    def _fmt_label(v, p=prefijo, s=sufijo, d=decimales):
                        if s == "%": return f"{v:.{d}f}%"
                        return f"{p}{v:,.0f}{s}" if d == 0 else f"{p}{v:,.{d}f}{s}"
                    fig.add_trace(go.Scatter(
                        x=df_m["Periodo"], y=df_m[metrica],
                        mode="lines+markers+text",
                        text=[_fmt_label(v) for v in df_m[metrica]],
                        textposition="top center",
                        line=dict(color=color, width=2, shape="spline", smoothing=0.8),
                        marker=dict(size=6, color=color),
                        textfont=dict(size=10, color=color),
                        name=metrica,
                        yaxis="y2" if metrica in _G_PCT else "y",
                    ))

                idx_2026 = next((i for i, p in enumerate(todos_periodos) if "26" in str(p)), None)
                if idx_2026 and idx_2026 > 0:
                    fig.add_shape(type="line", x0=idx_2026-0.5, x1=idx_2026-0.5, y0=0, y1=1,
                                  xref="x", yref="paper", line=dict(color="#94a3b8", dash="dash", width=1.5))
                    fig.add_annotation(x=idx_2026-0.5, y=1, xref="x", yref="paper", text="2026",
                                       showarrow=False, font=dict(color="#64748b", size=11), xanchor="left", yanchor="bottom")

                layout_kwargs = dict(height=480, hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    margin=dict(l=10, r=10, t=40, b=40),
                    xaxis=dict(tickangle=-45, categoryorder="array", categoryarray=todos_periodos),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                if doble_eje:
                    layout_kwargs["yaxis2"] = dict(overlaying="y", side="right", tickformat=".0f", ticksuffix="%", showgrid=False)
                fig.update_layout(**layout_kwargs)
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"Última actualización: {_fecha_evo} · [Fuente: T90 Real – pestaña T90 - mktVtas](https://docs.google.com/spreadsheets/d/{_EVO_SHEET_ID}/edit)")
