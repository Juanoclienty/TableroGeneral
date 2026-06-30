"""
datos_crm.py — Carga y procesamiento de datos del CRM Clienty (API REST).
"""
import io
import os
import json
import base64
import urllib.request
import urllib.error
import pandas as pd
from datetime import date, datetime, timedelta

ID_CALENDLY_TRAB = "1jtP9lYjVRnxFkvd0kN4xV5B6AQPEeFxgtxIRh5v-cgs"
_CREDS_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
_CACHE_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
_CACHE_VER       = "9"   # incrementar si cambia el schema
_CACHE_FILE      = os.path.join(_CACHE_DIR, f"df_crm_v{_CACHE_VER}.parquet")
_CACHE_DATE_FILE = os.path.join(_CACHE_DIR, f"df_crm_v{_CACHE_VER}.date")


# Mapeo Estado CRM → Estado resumen
ESTADO_MAP = {
    "0 - Llamado cancelado"       : "0. Lead",
    "1.2 - Reagendar R1"          : "0. Lead",
    "Nuevo"                       : "0. Lead",
    "Reingreso - CS"              : "0. Lead",
    "0.1 - Contacto inicial pre R1": "1. R1",
    "1.1 - Filtrado pre R1"       : "1. R1",
    "3 - Filtrado en R1"          : "1. R1",
    "2 - R1"                      : "1. R1",
    "4 - Follow podcast"          : "2. Follow",
    "5.2 - Filtrado pre R2"       : "2. Follow",
    "2 Reunión"                   : "3. R2",
    "5.1 - R2 confirmada"         : "3. R2",
    "5.3 - Reagendar R2"          : "3. R2",
    "Buyer Sin interés"           : "3. R2",
    "Coordinando reunión"         : "3. R2",
    "Irrelevante"                 : "3. R2",
    "SDR - Irrelevante"           : "3. R2",
    "Contactar a Futuro"          : "4. Presupuesto",
    "Dijo que no"                 : "4. Presupuesto",
    "Follow 2"                    : "4. Presupuesto",
    "Follow Clienty"              : "4. Presupuesto",
    "Stand By"                    : "4. Presupuesto",
    "Últimos detalles"            : "4. Presupuesto",
    "Venta ganada"                : "5. Venta",
    "Agencia"                     : "6. Otros",
    "Duplicados"                  : "6. Otros",
    "Back - Dado de baja"         : "6. Otros",
    "Back - Reunión confirmada"   : "6. Otros",
    "Back - Sin confirmar"        : "6. Otros",
    "Re-agendar"                  : "6. Otros",
}

ETAPAS = ["0. Lead", "1. R1", "2. Follow", "3. R2", "4. Presupuesto", "5. Venta", "6. Otros"]


# ── Credenciales ──────────────────────────────────────────────

def _get_api_config():
    """Lee credenciales desde st.secrets o variables de entorno."""
    try:
        import streamlit as st
        cfg = st.secrets["clienty"]
        return str(cfg["subdominio"]), str(cfg["username"]), str(cfg["password"])
    except Exception:
        return (
            os.environ.get("CLIENTY_SUBDOMINIO", ""),
            os.environ.get("CLIENTY_USERNAME", ""),
            os.environ.get("CLIENTY_PASSWORD", ""),
        )


# ── Fetch API ─────────────────────────────────────────────────

def _fetch_leads_api(subdominio: str, username: str, password: str) -> list:
    """Descarga todos los leads paginando el endpoint GET /lead."""
    token   = base64.b64encode(f"{username}:{password}".encode()).decode()
    base    = f"https://{subdominio}.clienty.co/api/integration"
    headers = {
        "Authorization": f"Basic {token}",
        "Accept":        "application/json",
        "User-Agent":    "Mozilla/5.0",
    }

    # Traer solo leads desde esta fecha
    cutoff = pd.Timestamp("2025-06-01", tz="UTC")

    leads = []
    page  = 1
    while True:
        url = f"{base}/lead?page={page}"
        req = urllib.request.Request(url, headers=headers)
        data = None
        for intento in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"API Clienty error {e.code} en {url}\nRespuesta: {body[:500]}") from e
            except Exception:
                if intento == 2:
                    raise
        if data is None:
            break

        # Estructura: {"success": true, "data": {"data": [...leads...], "pagination": {...}}}
        inner       = data.get("data") or {} if isinstance(data, dict) else {}
        batch       = (inner.get("data") or inner.get("leads") or inner.get("results") or []) if isinstance(inner, dict) else (inner if isinstance(inner, list) else [])
        pag         = (inner.get("pagination") or inner.get("meta") or {}) if isinstance(inner, dict) else {}
        last_page   = int(pag.get("lastPage") or pag.get("last_page") or pag.get("total_pages") or 1)

        if not batch:
            break
        leads.extend(batch)

        # Parar si llegamos a leads más viejos que el cutoff
        oldest = batch[-1].get("createdDate", "") if isinstance(batch[-1], dict) else ""
        if oldest:
            oldest_ts = pd.Timestamp(oldest, tz="UTC")
            if oldest_ts < cutoff:
                break

        if page >= last_page:
            break
        page += 1

    return leads


def _clasificar_calidad(txt):
    if pd.isna(txt):
        return "sin_data"
    t = str(txt).upper()
    if "R1PBF" in t:
        return "R1PBF"
    if "R1BF" in t:
        return "R1BF"
    if "VGF" in t:        # VGF (Very Good Fit) → cuenta como GF
        return "R1F"
    if "R1F" in t:
        return "R1F"
    return "sin_data"


