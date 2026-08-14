"""
datos.py — Carga y procesamiento de datos para el dashboard.
Modificá las URLs al principio si cambian los links de las sheets.
"""
import io
import os
import urllib.request
import pandas as pd
from datetime import date, timedelta

_CREDS_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
ID_CALENDLY_TRAB = "1jtP9lYjVRnxFkvd0kN4xV5B6AQPEeFxgtxIRh5v-cgs"

# ============================================================
# URLS DE LAS HOJAS DE GOOGLE SHEETS
# ============================================================
URL_CALENDLY  = "https://docs.google.com/spreadsheets/d/1KDlgqrTcaSlPSbARUJe4qnPhFdmgvQfoE2-WU1y0zzQ/export?format=csv"
URL_ADS       = "https://docs.google.com/spreadsheets/d/1mx6EXpdM6kKfzNNWQ_J7vcPBL2Ex36uRmtY-mxKXcoY/export?format=csv"
URL_OBJETIVOS = "https://docs.google.com/spreadsheets/d/1rOa7MvHxXUiU8nEMb5cKTyv8lMvPuZzrAT8Wj0KuD40/export?format=csv"

# Mapeo columna del sheet → número de mes (ene-26 = 1, etc.)
_MESES_COL = {
    "ene-26": 1, "feb-26": 2, "mar-26": 3, "abr-26": 4,
    "may-26": 5, "jun-26": 6, "jul-26": 7, "ago-26": 8,
    "sept-26": 9, "oct-26": 10, "nov-26": 11, "dic-26": 12,
}


# ============================================================
# HELPERS INTERNOS
# ============================================================

def _leer_sheet(url: str) -> pd.DataFrame:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        contenido = resp.read().decode("utf-8")
    return pd.read_csv(io.StringIO(contenido))


def _limpiar_monto(serie: pd.Series) -> pd.Series:
    """Convierte '$ 1.234,56' → 1234.56 (formato argentino)."""
    return (
        serie.astype(str)
        .str.replace(r"[$\s]", "", regex=True)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .replace("", "0")
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )


def _agregar_calidad(grp) -> pd.DataFrame:
    """Agrega conteos de GF/BF/PF/sin_data y métricas derivadas desde un groupby."""
    df = grp.agg(
        leads     = ("fecha_lead", "count"),
        gf        = ("calidad", lambda x: (x == "R1F").sum()),
        bf        = ("calidad", lambda x: (x == "R1BF").sum()),
        pf        = ("calidad", lambda x: (x == "R1PBF").sum()),
    ).reset_index()
    df[["gf", "bf", "pf"]] = df[["gf", "bf", "pf"]].astype(int)
    df["sin_data"] = (df["leads"] - df["gf"] - df["bf"] - df["pf"]).clip(lower=0)
    df["pct_gf"]   = (df["gf"].astype(float) / df["leads"].where(df["leads"] > 0) * 100).round(1)
    return df


def _merge_ads_y_costos(df: pd.DataFrame, ads_grp: pd.DataFrame, key: str) -> pd.DataFrame:
    """Une con ads, calcula CPL y CPL GF. Bug fix: .where() en vez de .replace(0, pd.NA)."""
    df = df.merge(ads_grp, on=key, how="left")
    df["inversion"] = df["inversion"].fillna(0)
    # Bug fix #5: .where(cond) reemplaza con NaN float donde la condición es False,
    # manteniendo el dtype float64 para que .round() funcione.
    df["cpl"]    = (df["inversion"] / df["leads"].where(df["leads"] > 0)).round(1)
    df["cpl_gf"] = (df["inversion"] / df["gf"].where(df["gf"] > 0)).round(1)
    for col in ["r1", "r2", "presu", "venta"]:
        df[col] = pd.NA
    return df


# ============================================================
# FUNCIONES DE CARGA
# ============================================================

