import streamlit as st
import streamlit.components.v1 as components
import urllib.request, urllib.parse, csv, io, json, re
from datetime import datetime

_SHEET_ID = "1hLhYgVwE1uRLiqCZKsAr9b3k3VSZYqYORdPURdvjPKs"

# ── helpers ──────────────────────────────────────────────────────────────────

def _fetch(sheet_id, tab):
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(tab)}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
    return list(csv.reader(io.StringIO(raw)))

def _parse_usd(s):
    """'USD $43.232,50' → 43232.50  |  '' → None"""
    if not s or s.strip() in ("", "-"):
        return None
    s = s.replace("USD", "").replace("$", "").strip()
    # Spanish format: . = thousands, , = decimal
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None

def _fmt(v, compact=False):
    if v is None:
        return "–"
    if compact:
        if abs(v) >= 1_000:
            return f"$ {v/1_000:,.0f}k".replace(",", ".")
        return f"$ {v:,.0f}".replace(",", ".")
    return f"$ {v:,.0f}".replace(",", ".")

def _pct(v, base):
    if v is None or not base:
        return "–"
    return f"{v/base*100:.1f}%"

# ── loaders ──────────────────────────────────────────────────────────────────

def _fetch_full(sheet_id, tab):
    """Fetch all rows — reads from local parquet cache if available."""
    import os, pandas as pd, urllib.parse as _up
    _cache_names = {
        "Real 2026":                  "er_Real_2026.parquet",
        "Real 2025":                  "er_Real_2025.parquet",
        "Unificado real 2025-2026":   "er_Unificado_real_2025_2026.parquet",
    }
    cache_file = _cache_names.get(tab)
    if cache_file:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache", cache_file)
        if os.path.exists(path):
            df = pd.read_parquet(path)
            # reconstruct rows as list of lists (header + data)
            rows = [list(df.columns)]
            for _, row in df.iterrows():
                rows.append([str(v) if v == v else "" for v in row])
            return rows
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/gviz/tq?tqx=out:csv&sheet={_up.quote(tab)}&range=A1:Z300")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
    return list(csv.reader(io.StringIO(raw)))

def _parse_rows_range(rows, start, end, col_offset, months):
    """Extract sub-item rows (label, [vals]) for rows[start:end]."""
    detail = []
    for r in rows[start:end]:
        lbl = r[0].strip()
        if not lbl:
            continue
        vals = [_parse_usd(r[col_offset + i] if (col_offset + i) < len(r) else "")
                for i in range(len(months))]
        detail.append((lbl, vals))
    return detail

@st.cache_data(ttl=1800)
def _load_2026():
    rows   = _fetch_full(_SHEET_ID, "Real 2026")
    months = [c for c in rows[0][3:] if c.strip()]
    n, o   = len(months), 3
    def _vals(i):
        r = rows[i] if i < len(rows) else []
        return [_parse_usd(r[o+j] if o+j < len(r) else "") for j in range(n)]
    def _row(name):
        for r in rows:
            if r[0].strip().lower() == name.strip().lower():
                return [_parse_usd(r[o+j] if o+j < len(r) else "") for j in range(n)]
        return [None] * n

    # rows 5-13: ingresos block
    ingresos_groups = [
        ("Ingresos recurrentes",        _vals(6),  [("Recurrente ARG", _vals(7)), ("Recurrente EXT", _vals(8))]),
        ("Ingresos por implementación", _vals(9),  [("Implementación ARG", _vals(10)), ("Implementación EXTERIOR", _vals(11))]),
        ("Otros ingresos",              _vals(12), [("Puente", _vals(13))]),
    ]
    # rows 15-43: sueldos block
    sueldos_groups = [
        ("CEOs",                      _vals(16), [("CEO Holding", _vals(17)), ("CEO Empresa", _vals(18))]),
        ("Sistemas",                  _vals(19), [("Sist. a Medida", _vals(20)), ("Dev. FS Sr", _vals(21))]),
        ("Customer Success",          _vals(22), [("Supervisor CS", _vals(23)), ("Estratega", _vals(24)), ("Implementadores", _vals(25)), ("Soporte", _vals(26)), ("Analista Fidelización", _vals(27))]),
        ("Marketing",                 _vals(28), [("Supervisor Mkt", _vals(29)), ("Paid Media", _vals(30)), ("Content Creator", _vals(31)), ("Diseño", _vals(32)), ("AS - Líder", _vals(33))]),
        ("Ventas - Comercial",        _vals(34), [("Closer", _vals(35)), ("Call Confirmer", _vals(36))]),
        ("Administración y Finanzas", _vals(37), [("Líder de Finanzas", _vals(38)), ("Administración", _vals(39)), ("Data Analyst", _vals(40))]),
        ("Recursos Humanos",          _vals(41), [("Honorarios RRHH", _vals(42)), ("Mejora Continua", _vals(43))]),
    ]

    return {
        "months":            months,
        "ingresos":          _row("Ingresos totales s/iva"),
        "total_gastos":      _row("Total gastos s/IVA"),
        "sueldos":           _row("Total Sueldos"),
        "publicidad":        _row("Publicidad"),
        "estructura":        _row("Costos Estructura"),
        "variables":         _row("Variables"),
        "otros_op":          _row("Otros Operación"),
        "profit_economico":  _row("Profit económico empresa"),
        "profit_real":       _row("Profit real retiro"),
        "pago_iva":          _row("Pago de IVA"),
        "dolar":             _row("Dólar"),
        "ingresos_groups":   ingresos_groups,
        "sueldos_groups":    sueldos_groups,
        "publicidad_detail": _parse_rows_range(rows, 45, 50, o, months),
        "estructura_detail": _parse_rows_range(rows, 51, 71, o, months),
        "variables_detail":  _parse_rows_range(rows, 72, 81, o, months),
        "otros_op_detail":   _parse_rows_range(rows, 82, 90, o, months),
    }