def _leads_to_df(leads: list) -> pd.DataFrame:
    """Convierte la lista de dicts de la API al DataFrame con columnas internas."""
    if not leads:
        return pd.DataFrame(columns=[
            "id", "Fecha de ingreso", "Emails", "Consulta", "Estado",
            "Empresa", "status_updated_at", "Etiquetas",
        ])

    rows = []
    for lead in leads:
        if not isinstance(lead, dict):
            continue
        status = lead.get("status") or lead.get("estado") or lead.get("state") or {}
        status_name = status.get("name", "") if isinstance(status, dict) else str(status or "")

        # Fecha del último cambio de estado (varios nombres posibles según versión API)
        status_date = ""
        if isinstance(status, dict):
            status_date = (status.get("updatedAt") or status.get("changedAt")
                           or status.get("created_at") or status.get("createdAt")
                           or status.get("date")       or status.get("fecha")
                           or status.get("updated_at") or status.get("statusDate") or "")
        if not status_date:
            status_date = (lead.get("statusChangedAt")   or lead.get("statusUpdatedAt")
                           or lead.get("status_changed_at") or lead.get("status_date")
                           or lead.get("statusDate")     or lead.get("statusAt")
                           or lead.get("lastStatusChange") or lead.get("last_status_change")
                           or lead.get("updatedAt")      or lead.get("updated_at")
                           or lead.get("lastModified")   or lead.get("last_modified") or "")

        # Empresa
        empresa = (lead.get("company") or lead.get("companyName")
                   or lead.get("empresa") or "")

        # Usuario asignado
        user = lead.get("user") or lead.get("assignedTo") or lead.get("owner") or lead.get("vendedor") or {}
        if isinstance(user, dict):
            usuario = user.get("name") or user.get("nombre") or user.get("email") or ""
        else:
            usuario = str(user) if user else ""

        # Nombre del contacto
        nombre = (lead.get("name") or lead.get("nombre") or lead.get("contactName")
                  or lead.get("fullName") or lead.get("contact_name") or "")
        if not nombre:
            fn = lead.get("firstName") or lead.get("first_name") or ""
            ln = lead.get("lastName")  or lead.get("last_name")  or ""
            nombre = f"{fn} {ln}".strip()

        # Teléfono
        telefono = (lead.get("phone") or lead.get("telefono") or
                    lead.get("phoneNumber") or lead.get("phone_number") or
                    lead.get("mobile") or "")

        # Monto de venta
        monto_raw = (lead.get("amount") or lead.get("monto") or
                     lead.get("value") or lead.get("deal_value") or "")
        if not monto_raw:
            cfields = lead.get("customFields") or lead.get("custom_fields") or lead.get("fields") or []
            if isinstance(cfields, list):
                for f in cfields:
                    if isinstance(f, dict):
                        fname = str(f.get("name") or f.get("label") or "").lower()
                        if any(k in fname for k in ("monto", "amount", "valor", "precio", "price")):
                            monto_raw = f.get("value") or ""
                            break
            elif isinstance(cfields, dict):
                for k, v in cfields.items():
                    if any(kw in str(k).lower() for kw in ("monto", "amount", "valor", "precio")):
                        monto_raw = v
                        break

        # Comentarios / notas de venta
        comentarios = (lead.get("comments") or lead.get("notes") or
                       lead.get("observations") or lead.get("comment") or
                       lead.get("note") or "")

        # Fecha de la 1ra reunión efectiva (campo interno Clienty)
        fecha_reunion = ""
        _cfields = lead.get("customFields") or lead.get("custom_fields") or lead.get("fields") or []
        if isinstance(_cfields, list):
            for _f in _cfields:
                if isinstance(_f, dict):
                    _fname = str(_f.get("name") or _f.get("label") or "").lower()
                    if any(k in _fname for k in ("1ra", "primera", "reunion", "reuni")):
                        fecha_reunion = str(_f.get("value") or "")
                        break
        elif isinstance(_cfields, dict):
            for _k, _v in _cfields.items():
                if any(kw in str(_k).lower() for kw in ("1ra", "primera", "reunion", "reuni")):
                    fecha_reunion = str(_v) if _v else ""
                    break

        # Etiquetas / tags del CRM
        tags_raw = lead.get("tags") or lead.get("etiquetas") or lead.get("labels") or []
        if isinstance(tags_raw, list):
            tag_parts = []
            for t in tags_raw:
                if isinstance(t, dict):
                    tag_parts.append(t.get("name") or t.get("label") or t.get("nombre") or "")
                elif isinstance(t, str):
                    tag_parts.append(t)
            etiquetas = ", ".join(p for p in tag_parts if p)
        else:
            etiquetas = str(tags_raw) if tags_raw else ""

        rows.append({
            "id":               lead.get("id", ""),
            "Fecha de ingreso": lead.get("createdDate", ""),
            "Emails":           lead.get("email", ""),
            "Consulta":         lead.get("message", ""),
            "Estado":           status_name,
            "Empresa":          str(empresa) if empresa else "",
            "status_updated_at": status_date,
            "Usuario":          usuario,
            "Etiquetas":        etiquetas,
            "Nombre":              nombre,
            "Telefono":            str(telefono) if telefono else "",
            "Monto":               str(monto_raw) if monto_raw else "",
            "Comentarios":         str(comentarios) if comentarios else "",
            "Fecha 1ra reunion":   fecha_reunion,
        })
    return pd.DataFrame(rows)


# ── Caché local (Parquet) ─────────────────────────────────────

def _cache_vigente() -> bool:
    if not os.path.exists(_CACHE_FILE):
        return False
    edad_horas = (datetime.now().timestamp() - os.path.getmtime(_CACHE_FILE)) / 3600
    return edad_horas < 24

def limpiar_cache():
    for f in [_CACHE_FILE, _CACHE_DATE_FILE]:
        if os.path.exists(f):
            os.remove(f)


# ── cargar_crm ────────────────────────────────────────────────

