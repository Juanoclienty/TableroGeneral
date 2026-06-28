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


def _obj_inv_proporcional(df_vista: pd.DataFrame, obj: dict) -> float:
    """Objetivo de inversión proporcional a los días del período mostrado."""
    if df_vista.empty:
        return 0.0
    fecha_ini = df_vista["fecha_ini"].min()
    fecha_fin = df_vista["fecha_fin"].max()
    dias = (fecha_fin - fecha_ini).days + 1
    mes_ref = fecha_fin.month
    return obj["inversion"].get(mes_ref, 23000) * dias / 30


def _fila_objetivo(df_vista: pd.DataFrame, obj: dict) -> dict:
    """
    Calcula objetivos proporcionales al período mostrado, mes a mes.
    Suma cada objetivo mensual ponderado por los días de overlap.
    """
    if df_vista.empty:
        return {}
    fecha_ini = df_vista["fecha_ini"].min()
    fecha_fin = df_vista["fecha_fin"].max()

    leads_obj = inv_obj = gf_obj = 0.0
    mes = fecha_ini.to_period("M")
    fin_p = fecha_fin.to_period("M")
    while mes <= fin_p:
        y, m = mes.year, mes.month
        days_in_month = _cal.monthrange(y, m)[1]
        overlap_start = max(fecha_ini, pd.Timestamp(y, m, 1))
        overlap_end   = min(fecha_fin, pd.Timestamp(y, m, days_in_month))
        ratio = (overlap_end - overlap_start).days + 1
        ratio /= days_in_month
        leads_obj += obj["leads"].get(m, 300) * ratio
        gf_obj    += obj["gf"].get(m, 240) * ratio
        inv_obj   += obj["inversion"].get(m, 23000) * ratio
        mes += 1

    leads_r = round(leads_obj)
    gf_r    = round(gf_obj)
    cpl_obj    = inv_obj / leads_obj if leads_obj > 0 else 0
    cpl_gf_obj = inv_obj / gf_obj   if gf_obj   > 0 else 0
    return {
        "Leads"    : leads_r,
        "GF"       : _fmt_pct(gf_r, leads_r),
        "BF"       : "–",
        "PF"       : "–",
        "s/d"      : "–",
        "% GF"     : f"{round(gf_obj/leads_obj*100) if leads_obj else 0}%",
        "Inversión": f"${inv_obj:,.0f}",
        "CPL"      : f"${cpl_obj:.0f}",
        "CPL GF"   : f"${cpl_gf_obj:.0f}",
    }


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
if "fecha_desde" not in st.session_state:
    st.session_state.fecha_desde = None
if "fecha_hasta" not in st.session_state:
    st.session_state.fecha_hasta = None


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

    vista = st.radio("", ["Semana", "Mes", "Día"], horizontal=True, label_visibility="collapsed")

    st.markdown("")

    fecha_min_data = df_sem["fecha_ini"].min().date()
    fecha_max_data = df_sem["fecha_fin"].max().date()

    if vista == "Día":
        st.caption("Vista Día: últimos 15 días desde ayer.")
        fecha_desde = fecha_min_data
        fecha_hasta = date.today() - timedelta(days=1)
    else:
        if st.session_state.fecha_desde is None:
            ini_def, fin_def = _semanas_cerradas_rango(8, 0)
            st.session_state.fecha_desde = ini_def
            st.session_state.fecha_hasta = fin_def

        col_d1, col_d2 = st.columns(2)
        fecha_desde = col_d1.date_input("Desde",
            value=st.session_state.fecha_desde,
            min_value=fecha_min_data, max_value=fecha_max_data,
            format="DD/MM/YYYY")
        fecha_hasta = col_d2.date_input("Hasta",
            value=st.session_state.fecha_hasta,
            min_value=fecha_min_data, max_value=fecha_max_data,
            format="DD/MM/YYYY")
        st.session_state.fecha_desde = fecha_desde
        st.session_state.fecha_hasta = fecha_hasta

        if vista == "Semana":
            col_8s, col_excl = st.columns(2)
            if col_8s.button("📅 8 sem.", help="Últimas 8 semanas cerradas", use_container_width=True):
                ini, fin = _semanas_cerradas_rango(8, 0)
                st.session_state.fecha_desde = ini
                st.session_state.fecha_hasta = fin
                st.rerun()
            if col_excl.button("📅 6 sem.", help="Semanas -8 a -2", use_container_width=True):
                ini, fin = _semanas_cerradas_rango(6, 2)
                st.session_state.fecha_desde = ini
                st.session_state.fecha_hasta = fin
                st.rerun()

        elif vista == "Mes":
            col_1m, col_3m = st.columns(2)
            if col_1m.button("📅 1 mes", help="Mes actual (1° hasta hoy)", use_container_width=True):
                ini, fin = _meses_rango(1)
                st.session_state.fecha_desde = ini
                st.session_state.fecha_hasta = fin
                st.rerun()
            if col_3m.button("📅 3 meses", help="Mes actual + 2 anteriores", use_container_width=True):
                ini, fin = _meses_rango(3)
                st.session_state.fecha_desde = ini
                st.session_state.fecha_hasta = fin
                st.rerun()

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
n_filas = len(df_vista)
leads_tot = int(df_vista["leads"].sum()) if not df_vista.empty else 0
sufijo_vista = {"Semana": f"{n_filas} semanas", "Mes": f"{n_filas} meses", "Día": f"{n_filas} días"}
st.caption(f"Vista: **{vista}** · {sufijo_vista.get(vista, '')} · {leads_tot:,} leads")


