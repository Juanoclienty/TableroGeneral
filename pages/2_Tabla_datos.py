"""
2_Tabla_datos.py — Tabla de datos unificada de leads del CRM.
"""
import re
import urllib.parse
import urllib.request
import streamlit as st
import pandas as pd
from datetime import date
import datos_crm
import datos

_ID_SOL  = "1Oto16BeUmohfjWlzGeH-Nj0d3RMmZLG17ZSPd93ePA8"
_ID_FER  = "1EDbB-LMLeXFaCJeAifbV9zLNh9R4piO0GYuAeMBupo8"
_ID_SEBA = "17IGWY-VvK8pB_0cN2gSNHrzyTMhndhRS8cWtJDNbBEQ"
_ID_RO   = "1PsGJ4DBwjfOaSV7icHLUbSmP8kDQ6gGLjztUD4_HNvs"

def _fetch_ext(sheet_id, sheet_name):
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(sheet_name)}")
    with urllib.request.urlopen(url, timeout=30) as r:
        return pd.read_csv(r, header=0)

def _parse_fecha_traz(s):
    """Parsea fechas tipo '22/1', '25/03', '14/07/2026'."""
    s = str(s).strip()
    if not s or s in ("nan", ""):
        return pd.NaT
    parts = s.split("/")
    hoy = pd.Timestamp.today()
    if len(parts) == 2:
        for yr in [hoy.year, hoy.year - 1]:
            try:
                t = pd.to_datetime(f"{parts[0]}/{parts[1]}/{yr}", dayfirst=True)
                if t <= hoy + pd.Timedelta(days=60):
                    return t
            except Exception:
                pass
    return pd.to_datetime(s, dayfirst=True, errors="coerce")

def _col_by_name(df, *candidates):
    """Encuentra la primera columna cuyo nombre contenga alguno de los candidatos (case-insensitive)."""
    hdr = [str(c).strip().lower() for c in df.columns]
    for cand in candidates:
        for i, h in enumerate(hdr):
            if cand.lower() in h:
                return df.columns[i]
    return None

_ID_TRAZ_SHEET  = "1eGCO6821Dy7j591fShFAkezDHoaRUvTXgAWJt8eDZus"
_ID_NOTAS_SHEET = "1BHzXgiDqYcnz7_kVASPCc65KXz4v6oqSeVCJlN48_J8"

@st.cache_data(ttl=86400, show_spinner=False)
def _cargar_notas_crm():
    try:
        df = _fetch_ext(_ID_NOTAS_SHEET, "BBDD_Clienty_CRM")
        col_id    = _col_by_name(df, "id") or df.columns[0]
        col_notas = _col_by_name(df, "notas") or df.columns[22]
        out = pd.DataFrame({
            "ID":        df[col_id].astype(str).str.strip().str.replace(r'\.0$', '', regex=True),
            "Notas CRM": df[col_notas].astype(str).str.strip(),
        })
        out = out[out["ID"].notna() & ~out["ID"].isin(["", "nan", "ID"])]
        out = out.drop_duplicates(subset="ID", keep="last")
        out["Notas CRM"] = out["Notas CRM"].replace("nan", "")
        return out
    except Exception:
        return pd.DataFrame(columns=["ID", "Notas CRM"])

_AR1_COLS = [
    "Nivel de conciencia", "Dolor declarado", "Timing", "Resumen ejecutivo",
    "Perfil fit", "Gestiona prospectos", "Vendedores", "Herramienta que busca",
    "Script nota", "Justificación estado", "Es decisor", "Chances de venta",
    "Objeción principal", "Tipo objeción", "Observaciones generales",
]