def cargar_crm() -> pd.DataFrame:
    # Usar caché local si es del día de hoy
    if _cache_vigente():
        return pd.read_parquet(_CACHE_FILE)

    subdominio, username, password = _get_api_config()
    leads = _fetch_leads_api(subdominio, username, password)
    df    = _leads_to_df(leads)

    # Fecha: API devuelve UTC, convertir a hora Argentina (UTC-3)
    df["fecha_ingreso"] = pd.to_datetime(df["Fecha de ingreso"], errors="coerce", utc=True)
    df["fecha_ingreso"] = df["fecha_ingreso"].dt.tz_convert("America/Argentina/Buenos_Aires").dt.tz_localize(None)
    df["fecha_lead"]    = df["fecha_ingreso"].dt.normalize()
    df["semana_inicio"] = df["fecha_lead"] - pd.to_timedelta(
        df["fecha_lead"].dt.dayofweek, unit="D"
    )

    # Calidad: desde el texto del campo Consulta (igual que en el sheet original)
    df["calidad"] = df["Consulta"].apply(_clasificar_calidad)

    # Estado resumen
    df["estado_resumen"] = df["Estado"].map(ESTADO_MAP).fillna("6. Otros")

    # Tiempo en estado actual: fecha del último cambio de estado → días transcurridos
    df["status_updated_at"] = pd.to_datetime(df["status_updated_at"], errors="coerce", utc=True)
    df["status_updated_at"] = df["status_updated_at"].dt.tz_convert("America/Argentina/Buenos_Aires").dt.tz_localize(None)
    hoy = pd.Timestamp.today().normalize()
    df["dias_en_estado"] = (hoy - df["status_updated_at"].dt.normalize()).dt.days

    # Merge con Calendly trabajada (Ticket, Equipo comercial, Consultas, Inversión Publicidad)
    try:
        from google.oauth2.service_account import Credentials
        import gspread
        creds  = Credentials.from_service_account_file(
            _CREDS_PATH,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        ws     = gspread.authorize(creds).open_by_key(ID_CALENDLY_TRAB).get_worksheet(0)
        df_cal = pd.DataFrame(ws.get_all_records())

        # Normalizar nombre de columna Inversión Publicidad (puede venir con o sin tilde)
        _col_inv = next(
            (c for c in df_cal.columns if "nversi" in c and "ublicidad" in c), None
        )
        if _col_inv and _col_inv != "Inversión Publicidad":
            df_cal = df_cal.rename(columns={_col_inv: "Inversión Publicidad"})

        cols_extra = [c for c in [
            "Tipo cliente", "Ticket", "Equipo comercial", "Consultas", "Inversión Publicidad",
            "Etiquetas",
        ] if c in df_cal.columns]

        if "Invitee Email" in df_cal.columns and cols_extra:
            df_cal_u = (df_cal[["Invitee Email"] + cols_extra]
                        .drop_duplicates(subset=["Invitee Email"]))
            df_cal_u["_ekey"] = df_cal_u["Invitee Email"].str.lower().str.strip()
            df["_ekey"]       = df["Emails"].str.lower().str.strip()
            df = df.merge(df_cal_u.drop(columns=["Invitee Email"]), on="_ekey", how="left",
                          suffixes=("", "_cal"))
            df.drop(columns=["_ekey"], inplace=True)
            # Si el sheet aporta etiquetas, combinarlas con las del CRM (sin pisar)
            if "Etiquetas_cal" in df.columns:
                cal_et = df["Etiquetas_cal"].fillna("").astype(str).str.strip()
                crm_et = df["Etiquetas"].fillna("").astype(str).str.strip()

                def _combinar_etiquetas(cal, crm):
                    vistas, resultado = set(), []
                    for tag in [t.strip() for s in [cal, crm] for t in s.split(",")]:
                        if tag and tag != "nan" and tag not in vistas:
                            vistas.add(tag)
                            resultado.append(tag)
                    return ", ".join(resultado)

                df["Etiquetas"] = [_combinar_etiquetas(c, r) for c, r in zip(cal_et, crm_et)]
                df.drop(columns=["Etiquetas_cal"], inplace=True)
    except Exception:
        pass

    # Guardar en caché local (normalizar columnas object a string para compatibilidad Parquet)
    os.makedirs(_CACHE_DIR, exist_ok=True)
    df_save = df.copy()
    for col in df_save.select_dtypes(include=["object"]).columns:
        df_save[col] = df_save[col].astype(str)
    df_save.to_parquet(_CACHE_FILE, index=False)
    with open(_CACHE_DATE_FILE, "w") as f:
        f.write(date.today().isoformat())

    return df


# ── Agregación ────────────────────────────────────────────────

def _agregar_crm(grp) -> pd.DataFrame:
    """Agrega conteos de leads, calidad y estados desde un groupby."""
    rows = []
    for key, grupo in grp:
        leads    = len(grupo)
        gf       = (grupo["calidad"] == "R1F").sum()
        bf       = (grupo["calidad"] == "R1BF").sum()
        pf       = (grupo["calidad"] == "R1PBF").sum()
        sin_data = leads - gf - bf - pf
        ec       = grupo["estado_resumen"].value_counts()

        row = {
            "_key"    : key,
            "leads"   : leads,
            "gf"      : gf,
            "bf"      : bf,
            "pf"      : pf,
            "sin_data": sin_data,
            "pct_gf"  : round(gf / leads * 100, 1) if leads > 0 else None,
        }
        for etapa in ETAPAS:
            row[etapa] = int(ec.get(etapa, 0))
        rows.append(row)

    if not rows:
        cols = ["_key", "leads", "gf", "bf", "pf", "sin_data", "pct_gf"] + ETAPAS
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows)


def _merge_ads(df: pd.DataFrame, ads_grp: pd.DataFrame, key: str) -> pd.DataFrame:
    df = df.merge(ads_grp, on=key, how="left")
    df["inversion"] = df["inversion"].fillna(0)
    df["cpl"]       = (df["inversion"] / df["leads"].where(df["leads"] > 0)).round(1)
    df["cpl_gf"]    = (df["inversion"] / df["gf"].where(df["gf"] > 0)).round(1)
    return df


# ── Vistas por período ─────────────────────────────────────────

def calcular_semanas_crm(df_crm: pd.DataFrame, df_ads: pd.DataFrame) -> pd.DataFrame:
    df_crm = df_crm.dropna(subset=["semana_inicio"])
    if df_crm.empty:
        return pd.DataFrame(columns=[
            "fecha_ini", "fecha_fin", "semana_inicio",
            "leads", "gf", "bf", "pf", "sin_data",
            "pct_gf", "inversion", "cpl", "cpl_gf"
        ] + ETAPAS)

    df = _agregar_crm(df_crm.groupby("semana_inicio"))
    df.rename(columns={"_key": "semana_inicio"}, inplace=True)
    df["fecha_ini"] = pd.to_datetime(df["semana_inicio"]).dt.normalize()
    df["fecha_fin"] = df["fecha_ini"] + pd.Timedelta(days=6)

    ads_grp = df_ads.groupby("semana_inicio")["inversion"].sum().reset_index()
    df = _merge_ads(df, ads_grp, "semana_inicio")
    return df.sort_values("fecha_ini").reset_index(drop=True)


