# pages/5_Equipos.py
import streamlit as st
import pandas as pd
from utils import load_data, check_auth, init_session_state

st.set_page_config(page_title="Equipo | NBA Stats App", layout="wide")

# Inicializar estado de sesión
init_session_state()

partidos, partidos_futuros, boxscores, equipos, jugadores = load_data()
ss = st.session_state

# ------------------ selección de equipo ------------------
team_abbrs = (
    equipos.get("TEAM_ABBREVIATION", pd.Series(dtype=str))
    .dropna().unique().tolist()
)
team_map = {}
if "TEAM_NAME" in equipos.columns:
    team_map = (
        equipos[["TEAM_ABBREVIATION", "TEAM_NAME"]]
        .drop_duplicates().set_index("TEAM_ABBREVIATION")["TEAM_NAME"]
        .to_dict()
    )

# Para obtener logo del equipo seleccionado:
team_logo_map = {}
if "TEAM_ABBREVIATION" in equipos.columns and "LOGO_URL" in equipos.columns:
    team_logo_map = (
        equipos[["TEAM_ABBREVIATION", "LOGO_URL"]]
        .drop_duplicates().set_index("TEAM_ABBREVIATION")["LOGO_URL"]
        .to_dict()
    )
else:
    team_logo_map = {}

default_abbr = ss.get("team_sel") if ss.get("team_sel") in team_abbrs else (team_abbrs[0] if team_abbrs else "")
team_sel = st.selectbox(
    "📌 Elegir equipo",
    sorted(team_abbrs),
    index=(sorted(team_abbrs).index(default_abbr) if default_abbr in team_abbrs else 0),
    format_func=lambda ab: f"{ab} — {team_map.get(ab, '')}"
)
team_name = team_map.get(team_sel, team_sel)
ss["team_sel"] = team_sel

# -- LOGO DEL EQUIPO (reemplaza el icono 🏀 al principio de la cabecera) --
selected_logo_url = team_logo_map.get(team_sel, None)
if selected_logo_url and isinstance(selected_logo_url, str) and selected_logo_url.strip():
    logo_html = f"""<img src="{selected_logo_url}" style="vertical-align:middle; height:38px; margin-right:12px; margin-top:-3px; border-radius:6px; box-shadow:none;" alt="logo"/>"""
else:
    logo_html = ""

# Mostrar el título con el logo en vez de 🏀
st.markdown(
    f"<h1 style='display:flex; align-items:center; gap:10px; font-size:2.2rem; font-weight:700;'>"
    f"{logo_html}<span>{team_sel} — {team_name}</span>"
    f"</h1>",
    unsafe_allow_html=True
)

# ------------------ helpers ------------------
def _col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    return None

def next_fixture(df_fut: pd.DataFrame, abbr: str):
    if df_fut is None or df_fut.empty:
        return None
    df = df_fut.copy()

    c_fecha = _col(df, "FECHA", "fecha", "date", "DATE")
    c_loc   = _col(df, "LOCAL", "home", "HOME")
    c_vis   = _col(df, "VISITANTE", "away", "AWAY")
    if not all([c_fecha, c_loc, c_vis]): return None

    mask = (df[c_loc] == abbr) | (df[c_vis] == abbr)
    df = df.loc[mask].copy()

    df[c_fecha] = pd.to_datetime(df[c_fecha], errors="coerce")
    df = df.sort_values(c_fecha)

    today = pd.Timestamp("today").normalize()
    fut = df[df[c_fecha] >= today]
    row = fut.iloc[0] if not fut.empty else (df.iloc[0] if not df.empty else None)
    if row is None: return None

    fecha = row[c_fecha].date() if pd.notnull(row[c_fecha]) else None
    home, away = row[c_loc], row[c_vis]
    rival = away if home == abbr else home
    condicion = "Local" if home == abbr else "Visitante"
    return {"fecha": fecha, "home": home, "away": away, "rival": rival, "condicion": condicion}

