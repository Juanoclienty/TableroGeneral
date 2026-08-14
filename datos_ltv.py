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
_BOARD_CS  = "6967792411"
_ID_LTV    = "1TGVc9zgYc0siaouIOi8xTOiFopgXuW8AXIB_dqYZ7Ps"
_ID_LTV_V2 = "1xmBfZSeYGNMgHwdvUvObyE8Y58MbkYCN3cBZtLpEW7o"
_ID_BBDD   = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"


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


def _parse_usd_ltv(s) -> float:
    """'$6.584' o '$ 6.584,50' → float."""
    s = str(s).replace("$", "").strip()
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _fetch_ltv_v2() -> pd.DataFrame:
    """Lee el sheet consolidado de LTV (nueva versión)."""
    url = f"https://docs.google.com/spreadsheets/d/{_ID_LTV_V2}/export?format=csv"
    df = _fetch_csv(url)
    df["_id"]      = df.get("ID CRM", pd.Series(dtype=str)).apply(_norm_id)
    df["_cliente"] = df.get("Cliente", pd.Series(dtype=str)).astype(str).str.strip()
    df["_ltv_r"]   = df.get("LTV Recurrente",    pd.Series(dtype=str)).apply(_parse_usd_ltv)
    df["_ltv_i"]   = df.get("LTV Implementación", pd.Series(dtype=str)).apply(_parse_usd_ltv)
    df["_ltv_t"]   = df.get("LTV Total",          pd.Series(dtype=str)).apply(_parse_usd_ltv)
    df["_estado"]  = df.get("Estado", pd.Series(dtype=str)).astype(str).str.strip()
    df["_fecha_baja"] = pd.to_datetime(
        df.get("Fecha Baja", pd.Series(dtype=str)), errors="coerce"
    )
    df["_meses_activo"] = pd.to_numeric(
        df.get("Meses activo", pd.Series(dtype=str)), errors="coerce"
    )
    df["_ultimo_tkt"] = df.get("Ultimo Tkt recurrente", pd.Series(dtype=str)).apply(
        lambda x: _parse_usd_ltv(x) if str(x).strip() not in ("", "nan", "NaN") else float("nan")
    )
    _col_fi = next((c for c in df.columns if "ingreso" in c.lower()), None)
    df["_fecha_ingreso"] = pd.to_datetime(
        df[_col_fi] if _col_fi else pd.Series(dtype=str), dayfirst=True, errors="coerce"
    )
    return df[df["_id"] != ""].reset_index(drop=True)


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
    Devuelve {"ltv_v2": df, "ventas": df, "ads": df}
    Lanza FileNotFoundError si no hay caché o el formato es viejo.
    """
    if not _CACHE_PATH.exists():
        raise FileNotFoundError("No hay datos LTV cacheados. Usá 'Actualizar datos' para cargar.")
    with open(_CACHE_PATH, "rb") as f:
        data = pickle.load(f)
    if "ltv_v2" not in data:
        raise FileNotFoundError("Caché LTV desactualizado. Usá 'Actualizar BD → Actualizar LTV' para regenerar.")
    return data


def actualizar_ltv(progress_cb=None) -> dict:
    """
    Re-fetchea todas las fuentes LTV y guarda en caché local.
    progress_cb(msg: str) — callback opcional para reportar progreso.
    Retorna el dict de datos.
    """
    def _log(msg):
        if progress_cb:
            progress_cb(msg)

    _log("Descargando LTV (sheet consolidado)...")
    df_ltv_v2 = _fetch_ltv_v2()

    _log("Descargando BBDD_Ventas...")
    df_ventas = _fetch_ventas()

    _log("Descargando datos de Ads...")
    df_ads = _fetch_ads()

    data = {
        "ltv_v2": df_ltv_v2,
        "ventas": df_ventas,
        "ads":    df_ads,
    }

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "wb") as f:
        pickle.dump(data, f)

    _log("Caché guardado.")
    return data


def cargar_ltv_lookup() -> dict:
    """
    Retorna {id_crm: {ltv_t, ltv_i, ltv_r, tkt_rec}} desde el caché LTV.
    Lanza FileNotFoundError si no hay caché.
    """
    data = cargar_ltv()
    df   = data["ltv_v2"]
    out  = {}
    for _, r in df.iterrows():
        _id = str(r.get("_id") or "").strip()
        if not _id:
            continue
        def _v(x):
            import math
            return None if (x is None or (isinstance(x, float) and math.isnan(x))) else round(float(x))
        out[_id] = {
            "ltv_t":   _v(r.get("_ltv_t")),
            "ltv_i":   _v(r.get("_ltv_i")),
            "ltv_r":   _v(r.get("_ltv_r")),
            "tkt_rec": _v(r.get("_ultimo_tkt")),
        }
    return out
