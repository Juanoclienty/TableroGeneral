"""
2_Actualizar_BD.py — Actualización de BBDD_Calendly_trabajada y caché LTV.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import datos_ltv

import io, urllib.request
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="Actualizar BD", page_icon="🔄", layout="centered")

st.markdown("## Actualizar base de datos Calendly")
st.caption("Descarga Calendly, aplica las tablas anexo y escribe en BBDD_Calendly_trabajada.")

st.markdown("""
**Cómo funciona el módulo "Actualizar BD":**

El flujo es así:

1. **Exportás Calendly** manualmente desde la plataforma y lo pegás en el Google Sheet fuente. Esa **sí es una tarea manual** que tenés que hacer vos.
2. El módulo lee esa data cruda de Calendly desde el Google Sheet.
3. **Aplica las "tablas anexo"** — son tablas de mapeo que vos mantenés en otro sheet. Ahí está la lógica de: este tipo de evento → este tipo de lead (GF, BF, PF), esta respuesta de rubro → este rubro normalizado, etc.
4. **Escribe el resultado procesado** en el sheet BBDD\\_Calendly\\_trabajada, que es el que usa todo el dashboard.

---

**Entonces el proceso manual que tenés que hacer es:**

1. Exportar los nuevos registros de Calendly
2. Pegarlos en el [**Sheet fuente (Calendly crudo)**](https://docs.google.com/spreadsheets/d/1KDlgqrTcaSlPSbARUJe4qnPhFdmgvQfoE2-WU1y0zzQ)
3. Entrar a este módulo y hacer click en el botón de actualizar
4. El dashboard toma automáticamente los datos ya procesados

---

📎 **Links útiles:**
- [Sheet fuente — Calendly crudo](https://docs.google.com/spreadsheets/d/1KDlgqrTcaSlPSbARUJe4qnPhFdmgvQfoE2-WU1y0zzQ)
- [Tablas anexo — Mapeos](https://docs.google.com/spreadsheets/d/1DCh_QEeF8n7VHkUSUaSAq4VNerQh8NbPK22CtU_Zcpo)
- [Resultado trabajado — Lo que usa el dashboard](https://docs.google.com/spreadsheets/d/1jtP9lYjVRnxFkvd0kN4xV5B6AQPEeFxgtxIRh5v-cgs)
""")

# ── Config ────────────────────────────────────────────────────
CREDS_PATH  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")
ID_ANEXO    = "1DCh_QEeF8n7VHkUSUaSAq4VNerQh8NbPK22CtU_Zcpo"
ID_CALENDLY = "1KDlgqrTcaSlPSbARUJe4qnPhFdmgvQfoE2-WU1y0zzQ"
ID_TRAB     = "1jtP9lYjVRnxFkvd0kN4xV5B6AQPEeFxgtxIRh5v-cgs"

def leer_csv(sheet_id, gid="0"):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        return pd.read_csv(io.StringIO(r.read().decode("utf-8")))

def build_map(df, col_raw, col_res):
    d = {}
    for _, row in df[[col_raw, col_res]].dropna().iterrows():
        key = str(row[col_raw]).strip().lower()
        val = str(row[col_res]).strip()
        if key and val and key != "nan":
            d[key] = val
    return d

def lookup(val, mapping):
    if pd.isna(val) or str(val).strip() == "":
        return "Falta info"
    return mapping.get(str(val).strip().lower(), "Falta info")

# ── UI ────────────────────────────────────────────────────────
if "ultima_actualizacion" not in st.session_state:
    st.session_state.ultima_actualizacion = None
if "resumen" not in st.session_state:
    st.session_state.resumen = None

if st.session_state.ultima_actualizacion:
    st.success(f"Ultima actualizacion: {st.session_state.ultima_actualizacion}")
    if st.session_state.resumen:
        st.dataframe(st.session_state.resumen, use_container_width=True, hide_index=True)

st.markdown("---")

if st.button("Ejecutar actualizacion", type="primary", use_container_width=True):

    with st.status("Procesando...", expanded=True) as status:

        st.write("Descargando tablas anexo...")
        df_anexo = leer_csv(ID_ANEXO)

        # Detectar columna Inversión con encoding flexible
        col_inv_raw = next((c for c in df_anexo.columns if "nversi" in c and "ublicidad" in c), None)
        col_inv_res = next((c for c in df_anexo.columns if "nversi" in c and "resumen" in c.lower()), None)

        map_tipo   = build_map(df_anexo, "Tipo cliente",     "Tipo cliente Resumen")
        map_ticket = build_map(df_anexo, "Ticket",           "Tkt resumen")
        map_equipo = build_map(df_anexo, "Equipo comercial", "Equipo comercial resumen")
        map_consul = build_map(df_anexo, "Consultas",        "Consultas resumen")
        map_inv    = build_map(df_anexo, col_inv_raw, col_inv_res) if col_inv_raw and col_inv_res else {}

        st.write("Descargando BBDD Calendly...")
        df_cal = leer_csv(ID_CALENDLY)
        st.write(f"  {len(df_cal)} registros encontrados.")

        st.write("Aplicando mapeos...")
        rows = []
        for _, r in df_cal.iterrows():
            inv_pub_raw = next(
                (r[c] for c in df_cal.columns if "nversi" in c and "ublicidad" in c), None
            )
            rows.append({
                "ID Final"            : r.get("ID Final", ""),
                "Invitee Email"       : r.get("Invitee Email", ""),
                "Event Type Name"     : r.get("Event Type Name", ""),
                "Start Date & Time"   : r.get("Start Date & Time", ""),
                "Rubro"               : r.get("Rubro", ""),
                "Tipo cliente"        : lookup(r.get("Tipo cliente"), map_tipo),
                "Ticket"              : lookup(r.get("Ticket"), map_ticket),
                "Equipo comercial"    : lookup(r.get("Equipo comercial"), map_equipo),
                "Consultas"           : lookup(r.get("Consultas"), map_consul),
                "Inversion Publicidad": lookup(inv_pub_raw, map_inv),
                "Inversion"           : r.get("Inversion", ""),
                "Tipo calendly"       : r.get("Tipo calendly", ""),
                "Fecha Lead"          : r.get("Fecha Lead", ""),
                "Num. de sem."        : r.get("Num. de sem.", ""),
            })

        df_out = pd.DataFrame(rows)

        st.write("Conectando con Google Sheets...")
        creds = Credentials.from_service_account_file(CREDS_PATH,
                    scopes=["https://www.googleapis.com/auth/spreadsheets"])
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(ID_TRAB)
        ws = sh.get_worksheet(0)

        st.write("Escribiendo datos...")
        ws.clear()
        headers = list(df_out.columns)
        data    = df_out.fillna("").astype(str).values.tolist()
        ws.update([headers] + data)

        # Resumen de calidad
        cols_map = ["Tipo cliente", "Ticket", "Equipo comercial", "Consultas", "Inversion Publicidad"]
        resumen_data = []
        for col in cols_map:
            fi = (df_out[col] == "Falta info").sum()
            resumen_data.append({
                "Campo"       : col,
                "Total"       : len(df_out),
                "Mapeados"    : len(df_out) - fi,
                "Falta info"  : fi,
                "% completado": f"{round((len(df_out)-fi)/len(df_out)*100)}%",
            })

        st.session_state.resumen = pd.DataFrame(resumen_data)
        st.session_state.ultima_actualizacion = datetime.now().strftime("%d/%m/%Y %H:%M")

        status.update(label="Actualizacion completada.", state="complete")

    st.success(f"Se escribieron {len(df_out)} filas en BBDD_Calendly_trabajada.")
    st.dataframe(st.session_state.resumen, use_container_width=True, hide_index=True)


# ── Actualizar LTV ────────────────────────────────────────────────

st.markdown("---")
st.markdown("## Actualizar LTV")
st.caption(
    "Descarga LTV Real, LTV Prom, BBDD_Ventas, Ads y estado Monday CS. "
    "Ejecutá esto cuando Finanzas confirme que los datos están actualizados."
)

_fecha_ltv = datos_ltv.cache_fecha()
if _fecha_ltv:
    st.info(f"Último caché LTV: {_fecha_ltv}")
else:
    st.warning("No hay caché LTV todavía. Ejecutá la actualización para cargarlo por primera vez.")

if st.button("Actualizar LTV", type="primary", use_container_width=True):
    with st.status("Actualizando LTV...", expanded=True) as _ltv_status:
        try:
            datos_ltv.actualizar_ltv(progress_cb=st.write)
            _ltv_status.update(label="LTV actualizado correctamente.", state="complete")
            st.success(f"Caché LTV guardado — {datos_ltv.cache_fecha()}")
        except Exception as _ltv_e:
            _ltv_status.update(label="Error al actualizar LTV.", state="error")
            st.error(f"Error: {_ltv_e}")
