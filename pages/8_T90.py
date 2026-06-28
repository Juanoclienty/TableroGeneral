"""
8_T90.py — T90: análisis trimestral por área.
"""
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import datos
import datos_crm

st.set_page_config(
    page_title="T90 — Clienty",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 T90")

# ── Tabla genérica reutilizable ───────────────────────────────────

_CSS = """
* { box-sizing:border-box; margin:0; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       background:#fff; padding:4px 0; }
.wrap { overflow-x:auto; border:1px solid #c8ccd0; border-radius:4px; }
table { border-collapse:collapse; font-size:0.74rem; white-space:nowrap; }
thead th { position:sticky; top:0; z-index:3; border:1px solid #b0bec5; }
.h-area  { background:#1a3a5c; color:#fff; font-weight:bold; padding:6px 8px; text-align:center; }
.h-mes   { background:#2c5f8a; color:#fff; padding:5px 6px; text-align:center; min-width:52px; }
.h-q     { background:#7b5e00; color:#fff; font-weight:bold; padding:5px 6px; text-align:center;
           min-width:64px; cursor:pointer; user-select:none; }
.h-q:hover { filter:brightness(1.15); }
.h-anual { background:#145a32; color:#fff; font-weight:bold; padding:5px 6px; text-align:center;
           min-width:70px; cursor:pointer; user-select:none; }
.h-anual:hover { filter:brightness(1.15); }
td.c-kpi, th.h-kpi {
    position:sticky; left:0; z-index:2;
    background:#f8fafc; border:1px solid #c8ccd0;
    padding:5px 8px; text-align:left; min-width:220px;
}
td { border:1px dotted #cdd4da; padding:4px 6px; text-align:right; }
.c-mes   { background:#fff; color:#333; }
.c-q     { background:#fff8e1; color:#6d4c00; font-weight:600; }
.c-anual { background:#e8f5e9; color:#1b5e20; font-weight:700; }
tr:nth-child(even) td.c-mes { background:#f7fafd; }
tr:nth-child(even) td.c-q   { background:#fffde7; }
tr.sep-row td { border-top:2px solid #90a4ae !important; }
tr.sub-row td.c-kpi { padding-left:22px; font-size:0.68rem; color:#555; }
tr.sub-row td { font-size:0.68rem; color:#555; }
.empty { color:#bbb; }
.tbtn-q { font-size:0.65rem; margin-left:4px; opacity:0.8; }
"""

_JS_TEMPLATE = """
var qmap   = QMAP;
var ymap   = YMAP;
var qstate = {};
var ystate = {};
Object.keys(qmap).forEach(function(k){ qstate[k] = false; });
Object.keys(ymap).forEach(function(k){ ystate[k] = false; });

function setCols(ids, hide) {
    ids.forEach(function(cid) {
        document.querySelectorAll('.col-'+cid).forEach(function(el){
            el.style.display = hide ? 'none' : '';
        });
    });
}

var currentYear = new Date().getFullYear();

window.addEventListener('load', function() {
    Object.keys(ymap).forEach(function(yid) {
        var yr = parseInt(yid.replace('y',''));
        var qs = ymap[yid] || [];
        if(yr < currentYear) {
            qs.forEach(function(qid) {
                setCols([qid], true);
                setCols(qmap[qid]||[], true);
            });
            var btn = document.getElementById('btn-'+yid);
            if(btn) btn.textContent = '+';
        } else {
            setCols(qs, false);
            qs.forEach(function(qid) {
                setCols(qmap[qid]||[], false);
                qstate[qid] = true;
                var btn = document.getElementById('btn-'+qid);
                if(btn) btn.textContent = '−';
            });
            ystate[yid] = true;
            var btn = document.getElementById('btn-'+yid);
            if(btn) btn.textContent = '−';
        }
    });
});

function toggleQ(qid) {
    var exp = qstate[qid];
    setCols(qmap[qid]||[], exp);
    var btn = document.getElementById('btn-'+qid);
    if(btn) btn.textContent = exp ? '+' : '−';
    qstate[qid] = !exp;
}

function toggleY(yid) {
    var exp = ystate[yid];
    var qs  = ymap[yid] || [];
    setCols(qs, exp);
    if(exp) {
        qs.forEach(function(qid) {
            setCols(qmap[qid]||[], true);
            qstate[qid] = false;
            var btn = document.getElementById('btn-'+qid);
            if(btn) btn.textContent = '+';
        });
    }
    var btn = document.getElementById('btn-'+yid);
    if(btn) btn.textContent = exp ? '+' : '−';
    ystate[yid] = !exp;
}
"""

def _col_id(y, m, tipo):
    if tipo == "anual": return f"y{y}"
    if tipo == "q":     return f"q{y}-{(m-1)//3+1}"
    return f"m{y}-{m}"

def _build_cols():
    import datetime
    cur_m = datetime.date.today().month
    cols = []
    for y in [2025, 2026]:
        cols.append((y, 99, str(y), "anual"))
        for q in range(1, 5):
            meses = [m for m in range((q-1)*3+1, q*3+1)
                     if not (y == 2026 and m > cur_m)]
            if not meses:
                break
            cols.append((y, q*3, f"Q{q}", "q"))
            for m in meses:
                cols.append((y, m, str(m), "mes"))
    return cols

def _fmt_val(v, tipo):
    """Formatea un valor numérico según tipo: num | usd | pct."""
    if v is None or (isinstance(v, float) and (v != v)):  # NaN check
        return '<span class="empty">—</span>'
    if tipo == "usd":
        return f"${v:,.0f}"
    if tipo == "pct":
        return f"{v:.1f}%"
    return f"{int(round(v)):,}"


def render_t90_tabla(kpis, datos_mes=None, datos_q=None, datos_yr=None):
    """
    kpis: list of (label, tipo)  tipo: "num"|"usd"|"pct"|"pending"
    datos_mes: {(y,m): {kpi: val}}  — valores mensuales
    datos_q:   {(y,qnum): {kpi: val}} — ya agregados correctamente
    datos_yr:  {y: {kpi: val}}        — ya agregados correctamente
    Si datos_q/datos_yr son None, agrega datos_mes sumando solo tipo "num"/"usd".
    """
    cols = _build_cols()
    all_ids = {_col_id(*c[:3]) for c in cols}

    q_meses_map = {}
    y_qs_map    = {}
    for (y, m, lbl, tipo) in cols:
        if tipo == "q":
            qid  = _col_id(y, m, "q")
            qnum = (m-1)//3+1
            q_meses_map[qid] = [f"m{y}-{mm}" for mm in range((qnum-1)*3+1, qnum*3+1)
                                 if f"m{y}-{mm}" in all_ids]
            y_qs_map.setdefault(f"y{y}", []).append(qid)

    datos = datos_mes or {}

    # Fallback: si no vienen datos_q/datos_yr pre-calculados, sumar (solo para num/usd)
    if datos_q is None:
        datos_q = {}
        for (y, m), vals in datos.items():
            qnum = (m - 1) // 3 + 1
            datos_q.setdefault((y, qnum), {})
            for lbl, v in vals.items():
                if v is None: continue
                tipo = next((t for l, t in kpis if l == lbl), "num")
                if tipo in ("num", "usd"):
                    datos_q[(y, qnum)][lbl] = datos_q[(y, qnum)].get(lbl, 0) + v

    if datos_yr is None:
        datos_yr = {}
        for (y, m), vals in datos.items():
            datos_yr.setdefault(y, {})
            for lbl, v in vals.items():
                if v is None: continue
                tipo = next((t for l, t in kpis if l == lbl), "num")
                if tipo in ("num", "usd"):
                    datos_yr[y][lbl] = datos_yr[y].get(lbl, 0) + v

    js = (_JS_TEMPLATE
          .replace("QMAP", json.dumps(q_meses_map))
          .replace("YMAP", json.dumps(y_qs_map)))

    # Header
    head = "<tr><th class='h-area h-kpi' style='left:0;cursor:default'>KPI</th>"
    for (y, m, lbl, tipo) in cols:
        cid = _col_id(y, m, tipo)
        yid = f"y{y}"
        if tipo == "mes":
            head += f"<th class='h-mes col-{cid}'>{lbl}</th>"
        elif tipo == "q":
            head += (f"<th class='h-q col-{cid}' onclick=\"toggleQ('{cid}')\">"
                     f"{lbl}&nbsp;<span id='btn-{cid}' class='tbtn-q'>−</span></th>")
        else:
            head += (f"<th class='h-anual' onclick=\"toggleY('{yid}')\">"
                     f"{lbl}&nbsp;<span id='btn-{yid}' class='tbtn-q'>−</span></th>")
    head += "</tr>"

    # Body
    tbody = ""
    for item in kpis:
        kpi_lbl, kpi_tipo = item[0], item[1]
        kpi_sub = len(item) > 2 and item[2] == "sub"
        if kpi_tipo == "sep":
            tbody += f"<tr style='height:6px;line-height:6px'><td colspan='{1+len(cols)}'></td></tr>"
            continue
        _h = 22 if kpi_sub else 27
        tr_cls = f" class='sub-row'" if kpi_sub else ""
        row = f"<tr{tr_cls} style='height:{_h}px'><td class='c-kpi'>{kpi_lbl}</td>"
        for (y, m, lbl_col, tipo_col) in cols:
            cid = _col_id(y, m, tipo_col)
            cls = {"mes": f"c-mes col-{cid}", "q": f"c-q col-{cid}", "anual": "c-anual"}[tipo_col]
            if kpi_tipo == "pending":
                cell = '<span class="empty">—</span>'
            else:
                if tipo_col == "mes":
                    v = datos_mes.get((y, m), {}).get(kpi_lbl) if datos_mes else None
                elif tipo_col == "q":
                    qnum = (m - 1) // 3 + 1
                    v = datos_q.get((y, qnum), {}).get(kpi_lbl)
                else:
                    v = datos_yr.get(y, {}).get(kpi_lbl)
                cell = _fmt_val(v, kpi_tipo)
            row += f'<td class="{cls}">{cell}</td>'
        row += "</tr>"
        tbody += row

    n_sep = sum(1 for it in kpis if it[1] == "sep")
    n_sub = sum(1 for it in kpis if len(it) > 2 and it[2] == "sub")
    height = (len(kpis) - n_sep - n_sub) * 27 + n_sub * 22 + n_sep * 6 + 70
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_CSS}</style></head><body>"
        f"<div class='wrap'><table><thead>{head}</thead><tbody>{tbody}</tbody></table></div>"
        f"<script>{js}</script></body></html>"
    )
    st.iframe(html, height=height + 60)