def games_for_team(df_games: pd.DataFrame, abbr: str) -> pd.DataFrame:
    """TODOS los partidos del equipo, más recientes primero."""
    if df_games is None or df_games.empty:
        return pd.DataFrame()

    df = df_games.copy()
    c_fecha = _col(df, "FECHA","fecha","DATE","date")
    c_loc   = _col(df, "LOCAL","home","HOME")
    c_vis   = _col(df, "VISITANTE","away","AWAY")
    c_pl    = _col(df, "PTS_LOCAL","pts_local","HOME_PTS")
    c_pv    = _col(df, "PTS_VISITANTE","pts_visitante","AWAY_PTS")
    if not all([c_fecha, c_loc, c_vis, c_pl, c_pv]): return pd.DataFrame()

    mask = (df[c_loc] == abbr) | (df[c_vis] == abbr)
    df = df.loc[mask, [c_fecha, c_loc, c_vis, c_pl, c_pv]].copy()
    if df.empty: return pd.DataFrame()

    df[c_fecha] = pd.to_datetime(df[c_fecha], errors="coerce")
    df = df.sort_values(c_fecha, ascending=False).reset_index(drop=True)
    df.rename(columns={
        c_fecha: "FECHA", c_loc: "LOCAL", c_vis: "VISITANTE",
        c_pl: "PTS_LOCAL", c_pv: "PTS_VISITANTE"
    }, inplace=True)
    return df

def render_history_cards(df: pd.DataFrame, abbr: str):
    """Muestra el historial: el equipo seleccionado va siempre en negrita (nombre y puntaje)."""
    if df.empty:
        st.info("No hay historial disponible.")
        return
    df = df.head(30)

    for _, r in df.iterrows():
        fecha = r["FECHA"].date() if pd.notnull(r["FECHA"]) else r["FECHA"]
        home, away = r["LOCAL"], r["VISITANTE"]
        ph, pa = int(r["PTS_LOCAL"]), int(r["PTS_VISITANTE"])

        # Resultado desde la perspectiva del seleccionado
        pts_for, pts_opp = (ph, pa) if home == abbr else (pa, ph)
        won = pts_for > pts_opp

        # Estilos condicionales: seleccionado en negrita, rival atenuado
        home_name_style = "font-weight:700;" if home == abbr else "color:#9aa4b8;"
        away_name_style = "font-weight:700;" if away == abbr else "color:#9aa4b8;"
        home_pts_style  = "font-weight:700;" if home == abbr else "color:#9aa4b8;"
        away_pts_style  = "font-weight:700;" if away == abbr else "color:#9aa4b8;"

        fecha_txt = fecha.strftime("%d/%m/%y") if hasattr(fecha, "strftime") else str(fecha)

        with st.container():
            c1, c2, c3 = st.columns([1.4, 2.4, 0.8])

            with c1:
                st.markdown(
                    f"<div style='margin-top:-2px;font-weight:600;'>{fecha_txt}</div>",
                    unsafe_allow_html=True
                )

            with c2:
                l1a, l1b = st.columns([4, 1])
                l1a.markdown(
                    f"<div style='margin-top:-2px;{home_name_style}'>{home}</div>",
                    unsafe_allow_html=True
                )
                l1b.markdown(
                    f"<div style='margin-top:-2px;{home_pts_style}'>{ph}</div>",
                    unsafe_allow_html=True
                )

                l2a, l2b = st.columns([4, 1])
                l2a.markdown(
                    f"<div style='margin-top:-6px;{away_name_style}'>{away}</div>",
                    unsafe_allow_html=True
                )
                l2b.markdown(
                    f"<div style='margin-top:-6px;{away_pts_style}'>{pa}</div>",
                    unsafe_allow_html=True
                )

            with c3:
                badge = f"""
                <div style="
                    display:inline-flex;align-items:center;justify-content:center;
                    background:{'#1f6f3f' if won else '#8e2727'};
                    color:#fff;border-radius:15px;width:26px;height:26px;font-weight:700;">
                    {'W' if won else 'L'}
                </div>"""
                st.markdown(f"<div style='margin-top:-2px;'>{badge}</div>", unsafe_allow_html=True)


