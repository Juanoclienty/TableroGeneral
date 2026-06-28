"""
procesar_calendly.py
Lee BBDD_Calendly, mapea los 5 campos via tablas anexo,
y escribe el resultado en BBDD_Calendly_trabajada.
"""
import io, urllib.request
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ── Credenciales ──────────────────────────────────────────────
CREDS_PATH = "C:/Users/rjuan/dashboard/credentials.json"
SCOPES     = ["https://www.googleapis.com/auth/spreadsheets"]

creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
gc    = gspread.authorize(creds)

# ── IDs de los sheets ─────────────────────────────────────────
ID_ANEXO    = "1DCh_QEeF8n7VHkUSUaSAq4VNerQh8NbPK22CtU_Zcpo"
ID_CALENDLY = "1KDlgqrTcaSlPSbARUJe4qnPhFdmgvQfoE2-WU1y0zzQ"
ID_TRAB     = "1jtP9lYjVRnxFkvd0kN4xV5B6AQPEeFxgtxIRh5v-cgs"

# ── Helper lectura CSV público ────────────────────────────────
def leer_csv(sheet_id, gid="0"):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        return pd.read_csv(io.StringIO(r.read().decode("utf-8")))

print("Descargando datos...")
df_anexo    = leer_csv(ID_ANEXO)
df_calendly = leer_csv(ID_CALENDLY)

# ── Construir diccionarios de mapeo (texto → resumen) ─────────
def build_map(df, col_raw, col_res):
    """Diccionario raw_valor.strip().lower() → resumen."""
    d = {}
    for _, row in df[[col_raw, col_res]].dropna().iterrows():
        key = str(row[col_raw]).strip().lower()
        val = str(row[col_res]).strip()
        if key and val and key != "nan":
            d[key] = val
    return d

map_tipo    = build_map(df_anexo, "Tipo cliente",          "Tipo cliente Resumen")
map_ticket  = build_map(df_anexo, "Ticket",                "Tkt resumen")
map_equipo  = build_map(df_anexo, "Equipo comercial",      "Equipo comercial resumen")
map_consul  = build_map(df_anexo, "Consultas",             "Consultas resumen")
map_inv     = build_map(df_anexo, "Inversión Publicidad",  "Inversion publicidad resumen")

# Intentar también con encoding alternativo si la columna tiene carácter raro
for col_try in ["Inversión Publicidad", "Inversion Publicidad", "Inversión Publicidad"]:
    if col_try in df_anexo.columns:
        map_inv = build_map(df_anexo, col_try, "Inversion publicidad resumen")
        break

def lookup(val, mapping):
    if pd.isna(val) or str(val).strip() == "":
        return "Falta info"
    key = str(val).strip().lower()
    return mapping.get(key, "Falta info")

# ── Construir df_trabajada ────────────────────────────────────
print(f"Procesando {len(df_calendly)} filas...")

rows = []
for _, r in df_calendly.iterrows():
    # Buscar columna Inversión Publicidad con encoding flexible
    inv_pub_raw = None
    for col in df_calendly.columns:
        if "nversi" in col and "ublicidad" in col:
            inv_pub_raw = r[col]
            break

    rows.append({
        "ID Final"           : r.get("ID Final", ""),
        "Invitee Email"      : r.get("Invitee Email", ""),
        "Event Type Name"    : r.get("Event Type Name", ""),
        "Start Date & Time"  : r.get("Start Date & Time", ""),
        "Rubro"              : r.get("Rubro", ""),
        "Tipo cliente"       : lookup(r.get("Tipo cliente"), map_tipo),
        "Ticket"             : lookup(r.get("Ticket"), map_ticket),
        "Equipo comercial"   : lookup(r.get("Equipo comercial"), map_equipo),
        "Consultas"          : lookup(r.get("Consultas"), map_consul),
        "Inversión Publicidad": lookup(inv_pub_raw, map_inv),
        "Inversion"          : r.get("Inversion", ""),
        "Tipo calendly"      : r.get("Tipo calendly", ""),
        "Fecha Lead"         : r.get("Fecha Lead", ""),
        "Num. de sem."       : r.get("Num. de sem.", ""),
    })

df_out = pd.DataFrame(rows)

# Stats
falta = (df_out[["Tipo cliente","Ticket","Equipo comercial","Consultas","Inversión Publicidad"]] == "Falta info").sum()
print("\nFalta info por columna:")
print(falta.to_string())
print(f"\nTotal filas: {len(df_out)}")

# ── Escribir en BBDD_Calendly_trabajada ──────────────────────
print("\nEscribiendo en Google Sheets...")
sh = gc.open_by_key(ID_TRAB)
ws = sh.get_worksheet(0)

# Limpiar hoja y escribir desde cero
ws.clear()

headers = list(df_out.columns)
data    = df_out.fillna("").astype(str).values.tolist()
ws.update([headers] + data)

print(f"✓ Listo. {len(df_out)} filas escritas en BBDD_Calendly_trabajada.")