def _leer_cache(filename: str):
    """Lee un parquet pre-cacheado si existe, sino retorna None."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", filename)
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


def cargar_calendly() -> pd.DataFrame:
    df = _leer_cache("sheet_calendly.parquet")
    if df is None:
        try:
            from google.oauth2.service_account import Credentials
            import gspread
            creds = Credentials.from_service_account_file(
                _CREDS_PATH,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            )
            ws = gspread.authorize(creds).open_by_key(ID_CALENDLY_TRAB).get_worksheet(0)
            df = pd.DataFrame(ws.get_all_records())
        except Exception:
            df = _leer_sheet(URL_CALENDLY)

    df["fecha_lead"]    = pd.to_datetime(df.get("Fecha Lead"), dayfirst=True, errors="coerce")
    df["semana_inicio"] = df["fecha_lead"] - pd.to_timedelta(df["fecha_lead"].dt.dayofweek, unit="D")
    col_tipo = next((c for c in df.columns if c.lower().strip() == "tipo calendly"), None)
    df["calidad"] = df[col_tipo].astype(str).str.strip() if col_tipo else "sin_data"
    return df


def cargar_ads() -> pd.DataFrame:
    import time
    _cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "sheet_ads.parquet")
    _TTL = 86400  # 24h
    _cache_ok = (
        os.path.exists(_cache_path)
        and (time.time() - os.path.getmtime(_cache_path)) < _TTL
    )
    if _cache_ok:
        df = pd.read_parquet(_cache_path)
    else:
        df = _leer_sheet(URL_ADS)
        df.to_parquet(_cache_path, index=False)
    df["fecha"]         = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    df["inversion"]     = _limpiar_monto(df["Inversión total"])
    df["semana_inicio"] = df["fecha"] - pd.to_timedelta(df["fecha"].dt.dayofweek, unit="D")
    return df[["fecha", "semana_inicio", "inversion"]].dropna(subset=["fecha"])


def cargar_objetivos() -> dict:
    """
    Lee el sheet de objetivos y retorna:
      { 'leads': {mes: val}, 'gf': {mes: val}, 'inversion': {mes: val},
        'cpl': {mes: val}, 'cpl_gf': {mes: val} }
    Las claves del dict interno son números de mes (1=enero … 12=diciembre).
    Los valores vienen directamente del sheet; no hay defaults hardcodeados.
    """
    # Filas de interés (valor exacto de la columna 'Unnamed: 0' en el CSV)
    kpi_map = {
        "Cantidad de prospectos":  "leads",
        "Leads GF (Un)":           "gf",
        "Inversión publicidad":    "inversion",
        "CPL":                     "cpl",
        "CPL GF":                  "cpl_gf",
    }
    result = {k: {} for k in kpi_map.values()}
    df = _leer_sheet(URL_OBJETIVOS)
    # La primera columna tiene los nombres de KPI
    label_col = df.columns[0]
    for _, row in df.iterrows():
        label = str(row[label_col]).strip()
        if label not in kpi_map:
            continue
        key = kpi_map[label]
        for col, mes_num in _MESES_COL.items():
            if col not in df.columns:
                continue
            val = _limpiar_monto(pd.Series([row[col]])).iloc[0]
            if val > 0:
                result[key][mes_num] = val
    return result


# ============================================================
# CÁLCULOS POR PERÍODO
# ============================================================

def calcular_semanas(df_cal: pd.DataFrame, df_ads: pd.DataFrame) -> pd.DataFrame:
    """Agrega por semana (Lunes–Domingo)."""
    df_cal = df_cal.dropna(subset=["semana_inicio"])
    grp    = df_cal.groupby("semana_inicio")
    df     = _agregar_calidad(grp)

    df["fecha_ini"] = pd.to_datetime(df["semana_inicio"]).dt.normalize()
    df["fecha_fin"] = df["fecha_ini"] + pd.Timedelta(days=6)

    ads_grp = df_ads.groupby("semana_inicio")["inversion"].sum().reset_index()
    ads_grp.rename(columns={"semana_inicio": "semana_inicio"}, inplace=True)
    df = _merge_ads_y_costos(df, ads_grp, "semana_inicio")

    return df.sort_values("fecha_ini").reset_index(drop=True)


def calcular_meses(df_cal: pd.DataFrame, df_ads: pd.DataFrame) -> pd.DataFrame:
    """Agrega por mes calendario."""
    df_cal = df_cal.dropna(subset=["fecha_lead"]).copy()
    df_cal["mes_key"] = df_cal["fecha_lead"].dt.to_period("M")

    grp = df_cal.groupby("mes_key")
    df  = _agregar_calidad(grp)

    df["fecha_ini"] = df["mes_key"].dt.start_time.dt.normalize()
    df["fecha_fin"] = df["mes_key"].dt.end_time.dt.normalize()

    df_ads2 = df_ads.copy()
    df_ads2["mes_key"] = df_ads2["fecha"].dt.to_period("M")
    ads_grp = df_ads2.groupby("mes_key")["inversion"].sum().reset_index()
    df = _merge_ads_y_costos(df, ads_grp, "mes_key")

    return df.sort_values("fecha_ini").reset_index(drop=True)



# ============================================================
# ADS DETALLE (Sheet BBDD_Detalle_ads)
# ============================================================

_ADS_SHEET_ID   = "1DSXU0pluCzCJDFwKremw7crWb1W21S9HtWDOsDhVG8E"
_CACHE_ADS_SEM  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "ads_detalle_sem.parquet")
_CACHE_ADS_MES  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "ads_detalle_mes.parquet")
_CACHE_ADS_DATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "ads_detalle.date")

import re as _re


def _extraer_num_ad(nombre: str) -> int:
    """'Ad_0813' / 'Ad 813' / 'Ad_293' → 813 / 813 / 293 (int, sin ceros)."""
    m = _re.search(r"\d+", str(nombre))
    return int(m.group()) if m else -1


def _procesar_ads_xlsx() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Descarga el xlsx de ads, procesa y retorna (df_sem, df_mes) ya
    dolarizados y con tipo/tematica del Anexo.
    """
    url = f"https://docs.google.com/spreadsheets/d/{_ADS_SHEET_ID}/export?format=xlsx"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        data = r.read()

    xls = pd.ExcelFile(io.BytesIO(data))

    # ── Tipo de cambio ─────────────────────────────────────────
    tc_df = pd.read_excel(io.BytesIO(data), sheet_name="Tipo de cambio")
    tc_df["fecha"] = pd.to_datetime(tc_df.iloc[:, 0], errors="coerce")
    tc_df["mes"]   = tc_df["fecha"].dt.month
    tc_map = tc_df.dropna(subset=["mes"]).set_index("mes")["Tipo de cambio"].to_dict()

    # ── Anexo ads — deduplicar quedando con la última fila ────
    anx = pd.read_excel(io.BytesIO(data), sheet_name="Anexo_ads")
    anx.columns = [c.strip() for c in anx.columns]
    anx["_num"] = anx["Nombre del AD"].apply(_extraer_num_ad)
    anx = anx[anx["_num"] >= 0].drop_duplicates(subset="_num", keep="last")
    anx["tipo"]     = anx.get("Tipo de contenido", pd.Series(dtype=str)).fillna("Sin clasificar").str.strip()
    _tem_col        = next((c for c in anx.columns if c.strip().lower() == "tematica"), None)
    anx["tematica"] = anx[_tem_col].fillna("Sin clasificar").str.strip() if _tem_col else "Sin clasificar"
    anx_map = anx.set_index("_num")[["tipo", "tematica"]]

    def _enriquecer(df: pd.DataFrame, periodo_col: str) -> pd.DataFrame:
        df = df.copy()
        df.columns = [c.strip() for c in df.columns]
        df["fecha_ini"] = pd.to_datetime(df["Inicio del informe"], errors="coerce")
        df["fecha_fin"] = pd.to_datetime(df["Fin del informe"],    errors="coerce")
        df["mes_num"]   = df["fecha_ini"].dt.month
        df["_num"]      = df["Nombre del anuncio"].apply(_extraer_num_ad)
        df["inversion_ars"] = pd.to_numeric(
            df["Importe gastado (ARS)"].astype(str)
            .str.replace(",", ".", regex=False), errors="coerce").fillna(0)
        df["tc"]            = df["mes_num"].map(tc_map).fillna(1)
        df["inversion_usd"] = (df["inversion_ars"] / df["tc"]).round(1)
        # Join con Anexo
        df = df.join(anx_map, on="_num", how="left")
        df["tipo"]     = df["tipo"].fillna("Sin clasificar")
        df["tematica"] = df["tematica"].fillna("Sin clasificar")
        df["nombre_ad"] = df["Nombre del anuncio"]
        keep = [periodo_col, "nombre_ad", "inversion_ars", "fecha_ini", "fecha_fin",
                "mes_num", "inversion_usd", "tipo", "tematica"]
        return df[[c for c in keep if c in df.columns]].reset_index(drop=True)

    df_sem = _enriquecer(
        pd.read_excel(io.BytesIO(data), sheet_name="Detalle_ads_sem"), "Semana")
    df_mes = _enriquecer(
        pd.read_excel(io.BytesIO(data), sheet_name="Detalle_ads_mes"), "Mes")

    return df_sem, df_mes