@st.cache_data(ttl=86400, show_spinner=False)
def _cargar_auditoria_r1():
    try:
        df = _fetch_ext(_ID_TRAZ_SHEET, "Auditoría R1")
        hdr = [str(c).strip().lower() for c in df.columns]
        col_id = next((df.columns[i] for i, h in enumerate(hdr) if "id" in h and "prospecto" in h), None)
        if col_id is None:
            col_id = next((df.columns[i] for i, h in enumerate(hdr) if h == "id"), df.columns[0])
        # Mapear columnas por nombre (case-insensitive)
        col_map = {}
        for target in _AR1_COLS:
            match = next((df.columns[i] for i, h in enumerate(hdr) if target.lower() in h), None)
            if match:
                col_map[match] = target
        keep = [col_id] + list(col_map.keys())
        out = df[keep].copy()
        out = out.rename(columns={col_id: "ID", **col_map})
        out["ID"] = out["ID"].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        out = out[out["ID"].notna() & ~out["ID"].isin(["", "nan", "ID"])]
        out = out.drop_duplicates(subset="ID", keep="last")
        return out
    except Exception:
        return pd.DataFrame(columns=["ID"] + _AR1_COLS)

@st.cache_data(ttl=86400, show_spinner=False)
def _cargar_cc_traz():
    frames = []
    for sheet_id, nombre in [(_ID_SOL, "Sol"), (_ID_FER, "Fer")]:
        try:
            df = _fetch_ext(sheet_id, "BBDD_R1")
            col_id  = _col_by_name(df, "id prospecto", "id")
            col_fec = _col_by_name(df, "fecha r1", "fecha_r1")
            if col_id is None or col_fec is None:
                continue
            col_notas = _col_by_name(df, "explicación del estado", "explicacion del estado")
            tmp = pd.DataFrame({
                "ID":       df[col_id].astype(str).str.strip().str.replace(r'\.0$', '', regex=True),
                "CC":       nombre,
                "_fec":     df[col_fec].apply(_parse_fecha_traz),
                "Notas CC": df[col_notas].astype(str).str.strip() if col_notas is not None else "",
            })
            tmp = tmp[tmp["ID"].notna() & ~tmp["ID"].isin(["", "nan", "ID", "ID prospecto"])]
            frames.append(tmp)
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(columns=["ID", "CC", "Fecha R1 - Traz"])
    df_all = pd.concat(frames, ignore_index=True)
    df_all = (df_all.sort_values("_fec")
                    .groupby("ID", as_index=False)
                    .agg(CC=("CC", "last"), _fec=("_fec", "max"), **{"Notas CC": ("Notas CC", "last")}))
    df_all["Fecha R1 - Traz"] = df_all["_fec"].dt.strftime("%d/%m/%Y").where(df_all["_fec"].notna(), "")
    return df_all[["ID", "CC", "Fecha R1 - Traz", "Notas CC"]]

@st.cache_data(ttl=86400, show_spinner=False)
def _cargar_closer_traz():
    frames = []
    for sheet_id, nombre in [(_ID_SEBA, "Seba"), (_ID_RO, "Ro")]:
        try:
            df = _fetch_ext(sheet_id, "BBDD_FINAL")
            col_id  = _col_by_name(df, "id prospecto", "id")
            col_fec = _col_by_name(df, "fecha r2", "fecha_r2")
            if col_id is None or col_fec is None:
                continue
            tmp = pd.DataFrame({
                "ID":     df[col_id].astype(str).str.strip().str.replace(r'\.0$', '', regex=True),
                "Closer": nombre,
                "_fec":   df[col_fec].apply(_parse_fecha_traz),
            })
            tmp = tmp[tmp["ID"].notna() & ~tmp["ID"].isin(["", "nan", "ID", "ID prospecto"])]
            frames.append(tmp)
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(columns=["ID", "Closer", "Fecha R2 - Traz"])
    df_all = pd.concat(frames, ignore_index=True)
    df_all = (df_all.sort_values("_fec")
                    .groupby("ID", as_index=False)
                    .agg(Closer=("Closer", "last"), _fec=("_fec", "max")))
    df_all["Fecha R2 - Traz"] = df_all["_fec"].dt.strftime("%d/%m/%Y").where(df_all["_fec"].notna(), "")
    return df_all[["ID", "Closer", "Fecha R2 - Traz"]]

