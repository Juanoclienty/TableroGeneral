"""
datos_ltv.py — Carga y persistencia de datos LTV.
Los datos se guardan localmente en data/ltv_cache.pkl.
Solo se re-fetchean al llamar actualizar_ltv() (botón manual).
"""
import os, json, pickle, pathlib, urllib.request, io
import pandas as pd

_ROOT       = pathlib.Path(__file__).parent
_CACHE_PATH = _ROOT / "data" / "ltv_cache.pkl"

_MONDAY_TOKEN = (
    "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjY2Nzg4MzU5OSwiYWFpIjoxMSwidWlkIjo3N"
    "DQ5MjMwMiwiaWFkIjoiMjAyNi0wNi0wN1QxNzozMTowMi4wMDBaIiwicGVyIjoibWU6"
    "d3JpdGUiLCJhY3RpZCI6MjQxNjExNjcsInJnbiI6InVzZTEifQ.L41MQVmopJ880Q2m"
    "uX6S6erxUv23uOSvppD9fmsoaMQ"
)
_BOARD_CS = "6967792411"
_ID_LTV   = "1TGVc9zgYc0siaouIOi8xTOiFopgXuW8AXIB_dqYZ7Ps"
_ID_BBDD  = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"


def _fetch_csv(url: str) -> pd.DataFrame:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        contenido = resp.read().decode("utf-8")
    df = pd.read_csv(io.StringIO(contenido), dtype=str)
    df.columns = df.columns.str.strip()
    return df


def _norm_id(v) -> str:
    s = str(v).strip()
    if s in ("", "nan", "None"):
        return ""
    try:
        return str(int(float(s)))
    except (ValueError, OverflowError):
        return ""


def _monday_req(query: str) -> dict:
    payload = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.monday.com/v2",
        data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": _MONDAY_TOKEN,
                 "API-Version": "2024-01"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_estado_monday() -> dict:
    """Retorna {id_crm: fecha_baja_o_NaT}."""
    lookup = {}
    cursor = None
    while True:
        page_arg = f'cursor: "{cursor}"' if cursor else "limit: 500"
        q = f"""{{
          boards(ids: [{_BOARD_CS}]) {{
            items_page({page_arg}) {{
              cursor
              items {{
                column_values(ids: ["id8__1", "fecha1"]) {{ id text }}
              }}
            }}
          }}
        }}"""
        try:
            data  = _monday_req(q)
            page  = data["data"]["boards"][0]["items_page"]
        except Exception:
            break
        for item in page["items"]:
            cv  = {c["id"]: c["text"] for c in item["column_values"]}
            idk = cv.get("id8__1", "").strip()
            if not idk:
                continue
            fecha_raw = cv.get("fecha1", "").strip()
            try:
                fb = pd.Timestamp(fecha_raw) if fecha_raw else pd.NaT
            except Exception:
                fb = pd.NaT
            lookup[idk] = fb
        cursor = page.get("cursor")
        if not cursor:
            break
    return lookup


def _fetch_ltv_real() -> pd.DataFrame:
    url = (f"https://docs.google.com/spreadsheets/d/{_ID_LTV}"
           f"/export?format=csv&sheet=LTV%20Real")
    df = _fetch_csv(url)
    _id_col  = next((c for c in df.columns if c.upper() == "ID CRM"), None)
    _usd_col = next((c for c in df.columns if "SECUNDARIA" in c.upper()), None)
    df["_id"]      = df[_id_col].apply(_norm_id) if _id_col else pd.Series("", index=df.index)
    _usd_raw = (df[_usd_col] if _usd_col else pd.Series(dtype=str)).astype(str).str.replace(",", ".", regex=False)
    df["_usd"]     = pd.to_numeric(_usd_raw, errors="coerce").fillna(0)
    df["_es_impl"] = (
        df.get("Producto", pd.Series(dtype=str))
        .astype(str).str.lower().str.contains("implementa", na=False)
    )
    df["_cliente"] = df.get("Cliente", pd.Series(dtype=str)).astype(str).str.strip()
    return df[df["_id"] != ""].reset_index(drop=True)