def cargar_anexo_ads() -> pd.DataFrame:
    """Retorna DataFrame con columnas [_num, tipo, tematica] desde Anexo_ads."""
    import io
    url = f"https://docs.google.com/spreadsheets/d/{_ADS_SHEET_ID}/export?format=xlsx"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        data = r.read()
    anx = pd.read_excel(io.BytesIO(data), sheet_name="Anexo_ads")
    anx.columns = [c.strip() for c in anx.columns]
    anx["_num"] = anx["Nombre del AD"].apply(_extraer_num_ad)
    anx = anx[anx["_num"] >= 0].drop_duplicates(subset="_num", keep="last")
    anx["tipo"] = anx.get("Tipo de contenido", pd.Series(dtype=str)).fillna("Sin clasificar").str.strip()
    _tem_col = next((c for c in anx.columns if c.strip().lower() == "tematica"), None)
    anx["tematica"] = anx[_tem_col].fillna("Sin clasificar").str.strip() if _tem_col else "Sin clasificar"
    return anx[["_num", "tipo", "tematica"]].reset_index(drop=True)


def actualizar_cache_ads() -> str:
    """Descarga, procesa y guarda los parquets de ads. Retorna timestamp."""
    df_sem, df_mes = _procesar_ads_xlsx()
    df_sem.to_parquet(_CACHE_ADS_SEM, index=False)
    df_mes.to_parquet(_CACHE_ADS_MES, index=False)
    ts = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")
    with open(_CACHE_ADS_DATE, "w") as f:
        f.write(ts)
    return ts