# ── Tabs ──────────────────────────────────────────────────────────

tab_real, tab_mkt, tab_fin, tab_cs = st.tabs([
    "📈 T90 Real",
    "📣 Mkt",
    "💰 Finanzas",
    "🤝 CS",
])

_VARS_PLACEHOLDER = [(f"Variable {i}", "num") for i in range(1, 11)]

# ── Carga de datos MKT ────────────────────────────────────────────

def _cargar_datos_mkt():
    return (
        datos_crm.cargar_meses_compartido(),
        datos_crm.cargar_ventas_cierre(),
        datos_crm.cargar_presupuestos_enviados(),
    )

def _cargar_datos_mkt_semanas():
    return (
        datos_crm.cargar_semanas_recientes(),
        datos_crm.cargar_ventas_semanas(),
        datos_crm.cargar_presupuestos_semanas(),
    )

def _kpis_de_raw(inv, leads, presu, venta_real, venta_cohort, gf, y):
    """Calcula todos los KPIs derivados desde los componentes crudos."""
    return {
        "Inversión publicidad":   inv           if inv           > 0 else None,
        "Leads":                  leads         if leads         > 0 else None,
        "CPL":                    inv / leads               if leads      > 0 and inv        > 0 else None,
        "% GF":                   gf  / leads * 100         if leads      > 0 and y >= 2026  else None,
        "Presupuestos reales":    presu         if presu         > 0 else None,
        "Ventas cohort":          venta_cohort  if venta_cohort  > 0 else None,
        "Ventas reales":          venta_real    if venta_real    > 0 else None,
        "CPE":                    inv / presu               if presu      > 0 and inv        > 0 else None,
        "CPV Co":                 inv / venta_cohort        if venta_cohort > 0 and inv       > 0 else None,
        "CPV":                    inv / venta_real          if venta_real   > 0 and inv       > 0 else None,
        "Tasa de cierre (Vta/Presu)": venta_real / presu * 100 if presu   > 0 and venta_real > 0 else None,
        "Tasa Vtas (Co)/Leads":   venta_cohort / leads * 100 if leads     > 0 and venta_cohort > 0 else None,
        "Tasa Vtas/Leads":        venta_real / leads * 100 if leads       > 0 and venta_real > 0 else None,
    }


