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
    _obj_mes = {"Leads": 313, "R1": 250, "Follow": 150, "R2": 117, "Presupuesto": 100}

    _secs = [
        ("p6-r1",    "Reunión 1", False, [
            ("Leads contactados", _obj_mes["Leads"]),
            ("R1 efectiva",       _obj_mes["R1"]),
            ("Follow",            _obj_mes["Follow"]),
        ]),
        ("p6-r2",    "Reunión 2", False, [
            ("R2 agendada",  _obj_mes["R2"]),
            ("R2 efectiva",  _obj_mes["R2"]),
            ("Presupuesto",  _obj_mes["Presupuesto"]),
        ]),
    ]

    html = """
<style>
body{font-family:sans-serif;font-size:12.5px;margin:0}
.p6-table{border-collapse:collapse;width:360px}
.p6-table th{background:#1e3a5f;color:#fff;padding:6px 12px;text-align:left;font-weight:600}
.p6-table th:last-child{text-align:right}
.p6-table td{padding:5px 12px;border-bottom:1px solid #e5e7eb}
.p6-table td:last-child{text-align:right;font-weight:600}
.p6-table tr.sec-hdr td{
    background:#1e3a5f;color:#fff;font-weight:700;
    padding:5px 12px;font-size:12px;letter-spacing:0.4px;
    cursor:pointer;user-select:none;
}
.p6-table tr.sec-hdr .chevron{display:inline-block;margin-right:6px;transition:transform 0.2s}
.p6-table tr.sec-hdr.collapsed .chevron{transform:rotate(-90deg)}
.p6-table tr.sec-row.hidden{display:none}
</style>
<table class="p6-table">
<thead><tr><th>Métrica</th><th>Objetivo mensual</th></tr></thead>
<tbody>
"""
    for sec_id, nombre_sec, colapsado, filas in _secs:
        collapsed_cls = " collapsed" if colapsado else ""
        html += (
            f'<tr class="sec-hdr{collapsed_cls}" onclick="toggleP6(\'{sec_id}\')">'
            f'<td colspan="2"><span class="chevron">▼</span>{nombre_sec}</td></tr>'
        )
        hidden_cls = " hidden" if colapsado else ""
        for nombre, val in filas:
            html += f'<tr class="sec-row{hidden_cls}" data-sec="{sec_id}"><td>{nombre}</td><td>{val}</td></tr>'

    html += """</tbody></table>
<script>
function toggleP6(id){
    var hdr=document.querySelector('.sec-hdr[onclick*="'+id+'"]');
    var rows=document.querySelectorAll('.sec-row[data-sec="'+id+'"]');
    var col=hdr.classList.contains('collapsed');
    if(col){hdr.classList.remove('collapsed');rows.forEach(function(r){r.classList.remove('hidden')});}
    else{hdr.classList.add('collapsed');rows.forEach(function(r){r.classList.add('hidden')});}
}
</script>"""
    components.html(html, height=240)


# ── Main ──────────────────────────────────────────────────────────────────────

tab1, tab2 = st.tabs(["Objetivos generales", "Proyecto 6 propuestas"])

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