def build_standings(df_games: pd.DataFrame, equipos_df: pd.DataFrame) -> dict:
    """
    Calcula las tablas de posiciones divididas por conferencia.
    Retorna un diccionario con 'East' y 'West', cada uno con un DataFrame.
    """
    if df_games is None or df_games.empty:
        return {"East": pd.DataFrame(), "West": pd.DataFrame()}

    df = df_games.copy()
    c_fecha = _col(df, "FECHA","fecha","DATE","date")
    c_loc   = _col(df, "LOCAL","home","HOME")
    c_vis   = _col(df, "VISITANTE","away","AWAY")
    c_pl    = _col(df, "PTS_LOCAL","pts_local","HOME_PTS")
    c_pv    = _col(df, "PTS_VISITANTE","pts_visitante","AWAY_PTS")
    if not all([c_fecha, c_loc, c_vis, c_pl, c_pv]): 
        return {"East": pd.DataFrame(), "West": pd.DataFrame()}

    df[c_fecha] = pd.to_datetime(df[c_fecha], errors="coerce")
    df = df.sort_values(c_fecha)

    home = df.assign(
        ABBR=df[c_loc], PTS_FOR=df[c_pl], PTS_AGAINST=df[c_pv],
        WIN=(df[c_pl] > df[c_pv]).astype(int), LOSS=(df[c_pl] < df[c_pv]).astype(int),
    )[["ABBR","PTS_FOR","PTS_AGAINST","WIN","LOSS",c_fecha]]

    away = df.assign(
        ABBR=df[c_vis], PTS_FOR=df[c_pv], PTS_AGAINST=df[c_pl],
        WIN=(df[c_pv] > df[c_pl]).astype(int), LOSS=(df[c_pv] < df[c_pl]).astype(int),
    )[["ABBR","PTS_FOR","PTS_AGAINST","WIN","LOSS",c_fecha]]

    all_rows = pd.concat([home, away], ignore_index=True)

    tabla = (
        all_rows.groupby("ABBR", as_index=False)
        .agg(PJ=(c_fecha, "count"),
             PG=("WIN", "sum"),
             PP=("LOSS", "sum"),
             PTS_FOR=("PTS_FOR", "sum"),
             PTS_AGAINST=("PTS_AGAINST", "sum"))
    )
    tabla["DIF"] = tabla["PTS_FOR"] - tabla["PTS_AGAINST"]

    last_all = {t: [] for t in tabla["ABBR"]}
    for _, r in df.iterrows():
        h, a = r[c_loc], r[c_vis]
        pl, pv = int(r[c_pl]), int(r[c_pv])
        last_all[h].append("W" if pl > pv else "L")
        last_all[a].append("W" if pv > pl else "L")

    def take_last5(seq):
        tail = seq[-5:] if len(seq) >= 5 else seq
        tail = ([""] * (5 - len(tail))) + tail
        return tail

    tabla["last5"] = tabla["ABBR"].map(lambda t: take_last5(last_all.get(t, [])))

    # Agregar nombre, conferencia y LOGO desde equipos_df
    if {"TEAM_NAME", "LOGO_URL"}.issubset(equipos_df.columns):
        tabla = tabla.merge(
            equipos_df[["TEAM_ABBREVIATION","TEAM_NAME","LOGO_URL"]].drop_duplicates(),
            left_on="ABBR", right_on="TEAM_ABBREVIATION", how="left"
        )
        tabla["Equipo"] = tabla["TEAM_NAME"].fillna(tabla["ABBR"])
        tabla["LOGO_URL"] = tabla["LOGO_URL"]
    elif "TEAM_NAME" in equipos_df.columns:
        tabla = tabla.merge(
            equipos_df[["TEAM_ABBREVIATION","TEAM_NAME"]].drop_duplicates(),
            left_on="ABBR", right_on="TEAM_ABBREVIATION", how="left"
        )
        tabla["Equipo"] = tabla["TEAM_NAME"].fillna(tabla["ABBR"])
        tabla["LOGO_URL"] = ""
    else:
        tabla["Equipo"] = tabla["ABBR"]
        tabla["LOGO_URL"] = ""
    
    # Agregar conferencia
    if "CONFERENCE" in equipos_df.columns:
        tabla = tabla.merge(
            equipos_df[["TEAM_ABBREVIATION","CONFERENCE"]].drop_duplicates(),
            left_on="ABBR", right_on="TEAM_ABBREVIATION", how="left"
        )
        tabla = tabla.dropna(subset=["CONFERENCE"])
    else:
        return {"East": pd.DataFrame(), "West": pd.DataFrame()}

    # Dividir por conferencia
    east = tabla[tabla["CONFERENCE"] == "East"].copy()
    west = tabla[tabla["CONFERENCE"] == "West"].copy()
    
    # Renombrar PG a W y PP a L
    east = east.rename(columns={"PG": "W", "PP": "L"})
    west = west.rename(columns={"PG": "W", "PP": "L"})
    
    # Ordenar por victorias (descendente) y luego por diferencia (descendente)
    east = east.sort_values(by=["W","DIF"], ascending=[False, False]).reset_index(drop=True)
    west = west.sort_values(by=["W","DIF"], ascending=[False, False]).reset_index(drop=True)
    
    # Agregar número de posición
    east.insert(0, "#", range(1, len(east) + 1))
    west.insert(0, "#", range(1, len(west) + 1))
    
    # Seleccionar columnas finales (mantener ABBR para selección, sin PJ, y con logo)
    east = east[["#","ABBR","Equipo","LOGO_URL","W","L","DIF","last5"]].copy()
    west = west[["#","ABBR","Equipo","LOGO_URL","W","L","DIF","last5"]].copy()
    
    return {"East": east, "West": west}