def calcular_meses_crm(df_crm: pd.DataFrame, df_ads: pd.DataFrame) -> pd.DataFrame:
    df_crm = df_crm.dropna(subset=["fecha_lead"]).copy()
    if df_crm.empty:
        return pd.DataFrame(columns=[
            "fecha_ini", "fecha_fin", "mes_key",
            "leads", "gf", "bf", "pf", "sin_data",
            "pct_gf", "inversion", "cpl", "cpl_gf"
        ] + ETAPAS)

    df_crm["mes_key"] = df_crm["fecha_lead"].dt.to_period("M")
    df = _agregar_crm(df_crm.groupby("mes_key"))
    df.rename(columns={"_key": "mes_key"}, inplace=True)
    df["fecha_ini"] = df["mes_key"].dt.start_time.dt.normalize()
    df["fecha_fin"] = df["mes_key"].dt.end_time.dt.normalize()

    df_ads2 = df_ads.copy()
    df_ads2["mes_key"] = df_ads2["fecha"].dt.to_period("M")
    ads_grp = df_ads2.groupby("mes_key")["inversion"].sum().reset_index()
    df = _merge_ads(df, ads_grp, "mes_key")
    return df.sort_values("fecha_ini").reset_index(drop=True)


def calcular_dias_crm(df_crm: pd.DataFrame, df_ads: pd.DataFrame, dias: int = 15) -> pd.DataFrame:
    ayer         = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    fecha_inicio = ayer - pd.Timedelta(days=dias - 1)

    df_crm = df_crm.dropna(subset=["fecha_lead"]).copy()
    df_crm = df_crm[(df_crm["fecha_lead"] >= fecha_inicio) & (df_crm["fecha_lead"] <= ayer)]
    df_crm["dia_key"] = df_crm["fecha_lead"].dt.normalize()

    df = _agregar_crm(df_crm.groupby("dia_key"))
    df.rename(columns={"_key": "fecha_ini"}, inplace=True)
    df["fecha_fin"] = df["fecha_ini"]

    df_ads2 = df_ads[(df_ads["fecha"] >= fecha_inicio) & (df_ads["fecha"] <= ayer)].copy()
    df_ads2["fecha_ini"] = df_ads2["fecha"].dt.normalize()
    ads_grp = df_ads2.groupby("fecha_ini")["inversion"].sum().reset_index()
    df = _merge_ads(df, ads_grp, "fecha_ini")
    return df.sort_values("fecha_ini").reset_index(drop=True)


# ── Caché compartido entre páginas ────────────────────────────────

import streamlit as _st
import json as _json
import urllib.request as _urllib_req

# ── Monday CS config (mismo board que 7_CS.py) ────────────────────
_MONDAY_TOKEN_CS = (
    "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjY2Nzg4MzU5OSwiYWFpIjoxMSwidWlkIjo3N"
    "DQ5MjMwMiwiaWFkIjoiMjAyNi0wNi0wN1QxNzozMTowMi4wMDBaIiwicGVyIjoibWU6"
    "d3JpdGUiLCJhY3RpZCI6MjQxNjExNjcsInJnbiI6InVzZTEifQ.L41MQVmopJ880Q2m"
    "uX6S6erxUv23uOSvppD9fmsoaMQ"
)
_BOARD_ID_CS    = "6967792411"
_GROUP_ACTIVOS_CS = "grupo_nuevo28466"

def _monday_request_cs(query: str) -> dict:
    payload = _json.dumps({"query": query}).encode("utf-8")
    req = _urllib_req.Request(
        "https://api.monday.com/v2",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": _MONDAY_TOKEN_CS,
            "API-Version":   "2024-01",
        },
    )
    with _urllib_req.urlopen(req, timeout=30) as resp:
        return _json.loads(resp.read().decode("utf-8"))

@_st.cache_resource(show_spinner="Cargando datos del CRM...")
def cargar_meses_compartido():
    """df mensual (leads + ads) cacheado entre todas las páginas."""
    import datos as _datos
    df_crm = cargar_crm()
    df_ads = _datos.cargar_ads()
    return calcular_meses_crm(df_crm, df_ads)


@_st.cache_data(ttl=3600, show_spinner=False)
def cargar_finanzas() -> dict:
    """
    Lee la pestaña de finanzas del excel T90 y devuelve
    {(year, month): {kpi: valor}} con valores numéricos limpios.
    """
    import pandas as _pd, math as _math
    _ID  = "15BJQ-28m5KvAcQeE0Mp76UnIyUVjMK1O"
    _GID = "471732478"
    url  = f"https://docs.google.com/spreadsheets/d/{_ID}/gviz/tq?tqx=out:csv&gid={_GID}"
    df   = _pd.read_csv(url, header=None, on_bad_lines="skip")

    # Fila 0 = años; construir mapping col_idx -> (year, month)
    years_row = df.iloc[0]
    col_to_ym = {}
    yr_count  = {}
    for ci in range(2, len(years_row)):
        raw = str(years_row.iloc[ci]).strip()
        if raw in ("", "nan", "NaN"):
            break
        try:
            y = int(float(raw))
        except ValueError:
            break
        yr_count.setdefault(y, 0)
        yr_count[y] += 1
        col_to_ym[ci] = (y, yr_count[y])

    _KPI_MAP = {
        "Factu real + puente": "Facturación",
        "Profit":              "Profit",
        "Profit (%)":          "Profit (%)",
        "Crecimiento USD":     "Crecimiento USD",
        "Tkt promedio":        "Tkt promedio",
        "Usuarios totales":    "Usuarios totales",
        "ARG":                 "Arg",
        "EXT":                 "Ext",
    }

    def _parse(raw):
        s = str(raw).strip()
        if s in ("", "nan", "NaN"):
            return None
        s = s.replace("$", "").replace("%", "").strip()
        # Formato argentino: puntos = miles, coma = decimal
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(".", "")
        try:
            v = float(s)
            return None if _math.isnan(v) else v
        except ValueError:
            return None

    datos = {}
    for ri in range(2, len(df)):
        kpi_raw = str(df.iloc[ri, 1]).strip()
        kpi = _KPI_MAP.get(kpi_raw)
        if kpi is None:
            continue
        for ci, (y, m) in col_to_ym.items():
            v = _parse(df.iloc[ri, ci])
            if v is None:
                continue
            datos.setdefault((y, m), {})[kpi] = v

    return datos


