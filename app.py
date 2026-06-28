"""
app.py — Shell de navegación del Dashboard Clienty.
"""
import streamlit as st

st.set_page_config(
    page_title="Clienty — Hub",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ocultar "Actualizar BD" del sidebar + evitar colapso en reruns
st.markdown("""
<style>
li:has(a[href*="Actualizar_BD"]) { display: none !important; }

/* Mantener sidebar visible aunque aria-expanded sea false */
section[data-testid="stSidebar"][aria-expanded="false"] {
    margin-left: 0 !important;
    visibility: visible !important;
}
section[data-testid="stSidebar"][aria-expanded="false"] > div {
    display: block !important;
}
</style>
""", unsafe_allow_html=True)

pg = st.navigation([
    st.Page("home.py",                   title="app",          icon="🏠", default=True),
    st.Page("pages/1_Marketing.py",      title="Marketing",    icon="📈"),
    st.Page("pages/3_Ventas.py",         title="Ventas",       icon="💼"),
    st.Page("pages/4_Trazabilidad.py",   title="Trazabilidad", icon="🔍"),
    st.Page("pages/5_VGF.py",            title="VGF",          icon="🎯"),
    st.Page("pages/6_LTV.py",            title="LTV",          icon="💰"),
    st.Page("pages/7_CS.py",             title="CS",           icon="🤝"),
    st.Page("pages/8_T90.py",               title="T90",            icon="📊"),
    st.Page("pages/9_Estado_Resultados.py", title="Est. Resultados", icon="📋"),
    st.Page("pages/10_Historico.py",        title="Histórico",       icon="📅"),
    st.Page("pages/2_Actualizar_BD.py",     title="Actualizar BD",   icon="🔄"),
])

pg.run()