def _construir_datos_mkt(df_men: "pd.DataFrame", vc: dict, pc: dict):
    """
    df_men: df mensual agrupado por mes de lead.
    vc: {(y,m): int} ventas por mes de cierre (BBDD_Ventas).
    pc: {(y,m): int} presupuestos por mes de envío (bbdd_presupuestos).
    Devuelve (datos_mes, datos_q, datos_yr) con tasas calculadas
    desde componentes acumulados — nunca promediados.
    """
    raws = {}
    for _, row in df_men.iterrows():
        p = row.get("mes_key")
        if p is None:
            continue
        y, m = p.year, p.month
        raws[(y, m)] = {
            "inv":          float(row.get("inversion", 0) or 0),
            "leads":        float(row.get("leads",      0) or 0),
            "presu":        float(pc.get((y, m),        0)),
            "venta_real":   float(vc.get((y, m),        0)),
            "venta_cohort": float(row.get("5. Venta",   0) or 0),
            "gf":           float(row.get("gf",         0) or 0),
        }

    # Meses presentes en vc o pc pero no en df_men
    for (y, m) in set(vc) | set(pc):
        if (y, m) not in raws:
            raws[(y, m)] = {"inv": 0, "leads": 0,
                            "presu":        float(pc.get((y, m), 0)),
                            "venta_real":   float(vc.get((y, m), 0)),
                            "venta_cohort": 0, "gf": 0}

    datos_mes = {(y, m): _kpis_de_raw(**r, y=y) for (y, m), r in raws.items()}

    _keys = ("inv", "leads", "presu", "venta_real", "venta_cohort", "gf")
    raw_q  = {}
    raw_yr = {}

    for (y, m), r in raws.items():
        qnum = (m - 1) // 3 + 1
        for acc, key in [(raw_q, (y, qnum)), (raw_yr, y)]:
            if key not in acc:
                acc[key] = {k: 0 for k in _keys}
            for k in _keys:
                acc[key][k] += r[k]

    datos_q  = {(y, qnum): _kpis_de_raw(**r, y=y) for (y, qnum), r in raw_q.items()}
    datos_yr = {y:          _kpis_de_raw(**r, y=y) for y,         r in raw_yr.items()}

    return datos_mes, datos_q, datos_yr


