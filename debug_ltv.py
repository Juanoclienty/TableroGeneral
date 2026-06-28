"""
debug_ltv.py — Imprime tabla ID / LTV Recurrente / LTV Implementación
Correr con: python debug_ltv.py
"""
import io, urllib.request
import pandas as pd

_ID_LTV = "1TGVc9zgYc0siaouIOi8xTOiFopgXuW8AXIB_dqYZ7Ps"


def _norm_id(v) -> str:
    s = str(v).strip()
    if s in ("", "nan", "None"):
        return ""
    try:
        return str(int(float(s)))
    except (ValueError, OverflowError):
        return ""


def _fetch(url: str) -> pd.DataFrame:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        contenido = resp.read().decode("utf-8")
    df = pd.read_csv(io.StringIO(contenido), dtype=str)
    df.columns = df.columns.str.strip()
    return df


# ── LTV Real ──────────────────────────────────────────────────
url_r = (f"https://docs.google.com/spreadsheets/d/{_ID_LTV}"
         f"/export?format=csv&sheet=LTV%20Real")
df_r = _fetch(url_r)
print(f"LTV Real — {len(df_r)} filas")
print("Columnas:", list(df_r.columns))

_id_col  = next((c for c in df_r.columns if c.upper() == "ID CRM"), None)
_usd_col = next((c for c in df_r.columns if "SECUNDARIA" in c.upper()), None)
_prod_col = next((c for c in df_r.columns if c.upper() == "PRODUCTO"), None)
print(f"  ID col: {_id_col!r}  |  USD col: {_usd_col!r}  |  Producto col: {_prod_col!r}")

df_r["_id"]   = df_r[_id_col].apply(_norm_id) if _id_col else ""
df_r["_usd"]  = pd.to_numeric(df_r[_usd_col] if _usd_col else pd.Series(dtype=str), errors="coerce").fillna(0)
df_r["_impl"] = df_r[_prod_col].astype(str).str.lower().str.contains("implementa", na=False) if _prod_col else False
df_r = df_r[df_r["_id"] != ""]

print(f"  Filas con ID válido: {len(df_r)}")
print(f"  Filas impl=True: {df_r['_impl'].sum()}  |  impl=False: {(~df_r['_impl']).sum()}")
print(f"  Valores únicos Producto: {df_r[_prod_col].dropna().unique()[:10].tolist() if _prod_col else 'N/A'}")
print()

real_rec  = df_r[~df_r["_impl"]].groupby("_id")["_usd"].sum()
real_impl = df_r[df_r["_impl"]].groupby("_id")["_usd"].sum()


# ── LTV Prom ─────────────────────────────────────────────────
url_p = (f"https://docs.google.com/spreadsheets/d/{_ID_LTV}"
         f"/gviz/tq?tqx=out:csv&sheet=LTV%20Prom%20-%202024.08")
df_p = _fetch(url_p)
print(f"LTV Prom — {len(df_p)} filas")
print("Columnas:", list(df_p.columns))

_id_col_p  = next((c for c in df_p.columns if c.upper() == "ID CRM"), None)
_usd_col_p = next((c for c in df_p.columns if "SECUNDARIA" in c.upper()), None)
print(f"  ID col: {_id_col_p!r}  |  USD col: {_usd_col_p!r}")

df_p["_id"]  = df_p[_id_col_p].apply(_norm_id) if _id_col_p else ""
df_p["_usd"] = pd.to_numeric(df_p[_usd_col_p] if _usd_col_p else pd.Series(dtype=str), errors="coerce").fillna(0)
df_p = df_p[df_p["_id"] != ""]
print(f"  Filas con ID válido: {len(df_p)}")
print()

prom_rec = df_p.groupby("_id")["_usd"].sum()


# ── Tabla combinada ───────────────────────────────────────────
todos_ids = sorted(set(real_rec.index) | set(real_impl.index) | set(prom_rec.index))
filas = []
for idk in todos_ids:
    rec  = float(real_rec.get(idk, 0)) + float(prom_rec.get(idk, 0))
    impl = float(real_impl.get(idk, 0))
    if rec > 0 or impl > 0:
        filas.append({"ID": idk, "LTV Recurrente": round(rec), "LTV Implementacion": round(impl)})

df_out = pd.DataFrame(filas)
print(f"Total clientes con LTV: {len(df_out)}")
print()
print(df_out.to_string(index=False))
