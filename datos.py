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

_MESES_COL = {
    1: "2026 Enero", 2: "2026 Febrero", 3: "2026 Marzo", 4: "2026 Abril",
    5: "2026 Mayo",  6: "2026 Junio",   7: "2026 Julio", 8: "2026 Agosto",
    9: "2026 Septiembre", 10: "2026 Octubre", 11: "2026 Noviembre", 12: "2026 Diciembre",
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
    df = _leer_cache("sheet_ads.parquet") or _leer_sheet(URL_ADS)
    df["fecha"]         = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    df["inversion"]     = _limpiar_monto(df["Inversión total"])
    df["semana_inicio"] = df["fecha"] - pd.to_timedelta(df["fecha"].dt.dayofweek, unit="D")
    return df[["fecha", "semana_inicio", "inversion"]].dropna(subset=["fecha"])


def cargar_objetivos() -> dict:
    """
    Retorna {
        'cpl':    {mes_num: val},   # CPL objetivo
        'cpl_gf': {mes_num: val},   # $R1 = CPL GF objetivo
        'leads':  {mes_num: val},   # leads mensuales objetivo
        'gf':     {mes_num: val},   # R1 (GF) mensuales objetivo
    }
    Defaults: cpl=74, cpl_gf=92, leads=300, gf=240.
    """
    defaults = {
        "cpl":      {m: 74.0    for m in range(1, 13)},
        "cpl_gf":   {m: 163.0   for m in range(1, 13)},
        "leads":    {m: 300.0   for m in range(1, 13)},
        "gf":       {m: 141.0   for m in range(1, 13)},
        "inversion":{m: 23000.0 for m in range(1, 13)},
    }
    kpi_map = {
        "CPL": "cpl",
        "CPL GF": "cpl_gf",
        "Leads": "leads",
        "Leads GF (Un)": "gf",
        "Inversión publicidad (Sin imp)": "inversion",
    }
    try:
        df     = _leer_sheet(URL_OBJETIVOS)
        result = {k: {} for k in defaults}
        for _, row in df.iterrows():
            # Ignorar filas del desglose semanal (Area vacía)
            area = str(row.get(" Area", row.get("Area", ""))).strip()
            if not area or area == "nan":
                continue
            kpi = str(row.get(" KPI", row.get("KPI", ""))).strip()
            if kpi not in kpi_map:
                continue
            key = kpi_map[kpi]
            for mes_num, col in _MESES_COL.items():
                if col in df.columns:
                    val = _limpiar_monto(pd.Series([row[col]])).iloc[0]
                    if val > 0:
                        result[key][mes_num] = val
        # Completar meses faltantes con defaults
        for key, defvals in defaults.items():
            for m in range(1, 13):
                if m not in result[key]:
                    result[key][m] = defvals[m]
        return result
    except Exception:
        return defaults


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