def _construir_datos_semanas(df_sem, vc_sem, pc_sem):
    """
    Construye {monday_ts: {kpi: val}} para las últimas 4 semanas.
    Devuelve (datos, semanas) donde semanas = [lunes_oldest, ..., lunes_actual].
    """
    semanas = datos_crm._get_4_semanas()
    out = {}
    for lunes in semanas:
        key = lunes.normalize()
        row_df = df_sem[df_sem["semana_inicio"].dt.normalize() == key]
        if row_df.empty:
            inv = leads = venta_cohort = gf = 0.0
        else:
            r            = row_df.iloc[0]
            inv          = float(r.get("inversion", 0) or 0)
            leads        = float(r.get("leads",     0) or 0)
            venta_cohort = float(r.get("5. Venta",  0) or 0)
            gf           = float(r.get("gf",        0) or 0)
        venta_real = float(vc_sem.get(key, 0))
        presu      = float(pc_sem.get(key, 0))
        out[key] = _kpis_de_raw(
            inv=inv, leads=leads, presu=presu,
            venta_real=venta_real, venta_cohort=venta_cohort,
            gf=gf, y=lunes.year,
        )
    return out, [s.normalize() for s in semanas]


def render_semanas_tabla(kpis, datos, semanas):
    """Tabla simple de 4 columnas semanales (sin collapse)."""
    ayer       = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    lunes_cur  = (ayer - pd.Timedelta(days=ayer.weekday())).normalize()
    labels     = [s.strftime("%d/%m") for s in semanas]

    css_sem = _CSS + """
table      { table-layout:fixed; width:100%; }
thead th, td { width:25%; min-width:0; }
.h-sem-cur { background:#2c5f8a; color:#fff; padding:5px 4px;
             text-align:center; font-weight:600; }
"""

    head = "<tr>"
    for lbl, s in zip(labels, semanas):
        cls = "h-sem-cur" if s == lunes_cur else "h-mes"
        head += f"<th class='{cls}' style='padding:6px 4px'>{lbl}</th>"
    head += "</tr>"

    tbody = ""
    for item in kpis:
        kpi_lbl, kpi_tipo = item[0], item[1]
        kpi_sub = len(item) > 2 and item[2] == "sub"
        if kpi_tipo == "sep":
            tbody += f"<tr style='height:6px;line-height:6px'><td colspan='{len(semanas)}'></td></tr>"
            continue
        _h = 22 if kpi_sub else 27
        tr_cls = " class='sub-row'" if kpi_sub else ""
        row = f"<tr{tr_cls} style='height:{_h}px'>"
        for s in semanas:
            if kpi_tipo == "pending":
                cell = '<span class="empty">—</span>'
            else:
                v    = datos.get(s, {}).get(kpi_lbl)
                cell = _fmt_val(v, kpi_tipo)
            row += f'<td class="c-mes">{cell}</td>'
        row += "</tr>"
        tbody += row

    n_sep = sum(1 for it in kpis if it[1] == "sep")
    n_sub = sum(1 for it in kpis if len(it) > 2 and it[2] == "sub")
    height = (len(kpis) - n_sep - n_sub) * 27 + n_sub * 22 + n_sep * 6 + 70

    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{css_sem}</style></head><body>"
        f"<div class='wrap'><table><thead>{head}</thead><tbody>{tbody}</tbody></table></div>"
        "</body></html>"
    )
    st.iframe(html, height=height + 60)