@st.cache_data(ttl=1800)
def _load_2025():
    rows   = _fetch_full(_SHEET_ID, "Real 2025")
    months = [c for c in rows[0][1:] if c.strip()]
    n, o   = len(months), 1
    def _vals(i):
        r = rows[i] if i < len(rows) else []
        return [_parse_usd(r[o+j] if o+j < len(r) else "") for j in range(n)]
    def _row(name):
        for r in rows:
            if r[0].strip().lower() == name.strip().lower():
                return [_parse_usd(r[o+j] if o+j < len(r) else "") for j in range(n)]
        return [None] * n

    # rows 2-9: ingresos block
    ingresos_groups = [
        ("Ingresos recurrentes",        _vals(3), []),
        ("Ingresos por implementación", _vals(4), []),
        ("Otros Ingresos",              _vals(5), [("Comisiones Marketing Simple", _vals(6)), ("Diferencia positiva TC", _vals(7)), ("Interés Ganado", _vals(8)), ("Puente", _vals(9))]),
    ]
    # rows 11-44: sueldos block
    sueldos_groups = [
        ("CEOs",                      _vals(12), [("CEO Empresa", _vals(13)), ("CEO Holding", _vals(14))]),
        ("Sistemas",                  _vals(15), [("Software a Medida", _vals(16))]),
        ("Customer Success",          _vals(17), [("Diseño", _vals(18)), ("Soporte", _vals(19)), ("Estratega", _vals(20)), ("Implementadores", _vals(21)), ("Líder CS", _vals(22)), ("Onboarding", _vals(23))]),
        ("Marketing",                 _vals(24), [("AS - Líder", _vals(25)), ("AS - Setters", _vals(26)), ("Content Creator", _vals(27)), ("Líder Marketing", _vals(28)), ("Paid Media", _vals(29)), ("Trafficker", _vals(30))]),
        ("Ventas - Comercial",        _vals(31), [("Back", _vals(32)), ("Call Confirmer", _vals(33)), ("Líder Ventas", _vals(34)), ("Comisiones por ventas", _vals(35)), ("Reuniones", _vals(36))]),
        ("Administración y Finanzas", _vals(37), [("Administración", _vals(38)), ("CFO Holding", _vals(39)), ("CFO Bono", _vals(40)), ("Finanzas", _vals(41))]),
        ("Recursos Humanos",          _vals(42), [("Honorarios RRHH", _vals(43)), ("Mejora continua", _vals(44))]),
    ]

    return {
        "months":            months,
        "ingresos":          _row("Ingresos totales s/iva"),
        "total_gastos":      _row("Total gastos s/IVA"),
        "sueldos":           _row("Total Sueldos"),
        "publicidad":        _row("Publicidad"),
        "estructura":        _row("Costos de Estructura"),
        "variables":         _row("Variables"),
        "otros_op":          _row("Otros Operación"),
        "profit_economico":  _row("Profit económico empresa"),
        "profit_real":       _row("Profit real retiro"),
        "pago_iva":          _row("Pago de IVA"),
        "dolar":             _row("Tipo de cambio"),
        "ingresos_groups":   ingresos_groups,
        "sueldos_groups":    sueldos_groups,
        "publicidad_detail": _parse_rows_range(rows, 46, 48, o, months),
        "estructura_detail": _parse_rows_range(rows, 49, 68, o, months),
        "variables_detail":  _parse_rows_range(rows, 69, 78, o, months),
        "otros_op_detail":   _parse_rows_range(rows, 79, 89, o, months),
    }

