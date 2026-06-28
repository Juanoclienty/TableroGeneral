"""
graficos.py — Funciones para crear los gráficos del dashboard.
Cada función recibe un DataFrame y retorna una figura de Plotly.
Podés modificar colores, estilos y títulos acá sin tocar app.py.
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# ============================================================
# PALETA DE COLORES
# Cambiá estos valores si querés ajustar los colores del dashboard
# ============================================================
COLOR_GF       = "#22c55e"   # verde (Good Fit)
COLOR_PF       = "#f59e0b"   # naranja (Partially Bad Fit)
COLOR_BF       = "#ef4444"   # rojo (Bad Fit)
COLOR_SIN_DATA = "#94a3b8"   # gris (Sin clasificación)
COLOR_CPL      = "#3b82f6"   # azul (CPL)
COLOR_CPL_GF   = "#8b5cf6"   # violeta (CPL GF)
COLOR_OBJ      = "#64748b"   # gris oscuro (objetivo)

LAYOUT_BASE = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=10, r=10, t=35, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    font=dict(family="sans-serif", size=12),
)


def bar_calidad_por_semana(df: pd.DataFrame) -> go.Figure:
    """
    Gráfico de barras apiladas: GF / PF / BF / Sin data por semana.
    Se muestra cuando no hay ninguna fila seleccionada en la tabla.
    """
    labels = df["fecha_ini"].dt.strftime("%d/%m")

    fig = go.Figure()
    for col, nombre, color in [
        ("gf",       "GF",        COLOR_GF),
        ("pf",       "PF",        COLOR_PF),
        ("bf",       "BF",        COLOR_BF),
        ("sin_data", "Sin datos", COLOR_SIN_DATA),
    ]:
        fig.add_trace(go.Bar(
            x=labels,
            y=df[col],
            name=nombre,
            marker_color=color,
            hovertemplate=f"<b>{nombre}</b>: %{{y}}<extra></extra>",
        ))

    # Línea de CPL sobre eje secundario
    fig.add_trace(go.Scatter(
        x=labels,
        y=df["cpl"],
        name="CPL ($)",
        mode="lines+markers",
        line=dict(color=COLOR_CPL, width=2),
        marker=dict(size=6),
        yaxis="y2",
        hovertemplate="CPL: $%{y:.0f}<extra></extra>",
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="stack",
        height=340,
        yaxis=dict(title="Leads"),
        yaxis2=dict(
            title="CPL ($)",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
    )
    return fig


def pie_y_metricas(df_sel: pd.DataFrame) -> go.Figure:
    """
    Gráfico de torta con la distribución GF/PF/BF para las filas seleccionadas.
    """
    totales = {
        "GF":        df_sel["gf"].sum(),
        "PF":        df_sel["pf"].sum(),
        "BF":        df_sel["bf"].sum(),
        "Sin datos": df_sel["sin_data"].sum(),
    }
    # Quitar categorías con 0
    labels = [k for k, v in totales.items() if v > 0]
    values = [v for v in totales.values() if v > 0]
    colors = [COLOR_GF, COLOR_PF, COLOR_BF, COLOR_SIN_DATA][:len(labels)]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.45,
        marker_colors=colors,
        textinfo="label+percent",
        hovertemplate="%{label}: %{value} leads<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="Calidad de leads (selección)",
        height=300,
        showlegend=False,
    )
    return fig


def embudo_ventas(data: dict) -> go.Figure:
    """
    Funnel chart con dos porcentajes por capa y fugas con % sobre fase anterior.
    data = {
      capas: [leads, r1, r2, presu, venta],
      labels: [...],
      fuga_leads: [(nombre, n), ...],
      fuga_r1:    [(nombre, n), ...],
      fuga_r2:    [(nombre, n), ...],
    }
    """
    capas  = data["capas"]
    labels = data["labels"]
    total  = capas[0] if capas[0] > 0 else 1
    n      = len(capas)

    COLORES = ["#3b82f6", "#22c55e", "#06b6d4", "#f59e0b", "#8b5cf6", "#10b981"]

    x_visual = [v ** 0.5 for v in capas]
    max_x    = x_visual[0] if x_visual[0] > 0 else 1

    # Texto dentro de las barras (adaptativo según ancho)
    texts = []
    for i, v in enumerate(capas):
        pct_lead = round(v / total * 100)
        if i == 0:
            texts.append(f"{v:,}  (100%)")
        elif i == n - 1:
            pct_prev = round(v / capas[i - 1] * 100) if capas[i - 1] > 0 else 0
            texts.append(f"{v:,}<br>T.C. {pct_prev}%")
        else:
            pct_prev   = round(v / capas[i - 1] * 100) if capas[i - 1] > 0 else 0
            prev_label = labels[i - 1]
            texts.append(f"{v:,}<br>{pct_lead}% leads  ·  {pct_prev}% /{prev_label}")

    # Hovertemplate: stats arriba, fuga debajo con título en línea propia
    fuga_map = {
        0: data.get("fuga_leads",  []),
        1: data.get("fuga_r1",     []),
        2: data.get("fuga_follow", []),
        3: data.get("fuga_r2",     []),
        4: data.get("fuga_presu",  []),
    }

    hovertemplates = []
    for i, v in enumerate(capas):
        pct_lead = round(v / total * 100)
        if i == 0:
            stats_html = f"<b>{labels[i]}</b>  {v:,}<br>{pct_lead}% del total de leads"
        else:
            pct_prev = round(v / capas[i - 1] * 100) if capas[i - 1] > 0 else 0
            stats_html = (f"<b>{labels[i]}</b>  {v:,}<br>"
                          f"{pct_lead}% del total  ·  {pct_prev}% de {labels[i-1]}")

        fugas = fuga_map.get(i, [])
        denom = capas[i] if capas[i] > 0 else 1
        fuga_lines = [f"  {name}: {nv} ({round(nv/denom*100)}%)"
                      for name, nv in fugas if nv > 0]

        if fuga_lines:
            template = (
                f"{stats_html}"
                "<br>─────────────<br>"
                "<b>↓ Fuga</b><br>"
                + "<br>".join(fuga_lines)
                + "<extra></extra>"
            )
        else:
            template = stats_html + "<extra></extra>"

        hovertemplates.append(template)

    fig = go.Figure(go.Funnel(
        y=labels,
        x=x_visual,
        text=texts,
        textposition="inside",
        textinfo="text",
        marker=dict(color=COLORES),
        connector=dict(line=dict(color="rgba(0,0,0,0.06)", width=1, dash="dot")),
        opacity=0.88,
        hovertemplate=hovertemplates,
    ))

    layout = {**LAYOUT_BASE, "margin": dict(l=20, r=20, t=20, b=10)}
    fig.update_layout(
        **layout,
        height=420,
        showlegend=False,
        funnelgap=0.06,
    )
    return fig


def bar_cpl_semanas(df_sel: pd.DataFrame, obj_cpl: dict) -> go.Figure:
    """
    Barras de CPL por semana (seleccionadas) con línea de objetivo.
    Verde si CPL < objetivo, rojo si CPL > objetivo.
    """
    labels = df_sel["fecha_ini"].dt.strftime("%d/%m")

    # Color por semana según vs objetivo
    colores = []
    for _, row in df_sel.iterrows():
        mes = row["fecha_ini"].month
        obj = obj_cpl.get(mes, 74)
        colores.append(COLOR_GF if row["cpl"] <= obj else COLOR_BF)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels,
        y=df_sel["cpl"],
        marker_color=colores,
        name="CPL real",
        hovertemplate="CPL: $%{y:.0f}<extra></extra>",
    ))

    # Línea de objetivo CPL
    obj_vals = [obj_cpl.get(row["fecha_ini"].month, 74) for _, row in df_sel.iterrows()]
    fig.add_trace(go.Scatter(
        x=labels,
        y=obj_vals,
        mode="lines",
        line=dict(color=COLOR_OBJ, dash="dash", width=2),
        name="Obj. CPL",
        hovertemplate="Obj: $%{y:.0f}<extra></extra>",
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        title="CPL vs Objetivo",
        height=280,
        yaxis=dict(title="CPL ($)"),
    )
    return fig