_MKT_KPIS = [
    ("Inversión publicidad",          "usd"),
    ("Leads",                         "num"),
    ("CPL",                           "usd"),
    ("% GF",                          "pct"),
    ("Presupuestos reales",           "num"),
    ("Ventas reales",                 "num"),
    ("CPE",                           "usd"),
    ("CPV",                           "usd"),
    ("Tasa de cierre (Vta/Presu)",    "pct"),
    ("Tasa Vtas/Leads",               "pct"),
    ("---",                           "sep"),
    ("Ventas cohort",                 "num"),
    ("CPV Co",                        "usd"),
    ("Tasa Vtas (Co)/Leads",          "pct"),
]

# ── Tabs ──────────────────────────────────────────────────────────

# Carga semanal compartida por todos los tabs que la usan
try:
    _df_sem, _vc_sem, _pc_sem = _cargar_datos_mkt_semanas()
    _datos_sem, _semanas = _construir_datos_semanas(_df_sem, _vc_sem, _pc_sem)
except Exception as _e:
    _datos_sem, _semanas = {}, []

with tab_real:
    try:
        _col_main, _col_sem = st.columns([4, 1])
        with _col_main:
            render_t90_tabla(_VARS_PLACEHOLDER)
        with _col_sem:
            if _semanas:
                render_semanas_tabla(_VARS_PLACEHOLDER, _datos_sem, _semanas)
    except Exception as _e:
        st.exception(_e)

with tab_mkt:
    try:
        _df_men, _vc, _pc = _cargar_datos_mkt()
        _mes_mkt, _q_mkt, _yr_mkt = _construir_datos_mkt(_df_men, _vc, _pc)
    except Exception as e:
        st.error(f"Error cargando datos MKT: {e}")
        _mes_mkt = _q_mkt = _yr_mkt = {}

    try:
        _col_main, _col_sem = st.columns([4, 1])
        with _col_main:
            render_t90_tabla(_MKT_KPIS, datos_mes=_mes_mkt, datos_q=_q_mkt, datos_yr=_yr_mkt)
        with _col_sem:
            if _semanas:
                _kpis_sem = [k for k in _MKT_KPIS if k[1] != "sep" and k[0] not in ("Ventas cohort", "CPV Co", "Tasa Vtas (Co)/Leads")]
                render_semanas_tabla(_kpis_sem, _datos_sem, _semanas)
    except Exception as _e:
        st.exception(_e)

_FIN_KPIS = [
    ("Facturación",    "usd"),
    ("Profit",         "usd"),
    ("Profit (%)",     "pct"),
    ("Crecimiento USD","usd"),
    ("Usuarios totales","num"),
    ("Arg",            "num", "sub"),
    ("Ext",            "num", "sub"),
    ("Tkt promedio",   "usd"),
]

