"""
11_Objetivos.py — Objetivos Marketing & Ventas
Tab 1: Tabla de objetivos generales (desde Google Sheets)
Tab 2: Proyecto 6 propuestas (objetivos de Trazabilidad)
"""
import streamlit as st
import urllib.request, csv, io, os
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Objetivos mkt-vtas", layout="wide")
st.markdown("## Objetivos mkt - vtas")

_URL_OBJ  = "https://docs.google.com/spreadsheets/d/1rOa7MvHxXUiU8nEMb5cKTyv8lMvPuZzrAT8Wj0KuD40/export?format=csv"
_URL_EDIT = "https://docs.google.com/spreadsheets/d/1rOa7MvHxXUiU8nEMb5cKTyv8lMvPuZzrAT8Wj0KuD40/edit"

_MES_ACTUAL = datetime.today().month  # 1-based → julio = 7 → col index 6

@st.cache_data(ttl=3600)
def _cargar_sheet():
    req = urllib.request.Request(_URL_OBJ, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
    return list(csv.reader(io.StringIO(raw)))

# ── Estructura fija de secciones ──────────────────────────────────────────────

_SECCIONES = [
    ("Embudo (en porcentual)", [
        ("R1 Efectivas/leads", False),
        ("R2 agendadas/leads", False),
        ("R2 Efectivas/R2A",   False),
        ("Presu./R2E",         False),
        ("Tasa de cierre",     True),   # True = fila gris
    ]),
    ("Inversión", [
        ("Inversión publicidad", False),
        ("CPL",                  False),
    ]),
    ("Embudo (en absolutos)", [
        ("Cantidad de prospectos", False),
        ("R1 Efectivas",           False),
        ("R2 agendadas",           False),
        ("R2 Efectivas",           False),
        ("Presupuestos enviados",  False),
        ("Ventas",                 False),
        ("Tasa sobre leads",       True),
    ]),
    ("Costos", [
        ("CPE", False),
        ("CPV", False),
    ]),
]

_FILAS_DESTACADAS = {"Ventas"}

# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
<style>
.obj-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
    font-family: inherit;
}
.obj-table th {
    background: #1e3a5f;
    color: #fff;
    text-align: center;
    padding: 5px 8px;
    font-weight: 600;
    white-space: nowrap;
}
.obj-table th.th-label { text-align: left; min-width: 165px; }
.obj-table th.mes-actual { background: #0f2540; }
.obj-table td {
    padding: 4px 8px;
    border-bottom: 1px solid #e5e7eb;
    text-align: right;
    white-space: nowrap;
}
.obj-table td.label-col { text-align: left; color: #374151; }
.obj-table td.mes-actual { background: #dbeafe; font-weight: 600; }
.obj-table tr.seccion-header td {
    background: #1e3a5f;
    color: #fff;
    font-weight: 700;
    padding: 5px 8px;
    font-size: 12px;
    letter-spacing: 0.4px;
}
.obj-table tr.fila-gris td { color: #9ca3af; }
.obj-table tr.fila-gris td.mes-actual { background: #e0ecfd; color: #6b7280; }
.obj-table tr.fila-ventas td { color: #15803d; font-weight: 700; }
.obj-table tr.fila-ventas td.mes-actual { background: #dcfce7; }
</style>
"""


def _render_tabla_objetivos(rows):
    meses = rows[0][1:]
    n = len(meses)

    # índice por nombre de fila (normalizado)
    datos = {}
    for row in rows[1:]:
        if row and row[0].strip():
            # normalizar "Inversión publicidad" con carácter corrupto
            key = row[0].strip().replace("�", "ó")
            datos[key] = row[1:n+1]

    mes_col = _MES_ACTUAL - 1  # 0-based

    th_label = '<th class="th-label label-col"></th>'
    ths = "".join(
        f'<th class="mes-actual">{m}</th>' if i == mes_col else f'<th>{m}</th>'
        for i, m in enumerate(meses)
    )
    hdr = f"<thead><tr>{th_label}{ths}</tr></thead>"

    body = "<tbody>"
    for nombre_sec, filas in _SECCIONES:
        body += f'<tr class="seccion-header"><td colspan="{n+1}">{nombre_sec}</td></tr>'
        for nombre_fila, es_gris in filas:
            # intentar con el nombre original y con "ó" normalizado
            vals = datos.get(nombre_fila) or datos.get(nombre_fila.replace("o", "ó")) or [""] * n
            es_ventas = nombre_fila in _FILAS_DESTACADAS
            css_tr = "fila-ventas" if es_ventas else ("fila-gris" if es_gris else "")
            tds = f'<td class="label-col">{nombre_fila}</td>'
            for i, v in enumerate(vals[:n]):
                css_td = "mes-actual" if i == mes_col else ""
                tds += f'<td class="{css_td}">{v.strip()}</td>'
            body += f'<tr class="{css_tr}">{tds}</tr>'

    body += "</tbody>"
    return f'{_CSS}<table class="obj-table">{hdr}{body}</table>'


# ── Tab 2: Proyecto 6 propuestas ──────────────────────────────────────────────

def _render_6_propuestas():
    """Mismos objetivos que Trazabilidad (OBJ["Mes"])."""
    _obj = {"Leads": 313, "R1": 250, "Follow": 150, "R2": 117, "Presupuesto": 100}

    filas = [
        ("Leads contactados", _obj["Leads"]),
        ("R1",                _obj["R1"]),
        ("Follow",            _obj["Follow"]),
        ("R2 agendada",       _obj["R2"]),
        ("R2 efectiva",       _obj["R2"]),
        ("Presupuesto",       _obj["Presupuesto"]),
    ]

    html = _CSS + """
    <table class="obj-table" style="max-width:420px">
    <thead><tr>
        <th class="th-label label-col">Métrica</th>
        <th>Objetivo mensual</th>
    </tr></thead><tbody>
    """
    for nombre, val in filas:
        html += f'<tr><td class="label-col">{nombre}</td><td>{val}</td></tr>'
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)


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
        st.markdown(_render_tabla_objetivos(rows), unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error cargando objetivos: {e}")

with tab2:
    st.markdown("### Proyecto 6 propuestas")
    _render_6_propuestas()