# ============================================================
# KPI CARDS — comparación con objetivos
# ============================================================
if not df_vista.empty:
    gf_tot   = int(df_vista["gf"].sum())
    inv_tot  = df_vista["inversion"].sum()
    cpl_p    = inv_tot / leads_tot if leads_tot > 0 else 0
    cpl_gf_p = inv_tot / gf_tot   if gf_tot   > 0 else 0
    mes_ref  = df_vista["fecha_ini"].iloc[-1].month

    obj_cpl_ref    = obj["cpl"].get(mes_ref, 74)
    obj_cpl_gf_ref = obj["cpl_gf"].get(mes_ref, 92)
    obj_leads_ref  = obj["leads"].get(mes_ref, 300)
    obj_gf_ref     = obj["gf"].get(mes_ref, 240)
    obj_inv_ref    = _obj_inv_proporcional(df_vista, obj)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Leads",
              f"{leads_tot:,}",
              f"{leads_tot - obj_leads_ref:+,.0f} vs obj {obj_leads_ref:,.0f}")
    k2.metric("GF",
              f"{gf_tot:,}",
              f"{gf_tot - obj_gf_ref:+,.0f} vs obj {obj_gf_ref:,.0f} · {round(gf_tot/leads_tot*100) if leads_tot else 0}%")
    k3.metric("Inversión",
              f"${inv_tot:,.0f}",
              f"{inv_tot - obj_inv_ref:+,.0f} vs obj ${obj_inv_ref:,.0f}",
              delta_color="inverse")
    k4.metric("CPL",
              f"${cpl_p:.0f}",
              f"{cpl_p - obj_cpl_ref:+.0f} vs obj ${obj_cpl_ref:.0f}",
              delta_color="inverse")
    k5.metric("CPL GF",
              f"${cpl_gf_p:.0f}",
              f"{cpl_gf_p - obj_cpl_gf_ref:+.0f} vs obj ${obj_cpl_gf_ref:.0f}",
              delta_color="inverse")

st.markdown("---")


# ============================================================
# TABLA + GRÁFICO
# ============================================================
col_tabla, col_graf = st.columns([3, 2], gap="medium")

