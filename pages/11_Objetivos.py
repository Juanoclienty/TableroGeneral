"""
11_Objetivos.py — Objetivos Marketing & Ventas
Tab 1: Tabla de objetivos generales (desde Google Sheets)
Tab 2: Proyecto 6 propuestas (objetivos de Trazabilidad)
"""
import streamlit as st
import streamlit.components.v1 as components
import urllib.request, csv, io, os
from datetime import datetime

st.set_page_config(page_title="Objetivos mkt-vtas", layout="wide")
st.markdown("## Objetivos mkt - vtas")

with st.sidebar:
    st.markdown("### Actualizar")
    col_a, col_b = st.columns(2)
    with col_a:
        _btn_refresh_api = st.button("🔄 API CRM", use_container_width=True, help="Recarga datos del CRM")
    with col_b:
        _btn_refresh_sheets = st.button("📋 Sheets", use_container_width=True, help="Recarga inversión desde Ads xlsx")

_URL_OBJ  = "https://docs.google.com/spreadsheets/d/1rOa7MvHxXUiU8nEMb5cKTyv8lMvPuZzrAT8Wj0KuD40/export?format=csv"
_URL_EDIT = "https://docs.google.com/spreadsheets/d/1rOa7MvHxXUiU8nEMb5cKTyv8lMvPuZzrAT8Wj0KuD40/edit"

_MES_ACTUAL = datetime.today().month  # 1-based