@_st.cache_data(ttl=3600, show_spinner=False)
def cargar_presupuestos_enviados() -> dict:
    """Presupuestos por mes de envío desde bbdd_presupuestos (FECHA DE ENVIO)."""
    import pandas as _pd
    _ID = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"
    url = f"https://docs.google.com/spreadsheets/d/{_ID}/gviz/tq?tqx=out:csv&sheet=bbdd_presupuestos"
    df = _pd.read_csv(url, dtype=str)
    df.columns = df.columns.str.strip()
    df["_fecha"] = _pd.to_datetime(df.get("FECHA DE ENVIO", ""), dayfirst=True, errors="coerce")
    df = df.dropna(subset=["_fecha"])
    counts = df["_fecha"].dt.to_period("M").value_counts()
    return {(int(p.year), int(p.month)): int(c) for p, c in counts.items()}


@_st.cache_data(ttl=3600, show_spinner=False)
def cargar_ventas_cierre() -> dict:
    """Ventas por mes de cierre desde BBDD_Ventas (columna Fecha)."""
    import pandas as _pd
    _ID = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"
    url = f"https://docs.google.com/spreadsheets/d/{_ID}/gviz/tq?tqx=out:csv&sheet=BBDD_Ventas"
    df = _pd.read_csv(url, dtype=str)
    df.columns = df.columns.str.strip()
    df["_fecha"] = _pd.to_datetime(df.get("Fecha", ""), dayfirst=True, errors="coerce")
    df = df.dropna(subset=["_fecha"])
    counts = df["_fecha"].dt.to_period("M").value_counts()
    return {(int(p.year), int(p.month)): int(c) for p, c in counts.items()}


def _lunes_de(fecha: "pd.Timestamp") -> "pd.Timestamp":
    return fecha - pd.Timedelta(days=fecha.weekday())


def _get_4_semanas() -> "list[pd.Timestamp]":
    ayer = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    lunes = _lunes_de(ayer)
    return [lunes - pd.Timedelta(weeks=i) for i in range(3, -1, -1)]


@_st.cache_data(ttl=3600, show_spinner=False)
def cargar_semanas_recientes():
    """df CRM agregado por semana para las últimas 4 semanas (hasta ayer)."""
    import datos as _datos
    semanas = _get_4_semanas()
    ayer    = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    f_ini   = semanas[0]

    df_crm = cargar_crm().dropna(subset=["fecha_lead"]).copy()
    df_crm = df_crm[(df_crm["fecha_lead"] >= f_ini) & (df_crm["fecha_lead"] <= ayer)]
    df_crm["semana_inicio"] = df_crm["fecha_lead"].apply(_lunes_de)

    df_agg = _agregar_crm(df_crm.groupby("semana_inicio"))
    df_agg.rename(columns={"_key": "semana_inicio"}, inplace=True)
    df_agg["semana_inicio"] = pd.to_datetime(df_agg["semana_inicio"])

    df_ads = _datos.cargar_ads()
    df_ads = df_ads[(df_ads["fecha"] >= f_ini) & (df_ads["fecha"] <= ayer)].copy()
    df_ads["semana_inicio"] = df_ads["fecha"].apply(_lunes_de)
    ads_grp = df_ads.groupby("semana_inicio")["inversion"].sum().reset_index()
    df_agg  = _merge_ads(df_agg, ads_grp, "semana_inicio")
    return df_agg.sort_values("semana_inicio").reset_index(drop=True)


@_st.cache_data(ttl=3600, show_spinner=False)
def cargar_ventas_semanas() -> dict:
    """Ventas por semana (Monday key) de las últimas 4 semanas."""
    semanas = _get_4_semanas()
    ayer    = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    _ID = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"
    url = f"https://docs.google.com/spreadsheets/d/{_ID}/gviz/tq?tqx=out:csv&sheet=BBDD_Ventas"
    df = pd.read_csv(url, dtype=str)
    df.columns = df.columns.str.strip()
    df["_fecha"] = pd.to_datetime(df.get("Fecha", ""), dayfirst=True, errors="coerce")
    df = df.dropna(subset=["_fecha"])
    df = df[(df["_fecha"] >= semanas[0]) & (df["_fecha"] <= ayer)]
    df["_lunes"] = df["_fecha"].apply(_lunes_de)
    counts = df.groupby("_lunes").size()
    return {ts.normalize(): int(c) for ts, c in counts.items()}


@_st.cache_data(ttl=3600, show_spinner=False)
def cargar_presupuestos_semanas() -> dict:
    """Presupuestos por semana (Monday key) de las últimas 4 semanas."""
    semanas = _get_4_semanas()
    ayer    = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    _ID = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"
    url = f"https://docs.google.com/spreadsheets/d/{_ID}/gviz/tq?tqx=out:csv&sheet=bbdd_presupuestos"
    df = pd.read_csv(url, dtype=str)
    df.columns = df.columns.str.strip()
    df["_fecha"] = pd.to_datetime(df.get("FECHA DE ENVIO", ""), dayfirst=True, errors="coerce")
    df = df.dropna(subset=["_fecha"])
    df = df[(df["_fecha"] >= semanas[0]) & (df["_fecha"] <= ayer)]
    df["_lunes"] = df["_fecha"].apply(_lunes_de)
    counts = df.groupby("_lunes").size()
    return {ts.normalize(): int(c) for ts, c in counts.items()}


_BOARD_OB          = "18390960078"
_GROUP_OB          = "topics"
_COL_INICIO        = "date_mkyq9yq5"
_COL_ETAPA         = "color_mkzdxkxs"
_COL_ESTRAT        = "personas_mkm2txzr"
_COL_RIESGO        = "color_mkyxb835"
_COL_MOTIVO_RIESGO = "color_mm168av2"
_COL_NOTAS         = "long_text_mm1ye19k"
_COL_RUBRO         = "reflejo6"
_COL_SUBRUBRO      = "text_mm16rqy6"
_COL_COM_LLAMADO   = "long_text_mm25mjnq"
_COL_CARGA_AUTO    = "carga_autom_tica"
_COL_WAPBOT        = "color_mm0q5wwf"
_COL_BOT           = "date_mm1chftg"
_COL_COM_BOT       = "long_text_mm25afqz"
_COL_BBDD          = "bbdd"
_COL_OB1           = "estado_mkkfw7ch"
_COL_DISENO        = "color_mkyaf45s"
_COL_COM_GRAFICO   = "long_text_mm253sey"
_COL_ESTADOS       = "dup__of_cambia_estados__1"
_COL_OB2           = "color_mks7k4q0"
_COL_OB2_SEC       = "color_mkyavnp7"
_COL_AUTOMATIONS   = "estado"
_COL_OB3           = "color_mm1gen1n"
_COL_CAP_VEND      = "estado_mkkfmnt6"
_COL_OB4           = "estado_mkkf9qbv"
_COL_OB5           = "color_mkyxnbyd"
_COL_M1            = "color_mkyxjwt1"
_COL_VENDEDORES    = "estado__1"
_COL_B2B           = "dup__of_rubro"
_COL_TIPO_CLI      = "dup__of_b2b___b2c"
_COL_LINK_DRIVE    = "enlace__1"
_COL_LINK_CRM      = "dup__of_mes_mkn1krsj"
_COL_PAIN          = "dup__of_contras__1"
_COL_COM_FINALES   = "long_text_mkyxrph7"
_COL_FIN           = "date_mkyq6fgr"