_MONTH_ORDER = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sept": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

def _month_ts(lbl):
    """'ene-25' → datetime(2025,1,1)"""
    try:
        parts = lbl.strip().split("-")
        m = _MONTH_ORDER.get(parts[0].lower(), 0)
        y = 2000 + int(parts[1])
        return datetime(y, m, 1)
    except Exception:
        return datetime(2000, 1, 1)

@st.cache_data(ttl=1800)
def _load_t12():
    rows      = _fetch_full(_SHEET_ID, "Unificado real 2025-2026")
    months = [c for c in rows[0][1:] if c.strip()]
    n      = len(months)
    o      = 1   # column offset: all months from ene-25

    def _vals(i):
        r = rows[i] if i < len(rows) else []
        return [_parse_usd(r[o + j] if o + j < len(r) else "") for j in range(n)]

    def _row(name):
        for r in rows:
            if r[0].strip().lower() == name.strip().lower():
                return [_parse_usd(r[o + j] if o + j < len(r) else "") for j in range(n)]
        return [None] * n

    ingresos_groups = [
        ("Ingresos recurrentes",        _vals(2),  [("Recurrente ARG", _vals(3)), ("Recurrente EXT", _vals(4))]),
        ("Ingresos por implementación", _vals(5),  [("Implementación ARG", _vals(6)), ("Implementación EXTERIOR", _vals(7))]),
        ("Otros ingresos",              _vals(8),  [("Comisiones Marketing Simple", _vals(9)), ("Diferencia positiva TC", _vals(10)), ("Interés Ganado", _vals(11)), ("Puente", _vals(12))]),
    ]
    sueldos_groups = [
        ("CEOs",                      _vals(15), [("CEO Holding", _vals(16)), ("CEO Empresa", _vals(17))]),
        ("Sistemas",                  _vals(18), [("Sist. a Medida", _vals(19)), ("Dev. FS Sr", _vals(20))]),
        ("Customer Success",          _vals(21), [("Supervisor CS", _vals(22)), ("Estratega", _vals(23)), ("Implementadores", _vals(24)), ("Soporte", _vals(25)), ("Analista Fidelización", _vals(26)), ("OB", _vals(27)), ("Diseño", _vals(28))]),
        ("Marketing",                 _vals(29), [("Supervisor Mkt", _vals(30)), ("Paid Media", _vals(31)), ("Content Creator", _vals(32)), ("Diseño Mkt", _vals(33)), ("AS - Líder", _vals(34)), ("AS - Setters", _vals(35)), ("Trafficker", _vals(36))]),
        ("Ventas - Comercial",        _vals(37), [("Closer", _vals(38)), ("Call Confirmer", _vals(39)), ("Back", _vals(40)), ("Líder Ventas", _vals(42)), ("Comisiones por ventas", _vals(43)), ("Reuniones", _vals(44))]),
        ("Administración y Finanzas", _vals(45), [("Líder de Finanzas", _vals(46)), ("Administración", _vals(47)), ("Data Analyst", _vals(48)), ("CFO Bono", _vals(49)), ("Finanzas", _vals(50))]),
        ("Recursos Humanos",          _vals(51), [("Honorarios RRHH", _vals(52)), ("Mejora Continua", _vals(53))]),
    ]

    return {
        "months":            months,
        "ingresos":          _row("Ingresos totales s/iva"),
        "total_gastos":      _row("Total gastos s/IVA"),
        "sueldos":           _row("Total Sueldos"),
        "publicidad":        _row("Publicidad"),
        "estructura":        _row("Costos Estructura"),
        "variables":         _row("Variables"),
        "otros_op":          _row("Otros Operación"),
        "profit_economico":  _row("Profit económico empresa"),
        "profit_real":       _row("Profit real retiro"),
        "pago_iva":          _row("Pago de IVA"),
        "dolar":             None,
        "ingresos_groups":   ingresos_groups,
        "sueldos_groups":    sueldos_groups,
        "publicidad_detail": _parse_rows_range(rows, 55, 60, o, months),
        "estructura_detail": _parse_rows_range(rows, 61, 82, o, months),
        "variables_detail":  _parse_rows_range(rows, 83, 95, o, months),
        "otros_op_detail":   _parse_rows_range(rows, 96, 106, o, months),
    }