def _construir_datos_fin(datos_mes: dict):
    """
    Agrega Finanzas por Q y año con la lógica correcta:
    - Facturación, Profit, Crecimiento USD: suma
    - Profit (%): Profit/Facturación recalculado
    - Usuarios totales, Arg, Ext: último mes del período (es un stock)
    - Tkt promedio: Facturación/Usuarios totales del período
    """
    # Acumular crudos por Q y año
    _SUMA  = ("Facturación", "Profit", "Crecimiento USD")
    _STOCK = ("Usuarios totales", "Arg", "Ext")

    raw_q  = {}   # (y, qnum) -> {k: v}
    raw_yr = {}   # y -> {k: v}

    # Ordenar meses para que el "último" sea correcto
    for (y, m) in sorted(datos_mes.keys()):
        vals = datos_mes[(y, m)]
        qnum = (m - 1) // 3 + 1

        for acc, key in [(raw_q, (y, qnum)), (raw_yr, y)]:
            if key not in acc:
                acc[key] = {k: 0 for k in _SUMA}
                acc[key].update({k: None for k in _STOCK})
                acc[key]["_y"] = y

            for k in _SUMA:
                if vals.get(k) is not None:
                    acc[key][k] = (acc[key].get(k) or 0) + vals[k]
            for k in _STOCK:
                if vals.get(k) is not None:
                    acc[key][k] = vals[k]   # sobreescribir → queda el último mes

    def _to_kpis(r):
        fact = r.get("Facturación") or 0
        prof = r.get("Profit") or 0
        usu  = r.get("Usuarios totales")
        return {
            "Facturación":     fact if fact else None,
            "Profit":          prof if prof else None,
            "Profit (%)":      prof / fact * 100 if fact else None,
            "Crecimiento USD": r.get("Crecimiento USD"),
            "Usuarios totales":usu,
            "Arg":             r.get("Arg"),
            "Ext":             r.get("Ext"),
            "Tkt promedio":    fact / usu if usu else None,
        }

    datos_q  = {k: _to_kpis(r) for k, r in raw_q.items()}
    datos_yr = {y: _to_kpis(r) for y, r in raw_yr.items()}
    return datos_mes, datos_q, datos_yr

with tab_fin:
    try:
        _mes_fin_raw = datos_crm.cargar_finanzas()
        _mes_fin, _q_fin, _yr_fin = _construir_datos_fin(_mes_fin_raw)
    except Exception as e:
        st.error(f"Error cargando datos Finanzas: {e}")
        _mes_fin = _q_fin = _yr_fin = {}
    try:
        render_t90_tabla(_FIN_KPIS, datos_mes=_mes_fin, datos_q=_q_fin, datos_yr=_yr_fin)
    except Exception as _e:
        st.exception(_e)

_CS_KPIS = [
    ("Bajas totales",           "num"),
    ("Bajas 2026",              "num", "sub"),
    ("Bajas pre 2026",          "num", "sub"),
    ("Churn $",                 "pending"),
    ("Churn %",                 "pending"),
    ("Usuarios totales",        "num"),
    ("Clientes en OB",          "num"),
    ("OB en SLA (≤30d)",        "num", "sub"),
    ("OB fuera de SLA (>30d)",  "num", "sub"),
]

_OB_KEYS = ("Clientes en OB", "OB en SLA (≤30d)", "OB fuera de SLA (>30d)")