st.set_page_config(
    page_title="Tabla de datos",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("## 🗂️ Tabla de datos")

@st.cache_data(ttl=3600, show_spinner="Cargando datos...")
def _cargar():
    return datos_crm.cargar_crm()

df_raw = _cargar()

# ── Filtrar 2026 ──────────────────────────────────────────────
df = df_raw[df_raw["fecha_lead"].dt.year == 2026].copy()

# ── Join con CC, Closer y Auditoría R1 desde Trazabilidad ────
_df_cc     = _cargar_cc_traz()
_df_closer = _cargar_closer_traz()
_df_ar1    = _cargar_auditoria_r1()
_df_notas  = _cargar_notas_crm()

df["id"] = df["id"].astype(str).str.strip()
df = df.merge(_df_cc,     left_on="id", right_on="ID", how="left").drop(columns=["ID"], errors="ignore")
df = df.merge(_df_closer, left_on="id", right_on="ID", how="left").drop(columns=["ID"], errors="ignore")
df = df.merge(_df_ar1, left_on="id", right_on="ID", how="left").drop(columns=["ID"], errors="ignore")
for _c in _AR1_COLS:
    if _c in df.columns:
        df[_c] = df[_c].fillna("")

df["CC"]              = df["CC"].fillna("")
df["Notas CC"]        = df["Notas CC"].fillna("") if "Notas CC" in df.columns else ""
df = df.merge(_df_notas, left_on="id", right_on="ID", how="left").drop(columns=["ID"], errors="ignore")
df["Notas CRM"]       = df["Notas CRM"].fillna("") if "Notas CRM" in df.columns else ""
df["Closer"]          = df["Closer"].fillna("")
df["Fecha R1 - Traz"] = df["Fecha R1 - Traz"].fillna("")
df["Fecha R2 - Traz"] = df["Fecha R2 - Traz"].fillna("")

# ── Parsear fechas de reunión desde texto libre ───────────────
_MESES = {
    "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
    "julio":7,"agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12,
}
def _parse_fecha_reunion(txt):
    if not txt or str(txt).strip() == "":
        return ""
    t = str(txt).strip()
    # ISO datetime: "2026-06-09 15:10:00"
    try:
        ts = pd.to_datetime(t)
        if pd.notna(ts):
            return ts.strftime("%d/%m/%Y")
    except Exception:
        pass
    # Texto en español: "miercoles 10 de junio 17:30" / "09 junio 2026 15:10"
    tl = t.lower()
    m = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})?", tl)
    if not m:
        m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", tl)
    if m:
        dia = int(m.group(1))
        mes = _MESES.get(m.group(2), 0)
        anio = int(m.group(3)) if m.group(3) else date.today().year
        if mes:
            return f"{dia:02d}/{mes:02d}/{anio}"
    return ""

_col_r1_crm = next((c for c in df.columns if "1ra" in c.lower() or "primera" in c.lower() or ("fecha" in c.lower() and "reuni" in c.lower())), None)
_col_r2_crm = next((c for c in df.columns if "hora" in c.lower() and "reuni" in c.lower()), None)
df["Fecha R1 - CRM"] = df[_col_r1_crm].apply(_parse_fecha_reunion) if _col_r1_crm else ""
df["Fecha R2 - CRM"] = df[_col_r2_crm].apply(_parse_fecha_reunion) if _col_r2_crm else ""

# ── Join con ads: Tipo de contenido y Temática ───────────────
def _xnum(s):
    m = re.search(r"\d+", str(s))
    return m.group(0) if m else ""

try:
    _ads_raw = datos.cargar_ads() if hasattr(datos, "cargar_ads") else pd.DataFrame()
    _df_ads = _ads_raw if isinstance(_ads_raw, pd.DataFrame) else pd.DataFrame()
    if not _df_ads.empty and "nombre_ad" in _df_ads.columns:
        _df_ads_u = (
            _df_ads[["nombre_ad", "tipo", "tematica"]]
            .copy()
            .assign(_num=lambda x: x["nombre_ad"].apply(_xnum))
            .drop_duplicates(subset="_num", keep="last")
            [["_num", "tipo", "tematica"]]
        )
        df["_num"] = df["utm_content"].apply(_xnum)
        df = df.merge(_df_ads_u, on="_num", how="left")
        df.drop(columns=["_num"], inplace=True)
    else:
        df["tipo"] = ""
        df["tematica"] = ""
except Exception:
    df["tipo"] = ""
    df["tematica"] = ""