def cargar_ads_detalle() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Retorna (df_sem, df_mes, ultima_actualizacion).
    Lee de parquet local; si no existe, descarga del xlsx.
    """
    ts = "–"
    if os.path.exists(_CACHE_ADS_DATE):
        with open(_CACHE_ADS_DATE) as f:
            ts = f.read().strip()

    if os.path.exists(_CACHE_ADS_SEM) and os.path.exists(_CACHE_ADS_MES):
        return pd.read_parquet(_CACHE_ADS_SEM), pd.read_parquet(_CACHE_ADS_MES), ts

    ts = actualizar_cache_ads()
    return pd.read_parquet(_CACHE_ADS_SEM), pd.read_parquet(_CACHE_ADS_MES), ts


def calcular_dias(df_cal: pd.DataFrame, df_ads: pd.DataFrame, dias: int = 15) -> pd.DataFrame:
    """
    Agrega por día. Muestra siempre los últimos N días desde T-1 (ayer) hacia atrás.
    El filtro de fecha del sidebar no aplica a esta vista.
    """
    ayer        = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    fecha_inicio = ayer - pd.Timedelta(days=dias - 1)

    df_cal = df_cal.dropna(subset=["fecha_lead"]).copy()
    df_cal = df_cal[(df_cal["fecha_lead"] >= fecha_inicio) & (df_cal["fecha_lead"] <= ayer)]
    df_cal["dia_key"] = df_cal["fecha_lead"].dt.normalize()

    grp = df_cal.groupby("dia_key")
    df  = _agregar_calidad(grp)
    df.rename(columns={"dia_key": "fecha_ini"}, inplace=True)
    df["fecha_fin"] = df["fecha_ini"]

    df_ads2 = df_ads[(df_ads["fecha"] >= fecha_inicio) & (df_ads["fecha"] <= ayer)].copy()
    df_ads2["fecha_ini"] = df_ads2["fecha"].dt.normalize()
    ads_grp = df_ads2.groupby("fecha_ini")["inversion"].sum().reset_index()
    df = _merge_ads_y_costos(df, ads_grp, "fecha_ini")

    return df.sort_values("fecha_ini").reset_index(drop=True)
