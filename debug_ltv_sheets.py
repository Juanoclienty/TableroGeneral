import pandas as pd

_ID_LTV = "1TGVc9zgYc0siaouIOi8xTOiFopgXuW8AXIB_dqYZ7Ps"

def _norm_id(v):
    s = str(v).strip()
    if s.endswith(".0") and s[:-2].lstrip("-").isdigit():
        s = s[:-2]
    return s if s not in ("nan", "None", "") else ""

# ── LTV Real ──────────────────────────────────────────────────────
url_real = f"https://docs.google.com/spreadsheets/d/{_ID_LTV}/gviz/tq?tqx=out:csv&sheet=LTV%20Real"
df_real = pd.read_csv(url_real, dtype=str)
df_real.columns = df_real.columns.str.strip()
df_real["_id"] = df_real["ID crm"].apply(_norm_id)

print("=== LTV Real ===")
print(f"Total filas: {len(df_real)}")
print(f"Filas con ID: {(df_real['_id'] != '').sum()}")
print(f"Filas sin ID: {(df_real['_id'] == '').sum()}")
print(f"IDs únicos: {df_real[df_real['_id'] != '']['_id'].nunique()}")
print("Top 10 IDs con más filas:")
print(df_real[df_real['_id'] != ''].groupby('_id').size().sort_values(ascending=False).head(10))

# ── LTV Prom ──────────────────────────────────────────────────────
url_prom = f"https://docs.google.com/spreadsheets/d/{_ID_LTV}/gviz/tq?tqx=out:csv&sheet=LTV%20Prom%20-%202024.08"
df_prom = pd.read_csv(url_prom, dtype=str)
df_prom.columns = df_prom.columns.str.strip()

# Detectar nombre de columna ID (puede ser "ID crm" o "ID CRM")
id_col = next((c for c in df_prom.columns if c.lower() == "id crm" or c.lower() == "id_crm"), None)
print(f"\n=== LTV Prom ===")
print(f"Columnas: {list(df_prom.columns)}")
print(f"Total filas: {len(df_prom)}")
if id_col:
    df_prom["_id"] = df_prom[id_col].apply(_norm_id)
    print(f"Columna ID encontrada: '{id_col}'")
    print(f"Filas con ID: {(df_prom['_id'] != '').sum()}")
    print(f"IDs únicos: {df_prom[df_prom['_id'] != '']['_id'].nunique()}")
    print("Primeros 10 IDs:")
    print(df_prom[df_prom['_id'] != ''][['_id', df_prom.columns[1], df_prom.columns[2]]].head(10).to_string(index=False))
else:
    print("!! No se encontró columna de ID")
    print(df_prom.head(5).to_string())