def render_standings_html(tablas: dict, selected: str):
    """
    Renderiza las tablas de posiciones divididas por conferencia.
    (Con logo por equipo y sin fondo extra para logos).
    """
    css = """
    <style>
      .standings { width:100%; border-collapse:separate; border-spacing:0 6px; }
      .standings th { text-align:center; color:#cfd9e6; font-weight:600; padding:8px 6px; }
      .standings td { text-align:center; color:#e6eef6; padding:10px 6px; }
      .row { background:#151a22; border:1px solid #222b38; }
      .row.sel { background:#233044; border-color:#2f3d53; }
      .left { text-align:left !important; padding-left:12px !important; }
      .eqlogo {
        vertical-align: middle;
        margin-right: 7px;
        margin-left: 2px;
        border-radius: 5px;
        box-shadow: none;
        background: transparent !important;
        border: none !important;
      }
      .pill {
        display:inline-flex; align-items:center; justify-content:center;
        border-radius:15px; padding:2px 0; margin:0 3px; font-weight:800;
        color:#fff; min-width:22px; height:20px; text-align:center;
      }
      .w { background:#1f6f3f; }
      .l { background:#8e2727; }
      .n { background:#6b7280; }
      /* Ajusta ancho columna equipo con logo */
      .standings .td-eq { text-align:left !important; padding-left:12px !important; }
    </style>
    """
    
    for conf_name, tabla in tablas.items():
        if tabla.empty:
            st.info(f"No hay posiciones disponibles para {conf_name} Conference.")
            continue
        
        st.markdown(f"### {conf_name} Conference")
        html = [css, "<table class='standings'>",
                "<thead><tr>",
                "<th>#</th><th class='left'>Equipo</th><th>W</th><th>L</th><th>DIF</th><th>Últimos 5</th>",
                "</tr></thead><tbody>"]

        for _, r in tabla.iterrows():
            # Verificar si el equipo seleccionado está en esta tabla
            cls = "row sel" if r["ABBR"] == selected else "row"
            pills = "".join(
                f"<span class='pill {'w' if v=='W' else 'l' if v=='L' else 'n'}'>{v if v else ''}</span>"
                for v in r["last5"]
            )

            logo_img = ""
            # Solo mostrar imagen si existe el campo/logo
            if isinstance(r.get("LOGO_URL", ""), str) and r.get("LOGO_URL", "").strip():
                logo_img = f"<img class='eqlogo' src='{r['LOGO_URL']}' alt='logo' width='28' style='vertical-align:middle;background:transparent;border:none;'/>"
            # Mostrado: logo + nombre (alineados)
            equipo_html = f"<span style='display:inline-flex;align-items:center'>{logo_img}<span>{r['Equipo']}</span></span>"

            html.append(
                f"<tr class='{cls}'>"
                f"<td>{int(r['#'])}</td>"
                f"<td class='left td-eq'>{equipo_html}</td>"
                f"<td>{r['W']}</td><td>{r['L']}</td><td>{r['DIF']}</td>"
                f"<td>{pills}</td>"
                f"</tr>"
            )

        html.append("</tbody></table>")
        st.markdown("".join(html), unsafe_allow_html=True)

