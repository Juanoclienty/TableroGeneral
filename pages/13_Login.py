"""
13_Login.py — Sesión del usuario (cerrar sesión).
"""
import streamlit as st
from auth import usuario_actual, logout

u = usuario_actual()

st.markdown("## Sesión")
st.markdown(f"**Usuario:** {u['nombre']}")
st.markdown(f"**Perfil:** {u['perfil'].replace('_', ' ').title()}")
st.markdown("---")

if st.button("Cerrar sesión", type="primary", use_container_width=False):
    st.session_state.clear()
    st.query_params["logout"] = "1"
    st.rerun()
