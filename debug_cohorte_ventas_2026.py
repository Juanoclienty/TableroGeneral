"""
Debug: Bajas en cohorte de VENTAS 2026.
Muestra los clientes que vendimos en 2026 y hoy están dados de baja.
"""
import sys, os, re, json, urllib.request
import pandas as pd

_MONDAY_TOKEN = (
    "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjY2Nzg4MzU5OSwiYWFpIjoxMSwidWlkIjo3N"
    "DQ5MjMwMiwiaWFkIjoiMjAyNi0wNi0wN1QxNzozMTowMi4wMDBaIiwicGVyIjoibWU6"
    "d3JpdGUiLCJhY3RpZCI6MjQxNjExNjcsInJnbiI6InVzZTEifQ.L41MQVmopJ880Q2m"
    "uX6S6erxUv23uOSvppD9fmsoaMQ"
)
_BOARD_ID      = "6967792411"
_GROUP_ACTIVOS = "grupo_nuevo28466"
_COLS          = ["id8__1", "fecha5", "fecha1"]
_ID_BBDD_CS    = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"

_MESES_ES = {
    "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
    "julio":7,"agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12,
}

def _monday_request(query):
    payload = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.monday.com/v2",
        data=payload,
        headers={"Content-Type":"application/json","Authorization":_MONDAY_TOKEN,"API-Version":"2024-01"},
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

# ── Cargar Monday ────────────────────────────────────────────────
print("Cargando Monday.com...")
cols_gql = ", ".join(f'"{c}"' for c in _COLS)
frag = f'id name group {{ id title }} column_values(ids: [{cols_gql}]) {{ id text }}'

q = f'{{ boards(ids: [{_BOARD_ID}]) {{ items_page(limit: 500) {{ cursor items {{ {frag} }} }} }} }}'
r = _monday_request(q)
page = r["data"]["boards"][0]["items_page"]
items = list(page["items"])
cursor = page.get("cursor")
while cursor:
    q2 = f'{{ next_items_page(limit: 500, cursor: "{cursor}") {{ cursor items {{ {frag} }} }} }}'
    r2 = _monday_request(q2)
    page = r2["data"]["next_items_page"]
    items.extend(page["items"])
    cursor = page.get("cursor")

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
df = df.drop_duplicates(subset=["monday_id"]).copy()

df_b = df[df["grupo_id"] != _GROUP_ACTIVOS].copy()
mask = df_b["_fecha_baja"].isna()
if mask.any():
    df_b.loc[mask, "_fecha_baja"] = df_b.loc[mask, "grupo_titulo"].apply(_inferir_fecha_grupo)
con_id = df_b[df_b["ID CRM"] != ""].sort_values("_fecha_baja", ascending=False, na_position="last").drop_duplicates("ID CRM", keep="first")
sin_id = df_b[df_b["ID CRM"] == ""]
df_b = pd.concat([con_id, sin_id], ignore_index=True)
df_b["Meses activos"] = ((df_b["_fecha_baja"] - df_b["_fecha_ingreso"]).dt.days / 30).round(1)

print(f"Total bajas en Monday: {len(df_b)}")

# ── Cargar BBDD_Ventas ───────────────────────────────────────────
print("Cargando BBDD_Ventas...")
url = f"https://docs.google.com/spreadsheets/d/{_ID_BBDD_CS}/gviz/tq?tqx=out:csv&sheet=BBDD_Ventas"
df_v = pd.read_csv(url, dtype=str)
df_v.columns = df_v.columns.str.strip()
df_v["_fecha"] = pd.to_datetime(df_v.get("Fecha",""), dayfirst=True, errors="coerce")
df_v["_id"]    = df_v.get("ID prospecto", pd.Series(dtype=str)).apply(_norm_id)
df_v = df_v.dropna(subset=["_fecha"])
df_v = df_v[df_v["_id"] != ""]
# Primera venta por cliente
df_v = df_v.sort_values("_fecha").drop_duplicates("_id", keep="first").reset_index(drop=True)

# Ventas 2026
df_v26 = df_v[df_v["_fecha"].dt.year == 2026].copy()
print(f"Ventas 2026 en BBDD_Ventas: {len(df_v26)}")

# ── Cruzar ───────────────────────────────────────────────────────
baja_ids = set(df_b[df_b["ID CRM"] != ""]["ID CRM"].unique())
df_v26["es_baja"] = df_v26["_id"].isin(baja_ids)

df_bajas_2026_venta = df_v26[df_v26["es_baja"]].copy()
df_bajas_2026_venta["Meses activos"] = df_bajas_2026_venta["_id"].map(
    df_b.set_index("ID CRM")["Meses activos"].to_dict()
)
df_bajas_2026_venta["Nombre Monday"] = df_bajas_2026_venta["_id"].map(
    df_b.set_index("ID CRM")["Nombre"].to_dict()
)
df_bajas_2026_venta["Fecha baja"] = df_bajas_2026_venta["_id"].map(
    df_b.set_index("ID CRM")["_fecha_baja"].to_dict()
)

pd.set_option("display.max_rows", 50)
pd.set_option("display.max_columns", 12)
pd.set_option("display.width", 160)
pd.set_option("display.max_colwidth", 35)

print(f"\n=== VENTAS 2026 QUE HOY SON BAJA ({len(df_bajas_2026_venta)} registros) ===\n")
out = df_bajas_2026_venta[["_id","Nombre Monday","_fecha","Fecha baja","Meses activos"]].copy()
out.columns = ["ID CRM","Nombre","Fecha venta (cohorte)","Fecha baja","Meses activos"]
out = out.sort_values("Fecha venta (cohorte)")
print(out.to_string(index=False))

# Guardar
out_path = os.path.join(os.path.dirname(__file__), "cache", "bajas_cohorte_venta_2026.csv")
out.to_csv(out_path, index=False, encoding="utf-8-sig")
print(f"\nGuardado en: {out_path}")
