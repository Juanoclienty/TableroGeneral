"""
app.py — Shell de navegación del Dashboard Clienty.
"""
import streamlit as st
from auth import login, logout, paginas_para_perfil, usuario_actual

st.set_page_config(
    page_title="Clienty — Hub",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Autenticación ─────────────────────────────────────────────────────────────
if not login():
    st.stop()

# ── Sidebar: usuario + logout ─────────────────────────────────────────────────
u = usuario_actual()
with st.sidebar:
    st.markdown(f"**{u['nombre']}**")
    st.caption(u["perfil"].replace("_", " ").title())
    if st.button("Cerrar sesión", use_container_width=True):
        st.session_state.clear()
        st.query_params["logout"] = "1"
        st.rerun()

# ── Navegación según perfil ───────────────────────────────────────────────────
st.markdown("""
<style>
li:has(a[href*="Actualizar_BD"]) { display: none !important; }
section[data-testid="stSidebar"][aria-expanded="false"] {
    margin-left: 0 !important;
    visibility: visible !important;
}
section[data-testid="stSidebar"][aria-expanded="false"] > div {
    display: block !important;
}
</style>
""", unsafe_allow_html=True)

pg = st.navigation(paginas_para_perfil(u["perfil"]))
pg.run()