def _construir_datos_cs(bajas: dict, fin: dict, ob_snap: dict) -> tuple:
    """
    bajas:   {(y,m): {"Bajas totales", "Bajas 2026", "Bajas pre 2026"}}
    fin:     {(y,m): {"Usuarios totales": ...}}
    ob_snap: {"Clientes en OB": n, "OB en SLA (≤30d)": n1, "OB fuera de SLA (>30d)": n2}
             — foto actual, se asigna solo al mes corriente
    """
    _SUMA_KEYS  = ("Bajas totales", "Bajas 2026", "Bajas pre 2026")
    _STOCK_KEYS = ("Usuarios totales",) + _OB_KEYS

    import datetime as _dt
    _hoy = _dt.date.today()
    _mes_cur = (_hoy.year, _hoy.month)

    all_keys = set(bajas) | set(fin) | {_mes_cur}
    datos_mes: dict = {}
    for (y, m) in all_keys:
        d = {}
        d.update(bajas.get((y, m), {}))
        d["Usuarios totales"] = fin.get((y, m), {}).get("Usuarios totales")
        if (y, m) == _mes_cur and ob_snap:
            d.update({k: ob_snap.get(k) for k in _OB_KEYS})
        datos_mes[(y, m)] = d

    raw_q: dict = {}
    raw_yr: dict = {}
    for (y, m) in sorted(datos_mes):
        vals = datos_mes[(y, m)]
        qnum = (m - 1) // 3 + 1
        for acc, key in [(raw_q, (y, qnum)), (raw_yr, y)]:
            if key not in acc:
                acc[key] = {k: 0 for k in _SUMA_KEYS}
                acc[key].update({k: None for k in _STOCK_KEYS})
                acc[key]["_y"] = y if isinstance(key, int) else key[0]
            for k in _SUMA_KEYS:
                if vals.get(k) is not None:
                    acc[key][k] = (acc[key].get(k) or 0) + vals[k]
            for k in _STOCK_KEYS:
                if vals.get(k) is not None:
                    acc[key][k] = vals[k]

    def _to_kpis(r):
        return {
            "Bajas totales":           r.get("Bajas totales")  or None,
            "Bajas 2026":              r.get("Bajas 2026")     or None,
            "Bajas pre 2026":          r.get("Bajas pre 2026") or None,
            "Usuarios totales":        r.get("Usuarios totales"),
            "Clientes en OB":          r.get("Clientes en OB"),
            "OB en SLA (≤30d)":        r.get("OB en SLA (≤30d)"),
            "OB fuera de SLA (>30d)":  r.get("OB fuera de SLA (>30d)"),
        }

    datos_q  = {k: _to_kpis(r) for k, r in raw_q.items()}
    datos_yr = {y: _to_kpis(r) for y, r in raw_yr.items()}
    return datos_mes, datos_q, datos_yr

with tab_cs:
    try:
        _bajas_cs  = datos_crm.cargar_bajas_t90()
        _fin_cs    = datos_crm.cargar_finanzas()
        _snaps     = datos_crm.actualizar_snapshots_ob()
        _ob_snap   = datos_crm.cargar_ob_t90()
        # Foto mensual: usar snapshot guardado si existe, sino live
        import datetime as _dt_cs
        _hoy_cs    = _dt_cs.date.today()
        _mes_cur_key = f"{_hoy_cs.year}-{_hoy_cs.month:02d}"
        _mes_prev_key = (_hoy_cs.replace(day=1) - _dt_cs.timedelta(days=1)).strftime("%Y-%m")
        # Mes anterior: siempre desde snapshot (ya cerrado)
        # Mes actual: live
        _ob_snap_mes = dict(_ob_snap)  # live para el mes actual
        _mes_cs, _q_cs, _yr_cs = _construir_datos_cs(_bajas_cs, _fin_cs, _ob_snap_mes)
        # Sobreescribir mes anterior con snapshot definitivo si existe
        if _mes_prev_key in _snaps["monthly"]:
            _prev = _snaps["monthly"][_mes_prev_key]
            _py, _pm = int(_mes_prev_key[:4]), int(_mes_prev_key[5:])
            if (_py, _pm) in _mes_cs:
                _mes_cs[(_py, _pm)].update(_prev)
    except Exception as e:
        st.error(f"Error cargando datos CS: {e}")
        _mes_cs = _q_cs = _yr_cs = {}
        _ob_snap = {}
        _snaps   = {"weekly": {}, "monthly": {}}

    # Datos semanales CS: snapshots históricos + live semana actual
    _datos_sem_cs: dict = {}
    if _semanas:
        for _s in _semanas:
            _sk = _s.strftime("%Y-%m-%d")
            if _sk in _snaps["weekly"]:
                _datos_sem_cs[_s] = _snaps["weekly"][_sk]
        # Semana actual: si no hay snapshot guardado todavía, usar live
        _lunes_cur = _semanas[-1]
        if _lunes_cur not in _datos_sem_cs and _ob_snap:
            _datos_sem_cs[_lunes_cur] = _ob_snap

    try:
        _col_main, _col_sem = st.columns([4, 1])
        with _col_main:
            render_t90_tabla(_CS_KPIS, datos_mes=_mes_cs, datos_q=_q_cs, datos_yr=_yr_cs)
        with _col_sem:
            if _semanas:
                _kpis_sem_cs = [k for k in _CS_KPIS if k[1] != "sep"]
                render_semanas_tabla(_kpis_sem_cs, _datos_sem_cs, _semanas)
    except Exception as _e:
        st.exception(_e)