with col_tabla:
    st.markdown('<p class="section-title">Embudo por período</p>', unsafe_allow_html=True)

    if df_vista.empty:
        st.info("No hay datos para el período seleccionado.")
        filas_sel = []
    else:
        df_disp = _preparar_display(df_vista, vista)

        if vista == "Día":
            cols_show = ["Fecha", "leads", "gf", "bf", "pf", "sin_data", "pct_gf_fmt",
                         "inversion_fmt", "cpl_fmt", "cpl_gf_fmt"]
        elif vista == "Mes":
            cols_show = ["Período", "leads", "gf", "bf", "pf", "sin_data", "pct_gf_fmt",
                         "inversion_fmt", "cpl_fmt", "cpl_gf_fmt"]
        else:
            cols_show = ["Ini-Fin", "leads", "gf", "bf", "pf", "sin_data", "pct_gf_fmt",
                         "inversion_fmt", "cpl_fmt", "cpl_gf_fmt"]

        rename_map = {
            "leads": "Leads", "gf": "GF", "bf": "BF", "pf": "PF",
            "sin_data": "s/d", "pct_gf_fmt": "% GF",
            "inversion_fmt": "Inversión", "cpl_fmt": "CPL", "cpl_gf_fmt": "CPL GF",
        }
        df_show = df_disp[cols_show].rename(columns=rename_map)

        evento = st.dataframe(
            df_show,
            selection_mode="multi-row",
            on_select="rerun",
            use_container_width=True,
            hide_index=True,
        )
        filas_sel = evento.selection.rows if evento.selection else []

        # ── Totalizador unificado ──
        rows_tot = [{"": "📊 TOTAL período"} | _fila_totalizador(df_vista)]
        if filas_sel:
            # Hay selección → segunda fila = selección
            df_sel_raw = df_vista.iloc[filas_sel]
            rows_tot.append({"": "📌 SELECCIÓN"} | _fila_totalizador(df_sel_raw))
        else:
            # Sin selección → segunda fila = objetivo del período
            rows_tot.append({"": "🎯 OBJETIVO período"} | _fila_objetivo(df_vista, obj))

        df_totales = pd.DataFrame(rows_tot)

        def _style_totales(row):
            label = str(row.iloc[0])
            if "TOTAL" in label:
                bg = "#f1f5f9"
            elif "OBJETIVO" in label:
                bg = "#fef9c3"   # amarillo suave
            else:
                bg = "#e0f2fe"   # azul (selección)
            return [f"background-color: {bg}; font-weight: bold"] * len(row)

        st.dataframe(
            df_totales.style.apply(_style_totales, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        st.caption("💡 Hacé click en una o más filas para ver el detalle →")


with col_graf:
    titulo_graf = {"Semana": "Leads por semana y CPL", "Mes": "Leads por mes y CPL", "Día": "Leads por día y CPL"}
    st.markdown(f'<p class="section-title">{titulo_graf[vista]}</p>', unsafe_allow_html=True)

    if df_vista.empty:
        st.info("Sin datos.")
    elif filas_sel:
        df_sel_raw = df_vista.iloc[filas_sel]
        leads_s  = int(df_sel_raw["leads"].sum())
        gf_s     = int(df_sel_raw["gf"].sum())
        inv_s    = df_sel_raw["inversion"].sum()
        cpl_s    = inv_s / leads_s if leads_s > 0 else 0
        cpl_gf_s = inv_s / gf_s   if gf_s   > 0 else 0
        pct_gf_s = round(gf_s / leads_s * 100) if leads_s > 0 else 0

        mes_s        = df_sel_raw["fecha_ini"].iloc[-1].month
        obj_cpl_s    = obj["cpl"].get(mes_s, 74)
        obj_cpl_gf_s = obj["cpl_gf"].get(mes_s, 92)
        obj_leads_s  = obj["leads"].get(mes_s, 300)
        obj_gf_s     = obj["gf"].get(mes_s, 240)
        obj_inv_s    = _obj_inv_proporcional(df_sel_raw, obj)

        lbl = (f"{df_sel_raw['fecha_ini'].min().strftime('%d/%m')} – "
               f"{df_sel_raw['fecha_fin'].max().strftime('%d/%m/%y')}")
        st.caption(f"Selección: {lbl}")

        # Métricas en una fila con comparación vs objetivo
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Leads",
                  f"{leads_s:,}",
                  f"{leads_s - obj_leads_s:+,.0f} vs {obj_leads_s:,.0f}")
        c2.metric("GF",
                  f"{gf_s:,}",
                  f"{gf_s - obj_gf_s:+,.0f} · {pct_gf_s}%")
        c3.metric("Inversión",
                  f"${inv_s:,.0f}",
                  f"{inv_s - obj_inv_s:+,.0f} vs ${obj_inv_s:,.0f}",
                  delta_color="inverse")
        c4.metric("CPL",
                  f"${cpl_s:.0f}",
                  f"{cpl_s - obj_cpl_s:+.0f} vs ${obj_cpl_s:.0f}",
                  delta_color="inverse")
        c5.metric("CPL GF",
                  f"${cpl_gf_s:.0f}",
                  f"{cpl_gf_s - obj_cpl_gf_s:+.0f} vs ${obj_cpl_gf_s:.0f}",
                  delta_color="inverse")

        st.plotly_chart(graficos.pie_y_metricas(df_sel_raw), use_container_width=True)
    else:
        st.caption("Sin selección — resumen general:")
        st.plotly_chart(graficos.bar_calidad_por_semana(df_vista), use_container_width=True)


# ============================================================
# SEÑALES TEMPRANAS (últimas 4 semanas, solo vista Semana)
# ============================================================
if vista == "Semana":
    st.markdown("---")
    st.markdown("## 🔍 Señales Tempranas")
    st.caption("Últimas 4 semanas — solo para la vista Semana")

    df_4 = df_sem.tail(4).copy()
    if not df_4.empty:
        registros = []
        for _, row in df_4.iterrows():
            mes     = row["fecha_ini"].month
            obj_c   = obj["cpl"].get(mes, 74)
            cpl_val = row["cpl"] if pd.notna(row["cpl"]) else 0
            diff    = cpl_val - obj_c
            registros.append({
                "Semana"   : row["fecha_ini"].strftime("%d/%m") + "–" + row["fecha_fin"].strftime("%d/%m/%y"),
                "Inversión": f'${row["inversion"]:,.0f}',
                "Leads"    : int(row["leads"]),
                "CPL"      : f"${cpl_val:.0f}",
                "CPL GF"   : f'${row["cpl_gf"]:.0f}' if pd.notna(row["cpl_gf"]) else "–",
                "% GF"     : f'{row["pct_gf"]:.0f}%'  if pd.notna(row["pct_gf"]) else "–",
                "Obj. CPL" : f"${obj_c:.0f}",
                "vs Obj."  : f"{diff:+.0f}" if cpl_val > 0 else "–",
            })

        def _color_fila(row):
            try:
                diff = float(str(row["vs Obj."]).replace("+", ""))
                bg = "#fef2f2" if diff > 0 else "#f0fdf4"
            except Exception:
                bg = ""
            return [f"background-color: {bg}" if bg else ""] * len(row)

        st.dataframe(
            pd.DataFrame(registros).style.apply(_color_fila, axis=1),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# SECCIÓN DE COMENTARIOS
# ============================================================
st.markdown("---")
with st.expander("💬 Comentarios del período", expanded=False):
    st.caption("Los comentarios se guardan en sesión. Al recargar datos se te preguntará si querés exportarlos a TXT.")

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

        variable_sel = c_col2.selectbox("Variable", [
            "Leads", "GF", "BF", "PF", "s/d", "% GF",
            "Inversión", "CPL", "CPL GF", "General"
        ])
        texto_com = st.text_area("Comentario", placeholder="Escribí tu observación acá...")
        enviado = st.form_submit_button("➕ Agregar comentario")

        if enviado and texto_com.strip():
            st.session_state.comentarios.append({
                "ts"      : datetime.now().strftime("%d/%m/%Y %H:%M"),
                "semana"  : semana_sel,
                "variable": variable_sel,
                "texto"   : texto_com.strip(),
            })
            st.success("Comentario agregado.")

    if st.session_state.comentarios:
        st.markdown("**Comentarios cargados en esta sesión:**")
        for i, c in enumerate(st.session_state.comentarios):
            col_c, col_x = st.columns([10, 1])
            col_c.markdown(f"**{c['semana']}** | *{c['variable']}* · {c['ts']}  \n{c['texto']}")
            if col_x.button("✕", key=f"del_com_{i}", help="Eliminar"):
                st.session_state.comentarios.pop(i)
                st.rerun()

        contenido_txt = "\n".join(
            f"[{c['ts']}] {c['semana']} | Variable: {c['variable']} | {c['texto']}"
            for c in st.session_state.comentarios
        )
        st.download_button(
            "⬇️ Descargar comentarios TXT",
            data=contenido_txt.encode("utf-8"),
            file_name=f"comentarios - {datetime.now().strftime('%d-%m-%Y')}.txt",
            mime="text/plain",
        )
    else:
        st.info("Sin comentarios en esta sesión.")