# ── render ───────────────────────────────────────────────────────────────────

def _sum(vals):
    if vals is None:
        return None
    v = [x for x in vals if x is not None]
    return sum(v) if v else None

def _avg(vals):
    if vals is None:
        return None
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None

def _render(d, year):
    months  = d["months"]
    n       = len(months)

    # ── Build table data ──────────────────────────────────────────────────────
    def _row_data(key):
        return d.get(key) or [None] * n

    _grp_id = [0]
    def _next_id():
        _grp_id[0] += 1
        return f"grp{_grp_id[0]}"

    # 4th field = parent_key: this row is a child of that parent
    # Both years: Ingresos (no sub-items) | Total gastos with 5 sub-items
    STRUCTURE = [
        ("INGRESOS",           None,              "section",   None),
        ("Ingresos totales",   "ingresos",        "total",     None),
        ("EGRESOS",            None,              "section",   None),
        ("Total gastos",       "total_gastos",    "total",     None),
        ("  Sueldos",          "sueldos",         "sub",       "total_gastos"),
        ("  Publicidad",       "publicidad",      "sub",       "total_gastos"),
        ("  Costos estructura","estructura",      "sub",       "total_gastos"),
        ("  Variables",        "variables",       "sub",       "total_gastos"),
        ("  Otros Operación",  "otros_op",        "sub",       "total_gastos"),
        ("RESULTADO",          None,              "section",   None),
        ("Profit económico",   "profit_economico","result",    None),
        ("Profit real",        "profit_real",     "highlight", None),
        ("Pago IVA",           "pago_iva",        "sub",       None),
    ]

    # Pre-assign group IDs for parent rows (rows with children in STRUCTURE)
    parent_to_grp = {}
    for _, key, _, parent_key in STRUCTURE:
        if parent_key and parent_key not in parent_to_grp:
            parent_to_grp[parent_key] = _next_id()

    # ── HTML table ────────────────────────────────────────────────────────────
    # Color hierarchy: section (dark navy) > total/principal (light blue bold) >
    #                  sub (medium gray bold) > detail rows (light, italic)
    STYLE_MAP = {
        "section":   {"bg": "#1a3a5c", "color": "white",   "fw": "700", "fs": "0.73rem", "indent": "0"},
        "total":     {"bg": "#bfdbfe", "color": "#1e3a5f", "fw": "700", "fs": "0.75rem", "indent": "0"},
        "sub":       {"bg": "#dde3ea", "color": "#1e293b", "fw": "600", "fs": "0.73rem", "indent": "12px"},
        "result":    {"bg": "#e0f2fe", "color": "#0369a1", "fw": "600", "fs": "0.73rem", "indent": "0"},
        "highlight": {"bg": "#d1fae5", "color": "#065f46", "fw": "700", "fs": "0.77rem", "indent": "0"},
    }

    _STICKY = "position:sticky;left:0;z-index:3;"
    _DET_BG = "#fafafa"

    def _td(val, bg, color, fw, fs, align="right"):
        return (f'<td style="padding:3px 7px;border:1px solid #e2e8f0;'
                f'background:{bg};color:{color};font-weight:{fw};font-size:{fs};'
                f'text-align:{align};white-space:nowrap">{val}</td>')

    # keys that expand into groups (3-level: L2 group totals + L3 items)
    GROUPS_MAP = {
        "ingresos": "ingresos_groups",
        "sueldos":  "sueldos_groups",
    }
    # keys that expand into flat detail rows
    DETAIL_MAP = {
        "publicidad": "publicidad_detail",
        "estructura": "estructura_detail",
        "variables":  "variables_detail",
        "otros_op":   "otros_op_detail",
    }

    def _detail_rows_html(detail, grp, bg, color, fs, indent_px=28):
        if not detail:
            return ""
        out = ""
        for lbl, vals in detail:
            tot = _sum(vals)
            out += f'<tr class="det-{grp}" style="display:none">'
            out += (f'<td style="{_STICKY}padding:2px 8px 2px {indent_px}px;border:1px solid #e2e8f0;'
                    f'background:{_DET_BG};color:{color};font-size:0.7rem;'
                    f'text-align:left;white-space:nowrap;font-style:italic">{lbl}</td>')
            for v in vals:
                out += _td(_fmt(v) if v is not None else "–", _DET_BG, color, "400", "0.7rem")
            out += _td(_fmt(tot) if tot is not None else "–", "#f1f5f9", color, "400", "0.7rem")
            out += '</tr>'
        return out

    def _groups_rows_html(groups, l1_grp, color):
        """Render 3-level rows: L2=group totals, L3=individual items."""
        out = ""
        _DET2 = "#f0f4f8"
        _DET3 = "#fafafa"
        for gi, (gname, gvals, items) in enumerate(groups):
            g2 = f"{l1_grp}-g{gi}"
            tot = _sum(gvals)
            has_items = items and len(items) > 0
            toggle2 = (f'<button id="btn-{g2}" class="tog" onclick="tog(\'{g2}\')">'
                       f'&#9654;</button>') if has_items else ""
            # L2 row
            out += f'<tr class="det-{l1_grp}" style="display:none">'
            out += (f'<td style="{_STICKY}padding:2px 8px 2px 18px;border:1px solid #e2e8f0;'
                    f'background:{_DET2};color:{color};font-size:0.72rem;font-weight:600;'
                    f'text-align:left;white-space:nowrap">{toggle2}{gname}</td>')
            for v in gvals:
                out += _td(_fmt(v) if v is not None else "–", _DET2, color, "600", "0.72rem")
            out += _td(_fmt(tot) if tot is not None else "–", "#dbeafe", color, "600", "0.72rem")
            out += '</tr>'
            # L3 rows
            if has_items:
                for iname, ivals in items:
                    itot = _sum(ivals)
                    out += f'<tr class="det-{g2}" style="display:none">'
                    out += (f'<td style="{_STICKY}padding:2px 8px 2px 34px;border:1px solid #e2e8f0;'
                            f'background:{_DET3};color:{color};font-size:0.68rem;'
                            f'text-align:left;white-space:nowrap;font-style:italic">{iname}</td>')
                    for v in ivals:
                        out += _td(_fmt(v) if v is not None else "–", _DET3, color, "400", "0.68rem")
                    out += _td(_fmt(itot) if itot is not None else "–", "#f1f5f9", color, "400", "0.68rem")
                    out += '</tr>'
        return out

    # header
    CSS = """
    <style>
    * { box-sizing: border-box; margin: 0; }
    body { font-family: system-ui, sans-serif; background: #fff; }
    .wrap { overflow-x: auto; }
    table { border-collapse: collapse; }
    .tog { background: none; border: none; cursor: pointer; font-size: 0.7rem;
           color: #64748b; padding: 0 4px 0 0; vertical-align: middle; transition: transform .2s; }
    .tog.open { transform: rotate(90deg); }
    </style>
    """
    JS = """
    <script>
    function tog(id) {
      var rows = document.querySelectorAll('.det-' + id);
      var btn  = document.getElementById('btn-' + id);
      var open = btn.classList.toggle('open');
      rows.forEach(function(r) { r.style.display = open ? '' : 'none'; });
      if (!open) {
        // Close child sub-groups when parent closes
        document.querySelectorAll('[id^="btn-' + id + '-"]').forEach(function(sb) {
          if (sb.classList.contains('open')) {
            sb.classList.remove('open');
            var sid = sb.id.slice(4);
            document.querySelectorAll('.det-' + sid).forEach(function(r) {
              r.style.display = 'none';
            });
          }
        });
      }
    }
    </script>
    """

    h = CSS + '<div class="wrap"><table>'
    h += '<thead><tr>'
    h += (f'<th style="{_STICKY}background:#1a3a5c;color:white;padding:4px 10px;'
          f'text-align:left;font-size:0.72rem;border:1px solid #e2e8f0;min-width:170px">Concepto</th>')
    for m in months:
        h += (f'<th style="background:#1a3a5c;color:white;padding:4px 7px;text-align:right;'
              f'font-size:0.7rem;border:1px solid #e2e8f0;white-space:nowrap">{m}</th>')
    h += (f'<th style="background:#0f2743;color:white;padding:4px 7px;text-align:right;'
          f'font-size:0.7rem;border:1px solid #e2e8f0">Total</th>')
    h += '</tr></thead><tbody>'

    # Darker shades for the Total column (one tone stronger than row bg)
    TOTAL_COL_BG = {
        "section":   "#1a3a5c",
        "total":     "#7ab2f4",
        "sub":       "#b0bdc8",
        "result":    "#7dd3fc",
        "highlight": "#6ee7b7",
    }

    detail_row_count = 0
    for row_entry in STRUCTURE:
        label, key, style, parent_key = row_entry
        s = STYLE_MAP[style]
        bg, color, fw, fs = s["bg"], s["color"], s["fw"], s["fs"]
        indent = s["indent"]
        label_disp = label.strip()

        if style == "section":
            h += '<tr>'
            h += (f'<td style="{_STICKY}background:{bg};color:{color};font-weight:{fw};'
                  f'font-size:{fs};padding:5px 12px;border:1px solid #475569;'
                  f'letter-spacing:.04em">{label_disp}</td>')
            for _ in range(n + 1):
                h += (f'<td style="background:{bg};border:1px solid #475569"></td>')
            h += '</tr>'
            continue

        vals = _row_data(key) if key else [None] * n
        total = _sum(vals)
        bg2   = TOTAL_COL_BG[style]
        total_c = "#b91c1c" if (total is not None and total < 0) else color

        # ── expand buttons ────────────────────────────────────────────────────
        # 1. Structure-level parent toggle (expands/collapses child STRUCTURE rows)
        struct_grp = parent_to_grp.get(key)  # this row is a parent of other STRUCTURE rows
        struct_btn = (f'<button id="btn-{struct_grp}" class="tog open" onclick="tog(\'{struct_grp}\')">'
                      f'&#9654;</button>') if struct_grp else ""

        # 2. Detail-level toggle (expands leaf items from Google Sheet data)
        groups    = d.get(GROUPS_MAP.get(key, ""), None) if key else None
        detail    = d.get(DETAIL_MAP.get(key, ""), None) if (key and not groups) else None
        has_detail = bool(groups or detail)
        if has_detail:
            det_grp = _next_id()
            if groups:
                detail_row_count += len(groups) + sum(len(it) for _, _, it in groups if it)
            else:
                detail_row_count += len(detail)
            det_btn = f'<button id="btn-{det_grp}" class="tog" onclick="tog(\'{det_grp}\')">&#9654;</button>'
        else:
            det_grp = None
            det_btn = ""

        toggle_btn = struct_btn + det_btn

        label_cell = (f'<span style="padding-left:{indent}">{label_disp}</span>'
                      if indent != "0" else label_disp)

        # ── row classes (hidden if this row is a child of a parent group) ────
        if parent_key and parent_key in parent_to_grp:
            p_grp = parent_to_grp[parent_key]
            row_cls = f' class="det-{p_grp}"'
            row_display = ""   # start expanded
        else:
            row_cls = ""
            row_display = ""

        h += f'<tr{row_cls}{row_display}>'
        h += (f'<td style="{_STICKY}padding:3px 8px;border:1px solid #e2e8f0;'
              f'background:{bg};color:{color};font-weight:{fw};font-size:{fs};text-align:left">'
              f'{toggle_btn}{label_cell}</td>')
        for v in vals:
            cell = _fmt(v) if v is not None else "–"
            _c = "#b91c1c" if (v is not None and v < 0 and style in ("highlight","result","total")) else color
            h += _td(cell, bg, _c, fw, fs)
        h += _td(_fmt(total) if total is not None else "–", bg2, total_c, fw, fs)
        h += '</tr>'

        if det_grp and groups:
            h += _groups_rows_html(groups, det_grp, color)
        elif det_grp and detail:
            h += _detail_rows_html(detail, det_grp, bg, color, fs)

    h += '</tbody></table></div>'
    h += JS

    n_visible = len([s for _, _, s, _ in STRUCTURE if s != "section"])
    height = n_visible * 32 + detail_row_count * 28 + 80

    components.html(
        f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>{h}</body></html>',
        height=height,
        scrolling=False,
    )

# ── main ─────────────────────────────────────────────────────────────────────

st.markdown("## Estado de Resultados")

col_yr, _ = st.columns([2, 6])
with col_yr:
    year = st.radio("Vista", ["25-26", "26", "25"], horizontal=True, label_visibility="collapsed")

st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

try:
    if year == "25-26":
        data = _load_t12()
    elif year == "26":
        data = _load_2026()
    else:
        data = _load_2025() if year == "25" else _load_2025()
    _render(data, year)
except Exception as e:
    st.error(f"Error cargando datos: {e}")