@st.cache_data(ttl=3600)
def _cargar_sheet():
    req = urllib.request.Request(_URL_OBJ, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
    return list(csv.reader(io.StringIO(raw)))

_SECCIONES = [
    ("embudo-pct", "Embudo (en porcentual)", True, [  # True = colapsado por defecto
        ("R1 Efectivas/leads", False),
        ("R2 agendadas/leads", False),
        ("R2 Efectivas/R2A",   False),
        ("Presu./R2E",         False),
        ("Tasa de cierre",     True),
    ]),
    ("inversion", "Inversión", False, [
        ("Inversión publicidad", False),
        ("CPL",                  False),
    ]),
    ("embudo-abs", "Embudo (en absolutos)", False, [
        ("Cantidad de prospectos", False),
        ("R1 Efectivas",           False),
        ("R2 agendadas",           False),
        ("R2 Efectivas",           False),
        ("Presupuestos enviados",  False),
        ("Ventas",                 False),
        ("Tasa sobre leads",       True),
    ]),
    ("costos", "Costos", False, [
        ("CPE", False),
        ("CPV", False),
    ]),
]

_FILAS_DESTACADAS = {"Ventas"}


def _render_tabla_objetivos(rows):
    meses = rows[0][1:]
    n = len(meses)

    datos = {}
    for row in rows[1:]:
        if row and row[0].strip():
            key = row[0].strip().replace("â€™", "ó").replace("Ã³", "ó").replace("?", "ó")
            # también captura el carácter corrupto genérico
            key = "".join(c if ord(c) < 128 or c in "áéíóúüñÁÉÍÓÚÜÑ" else "ó" for c in key)
            datos[key] = row[1:n+1]
    # alias para inversión con carácter corrupto
    for k in list(datos.keys()):
        if "publicidad" in k.lower() and k != "Inversión publicidad":
            datos["Inversión publicidad"] = datos[k]

    mes_col = _MES_ACTUAL - 1  # 0-based

    # ── CSS ──────────────────────────────────────────────────────────────────
    css = """
<style>
body { font-family: sans-serif; font-size: 12.5px; margin: 0; }
.obj-wrap { overflow-x: auto; }
.obj-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
}
.obj-table th {
    background: #1e3a5f;
    color: #fff;
    text-align: center;
    padding: 6px 10px;
    font-weight: 600;
    white-space: nowrap;
    position: sticky;
    top: 0;
    z-index: 2;
}
.obj-table th.th-label {
    text-align: left;
    min-width: 175px;
    z-index: 3;
    position: sticky;
    left: 0;
}
.obj-table th.mes-actual { background: #0d1f35; }
.obj-table td {
    padding: 5px 10px;
    border-bottom: 1px solid #e5e7eb;
    text-align: right;
    white-space: nowrap;
}
.obj-table td.label-col {
    text-align: left;
    color: #374151;
    padding-left: 12px;
}
.obj-table td.mes-actual { background: #dbeafe; font-weight: 600; }

/* Fila de sección (clickable) */
.obj-table tr.sec-hdr td {
    background: #1e3a5f;
    color: #fff;
    font-weight: 700;
    padding: 5px 10px;
    font-size: 12px;
    letter-spacing: 0.4px;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
}
.obj-table tr.sec-hdr td.sec-label {
    text-align: left;
}
.obj-table tr.sec-hdr td .chevron {
    display: inline-block;
    margin-right: 6px;
    transition: transform 0.2s;
    font-style: normal;
}
.obj-table tr.sec-hdr.collapsed td .chevron { transform: rotate(-90deg); }
.obj-table tr.sec-hdr td.mes-actual-hdr { background: #0d1f35; }

/* Filas de datos ocultas */
.obj-table tr.sec-row { transition: opacity 0.15s; }
.obj-table tr.sec-row.hidden { display: none; }

.obj-table tr.fila-gris td { color: #9ca3af; }
.obj-table tr.fila-gris td.mes-actual { background: #e0ecfd; color: #6b7280; }
.obj-table tr.fila-ventas td { color: #15803d; font-weight: 700; }
.obj-table tr.fila-ventas td.mes-actual { background: #dcfce7; }
</style>
"""

    # ── Header ───────────────────────────────────────────────────────────────
    th_label = '<th class="th-label"></th>'
    ths = "".join(
        f'<th class="mes-actual">{m}</th>' if i == mes_col else f'<th>{m}</th>'
        for i, m in enumerate(meses)
    )
    hdr = f"<thead><tr>{th_label}{ths}</tr></thead>"

    # ── Body ─────────────────────────────────────────────────────────────────
    body = "<tbody>"
    for sec_id, nombre_sec, colapsado, filas in _SECCIONES:
        collapsed_cls = " collapsed" if colapsado else ""
        # celda label de sección
        td_sec_label = f'<td class="sec-label"><span class="chevron">▼</span>{nombre_sec}</td>'
        # celdas vacías del header de sección, con resalte en mes actual
        td_sec_meses = "".join(
            f'<td class="mes-actual-hdr"></td>' if i == mes_col else '<td></td>'
            for i in range(n)
        )
        body += (
            f'<tr class="sec-hdr{collapsed_cls}" onclick="toggleSec(\'{sec_id}\')">'
            f'{td_sec_label}{td_sec_meses}</tr>'
        )
        hidden_cls = " hidden" if colapsado else ""
        for nombre_fila, es_gris in filas:
            vals = datos.get(nombre_fila, [""] * n)
            es_ventas = nombre_fila in _FILAS_DESTACADAS
            css_tr = "fila-ventas" if es_ventas else ("fila-gris" if es_gris else "")
            tds = f'<td class="label-col">{nombre_fila}</td>'
            for i, v in enumerate(vals[:n]):
                css_td = "mes-actual" if i == mes_col else ""
                tds += f'<td class="{css_td}">{v.strip()}</td>'
            body += f'<tr class="sec-row{hidden_cls}" data-sec="{sec_id}" class2="{css_tr}"><td class="label-col" style="padding-left:12px">{nombre_fila}</td>{"".join(f"""<td class="{"mes-actual" if i==mes_col else ""}">{v.strip()}</td>""" for i,v in enumerate(vals[:n]))}</tr>'

        # rebuild cleaner
    # Rebuild body properly
    body = "<tbody>"
    for sec_id, nombre_sec, colapsado, filas in _SECCIONES:
        collapsed_cls = " collapsed" if colapsado else ""
        td_sec_label = f'<td class="sec-label"><span class="chevron">▼</span>{nombre_sec}</td>'
        td_sec_meses = "".join(
            f'<td class="mes-actual-hdr"></td>' if i == mes_col else '<td></td>'
            for i in range(n)
        )
        body += (
            f'<tr class="sec-hdr{collapsed_cls}" onclick="toggleSec(\'{sec_id}\')">'
            f'{td_sec_label}{td_sec_meses}</tr>'
        )
        hidden_cls = " hidden" if colapsado else ""
        for nombre_fila, es_gris in filas:
            vals = datos.get(nombre_fila, [""] * n)
            es_ventas = nombre_fila in _FILAS_DESTACADAS
            row_cls = "fila-ventas" if es_ventas else ("fila-gris" if es_gris else "")
            label_style = ' style="color:#9ca3af"' if es_gris else (' style="color:#15803d;font-weight:700"' if es_ventas else "")
            tds = f'<td class="label-col"{label_style}>{nombre_fila}</td>'
            for i, v in enumerate(vals[:n]):
                td_cls = "mes-actual" if i == mes_col else ""
                tds += f'<td class="{td_cls}">{v.strip()}</td>'
            body += f'<tr class="sec-row {row_cls}{hidden_cls}" data-sec="{sec_id}">{tds}</tr>'
    body += "</tbody>"

    js = """
<script>
function toggleSec(id) {
    var hdr = document.querySelector('.sec-hdr[onclick*="' + id + '"]');
    var rows = document.querySelectorAll('.sec-row[data-sec="' + id + '"]');
    var isCollapsed = hdr.classList.contains('collapsed');
    if (isCollapsed) {
        hdr.classList.remove('collapsed');
        rows.forEach(function(r){ r.classList.remove('hidden'); });
    } else {
        hdr.classList.add('collapsed');
        rows.forEach(function(r){ r.classList.add('hidden'); });
    }
}
</script>
"""

    height = 60 + len(meses) * 0 + sum(len(f) for _, _, _, f in _SECCIONES) * 28 + len(_SECCIONES) * 32
    return css + f'<div class="obj-wrap"><table class="obj-table">{hdr}{body}</table></div>' + js, height


def _render_6_propuestas():
    _dia = {"Leads": 19,  "R1": 15,  "Follow": 9,  "R2": 7,   "Presupuesto": 6}
    _sem = {"Leads": 80,  "R1": 64,  "Follow": 38, "R2": 30,  "Presupuesto": 26}
    _mes = {"Leads": 313, "R1": 250, "Follow": 150,"R2": 117, "Presupuesto": 100}

    filas = [
        ("Leads contactados", "Leads"),
        ("R1 efectiva",       "R1"),
        ("Follow",            "Follow"),
        ("R2 agendada",       "R2"),
        ("R2 efectiva",       "R2"),
        ("Presupuesto",       "Presupuesto"),
    ]

    html = """
<style>
body{font-family:sans-serif;font-size:12.5px;margin:0}
.p6-table{border-collapse:collapse;width:480px}
.p6-table th{background:#1e3a5f;color:#fff;padding:6px 16px;text-align:right;font-weight:600;white-space:nowrap}
.p6-table th.th-label{text-align:left;min-width:160px}
.p6-table td{padding:5px 16px;border-bottom:1px solid #e5e7eb;text-align:right;white-space:nowrap}
.p6-table td.label-col{text-align:left;color:#374151}
</style>
<table class="p6-table">
<thead><tr>
  <th class="th-label">Métrica</th>
  <th>Objetivo mensual</th>
  <th>Objetivo semanal</th>
  <th>Objetivo diario</th>
</tr></thead><tbody>
"""
    for nombre, key in filas:
        html += (
            f'<tr>'
            f'<td class="label-col">{nombre}</td>'
            f'<td>{_mes[key]}</td>'
            f'<td>{_sem[key]}</td>'
            f'<td>{_dia[key]}</td>'
            f'</tr>'
        )
    html += "</tbody></table>"
    components.html(html, height=240)


# ── Tab 3: Real vs Proyectado ─────────────────────────────────────────────────

@st.cache_data(ttl=86400)
def _cargar_real_mes():
    """Carga datos reales del mes actual desde CRM y ads."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    import datos as _datos
    import datos_crm as _dcrm

    df_crm = _dcrm.cargar_crm()

    hoy = datetime.today()
    mes_actual  = hoy.month
    anio_actual = hoy.year

    df_mes = df_crm[
        (df_crm["fecha_lead"].dt.month == mes_actual) &
        (df_crm["fecha_lead"].dt.year  == anio_actual)
    ] if not df_crm.empty else df_crm

    leads    = len(df_mes)
    r1       = int(df_mes["estado_resumen"].isin(["1. R1","2. Follow","3. R2","4. Presupuesto","5. Venta"]).sum()) if not df_mes.empty else 0
    follow   = int(df_mes["estado_resumen"].isin(["2. Follow","3. R2","4. Presupuesto","5. Venta"]).sum()) if not df_mes.empty else 0
    r2_agend = int(df_mes["estado_resumen"].isin(["3. R2","4. Presupuesto","5. Venta"]).sum()) if not df_mes.empty else 0
    r2_efect = int(df_mes["estado_resumen"].isin(["3. R2","4. Presupuesto","5. Venta"]).sum()) if not df_mes.empty else 0
    presup   = int(df_mes["estado_resumen"].isin(["4. Presupuesto","5. Venta"]).sum()) if not df_mes.empty else 0
    ventas   = int((df_mes["estado_resumen"] == "5. Venta").sum()) if not df_mes.empty else 0

    # Inversión: desde sheet_ads (mismo origen que Ventas y Marketing)
    inv = 0.0
    try:
        df_ads = _datos.cargar_ads()
        inv = float(df_ads[
            (df_ads["fecha"].dt.month == mes_actual) &
            (df_ads["fecha"].dt.year  == anio_actual)
        ]["inversion"].sum())
    except Exception:
        pass

    # Ventas reales: desde BBDD_Ventas (fecha de cierre en el mes actual)
    ventas_reales = 0
    try:
        import pandas as _pd
        _ID_BBDD = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"
        _url_bbdd = f"https://docs.google.com/spreadsheets/d/{_ID_BBDD}/gviz/tq?tqx=out:csv&sheet=BBDD_Ventas"
        df_bbdd = _pd.read_csv(_url_bbdd, dtype=str)
        df_bbdd["Fecha"] = _pd.to_datetime(df_bbdd["Fecha"], dayfirst=True, errors="coerce")
        ventas_reales = int(((df_bbdd["Fecha"].dt.month == mes_actual) & (df_bbdd["Fecha"].dt.year == anio_actual)).sum())
    except Exception:
        pass

    cpl = round(inv / leads,        0) if leads  > 0 else 0
    cpe = round(inv / presup,       0) if presup > 0 else 0
    cpv = round(inv / ventas_reales, 0) if ventas_reales > 0 else 0

    return {
        "inversion":     inv,
        "cpl":           cpl,
        "leads":         leads,
        "r1":            r1,
        "follow":        follow,
        "r2_ag":         r2_agend,
        "r2_ef":         r2_efect,
        "presup":        presup,
        "ventas_co":     ventas,
        "ventas_reales": ventas_reales,
        "cpe":           cpe,
        "cpv":           cpv,
    }


if _btn_refresh_api:
    import datos_crm as _dcrm_sb
    with st.spinner("Descargando CRM..."):
        _dcrm_sb.limpiar_cache()
        st.cache_data.clear()
    st.rerun()

if _btn_refresh_sheets:
    import datos as _datos_sb
    with st.spinner("Descargando Ads xlsx..."):
        _datos_sb.actualizar_cache_ads()
        st.cache_data.clear()
    st.rerun()


def _render_real_vs_proy(rows_sheet):
    """Tabla comparativa: Proyectado | Proy. 6 prop. | Real."""
    # Datos proyectados del sheet (mes actual)
    meses_hdr = rows_sheet[0][1:]
    mes_col   = _MES_ACTUAL - 1  # 0-based

    datos_sheet = {}
    for row in rows_sheet[1:]:
        if row and row[0].strip():
            key = row[0].strip().replace("â€™", "ó").replace("Ã³", "ó")
            key = "".join(c if ord(c) < 128 or c in "áéíóúüñÁÉÍÓÚÜÑ" else "ó" for c in key)
            vals = row[1:]
            datos_sheet[key] = vals[mes_col].strip() if mes_col < len(vals) else "—"
    for k in list(datos_sheet.keys()):
        if "publicidad" in k.lower() and k != "Inversión publicidad":
            datos_sheet["Inversión publicidad"] = datos_sheet[k]

    # Datos reales
    try:
        real = _cargar_real_mes()
    except Exception:
        real = {}

    def _fmt_inv(v):
        if not v: return "—"
        try: return f"${float(str(v).replace('$','').replace('.','').replace(',','.').strip()):,.0f}"
        except: return str(v)

    def _r(key, fmt=None):
        v = real.get(key, 0)
        if fmt == "$": return f"${v:,.0f}" if v else "—"
        return str(int(v)) if v else "—"

    # Objetivos 6 propuestas (mes)
    p6 = {"leads": 313, "r1": 250, "follow": 150, "r2_ag": 117, "r2_ef": 117, "presup": 100, "ventas": "—"}

    # Estructura: (nombre_fila, val_proy_sheet_key, val_p6_key_or_None, val_real_key, fmt)
    _SECS_RVP = [
        ("Inversión", [
            ("Inversión publicidad", "Inversión publicidad", None,      "inversion", "$"),
            ("CPL",                  "CPL",                  None,      "cpl",       "$"),
        ]),
        ("Embudo (en absolutos)", [
            ("Cantidad de prospectos", "Cantidad de prospectos", "leads",  "leads",  "n"),
            ("R1 Efectivas",           "R1 Efectivas",           "r1",     "r1",     "n"),
            ("R2 agendadas",           "R2 agendadas",           "r2_ag",  "r2_ag",  "n"),
            ("R2 Efectivas",           "R2 Efectivas",           "r2_ef",  "r2_ef",  "n"),
            ("Presupuestos enviados",  "Presupuestos enviados",  "presup", "presup",        "n"),
            ("Ventas reales",          "Ventas",                 None,     "ventas_reales", "n"),
            ("Tasa sobre leads",       "Tasa sobre leads",       None,     None,            "pct"),
            ("Ventas (Co)",            None,                     "ventas", "ventas_co",     "n"),
        ]),
        ("Costos", [
            ("CPE", "CPE", None, "cpe", "$"),
            ("CPV", "CPV", None, "cpv", "$"),
        ]),
    ]

    _GRISES  = {"Tasa sobre leads", "Ventas (Co)"}
    _VERDES  = {"Ventas reales"}

    # calcular tasa real (usa ventas_reales)
    tasa_real = f"{round(real.get('ventas_reales',0)/real.get('leads',1)*100,1)}%" if real.get("leads") else "—"

    css = """
<style>
body{font-family:sans-serif;font-size:12.5px;margin:0}
.rvp{border-collapse:collapse;width:100%}
.rvp th{background:#1e3a5f;color:#fff;padding:6px 12px;text-align:right;font-weight:600;white-space:nowrap}
.rvp th.th-label{text-align:left;min-width:175px}
.rvp td{padding:5px 12px;border-bottom:1px solid #e5e7eb;text-align:right;white-space:nowrap}
.rvp td.label-col{text-align:left;color:#374151}
.rvp tr.sec-hdr td{background:#1e3a5f;color:#fff;font-weight:700;padding:5px 12px;font-size:12px;text-align:left}
.rvp tr.fila-gris td{color:#9ca3af}
.rvp tr.fila-ventas td{color:#15803d;font-weight:700}
</style>
"""
    html = css + """<table class="rvp">
<thead><tr>
  <th class="th-label">Métrica</th>
  <th>Proyectado</th>
  <th>Proy. 6 prop.</th>
  <th>Real</th>
</tr></thead><tbody>
"""
    for nombre_sec, filas in _SECS_RVP:
        html += f'<tr class="sec-hdr"><td colspan="4">{nombre_sec}</td></tr>'
        for nombre_fila, sheet_key, p6_key, real_key, fmt in filas:
            proy_val = datos_sheet.get(sheet_key, "—") if sheet_key else "—"
            p6_val   = str(p6.get(p6_key, "—")) if p6_key else "—"
            if real_key is None:
                real_val = tasa_real
            elif fmt == "$":
                real_val = _r(real_key, "$")
            else:
                real_val = _r(real_key)

            css_tr = "fila-ventas" if nombre_fila in _VERDES else ("fila-gris" if nombre_fila in _GRISES else "")
            lbl_style = ' style="color:#9ca3af"' if nombre_fila in _GRISES else (' style="color:#15803d;font-weight:700"' if nombre_fila in _VERDES else "")
            html += (
                f'<tr class="{css_tr}">'
                f'<td class="label-col"{lbl_style}>{nombre_fila}</td>'
                f'<td>{proy_val}</td>'
                f'<td>{p6_val}</td>'
                f'<td>{real_val}</td>'
                f'</tr>'
            )
    html += "</tbody></table>"

    n_filas = sum(len(f) for _, f in _SECS_RVP)
    height  = 40 + len(_SECS_RVP) * 30 + n_filas * 28
    components.html(html, height=height, scrolling=False)

    st.markdown(
        "<div style='font-size:0.75rem;color:#9ca3af;margin-top:12px;line-height:1.6'>"
        "<b>Fuentes columna Real:</b><br>"
        "· <b>Inversión publicidad</b> — Google Sheet de Ads (mismo origen que Ventas), suma del mes actual<br>"
        "· <b>CPL</b> — Inversión / Leads<br>"
        "· <b>Leads, R1 Efectivas, R2, Presupuestos</b> — API Clienty CRM, leads con fecha_lead en el mes actual<br>"
        "· <b>Ventas reales</b> — BBDD_Ventas (Google Sheet), filas con fecha de cierre en el mes actual<br>"
        "· <b>Ventas (Co)</b> — API Clienty CRM, leads con fecha_lead en el mes actual en estado 5. Venta<br>"
        "· <b>CPE</b> — Inversión / Presupuestos<br>"
        "· <b>CPV</b> — Inversión / Ventas reales"
        "</div>",
        unsafe_allow_html=True,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

_MES_NOMBRE = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"][_MES_ACTUAL - 1]
tab1, tab2, tab3 = st.tabs([
    "Objetivos generales",
    "Proyecto 6 propuestas",
    f"Real vs Proy ({_MES_NOMBRE})",
])

with tab1:
    st.markdown(
        f'<div style="margin-bottom:8px;font-size:12px;color:#6b7280">'
        f'Fuente: <a href="{_URL_EDIT}" target="_blank">Ver / editar en Google Sheets</a>'
        f'</div>',
        unsafe_allow_html=True,
    )
    try:
        rows = _cargar_sheet()
        html_table, est_height = _render_tabla_objetivos(rows)
        components.html(html_table, height=est_height, scrolling=False)
    except Exception as e:
        st.error(f"Error cargando objetivos: {e}")

with tab2:
    st.markdown("### Proyecto 6 propuestas")
    _render_6_propuestas()

with tab3:
    try:
        rows = _cargar_sheet()
        _render_real_vs_proy(rows)
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