# ── Chance de venta desde Etiquetas ──────────────────────────
def _chance(et):
    s = str(et).lower() if pd.notna(et) else ""
    if "chance de venta media-alta" in s: return "Media-Alta"
    if "chance de venta alta"       in s: return "Alta"
    if "chance de venta media"      in s: return "Media"
    if "chance de venta baja"       in s: return "Baja"
    return ""

df["Chance de venta"] = df["Etiquetas"].apply(_chance)

def _podcast(et):
    s = str(et).lower() if pd.notna(et) else ""
    if "podcast escuchado" in s and "no escuchado" not in s: return "Si"
    if "podcast no escuchado" in s: return "No"
    return ""

def _mistery(et):
    s = str(et).lower() if pd.notna(et) else ""
    return "Si" if "mistery shopper" in s else ""

df["Podcast"]         = df["Etiquetas"].apply(_podcast)
df["Mistery Shopper"] = df["Etiquetas"].apply(_mistery)

# ── Mapeo calidad → Form ──────────────────────────────────────
_FORM_MAP = {"R1F": "GF", "R1BF": "BF", "R1PBF": "PF"}
df["Form"] = df["calidad"].map(_FORM_MAP).fillna("s/d")

# ── Mapeo estado_resumen → etapa legible ─────────────────────
_ETAPA_MAP = {
    "0. Lead":         "Lead",
    "1. R1":           "R1",
    "2. Follow":       "Follow podcast",
    "3. R2":           "R2",
    "4. Presupuesto":  "Presupuesto",
    "5. Venta":        "Venta",
    "6. Otros":        "Otros",
}
df["Etapa embudo"] = df["estado_resumen"].map(_ETAPA_MAP).fillna("Otros")

# ── Seleccionar y renombrar columnas ──────────────────────────
cols_map = {
    "id":                   "ID",
    "fecha_lead":           "Fecha lead",
    "Form":                 "Form",
    "Estado":               "Estado CRM",
    "Etapa embudo":         "Etapa embudo",
    "Chance de venta":      "Chance de venta",
    "Podcast":              "Podcast",
    "Mistery Shopper":      "Mistery Shopper",
    "CC":                   "Call Confirmer",
    "Fecha R1 - Traz":      "Fecha R1 - Traz",
    "Notas CC":             "Notas CC",
    "Closer":               "Closer",
    "Fecha R2 - Traz":      "Fecha R2 - Traz",
    "Fecha R1 - CRM":       "Fecha R1 - CRM",
    "Fecha R2 - CRM":       "Fecha R2 - CRM",
    "utm_content":          "UTM Content",
    "tipo":                 "Tipo de contenido",
    "tematica":             "Temática",
    # Jotform
    "Rol":                  "Rol (JT)",
    "Cant vendedores":      "Cant. Vendedores (JT)",
    "Inversion ads":        "Inversión Ads (JT)",
    "Predisposicion":       "Predisposición (JT)",
    "Pilar":                "Pilar (JT)",
    "Quien decide":         "Quién toma decisión (JT)",
    "A quien le vende":     "A quién le vendés (JT)",
    "Proceso de venta":     "Proceso de venta (JT)",
    # Auditoría R1
    **{c: f"{c} (AR1)" for c in _AR1_COLS},
    # Calendly
    "Tipo cliente":         "Tipo de cliente (Cal)",
    "Ticket":               "Ticket (Cal)",
    "Equipo comercial":     "Equipo Comercial (Cal)",
    "Consultas":            "Consultas (Cal)",
    "Inversión Publicidad": "Inv. Publicidad (Cal)",
    # Notas CRM
    "Notas CRM":            "Notas CRM",
}

df_tabla = df[[c for c in cols_map if c in df.columns]].rename(columns=cols_map)
df_tabla = df_tabla.replace("Falta info", "")
df_tabla["Fecha lead"] = pd.to_datetime(df_tabla["Fecha lead"]).dt.strftime("%d/%m/%Y")
df_tabla["ID"] = df_tabla["ID"].astype(str)