def _fetch_ltv_prom() -> pd.DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{_ID_LTV}/export?format=xlsx"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        xdata = resp.read()
    xl = pd.ExcelFile(io.BytesIO(xdata))
    df = xl.parse("LTV Prom - 2024.08", dtype=str)
    df.columns = df.columns.str.strip()
    _id_col  = next((c for c in df.columns if c.upper() == "ID CRM"), None)
    _usd_col = next((c for c in df.columns if "SECUNDARIA" in c.upper()), None)
    df["_id"]      = df[_id_col].apply(_norm_id) if _id_col else pd.Series("", index=df.index)
    _usd_raw = (df[_usd_col] if _usd_col else pd.Series(dtype=str)).astype(str).str.replace(",", ".", regex=False)
    df["_usd"]     = pd.to_numeric(_usd_raw, errors="coerce").fillna(0)
    df["_cliente"] = df.get("Cliente", pd.Series(dtype=str)).astype(str).str.strip()
    return df.reset_index(drop=True)


def _fetch_ventas() -> pd.DataFrame:
    url = (f"https://docs.google.com/spreadsheets/d/{_ID_BBDD}"
           f"/gviz/tq?tqx=out:csv&sheet=BBDD_Ventas")
    df = pd.read_csv(url, dtype=str)
    df.columns = df.columns.str.strip()
    df["_fecha"] = pd.to_datetime(df.get("Fecha", ""), dayfirst=True, errors="coerce")
    df["_id"]    = df.get("ID prospecto", pd.Series(dtype=str)).apply(_norm_id)
    return df


def _fetch_ads() -> pd.DataFrame:
    import sys, os as _os
    sys.path.insert(0, str(_ROOT))
    import datos
    return datos.cargar_ads()


# ── API pública ───────────────────────────────────────────────────────────────

def cache_existe() -> bool:
    return _CACHE_PATH.exists()


def cache_fecha() -> str | None:
    """Retorna fecha/hora de la última actualización o None."""
    if not _CACHE_PATH.exists():
        return None
    import datetime
    ts = _CACHE_PATH.stat().st_mtime
    return datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


def cargar_ltv() -> dict:
    """
    Lee los datos LTV del caché local.
    Devuelve {"real": df, "prom": df, "ventas": df, "ads": df, "monday": dict}
    Lanza FileNotFoundError si no hay caché — el caller debe manejar esto.
    """
    if not _CACHE_PATH.exists():
        raise FileNotFoundError("No hay datos LTV cacheados. Usá 'Actualizar datos' para cargar.")
    with open(_CACHE_PATH, "rb") as f:
        return pickle.load(f)


def actualizar_ltv(progress_cb=None) -> dict:
    """
    Re-fetchea todas las fuentes LTV y guarda en caché local.
    progress_cb(msg: str) — callback opcional para reportar progreso.
    Retorna el dict de datos.
    """
    def _log(msg):
        if progress_cb:
            progress_cb(msg)

    _log("Descargando LTV Real (Finnegans)...")
    df_real = _fetch_ltv_real()

    _log("Descargando LTV Prom pre-Finnegans (xlsx)...")
    df_prom = _fetch_ltv_prom()

    _log("Descargando BBDD_Ventas...")
    df_ventas = _fetch_ventas()

    _log("Descargando datos de Ads...")
    df_ads = _fetch_ads()

    _log("Descargando estado clientes desde Monday CS...")
    monday = _fetch_estado_monday()

    data = {
        "real":   df_real,
        "prom":   df_prom,
        "ventas": df_ventas,
        "ads":    df_ads,
        "monday": monday,
    }

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "wb") as f:
        pickle.dump(data, f)

    _log("Caché guardado.")
    return data
