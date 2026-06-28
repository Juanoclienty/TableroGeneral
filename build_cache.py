"""
build_cache.py — Pre-fetches all remote data and saves to cache/ and data/ folders.
Run daily via GitHub Actions so the Streamlit app reads from files instead of APIs.
"""
import os, sys, io, pickle, urllib.request
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(ROOT, "cache")
DATA_DIR  = os.path.join(ROOT, "data")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(DATA_DIR,  exist_ok=True)

def _fetch_csv(url: str) -> pd.DataFrame:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    return pd.read_csv(io.StringIO(raw))

def _fetch_gviz(sheet_id: str, sheet_name: str = "") -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    if sheet_name:
        url += f"&sheet={urllib.parse.quote(sheet_name)}"
    return _fetch_csv(url)

import urllib.parse

# ── 1. Monday CRM (forzar refresh borrando el .date) ─────────────────────────
print("Actualizando Monday CRM...")
sys.path.insert(0, ROOT)
try:
    import datos_crm
    date_file = os.path.join(CACHE_DIR, f"df_crm_v{datos_crm._CACHE_VER}.date")
    if os.path.exists(date_file):
        os.remove(date_file)
    # Usar secrets de GitHub Actions si están disponibles
    sub  = os.environ.get("CLIENTY_SUBDOMINIO", "clienty")
    user = os.environ.get("CLIENTY_USERNAME",   "")
    pwd  = os.environ.get("CLIENTY_PASSWORD",   "")
    if user and pwd:
        datos_crm.cargar_crm(sub, user, pwd)
        print("  ✓ Monday CRM actualizado")
    else:
        print("  ⚠ Credenciales no configuradas, saltando Monday")
except Exception as e:
    print(f"  ✗ Error Monday: {e}")

# ── 2. Google Sheets — Marketing (Calendly, Ads, Objetivos) ──────────────────
print("Cacheando Google Sheets — Marketing...")
sheets_marketing = {
    "calendly":  "https://docs.google.com/spreadsheets/d/1KDlgqrTcaSlPSbARUJe4qnPhFdmgvQfoE2-WU1y0zzQ/export?format=csv",
    "ads":       "https://docs.google.com/spreadsheets/d/1mx6EXpdM6kKfzNNWQ_J7vcPBL2Ex36uRmtY-mxKXcoY/export?format=csv",
    "objetivos": "https://docs.google.com/spreadsheets/d/1rOa7MvHxXUiU8nEMb5cKTyv8lMvPuZzrAT8Wj0KuD40/export?format=csv",
}
for name, url in sheets_marketing.items():
    try:
        df = _fetch_csv(url)
        df.to_parquet(os.path.join(CACHE_DIR, f"sheet_{name}.parquet"), index=False)
        print(f"  ✓ {name} ({len(df)} filas)")
    except Exception as e:
        print(f"  ✗ {name}: {e}")

# ── 3. Estado de Resultados ───────────────────────────────────────────────────
print("Cacheando Estado de Resultados...")
ID_ER = "1hLhYgVwE1uRLiqCZKsAr9b3k3VSZYqYORdPURdvjPKs"
er_sheets = ["Real 2026", "Real 2025", "Unificado real 2025-2026"]
for sheet in er_sheets:
    try:
        url = f"https://docs.google.com/spreadsheets/d/{ID_ER}/gviz/tq?tqx=out:csv&range=A1:Z300&sheet={urllib.parse.quote(sheet)}"
        df = _fetch_csv(url)
        fname = sheet.replace(" ", "_").replace("-", "_")
        df.to_parquet(os.path.join(CACHE_DIR, f"er_{fname}.parquet"), index=False)
        print(f"  ✓ {sheet} ({len(df)} filas)")
    except Exception as e:
        print(f"  ✗ {sheet}: {e}")

# ── 4. Ventas / CS / BBDD ─────────────────────────────────────────────────────
print("Cacheando BBDD Ventas y CS...")
ID_BBDD = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"
bbdd_sheets = ["BBDD_Ventas", "bbdd_presupuestos"]
for sheet in bbdd_sheets:
    try:
        url = f"https://docs.google.com/spreadsheets/d/{ID_BBDD}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(sheet)}"
        df = _fetch_csv(url)
        df.to_parquet(os.path.join(CACHE_DIR, f"bbdd_{sheet}.parquet"), index=False)
        print(f"  ✓ {sheet} ({len(df)} filas)")
    except Exception as e:
        print(f"  ✗ {sheet}: {e}")

# ── 5. LTV ────────────────────────────────────────────────────────────────────
print("Cacheando LTV...")
ID_LTV = "1TGVc9zgYc0siaouIOi8xTOiFopgXuW8AXIB_dqYZ7Ps"
ltv_sheets = [
    ("LTV Real",            "ltv_real"),
    ("LTV Prom - 2024.08",  "ltv_prom"),
]
for sheet, fname in ltv_sheets:
    try:
        url = f"https://docs.google.com/spreadsheets/d/{ID_LTV}/export?format=csv&sheet={urllib.parse.quote(sheet)}"
        df = _fetch_csv(url)
        df.to_parquet(os.path.join(CACHE_DIR, f"{fname}.parquet"), index=False)
        print(f"  ✓ {sheet} ({len(df)} filas)")
    except Exception as e:
        print(f"  ✗ {sheet}: {e}")

# ── 6. Histórico ──────────────────────────────────────────────────────────────
print("Cacheando Histórico...")
try:
    ID_HIST = "1Gx8D17EGw4Lwoo82F11PBQ9fl6aC8dQDPdurxWxSOP4"
    url = f"https://docs.google.com/spreadsheets/d/{ID_HIST}/gviz/tq?tqx=out:csv"
    df = _fetch_csv(url)
    df.to_parquet(os.path.join(CACHE_DIR, "historico.parquet"), index=False)
    print(f"  ✓ Histórico ({len(df)} filas)")
except Exception as e:
    print(f"  ✗ Histórico: {e}")

print("\n✅ Cache build completo.")
