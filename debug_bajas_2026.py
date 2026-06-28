"""
Script de debug: bajas 2026 con ID, Nombre, Fecha ingreso, Fecha baja, Duración.
Ejecutar: python debug_bajas_2026.py
"""
import sys, os, re, json, urllib.request
import pandas as pd
from datetime import date

_MONDAY_TOKEN = (
    "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjY2Nzg4MzU5OSwiYWFpIjoxMSwidWlkIjo3N"
    "DQ5MjMwMiwiaWFkIjoiMjAyNi0wNi0wN1QxNzozMTowMi4wMDBaIiwicGVyIjoibWU6"
    "d3JpdGUiLCJhY3RpZCI6MjQxNjExNjcsInJnbiI6InVzZTEifQ.L41MQVmopJ880Q2m"
    "uX6S6erxUv23uOSvppD9fmsoaMQ"
)
_BOARD_ID      = "6967792411"
_GROUP_ACTIVOS = "grupo_nuevo28466"
_COLS          = ["id8__1", "fecha5", "fecha1", "status0", "rubro_mkmttagz", "pain__1"]

_MESES_ES = {
    "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
    "julio":7,"agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12,
}

def _monday_request(query):
    payload = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.monday.com/v2",
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": _MONDAY_TOKEN,
            "API-Version":   "2024-01",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _inferir_fecha_grupo(titulo):
    t = titulo.lower()
    for mes_str, mes_num in _MESES_ES.items():
        if mes_str in t:
            m = re.search(r"\b(20\d{2})\b", titulo)
            if m:
                return pd.Timestamp(year=int(m.group(1)), month=mes_num, day=1)
    return pd.NaT

def _norm_id(v):
    s = str(v).strip()
    if s.endswith(".0") and s[:-2].lstrip("-").isdigit():
        s = s[:-2]
    return s if s not in ("nan","None","") else ""

print("Cargando datos de Monday.com...")

cols_gql = ", ".join(f'"{c}"' for c in _COLS)
item_frag = f"""
  id name
  group {{ id title }}
  column_values(ids: [{cols_gql}]) {{ id text }}
"""

q = f"""{{
  boards(ids: [{_BOARD_ID}]) {{
    items_page(limit: 500) {{ cursor items {{ {item_frag} }} }}
  }}
}}"""

r      = _monday_request(q)
page   = r["data"]["boards"][0]["items_page"]
items  = list(page["items"])
cursor = page.get("cursor")

while cursor:
    q2 = f"""{{
      next_items_page(limit: 500, cursor: "{cursor}") {{
        cursor items {{ {item_frag} }}
      }}
    }}"""
    r2     = _monday_request(q2)
    page   = r2["data"]["next_items_page"]
    items.extend(page["items"])
    cursor = page.get("cursor")

print(f"Total items cargados: {len(items)}")

rows = []
for item in items:
    cv = {c["id"]: (c["text"] or "") for c in item["column_values"]}
    rows.append({
        "monday_id":    item["id"],
        "ID CRM":       _norm_id(cv.get("id8__1","")),
        "Nombre":       item["name"],
        "grupo_id":     item["group"]["id"],
        "grupo_titulo": item["group"]["title"],
        "_fecha_ingreso": cv.get("fecha5",""),
        "_fecha_baja":    cv.get("fecha1",""),
    })

df = pd.DataFrame(rows)
df["_fecha_ingreso"] = pd.to_datetime(df["_fecha_ingreso"], errors="coerce")
df["_fecha_baja"]    = pd.to_datetime(df["_fecha_baja"],    errors="coerce")

# Dedup por monday_id
df = df.drop_duplicates(subset=["monday_id"]).copy()

# Separar bajas
df_b = df[df["grupo_id"] != _GROUP_ACTIVOS].copy()

# Completar fecha_baja desde nombre del grupo
mask = df_b["_fecha_baja"].isna()
if mask.any():
    df_b.loc[mask, "_fecha_baja"] = df_b.loc[mask, "grupo_titulo"].apply(_inferir_fecha_grupo)

# Dedup por ID CRM (más reciente)
con_id = df_b[df_b["ID CRM"] != ""].sort_values("_fecha_baja", ascending=False, na_position="last").drop_duplicates("ID CRM", keep="first")
sin_id = df_b[df_b["ID CRM"] == ""]
df_b = pd.concat([con_id, sin_id], ignore_index=True)

# Duración en meses
df_b["Duracion_meses"] = ((df_b["_fecha_baja"] - df_b["_fecha_ingreso"]).dt.days / 30).round(1)

# Filtrar 2026
df_2026 = df_b[df_b["_fecha_baja"].dt.year == 2026].copy()
df_2026 = df_2026.sort_values("_fecha_baja")

# Columnas a mostrar
out = df_2026[["ID CRM","Nombre","_fecha_ingreso","_fecha_baja","Duracion_meses","grupo_titulo"]].copy()
out.columns = ["ID CRM","Nombre","Fecha ingreso","Fecha baja","Duración (meses)","Grupo Monday"]

print(f"\n=== BAJAS 2026 ({len(out)} registros) ===\n")
pd.set_option("display.max_rows", 200)
pd.set_option("display.max_columns", 10)
pd.set_option("display.width", 140)
pd.set_option("display.max_colwidth", 35)
print(out.to_string(index=False))

# Guardar CSV por si acaso
out_path = os.path.join(os.path.dirname(__file__), "cache", "bajas_2026_debug.csv")
out.to_csv(out_path, index=False, encoding="utf-8-sig")
print(f"\nGuardado en: {out_path}")

# Resumen por mes de baja
print("\n=== RESUMEN POR MES DE BAJA ===")
resumen = (
    df_2026.assign(mes=df_2026["_fecha_baja"].dt.to_period("M"))
    .groupby("mes").size().rename("Bajas")
)
print(resumen.to_string())
