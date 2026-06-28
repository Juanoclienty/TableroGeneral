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

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="card">
        <div class="card-icon">📈</div>
        <div class="card-title">Marketing</div>
        <div class="card-desc">Leads, CPL, GF/BF/PF, inversión y objetivos por semana, mes o día</div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/1_Marketing.py", label="Ir a Marketing", use_container_width=True)

with col2:
    st.markdown("""
    <div class="card">
        <div class="card-icon">💼</div>
        <div class="card-title">Ventas (Fecha cohort)</div>
        <div class="card-desc">Embudo de ventas, conversión por etapa y análisis de cohortes</div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/3_Ventas.py", label="Ir a Ventas", use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    st.markdown("""
    <div class="card">
        <div class="card-icon">🔍</div>
        <div class="card-title">Trazabilidad</div>
        <div class="card-desc">Seguimiento detallado del recorrido de cada lead</div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/4_Trazabilidad.py", label="Ir a Trazabilidad", use_container_width=True)

with col4:
    st.markdown("""
    <div class="card">
        <div class="card-icon">🔄</div>
        <div class="card-title">Actualizar base de datos</div>
        <div class="card-desc">Procesa Calendly y actualiza BBDD_Calendly_trabajada en Google Sheets</div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/2_Actualizar_BD.py", label="Ir a Actualizar BD", use_container_width=True)

st.markdown("---")
st.caption("Clienty CRM · Dashboard interno · v0.3")
