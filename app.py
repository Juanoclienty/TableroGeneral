"""
app.py — Shell de navegación del Dashboard Clienty.
"""
import ssl, certifi, os
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
ssl._create_default_https_context = ssl.create_default_context

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

u = usuario_actual()

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