# ---------- roster helpers ----------
def _full_name_from_row(r: pd.Series) -> str:
    if "PLAYER_NAME" in r:
        return str(r["PLAYER_NAME"])
    first = str(r.get("FIRST_NAME", "")).strip()
    last = str(r.get("LAST_NAME", "")).strip()
    return (first + " " + last).strip()

def build_roster(jug_df: pd.DataFrame, abbr: str, name: str) -> pd.DataFrame:
    if jug_df is None or jug_df.empty:
        return pd.DataFrame()
    df = jug_df.copy()

    c_abbr = _col(df, "TEAM_ABBREVIATION", "TEAM")
    c_name = _col(df, "TEAM_NAME")

    mask = pd.Series([False] * len(df))
    if c_abbr:
        mask = mask | (df[c_abbr].astype(str) == str(abbr))
    if c_name:
        mask = mask | (df[c_name].astype(str) == str(name))

    df = df.loc[mask].copy()
    if df.empty: return pd.DataFrame()

    df["Jugador"] = df.apply(_full_name_from_row, axis=1)
    pos_col = _col(df, "POSITION", "POS")
    age_col = _col(df, "AGE")
    df["Posición"] = df[pos_col] if pos_col else ""
    df["Edad"] = pd.to_numeric(df[age_col], errors="coerce") if age_col else pd.NA

    out = df[["Jugador", "Posición", "Edad"]].drop_duplicates()
    out = out.sort_values(by=["Posición", "Edad", "Jugador"], ascending=[True, True, True]).reset_index(drop=True)
    return out