@_st.cache_data(ttl=86400, show_spinner=False)
def cargar_ob_t90() -> dict:
    """
    Foto actual de Clientes en OB (group 'topics' del board Implementación Level 10).
    Días en OB = desde 'Inicio de implementación' hasta ayer.
    Devuelve {"Clientes en OB": n, "OB en SLA (≤30d)": n1, "OB fuera de SLA (>30d)": n2}
    """
    fragment = f'id column_values(ids: ["{_COL_INICIO}"]) {{ id text }}'
    q = (
        f'{{ boards(ids: [{_BOARD_OB}]) {{'
        f'  groups(ids: ["{_GROUP_OB}"]) {{'
        f'    items_page(limit: 500) {{ cursor items {{ {fragment} }} }}'
        f'  }}'
        f'}}}}'
    )
    r      = _monday_request_cs(q)
    page   = r["data"]["boards"][0]["groups"][0]["items_page"]
    items  = list(page["items"])
    cursor = page.get("cursor")
    while cursor:
        q2 = f'{{ next_items_page(limit: 500, cursor: "{cursor}") {{ cursor items {{ {fragment} }} }} }}'
        r2     = _monday_request_cs(q2)
        page   = r2["data"]["next_items_page"]
        items.extend(page["items"])
        cursor = page.get("cursor")

    ayer        = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    total = en_sla = fuera_sla = 0
    for item in items:
        cv      = {c["id"]: c["text"] for c in item["column_values"]}
        inicio  = cv.get(_COL_INICIO, "")
        total  += 1
        if inicio:
            try:
                dias = (ayer - pd.Timestamp(inicio)).days
                if dias <= 30:
                    en_sla   += 1
                else:
                    fuera_sla += 1
            except Exception:
                pass

    return {
        "Clientes en OB":         total,
        "OB en SLA (≤30d)":       en_sla,
        "OB fuera de SLA (>30d)": fuera_sla,
    }


@_st.cache_data(ttl=86400, show_spinner=False)
def cargar_ob_detalle() -> "pd.DataFrame":
    """
    Devuelve un DataFrame con una fila por cliente en OB.
    Columnas: nombre, estratega, etapa, dias, sla
    """
    cols_ids = [
        _COL_INICIO, _COL_FIN, _COL_ETAPA, _COL_ESTRAT, _COL_RIESGO,
        _COL_MOTIVO_RIESGO, _COL_NOTAS, _COL_RUBRO, _COL_SUBRUBRO,
        _COL_COM_LLAMADO, _COL_CARGA_AUTO, _COL_WAPBOT, _COL_BOT, _COL_COM_BOT,
        _COL_BBDD, _COL_OB1, _COL_DISENO, _COL_COM_GRAFICO, _COL_ESTADOS,
        _COL_OB2, _COL_OB2_SEC, _COL_AUTOMATIONS, _COL_OB3, _COL_CAP_VEND,
        _COL_OB4, _COL_OB5, _COL_M1,
        _COL_VENDEDORES, _COL_B2B, _COL_TIPO_CLI, _COL_LINK_DRIVE,
        _COL_LINK_CRM, _COL_PAIN, _COL_COM_FINALES,
    ]
    fragment = f'name column_values(ids: {_json.dumps(cols_ids)}) {{ id text }}'
    q = (
        f'{{ boards(ids: [{_BOARD_OB}]) {{'
        f'  groups(ids: ["{_GROUP_OB}"]) {{'
        f'    items_page(limit: 500) {{ cursor items {{ {fragment} }} }}'
        f'  }}'
        f'}}}}'
    )
    r      = _monday_request_cs(q)
    page   = r["data"]["boards"][0]["groups"][0]["items_page"]
    items  = list(page["items"])
    cursor = page.get("cursor")
    while cursor:
        q2 = f'{{ next_items_page(limit: 500, cursor: "{cursor}") {{ cursor items {{ {fragment} }} }} }}'
        r2 = _monday_request_cs(q2)
        page = r2["data"]["next_items_page"]
        items.extend(page["items"])
        cursor = page.get("cursor")

    ayer = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    filas = []
    for item in items:
        cv       = {c["id"]: c["text"] for c in item["column_values"]}
        inicio   = cv.get(_COL_INICIO, "")
        etapa     = cv.get(_COL_ETAPA,  "") or "Sin etapa"
        estratega = cv.get(_COL_ESTRAT, "") or "Sin estratega"
        riesgo    = cv.get(_COL_RIESGO, "") or "—"
        dias = None
        if inicio:
            try:
                dias = (ayer - pd.Timestamp(inicio)).days
            except Exception:
                pass
        sla = None
        if dias is not None:
            sla = "≤30d" if dias <= 30 else ">30d"
        def _cv(col): return cv.get(col, "") or ""
        filas.append({
            "nombre":        item.get("name", ""),
            "estratega":     estratega,
            "etapa":         etapa,
            "inicio":        inicio or "—",
            "fin_impl":      cv.get(_COL_FIN, "") or "",
            "dias":          dias if dias is not None else "—",
            "sla":           sla or "Sin fecha",
            "riesgo":        riesgo,
            "motivo_riesgo": _cv(_COL_MOTIVO_RIESGO),
            "notas":         _cv(_COL_NOTAS),
            "rubro":         _cv(_COL_RUBRO),
            "subrubro":      _cv(_COL_SUBRUBRO),
            "com_llamado":   _cv(_COL_COM_LLAMADO),
            "carga_auto":    _cv(_COL_CARGA_AUTO),
            "wapbot":        _cv(_COL_WAPBOT),
            "bot":           _cv(_COL_BOT),
            "com_bot":       _cv(_COL_COM_BOT),
            "bbdd":          _cv(_COL_BBDD),
            "ob1":           _cv(_COL_OB1),
            "diseno":        _cv(_COL_DISENO),
            "com_grafico":   _cv(_COL_COM_GRAFICO),
            "estados":       _cv(_COL_ESTADOS),
            "ob2":           _cv(_COL_OB2),
            "ob2_sec":       _cv(_COL_OB2_SEC),
            "automations":   _cv(_COL_AUTOMATIONS),
            "ob3":           _cv(_COL_OB3),
            "cap_vend":      _cv(_COL_CAP_VEND),
            "ob4":           _cv(_COL_OB4),
            "ob5":           _cv(_COL_OB5),
            "m1":            _cv(_COL_M1),
            "vendedores":    _cv(_COL_VENDEDORES),
            "b2b":           _cv(_COL_B2B),
            "tipo_cli":      _cv(_COL_TIPO_CLI),
            "link_drive":    _cv(_COL_LINK_DRIVE),
            "link_crm":      _cv(_COL_LINK_CRM),
            "pain":          _cv(_COL_PAIN),
            "com_finales":   _cv(_COL_COM_FINALES),
        })
    return pd.DataFrame(filas)


