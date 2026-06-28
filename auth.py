"""
auth.py — Autenticación y control de perfiles para el Dashboard Clienty.

Perfiles:
  mkt_vtas  → Marketing, Ventas, Trazabilidad, T90
  finanzas  → LTV, Estado de Resultados, T90
  cs        → CS, T90
  completo  → todo

Usuarios definidos en secrets.toml:
  [usuarios.juan]
  password = "<hash bcrypt>"
  nombre   = "Juan"
  perfil   = "completo"
"""
import streamlit as st
import bcrypt


# ── Páginas por perfil ────────────────────────────────────────────────────────

_PAGINAS_BASE = [
    # (archivo, título, ícono)
    ("home.py",                       "app",             "🏠"),
    ("pages/1_Marketing.py",          "Marketing",       "📈"),
    ("pages/3_Ventas.py",             "Ventas",          "💼"),
    ("pages/4_Trazabilidad.py",       "Trazabilidad",    "🔍"),
    ("pages/5_VGF.py",                "VGF",             "🎯"),
    ("pages/6_LTV.py",                "LTV",             "💰"),
    ("pages/7_CS.py",                 "CS",              "🤝"),
    ("pages/8_T90.py",                "T90",             "📊"),
    ("pages/9_Estado_Resultados.py",  "Est. Resultados", "📋"),
    ("pages/10_Historico.py",         "Histórico",       "📅"),
    ("pages/2_Actualizar_BD.py",      "Actualizar BD",   "🔄"),
]

_PERFIL_PAGINAS = {
    "mkt_vtas": {"Marketing", "Ventas", "Trazabilidad", "T90"},
    "finanzas":  {"LTV", "Est. Resultados", "T90"},
    "cs":        {"CS", "T90"},
    "completo":  None,  # None = todas
}

# Páginas que nunca aparecen en el sidebar (independientemente del perfil)
_SIEMPRE_OCULTAS = {"Actualizar BD"}


def paginas_para_perfil(perfil: str) -> list:
    """Retorna lista de st.Page según el perfil del usuario."""
    permitidas = _PERFIL_PAGINAS.get(perfil)
    paginas = []
    for archivo, titulo, icono in _PAGINAS_BASE:
        if titulo in _SIEMPRE_OCULTAS:
            continue
        if titulo == "app":
            paginas.append(st.Page(archivo, title=titulo, icon=icono, default=True))
            continue
        if permitidas is None or titulo in permitidas:
            paginas.append(st.Page(archivo, title=titulo, icon=icono))
    return paginas


# ── Autenticación ─────────────────────────────────────────────────────────────

def _verificar_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


_PERFILES_ABIERTOS = {
    "Perfil.mkt.vtas": ("mkt_vtas",  "Mkt y Ventas"),
    "Perfil.CS":        ("cs",        "CS"),
    "Perfil.finanzas":  ("finanzas",  "Finanzas"),
}


def _cargar_usuarios() -> dict:
    """Lee usuarios con contraseña desde st.secrets['usuarios']."""
    try:
        return dict(st.secrets.get("usuarios", {}))
    except Exception:
        return {}


def login() -> bool:
    """
    Muestra pantalla de login si no hay sesión activa.
    - Perfiles abiertos: solo nombre de usuario, sin contraseña.
    - Perfil completo: usuario + contraseña.
    Retorna True si el usuario está autenticado.
    """
    if st.session_state.get("autenticado"):
        return True

    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    .login-box {
        max-width: 400px;
        margin: 80px auto 0;
        padding: 40px;
        background: #ffffff;
        border-radius: 16px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    }
    .login-title {
        font-size: 1.8rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 8px;
        color: #1a1a2e;
    }
    .login-sub {
        text-align: center;
        color: #888;
        margin-bottom: 28px;
        font-size: 0.95rem;
    }
    </style>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Clienty Dashboard</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Ingresá tu usuario para continuar</div>', unsafe_allow_html=True)

        usuario  = st.text_input("Usuario", placeholder="tu_usuario")
        password = st.text_input("Contraseña", type="password", placeholder="Solo para perfil completo")

        if st.button("Ingresar", use_container_width=True, type="primary"):
            # Perfiles abiertos (sin contraseña)
            if usuario in _PERFILES_ABIERTOS:
                perfil, nombre = _PERFILES_ABIERTOS[usuario]
                st.session_state["autenticado"] = True
                st.session_state["usuario"]     = usuario
                st.session_state["nombre"]      = nombre
                st.session_state["perfil"]      = perfil
                st.rerun()
            else:
                # Usuarios con contraseña (perfil completo)
                usuarios = _cargar_usuarios()
                datos = usuarios.get(usuario)
                if datos and _verificar_password(password, str(datos.get("password", ""))):
                    st.session_state["autenticado"] = True
                    st.session_state["usuario"]     = usuario
                    st.session_state["nombre"]      = str(datos.get("nombre", usuario))
                    st.session_state["perfil"]      = str(datos.get("perfil", "completo"))
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

        st.markdown('</div>', unsafe_allow_html=True)

    return False


def logout():
    """Cierra la sesión del usuario."""
    for k in ["autenticado", "usuario", "nombre", "perfil"]:
        st.session_state.pop(k, None)
    st.rerun()


def usuario_actual() -> dict:
    return {
        "usuario": st.session_state.get("usuario", ""),
        "nombre":  st.session_state.get("nombre", ""),
        "perfil":  st.session_state.get("perfil", ""),
    }