def render_roster_clickable(roster: pd.DataFrame):
    """Tabla con nombres clickeables que llevan a la página del jugador."""
    st.markdown("""
    <style>
      /* Estilo para que los botones de nombres sean completamente invisibles - sin bordes ni fondos */
      #roster-players-table .stButton {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        width: 100% !important;
        box-shadow: none !important;
        outline: none !important;
      }
      #roster-players-table .stButton > button {
        background: transparent !important;
        border: none !important;
        border-width: 0 !important;
        border-style: none !important;
        border-color: transparent !important;
        outline: none !important;
        outline-width: 0 !important;
        box-shadow: none !important;
        -webkit-box-shadow: none !important;
        -moz-box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
        border-radius: 0 !important;
        color: #a8b7ff !important;
        font-weight: 800 !important;
        cursor: pointer;
        text-align: left !important;
        justify-content: flex-start !important;
        align-items: flex-start !important;
        display: flex !important;
        width: 100% !important;
        height: auto !important;
        min-height: auto !important;
        box-sizing: border-box !important;
      }
      /* Asegurar que el texto dentro del botón esté alineado a la izquierda */
      #roster-players-table .stButton > button,
      #roster-players-table .stButton > button > div,
      #roster-players-table .stButton > button > div > p {
        text-align: left !important;
        justify-content: flex-start !important;
        align-items: flex-start !important;
        display: flex !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        padding-left: 0 !important;
      }
      /* Forzar alineación a la izquierda de todos los elementos internos */
      #roster-players-table .stButton > button * {
        text-align: left !important;
        justify-content: flex-start !important;
        align-items: flex-start !important;
        margin-left: 0 !important;
        margin-right: auto !important;
      }
      /* Forzar que el contenido del botón esté a la izquierda usando padding y margin */
      #roster-players-table .stButton {
        text-align: left !important;
        padding-left: 0 !important;
      }
      #roster-players-table .stButton > button {
        padding-left: 0 !important;
        margin-left: 0 !important;
      }
      #roster-players-table .stButton > button > div {
        padding-left: 0 !important;
        margin-left: 0 !important;
        text-align: left !important;
      }
      #roster-players-table .stButton > button > div > p {
        padding-left: 0 !important;
        margin-left: 0 !important;
        text-align: left !important;
      }
      #roster-players-table .stButton > button:hover,
      #roster-players-table .stButton > button:focus,
      #roster-players-table .stButton > button:active,
      #roster-players-table .stButton > button:focus-visible {
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        border-width: 0 !important;
        border-style: none !important;
        border-color: transparent !important;
        outline: none !important;
        outline-width: 0 !important;
        box-shadow: none !important;
        -webkit-box-shadow: none !important;
        -moz-box-shadow: none !important;
        text-decoration: underline !important;
      }
      /* Eliminar cualquier borde o sombra de estados adicionales */
      #roster-players-table .stButton > button:before,
      #roster-players-table .stButton > button:after {
        border: none !important;
        box-shadow: none !important;
      }
      /* Contenedor de la tabla */
      .roster-table-container {
        border: 1px solid #243249;
        border-radius: 12px;
        overflow: hidden;
        margin-bottom: 1rem;
      }
      .roster-header-row {
        background: #141a24;
        padding: 12px 14px;
        font-weight: 700;
        color: #cfd9e6;
        border-bottom: 1px solid #243249;
      }
      .roster-data-row {
        padding: 10px 14px;
        border-bottom: 1px solid #243249;
        display: flex;
        align-items: center;
        min-height: 40px;
      }
      .roster-row-even {
        background: #101620;
      }
      .roster-row-odd {
        background: #0d121a;
      }
      .roster-row:last-child .roster-data-row {
        border-bottom: none;
      }
      /* Estilos para las filas de la tabla usando columnas de Streamlit */
      /* Aplicar estilos a las columnas dentro de containers específicos */
      #roster-players-table [data-testid="stHorizontalBlock"] {
        border-bottom: 1px solid #243249;
        min-height: 40px;
        margin: 0;
      }
      /* Agregar espacio entre el encabezado y la primera fila */
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:first-of-type {
        margin-top: 12px;
      }
      #roster-players-table [data-testid="stHorizontalBlock"] [data-testid="column"] {
        padding: 10px 14px !important;
        display: flex;
        align-items: center;
        height: 100%;
        border: none !important;
      }
      /* Forzar alineación a la izquierda en la primera columna (nombres) */
      #roster-players-table [data-testid="stHorizontalBlock"] [data-testid="column"]:first-child {
        justify-content: flex-start !important;
        text-align: left !important;
      }
      #roster-players-table [data-testid="stHorizontalBlock"] [data-testid="column"]:first-child > div {
        justify-content: flex-start !important;
        text-align: left !important;
        width: 100% !important;
      }
      /* Fondo alternado usando nth-of-type para los containers */
      #roster-players-table [data-testid="stHorizontalBlock"]:nth-of-type(odd) [data-testid="column"] {
        background: #101620 !important;
      }
      #roster-players-table [data-testid="stHorizontalBlock"]:nth-of-type(even) [data-testid="column"] {
        background: #0d121a !important;
      }
      /* Ajustar para que la primera fila (después de la cabecera) sea par */
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(2) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(4) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(6) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(8) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(10) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(12) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(14) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(16) [data-testid="column"] {
        background: #101620 !important;
      }
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(3) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(5) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(7) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(9) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(11) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(13) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(15) [data-testid="column"],
      #roster-players-table .roster-table-container > [data-testid="stHorizontalBlock"]:nth-of-type(17) [data-testid="column"] {
        background: #0d121a !important;
      }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div id="roster-players-table"><div class="roster-table-container">', unsafe_allow_html=True)
    
    # Cabecera de la tabla
    header_cols = st.columns([0.50, 0.30, 0.20])
    with header_cols[0]:
        st.markdown('<div class="roster-header-row">Jugador</div>', unsafe_allow_html=True)
    with header_cols[1]:
        st.markdown('<div class="roster-header-row">Posición</div>', unsafe_allow_html=True)
    with header_cols[2]:
        st.markdown('<div class="roster-header-row">Edad</div>', unsafe_allow_html=True)
    
    # Espacio entre encabezado y primera fila
    st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
    
    # Filas de la tabla - solo el nombre es clickeable
    for idx, (i, r) in enumerate(roster.iterrows()):
        nombre = r["Jugador"]
        pos = "" if pd.isna(r["Posición"]) else str(r["Posición"])
        edad = "" if pd.isna(r["Edad"]) else str(int(r["Edad"]))
        
        # Usar container para envolver todo en una fila
        with st.container():
            row_cols = st.columns([0.50, 0.30, 0.20])
            with row_cols[0]:
                # Botón invisible dentro de la celda
                if st.button(nombre, key=f"roster_btn_{i}", use_container_width=True):
                    st.session_state["jugador_sel"] = nombre
                    st.switch_page("pages/4_Jugadores.py")
            with row_cols[1]:
                st.markdown(pos, unsafe_allow_html=True)
            with row_cols[2]:
                st.markdown(edad, unsafe_allow_html=True)
    
    st.markdown('</div></div>', unsafe_allow_html=True)

# ------------------ layout ------------------
col_left, col_right = st.columns([1, 1.3])

with col_left:
    st.markdown("### 📆 Próximo partido")
    fx = next_fixture(partidos_futuros, team_sel)
    if not fx:
        st.info("Sin datos de próximos partidos.")
    else:
        box = st.container(border=True)
        with box:
            # Obtener logos de home y away del df equipos
            home_logo = None
            away_logo = None
            if fx and not equipos.empty and "TEAM_ABBREVIATION" in equipos.columns and "LOGO_URL" in equipos.columns:
                try:
                    home_abbr = fx["home"]
                    away_abbr = fx["away"]
                    home_logo = equipos.loc[equipos["TEAM_ABBREVIATION"] == home_abbr, "LOGO_URL"].values
                    home_logo = home_logo[0] if len(home_logo) > 0 else None
                    away_logo = equipos.loc[equipos["TEAM_ABBREVIATION"] == away_abbr, "LOGO_URL"].values
                    away_logo = away_logo[0] if len(away_logo) > 0 else None
                except Exception:
                    home_logo, away_logo = None, None

            # ========= Alinear logos y abreviaciones en mismo eje, solo UNA VEZ cada uno + fecha, sin repetir =========
            st.markdown("""
            <style>
            .np-row {
                display: flex;
                flex-direction: row;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 0.2em;
                margin-top: 8px;
            }
            .np-team-block {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-width: 80px;
            }
            .np-team-abbr {
                font-weight: bold;
                font-size: 1.1em;
                margin-top: 6px;
                letter-spacing: 1.5px;
                text-align: center;
            }
            .np-middle-block {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-width: 70px;
            }
            </style>
            """, unsafe_allow_html=True)

            # Solo una fila, con escudos y abreviatura debajo (cada lado) y fecha azul en el centro (debajo de VS)
            fecha_txt = fx['fecha'].strftime('%d %b %Y') if hasattr(fx['fecha'], "strftime") else str(fx['fecha'])
            st.markdown(
                f"""
                <div class="np-row">
                    <div class="np-team-block">
                        {'<img src="' + home_logo + '" width="56"/>' if home_logo else ''}
                        <div class="np-team-abbr">{fx['home']}</div>
                    </div>
                    <div class="np-middle-block">
                        <span style='font-size:26px; font-weight:700; color:#fff'>VS</span>
                        <span style='color:#7c8cff;font-size:13px;margin-top:3px'>{fecha_txt}</span>
                    </div>
                    <div class="np-team-block">
                        {'<img src="' + away_logo + '" width="56"/>' if away_logo else ''}
                        <div class="np-team-abbr">{fx['away']}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
    st.markdown("### 📜 Historial reciente")
    juegos = games_for_team(partidos, team_sel)
    render_history_cards(juegos, team_sel)

with col_right:
    # ===== Tabs con estilo (Clasificaciones / Jugadores)
    st.markdown("""
    <style>
      div[role="tablist"]{ gap:64px; border-bottom:1px solid #2b3560; margin-bottom:8px; }
      button[role="tab"]{
        background:transparent!important; border:none!important; color:#8ea2ff!important;
        padding:8px 6px!important; font-weight:700!important; letter-spacing:.2px;
      }
      button[role="tab"][aria-selected="true"]{
        color:#cdd7ff!important; border-bottom:2px solid #7c8cff!important; border-radius:0!important;
      }
    </style>
    """, unsafe_allow_html=True)

    tab_cls, tab_roster = st.tabs(["Clasificaciones", "Jugadores"])

    with tab_cls:
        standings = build_standings(partidos, equipos)
        render_standings_html(standings, team_sel)

    with tab_roster:
        roster = build_roster(jugadores, team_sel, team_name)
        if roster.empty:
            st.info("No se encontraron jugadores para este equipo.")
        else:
            render_roster_clickable(roster)  # ✅ sin scroll y con click en nombre

st.divider()
if st.button("⬅ Volver al Inicio"):
    st.switch_page("Home.py")