import json as _json_mod
import os as _os
import pathlib as _pathlib

_SNAPSHOTS_PATH = _pathlib.Path(__file__).parent / "data" / "snapshots.json"
_OB_SNAP_KEYS   = ("Clientes en OB", "OB en SLA (≤30d)", "OB fuera de SLA (>30d)")


def _load_snapshots() -> dict:
    if _SNAPSHOTS_PATH.exists():
        with open(_SNAPSHOTS_PATH, "r", encoding="utf-8") as f:
            return _json_mod.load(f)
    return {"weekly": {}, "monthly": {}}


def _save_snapshots(data: dict) -> None:
    _SNAPSHOTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SNAPSHOTS_PATH, "w", encoding="utf-8") as f:
        _json_mod.dump(data, f, ensure_ascii=False, indent=2)


def actualizar_snapshots_ob() -> dict:
    """
    Revisa si corresponde guardar una foto nueva (semanal o mensual) y lo hace.
    Devuelve el dict de snapshots completo {"weekly": {...}, "monthly": {...}}.
    """
    import datetime as _dt
    hoy    = _dt.date.today()
    snaps  = _load_snapshots()
    dirty  = False

    # Foto semanal: cada lunes
    if hoy.weekday() == 0:
        lunes_key = hoy.strftime("%Y-%m-%d")
        if lunes_key not in snaps["weekly"]:
            ob = cargar_ob_t90()
            snaps["weekly"][lunes_key] = {k: ob[k] for k in _OB_SNAP_KEYS}
            dirty = True

    # Foto mensual: primer día del mes → cierra el mes anterior
    if hoy.day == 1:
        mes_anterior = (hoy.replace(day=1) - _dt.timedelta(days=1))
        mes_key = mes_anterior.strftime("%Y-%m")
        if mes_key not in snaps["monthly"]:
            ob = cargar_ob_t90()
            snaps["monthly"][mes_key] = {k: ob[k] for k in _OB_SNAP_KEYS}
            dirty = True

    if dirty:
        _save_snapshots(snaps)

    return snaps


@_st.cache_data(ttl=86400, show_spinner=False)
def cargar_monday_cs_t90() -> "pd.DataFrame":
    """Carga todos los clientes del board Monday CS para T90."""
    cols = ["id8__1", "fecha5", "fecha1", "status0"]
    cols_gql = ", ".join(f'"{c}"' for c in cols)
    fragment = f"""
      id name group {{ id title }}
      column_values(ids: [{cols_gql}]) {{ id text }}
    """
    q = f'{{ boards(ids: [{_BOARD_ID_CS}]) {{ items_page(limit: 500) {{ cursor items {{ {fragment} }} }} }} }}'
    r = _monday_request_cs(q)
    page  = r["data"]["boards"][0]["items_page"]
    items = list(page["items"])
    cursor = page.get("cursor")
    while cursor:
        q2 = f'{{ next_items_page(limit: 500, cursor: "{cursor}") {{ cursor items {{ {fragment} }} }} }}'
        r2 = _monday_request_cs(q2)
        page = r2["data"]["next_items_page"]
        items.extend(page["items"])
        cursor = page.get("cursor")

    rows = []
    for item in items:
        cv = {c["id"]: (c["text"] or "") for c in item["column_values"]}
        rows.append({
            "grupo_id":       item["group"]["id"],
            "grupo_titulo":   item["group"]["title"],
            "id_crm":         cv.get("id8__1", "").strip(),
            "_fecha_ingreso": cv.get("fecha5", ""),
            "_fecha_baja":    cv.get("fecha1", ""),
        })
    df = pd.DataFrame(rows)
    df["_fecha_ingreso"] = pd.to_datetime(df["_fecha_ingreso"], errors="coerce")
    df["_fecha_baja"]    = pd.to_datetime(df["_fecha_baja"],    errors="coerce")
    return df