# ── Sidebar: filtros ──────────────────────────────────────────
with st.sidebar:
    st.markdown("### Actualizar")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 API CRM", use_container_width=True, help="Fuerza recarga desde la API de Clienty"):
            datos_crm.limpiar_cache()
            st.cache_data.clear()
            st.rerun()
    with col_b:
        if st.button("📋 Sheets", use_container_width=True, help="Fuerza recarga de CC, Closer y Calendly"):
            _cargar_cc_traz.clear()
            _cargar_closer_traz.clear()
            _cargar_auditoria_r1.clear()
            _cargar_notas_crm.clear()
            st.rerun()



    st.markdown("### Filtros")

    _form_opts = ["Todos", "GF", "BF", "PF", "s/d"]
    filtro_form = st.multiselect("Form", ["GF", "BF", "PF", "s/d"], key="td_form")

    _etapas = sorted(df_tabla["Etapa embudo"].dropna().unique().tolist())
    filtro_etapa = st.multiselect("Etapa embudo", _etapas, key="td_etapa")

    filtro_texto = st.text_input("Buscar (ID, UTM, Estado...)", key="td_buscar")

# ── Aplicar filtros ───────────────────────────────────────────
df_f = df_tabla.copy()
if filtro_form:
    df_f = df_f[df_f["Form"].isin(filtro_form)]
if filtro_etapa:
    df_f = df_f[df_f["Etapa embudo"].isin(filtro_etapa)]
if filtro_texto:
    mask = df_f.apply(lambda row: row.astype(str).str.contains(filtro_texto, case=False, na=False).any(), axis=1)
    df_f = df_f[mask]

tab_tabla, tab_origen = st.tabs(["Tabla", "Origen"])

with tab_tabla:
 st.caption(f"{len(df_f):,} leads · 2026")

 _API     = "API Clienty"
 _CAL     = "Sheets · Calendly"
 _TRAZ    = "Sheets · Trazabilidad"
 _ADS     = "Sheets · Ads"
 _CALC    = "Campo calculado"

 st.dataframe(
    df_f.set_index("ID"),
    use_container_width=True,
    hide_index=False,
    column_config={
        "Fecha lead":               st.column_config.TextColumn(help=_API),
        "Form":                     st.column_config.TextColumn(help=_CALC),
        "Estado CRM":               st.column_config.TextColumn(help=_API),
        "Etapa embudo":             st.column_config.TextColumn(help=_CALC),
        "Chance de venta":          st.column_config.TextColumn(help=_API),
        "Podcast":                  st.column_config.TextColumn(help=_API),
        "Mistery Shopper":          st.column_config.TextColumn(help=_API),
        "Call Confirmer":           st.column_config.TextColumn(help=_TRAZ),
        "Fecha R1 - Traz":          st.column_config.TextColumn(help=_TRAZ),
        "Closer":                   st.column_config.TextColumn(help=_TRAZ),
        "Fecha R2 - Traz":          st.column_config.TextColumn(help=_TRAZ),
        "Fecha R1 - CRM":           st.column_config.TextColumn(help=_API),
        "Fecha R2 - CRM":           st.column_config.TextColumn(help=_API),
        "UTM Content":              st.column_config.TextColumn(help=_API),
        "Tipo de contenido":        st.column_config.TextColumn(help=_ADS),
        "Temática":                 st.column_config.TextColumn(help=_ADS),
        "Tipo de cliente (Cal)":    st.column_config.TextColumn(help=_CAL),
        "Ticket (Cal)":             st.column_config.TextColumn(help=_CAL),
        "Equipo Comercial (Cal)":   st.column_config.TextColumn(help=_CAL),
        "Consultas (Cal)":          st.column_config.TextColumn(help=_CAL),
        "Inv. Publicidad (Cal)":    st.column_config.TextColumn(help=_CAL),
        "Rol (JT)":                 st.column_config.TextColumn(help="Jotform"),
        "Cant. Vendedores (JT)":    st.column_config.TextColumn(help="Jotform"),
        "Inversión Ads (JT)":       st.column_config.TextColumn(help="Jotform"),
        "Predisposición (JT)":      st.column_config.TextColumn(help="Jotform"),
        "Pilar (JT)":               st.column_config.TextColumn(help="Jotform"),
        "Quién toma decisión (JT)": st.column_config.TextColumn(help="Jotform"),
        "A quién le vendés (JT)":   st.column_config.TextColumn(help="Jotform"),
        "Proceso de venta (JT)":    st.column_config.TextColumn(help="Jotform"),
    },
 )

