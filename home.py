"""
home.py — Pantalla principal del Dashboard Clienty.
"""
import streamlit as st

st.markdown("""
<style>
    .card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 28px 24px;
        margin-bottom: 8px;
        text-align: center;
        transition: box-shadow 0.2s;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
    .card-icon  { font-size: 2.4rem; margin-bottom: 8px; }
    .card-title { font-size: 1.1rem; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
    .card-desc  { font-size: 0.85rem; color: #64748b; }
    .main-title { text-align: center; color: #1e293b; margin-bottom: 4px; }
    .main-sub   { text-align: center; color: #64748b; font-size: 0.95rem; margin-bottom: 40px; }
    [data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-title">Dashboard Clienty</h1>', unsafe_allow_html=True)
st.markdown('<p class="main-sub">Seleccioná la sección a la que querés ir</p>', unsafe_allow_html=True)

perfil = st.session_state.get("perfil", "")

_TODAS = [
    ("Marketing",       "📈", "Leads, CPL, GF/BF/PF, inversión y objetivos por semana, mes o día",   "pages/1_Marketing.py",         "Ir a Marketing"),
    ("Ventas",          "💼", "Embudo de ventas, conversión por etapa y análisis de cohortes",         "pages/3_Ventas.py",            "Ir a Ventas"),
    ("Trazabilidad",    "🔍", "Seguimiento detallado del recorrido de cada lead",                      "pages/4_Trazabilidad.py",      "Ir a Trazabilidad"),
    ("VGF",             "🎯", "Análisis de VGF",                                                       "pages/5_VGF.py",               "Ir a VGF"),
    ("LTV",             "💰", "Lifetime value de clientes",                                            "pages/6_LTV.py",               "Ir a LTV"),
    ("CS",              "🤝", "Customer success y seguimiento de clientes",                            "pages/7_CS.py",                "Ir a CS"),
    ("T90",             "📊", "Análisis de primeros 90 días",                                          "pages/8_T90.py",               "Ir a T90"),
    ("Est. Resultados", "📋", "Estado de resultados financiero",                                       "pages/9_Estado_Resultados.py", "Ir a Est. Resultados"),
    ("Histórico",       "📅", "Histórico de bajas y ventas",                                           "pages/10_Historico.py",        "Ir a Histórico"),
]

_PERFIL_PAGINAS = {
    "mkt_vtas": {"Marketing", "Ventas", "Trazabilidad", "T90"},
    "finanzas":  {"LTV", "Est. Resultados", "T90"},
    "cs":        {"CS", "T90"},
    "completo":  None,
}

permitidas = _PERFIL_PAGINAS.get(perfil)
cards = [(t, i, d, f, l) for t, i, d, f, l in _TODAS if permitidas is None or t in permitidas]

for idx in range(0, len(cards), 2):
    cols = st.columns(2)
    for ci, (titulo, icono, desc, archivo, label) in enumerate(cards[idx:idx+2]):
        with cols[ci]:
            st.markdown(f"""
            <div class="card">
                <div class="card-icon">{icono}</div>
                <div class="card-title">{titulo}</div>
                <div class="card-desc">{desc}</div>
            </div>
            """, unsafe_allow_html=True)
            st.page_link(archivo, label=label, use_container_width=True)

st.markdown("---")
st.caption("Clienty CRM · Dashboard interno · v0.3")