@_st.cache_data(ttl=86400, show_spinner=False)
def cargar_bajas_t90() -> dict:
    """
    Bajas por mes de baja → {(y,m): {"Bajas totales": n, "Bajas 2026": n, "Bajas pre 2026": n}}
    """
    import re as _re

    _MESES_ES = {
        "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
        "julio":7,"agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12,
    }

    def _inferir_fecha_grupo(titulo: str) -> "pd.Timestamp":
        t = titulo.lower().strip()
        for mes, num in _MESES_ES.items():
            if mes in t:
                m = _re.search(r"20\d{2}", t)
                yr = int(m.group()) if m else pd.Timestamp.today().year
                return pd.Timestamp(year=yr, month=num, day=1)
        return pd.NaT

    def _norm_id(v) -> str:
        s = str(v).strip()
        if s.endswith(".0") and s[:-2].lstrip("-").isdigit():
            s = s[:-2]
        return s if s not in ("nan", "None", "") else ""

    # IDs con fecha_venta 2026 según BBDD_Ventas (columna "ID prospecto")
    _ID_BBDD = "1pCQtjCZZOrhP21K-EyFECtoNeNNosZfOEgDp9YUZE6M"
    _url_vtas = f"https://docs.google.com/spreadsheets/d/{_ID_BBDD}/gviz/tq?tqx=out:csv&sheet=BBDD_Ventas"
    df_vtas = pd.read_csv(_url_vtas, dtype=str)
    df_vtas.columns = df_vtas.columns.str.strip()
    df_vtas["_fv"] = pd.to_datetime(df_vtas.get("Fecha", ""), dayfirst=True, errors="coerce")
    df_vtas["_id"] = df_vtas.get("ID prospecto", pd.Series(dtype=str)).apply(_norm_id)
    ids_2026 = set(
        df_vtas.loc[(df_vtas["_fv"].dt.year == 2026) & (df_vtas["_id"] != ""), "_id"].unique()
    )

    df = cargar_monday_cs_t90()
    df_b = df[df["grupo_id"] != _GROUP_ACTIVOS_CS].copy()

    mask = df_b["_fecha_baja"].isna()
    df_b.loc[mask, "_fecha_baja"] = df_b.loc[mask, "grupo_titulo"].apply(_inferir_fecha_grupo)

    df_b = df_b.dropna(subset=["_fecha_baja"]).copy()
    df_b["_y"] = df_b["_fecha_baja"].dt.year
    df_b["_m"] = df_b["_fecha_baja"].dt.month

    df_b["_id_norm"] = df_b["id_crm"].apply(_norm_id)

    result: dict = {}
    for (y, m), grp in df_b.groupby(["_y", "_m"]):
        total = len(grp)
        b2026 = int(grp["_id_norm"].isin(ids_2026).sum())
        result[(int(y), int(m))] = {
            "Bajas totales":  total,
            "Bajas 2026":     b2026,
            "Bajas pre 2026": total - b2026,
        }
    return result


_BOARD_ID_BAJAS  = "9195110137"
_COL_ID_BAJAS    = "id8__1"
_COL_A2_BAJAS    = "abono_usd"   # ARS mensual
_COL_TC_BAJAS    = "n_meros7"    # Tipo de cambio
_COL_BONIF_BAJAS = "n_meros0"    # % de descuento

@_st.cache_data(ttl=86400, show_spinner=False)
def cargar_recurrente_bajas() -> dict:
    """Retorna {id_crm: recurrente_usd} calculado como (A2/TC)*(1-bonif/100)."""
    _cols = [_COL_ID_BAJAS, _COL_A2_BAJAS, _COL_TC_BAJAS, _COL_BONIF_BAJAS]
    _cols_gql = ", ".join(f'"{c}"' for c in _cols)
    fragment = f'id name column_values(ids: [{_cols_gql}]) {{ id text }}'
    q = f'{{ boards(ids: [{_BOARD_ID_BAJAS}]) {{ items_page(limit: 500) {{ cursor items {{ {fragment} }} }} }} }}'
    r = _monday_request_cs(q)
    page  = r["data"]["boards"][0]["items_page"]
    items = list(page["items"])
    cursor = page.get("cursor")
    while cursor:
        q2 = f'{{ next_items_page(limit: 500, cursor: "{cursor}") {{ cursor items {{ {fragment} }} }} }}'
        r2 = _monday_request_cs(q2)
        np = r2["data"]["next_items_page"]
        items += np["items"]
        cursor = np.get("cursor")

    def _num(s):
        try:
            return float((s or "").replace(",", ".").replace("$", "").strip())
        except Exception:
            return None

    result = {}
    for item in items:
        cv = {v["id"]: v["text"] for v in item["column_values"]}
        raw_id = cv.get(_COL_ID_BAJAS, "") or ""
        if not raw_id:
            continue
        try:
            _id = str(int(float(raw_id.replace(",", "."))))
        except Exception:
            _id = raw_id.strip()
        a2    = _num(cv.get(_COL_A2_BAJAS))
        tc    = _num(cv.get(_COL_TC_BAJAS))
        bonif = _num(cv.get(_COL_BONIF_BAJAS)) or 0.0
        if a2 and tc and tc != 0:
            result[_id] = round((a2 / tc) * (1 - bonif / 100), 2)
    return result


_BOARD_ID_PED_BAJA  = "7038826698"
_PBAJ_COLS = [
    "lookup_mm4sedxb",       # ID
    "dup__of_tel_fono__1",   # Mes
    "conectar_tableros__1",  # Clientes y ex-clientes
    "reflejo__1",            # Motivo de baja
    "fecha_de_pedido__1",    # Fecha de pedido
    "color3__1",             # Situación del cliente
    "motivo__1",             # Motivo y actualizaciones
    "text1__1",              # Comentarios (Flori)
    "numeric_mm4fg4hx",      # Monto Recurrente
]

@_st.cache_data(ttl=3600, show_spinner=False)
def cargar_pedidos_baja() -> "pd.DataFrame":
    """Retorna DataFrame con pedidos de baja desde Monday board 7038826698."""
    _cols_gql = ", ".join(f'"{c}"' for c in _PBAJ_COLS)
    _cv_fields = "id text ... on MirrorValue { display_value } ... on StatusValue { label }"
    fragment   = f'id name column_values(ids: [{_cols_gql}]) {{ {_cv_fields} }}'
    q  = f'{{ boards(ids: [{_BOARD_ID_PED_BAJA}]) {{ items_page(limit: 500) {{ cursor items {{ {fragment} }} }} }} }}'
    r  = _monday_request_cs(q)
    page   = r["data"]["boards"][0]["items_page"]
    items  = list(page["items"])
    cursor = page.get("cursor")
    while cursor:
        q2 = f'{{ next_items_page(limit: 500, cursor: "{cursor}") {{ cursor items {{ {fragment} }} }} }}'
        r2 = _monday_request_cs(q2)
        np = r2["data"]["next_items_page"]
        items += np["items"]
        cursor = np.get("cursor")

    def _cv_val(v):
        return v.get("display_value") or v.get("label") or v.get("text") or ""

    rows = []
    for item in items:
        cv = {v["id"]: _cv_val(v) for v in item["column_values"]}
        rows.append({
            "ID":                   cv.get("lookup_mm4sedxb", ""),
            "Clientes y ex-clientes": item["name"],
            "Motivo de baja":       cv.get("reflejo__1", ""),
            "Fecha de pedido":      cv.get("fecha_de_pedido__1", ""),
            "Situación del cliente": cv.get("color3__1", ""),
            "Motivo y actualizaciones": cv.get("motivo__1", ""),
            "Comentarios (Flori)":  cv.get("text1__1", ""),
            "Monto Recurrente":     cv.get("numeric_mm4fg4hx", ""),
        })
    return pd.DataFrame(rows)