with tab_origen:
    _URL = "https://docs.google.com/spreadsheets/d/{}/edit"
    def _a(label, url):
        return f'<a href="{url}" target="_blank">{label}</a>'

    _u_cal  = _URL.format("1jtP9lYjVRnxFkvd0kN4xV5B6AQPEeFxgtxIRh5v-cgs")
    _u_ads  = _URL.format("1DSXU0pluCzCJDFwKremw7crWb1W21S9HtWDOsDhVG8E")
    _u_sol  = _URL.format("1Oto16BeUmohfjWlzGeH-Nj0d3RMmZLG17ZSPd93ePA8")
    _u_fer  = _URL.format("1EDbB-LMLeXFaCJeAifbV9zLNh9R4piO0GYuAeMBupo8")
    _u_seba = _URL.format("17IGWY-VvK8pB_0cN2gSNHrzyTMhndhRS8cWtJDNbBEQ")
    _u_ro   = _URL.format("1PsGJ4DBwjfOaSV7icHLUbSmP8kDQ6gGLjztUD4_HNvs")

    _cc_links     = f"{_a('Sol', _u_sol)} / {_a('Fer', _u_fer)}"
    _closer_links = f"{_a('Seba', _u_seba)} / {_a('Ro', _u_ro)}"

    _rows = [
        ("ID",                      "API Clienty",        "Identificador único del lead en el CRM."),
        ("Fecha lead",              "API Clienty",        "Fecha en que ingresó el lead al CRM."),
        ("Form",                    "Campo calculado",    "Derivado de la calidad del lead: R1F → GF, R1BF → BF, R1PBF → PF, resto → s/d."),
        ("Estado CRM",              "API Clienty",        "Estado actual del lead en el CRM."),
        ("Etapa embudo",            "Campo calculado",    "Mapeado desde estado_resumen: Lead, R1, Follow podcast, R2, Presupuesto, Venta, Otros."),
        ("Chance de venta",         "API Clienty",        "Extraído de las etiquetas del lead: Alta, Media-Alta, Media, Baja."),
        ("Podcast",                 "API Clienty",        "Extraído de las etiquetas: 'podcast escuchado' → Sí / 'podcast no escuchado' → No."),
        ("Mistery Shopper",         "API Clienty",        "Extraído de las etiquetas: 'mistery shopper' → Sí."),
        ("Call Confirmer",          _cc_links,            "Se busca el ID del lead en BBDD_R1 de Sol y Fer. El que lo tenga es el CC asignado."),
        ("Fecha R1 - Traz",         _cc_links,            "Fecha R1 registrada por el CC en su BBDD. Si el lead aparece más de una vez, se toma la fecha máxima."),
        ("Notas CC",                _cc_links,            "Columna 'Explicación del estado' del sheet del CC (Sol/Fer). Corresponde a la fila con la fecha R1 más reciente."),
        ("Closer",                  _closer_links,        "Se busca el ID del lead en BBDD_FINAL de Seba y Ro. El que lo tenga es el Closer asignado."),
        ("Fecha R2 - Traz",         _closer_links,        "Fecha R2 registrada por el Closer en su BBDD. Si aparece más de una vez, se toma la fecha máxima."),
        ("Fecha R1 - CRM",          "API Clienty",        "Fecha extraída del campo 'Dato interno hora 1ra reunion efectiva'. Solo se guarda la fecha, sin hora."),
        ("Fecha R2 - CRM",          "API Clienty",        "Fecha extraída del campo 'Dato interno hora reunion'. Solo se guarda la fecha, sin hora."),
        ("UTM Content",             "API Clienty",        "Campo utm_content del lead. Permite identificar el ad que generó el lead."),
        ("Tipo de contenido",       _a("Sheet Ads", _u_ads),      "Tipo de contenido del ad (ej. Video, Imagen). Join por número de ad extraído del UTM Content."),
        ("Temática",                _a("Sheet Ads", _u_ads),      "Temática del ad. Join por número de ad extraído del UTM Content."),
        ("Tipo de cliente (Cal)",   _a("Sheet Calendly", _u_cal), "Tipo de cliente según la reunión de Calendly. Join por email."),
        ("Ticket (Cal)",            _a("Sheet Calendly", _u_cal), "Ticket declarado en la reunión de Calendly. Join por email."),
        ("Equipo Comercial (Cal)",  _a("Sheet Calendly", _u_cal), "Tamaño del equipo comercial declarado en Calendly. Join por email."),
        ("Consultas (Cal)",         _a("Sheet Calendly", _u_cal), "Cantidad de consultas declaradas en Calendly. Join por email."),
        ("Inv. Publicidad (Cal)",   _a("Sheet Calendly", _u_cal), "Inversión en publicidad declarada en Calendly. Join por email."),
        ("Nivel de conciencia (AR1)",    _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Dolor declarado (AR1)",       _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Timing (AR1)",                _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Resumen ejecutivo (AR1)",     _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Perfil fit (AR1)",            _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Gestiona prospectos (AR1)",   _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Vendedores (AR1)",            _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Herramienta que busca (AR1)", _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Script nota (AR1)",           _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Justificación estado (AR1)",  _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Es decisor (AR1)",            _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Chances de venta (AR1)",      _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Objeción principal (AR1)",    _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Tipo objeción (AR1)",         _a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Observaciones generales (AR1)",_a("Auditoría R1", f"https://docs.google.com/spreadsheets/d/{_ID_TRAZ_SHEET}/edit"), "Pestaña 'Auditoria R1'. Join por ID de prospecto."),
        ("Rol (JT)",                "API Clienty · Jotform", "Campo personalizado 'Rol' del formulario de Jotform, almacenado en customFields del lead."),
        ("Cant. Vendedores (JT)",   "API Clienty · Jotform", "Campo personalizado 'Cant. Vendedores' del formulario Jotform."),
        ("Inversión Ads (JT)",      "API Clienty · Jotform", "Campo personalizado 'Inversión Ads' del formulario Jotform."),
        ("Predisposición (JT)",     "API Clienty · Jotform", "Campo personalizado 'Predisposición' del formulario Jotform."),
        ("Pilar (JT)",              "API Clienty · Jotform", "Campo personalizado 'Pilar' del formulario Jotform."),
        ("Quién toma decisión (JT)","API Clienty · Jotform", "Campo personalizado 'Quién toma decisión' del formulario Jotform."),
        ("A quién le vendés (JT)",  "API Clienty · Jotform", "Campo personalizado 'A quién le vendés' del formulario Jotform."),
        ("Proceso de venta (JT)",   "API Clienty · Jotform", "Campo personalizado 'Proceso de venta' del formulario Jotform."),
        ("Notas CRM",               _a("BBDD Clienty CRM", f"https://docs.google.com/spreadsheets/d/{_ID_NOTAS_SHEET}/edit"), "Columna 'Notas' del sheet BBDD_Clienty_CRM. Join por ID de prospecto."),
    ]

    html = """
    <style>
    .orig-table { width:100%; border-collapse:collapse; font-size:0.88rem; }
    .orig-table th { background:#1e3a5f; color:white; padding:8px 12px; text-align:left; }
    .orig-table td { padding:7px 12px; border-bottom:1px solid #e2e8f0; vertical-align:top; }
    .orig-table tr:nth-child(even) td { background:#f8fafc; }
    .orig-table a { color:#2563eb; text-decoration:none; }
    .orig-table a:hover { text-decoration:underline; }
    .orig-table td:first-child { font-weight:600; white-space:nowrap; }
    </style>
    <table class="orig-table">
    <thead><tr><th style="width:200px">Campo</th><th style="width:220px">Origen</th><th>Descripción</th></tr></thead>
    <tbody>
    """
    for campo, origen, desc in _rows:
        html += f"<tr><td>{campo}</td><td>{origen}</td><td>{desc}</td></tr>\n"
    html += "</tbody></table>"
    st.html(html)
