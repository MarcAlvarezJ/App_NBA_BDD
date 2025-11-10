# main.py

import streamlit as st
import pandas as pd
from utils import load_data, check_auth, logout, get_current_user, init_session_state

# ---------------------------------------------------
# Config & Session
# ---------------------------------------------------
st.set_page_config(page_title="NBA Stats App", layout="wide")


# CSS personalizado para fondo negro
st.markdown("""
<style>
    /* Fondo principal negro */
    .stApp {
        background-color: #000000;
    }
    
    /* Fondo de los contenedores principales */
    .main .block-container {
        background-color: #000000;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Fondo de las secciones */
    section[data-testid="stSidebar"] {
        background-color: #0e1117;
    }
    
    /* Ajustes de texto para mejor legibilidad */
    h1, h2, h3, h4, h5, h6, p, div, span {
        color: #ffffff !important;
    }
    
    /* Dataframes con fondo oscuro */
    .dataframe {
        background-color: #0e1117 !important;
    }
    
    /* Inputs y selectboxes */
    .stSelectbox > div > div {
        background-color: #0e1117;
    }
    
    /* Botones */
    .stButton > button {
        background-color: #1f77b4;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


init_session_state()

partidos, partidos_futuros, boxscores, equipos, jugadores = load_data()

ss = st.session_state
ss.setdefault("jugador_sel", "")
ss.setdefault("team_sel", "")

if ss.get("_last_page") != "main":
    ss.jugador_sel = ""
    ss.team_sel = ""

# ---------------------------------------------------
# TOP BAR (logo NBA + user info + auth)
# ---------------------------------------------------
col1, col2, col3, col4 = st.columns([4, 1, 1, 1])

with col1:
    # Logo NBA + título
    nba_logo_url = "https://1000marcas.net/wp-content/uploads/2019/12/NBA-Logo.png"
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
            <img src="{nba_logo_url}" alt="NBA Logo" style="height:68px;">
            <h1 style="margin:0;font-size:2.2rem;font-weight:700;">NBA Stats App</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    user = get_current_user()
    if user:
        st.success(f"👤 {user.email}")
        st.caption("Modo: Autenticado")
    else:
        st.info("👤 Usuario anónimo")
        st.caption("Modo: Sin autenticación")

with col3:
    if check_auth():
        if st.button("⚙️ Administración"):
            st.switch_page("pages/6_Admin.py")

with col4:
    if check_auth():
        if st.button("🚪 Cerrar Sesión"):
            logout()
            st.rerun()
    else:
        if st.button("🔐 Iniciar Sesión"):
            st.switch_page("pages/0_Login.py")

# ---------------------------------------------------
# BUSCADOR GLOBAL (jugadores + equipos) + logo equipo seleccionado
# ---------------------------------------------------

# Mapa de logos por abreviatura
team_logo_map = {}
if (
    equipos is not None
    and not equipos.empty
    and "TEAM_ABBREVIATION" in equipos.columns
    and "LOGO_URL" in equipos.columns
):
    team_logo_map = (
        equipos[["TEAM_ABBREVIATION", "LOGO_URL"]]
        .dropna()
        .drop_duplicates()
        .set_index("TEAM_ABBREVIATION")["LOGO_URL"]
        .to_dict()
    )

# Jugadores
player_opts = []
if jugadores is not None and not jugadores.empty and "PLAYER_NAME" in jugadores.columns:
    player_opts = [
        ("player", n)
        for n in sorted(jugadores["PLAYER_NAME"].dropna().unique())
    ]

# Equipos (abreviatura + nombre)
team_opts = []
if (
    equipos is not None
    and not equipos.empty
    and "TEAM_ABBREVIATION" in equipos.columns
    and "TEAM_NAME" in equipos.columns
):
    team_rows = (
        equipos[["TEAM_ABBREVIATION", "TEAM_NAME"]]
        .dropna()
        .drop_duplicates()
        .sort_values("TEAM_ABBREVIATION")
    )
    team_opts = [
        ("team", r.TEAM_ABBREVIATION, r.TEAM_NAME) for _, r in team_rows.iterrows()
    ]

# Opciones combinadas
options = [("",)] + player_opts + team_opts


def format_opt(opt):
    """Texto que se ve en el selectbox (sin 🏀, usando solo abbr - nombre)."""
    if not opt or opt[0] == "":
        return ""
    if opt[0] == "player":
        return f"👤 {opt[1]}"
    if opt[0] == "team":
        abbr = opt[1]
        name = opt[2] if len(opt) > 2 else ""
        return f"🏀{abbr} — {name}"
    return str(opt)


search_col, logo_col = st.columns([4, 1])

with search_col:
    sel_any = st.selectbox(
        "🔎 Buscar jugador o equipo",
        options,
        format_func=format_opt,
        key="buscador_global_main",
    )

# Mostrar logo del equipo seleccionado al lado del buscador
with logo_col:
    if sel_any and sel_any[0] == "team":
        abbr = sel_any[1]
        logo_url = team_logo_map.get(abbr)
        if logo_url:
            st.image(logo_url, width=40)

# Navegación según selección
if sel_any:
    if sel_any[0] == "player":
        ss.jugador_sel = sel_any[1]
        st.switch_page("pages/4_Jugadores.py")
    elif sel_any[0] == "team":
        ss.team_sel = sel_any[1]
        st.switch_page("pages/5_Equipos.py")

# ---------------------------------------------------
# TÍTULO TABLAS (después del buscador)
# ---------------------------------------------------
st.header("Tabla de Posiciones")

# ---------------------------------------------------
# STANDINGS (estilo 5_Equipos.py, lado a lado)
# ---------------------------------------------------

def _col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    return None


def build_standings(df_games: pd.DataFrame, equipos_df: pd.DataFrame) -> dict:
    if df_games is None or df_games.empty:
        return {"East": pd.DataFrame(), "West": pd.DataFrame()}

    df = df_games.copy()
    c_fecha = _col(df, "FECHA", "fecha", "DATE", "date")
    c_loc = _col(df, "LOCAL", "home", "HOME")
    c_vis = _col(df, "VISITANTE", "away", "AWAY")
    c_pl = _col(df, "PTS_LOCAL", "pts_local", "HOME_PTS")
    c_pv = _col(df, "PTS_VISITANTE", "pts_visitante", "AWAY_PTS")
    if not all([c_fecha, c_loc, c_vis, c_pl, c_pv]):
        return {"East": pd.DataFrame(), "West": pd.DataFrame()}

    df[c_fecha] = pd.to_datetime(df[c_fecha], errors="coerce")
    df = df.sort_values(c_fecha)

    home = df.assign(
        ABBR=df[c_loc],
        PTS_FOR=df[c_pl],
        PTS_AGAINST=df[c_pv],
        WIN=(df[c_pl] > df[c_pv]).astype(int),
        LOSS=(df[c_pl] < df[c_pv]).astype(int),
    )[["ABBR", "PTS_FOR", "PTS_AGAINST", "WIN", "LOSS", c_fecha]]

    away = df.assign(
        ABBR=df[c_vis],
        PTS_FOR=df[c_pv],
        PTS_AGAINST=df[c_pl],
        WIN=(df[c_pv] > df[c_pl]).astype(int),
        LOSS=(df[c_pv] < df[c_pl]).astype(int),
    )[["ABBR", "PTS_FOR", "PTS_AGAINST", "WIN", "LOSS", c_fecha]]

    all_rows = pd.concat([home, away], ignore_index=True)

    tabla = (
        all_rows.groupby("ABBR", as_index=False)
        .agg(
            PJ=(c_fecha, "count"),
            PG=("WIN", "sum"),
            PP=("LOSS", "sum"),
            PTS_FOR=("PTS_FOR", "sum"),
            PTS_AGAINST=("PTS_AGAINST", "sum"),
        )
    )
    tabla["DIF"] = tabla["PTS_FOR"] - tabla["PTS_AGAINST"]

    # Últimos 5 resultados (W/L)
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

    # Nombre + logo
    if {"TEAM_NAME", "LOGO_URL"}.issubset(equipos_df.columns):
        tabla = tabla.merge(
            equipos_df[["TEAM_ABBREVIATION", "TEAM_NAME", "LOGO_URL"]].drop_duplicates(),
            left_on="ABBR",
            right_on="TEAM_ABBREVIATION",
            how="left",
        )
        tabla["Equipo"] = tabla["TEAM_NAME"].fillna(tabla["ABBR"])
    elif "TEAM_NAME" in equipos_df.columns:
        tabla = tabla.merge(
            equipos_df[["TEAM_ABBREVIATION", "TEAM_NAME"]].drop_duplicates(),
            left_on="ABBR",
            right_on="TEAM_ABBREVIATION",
            how="left",
        )
        tabla["Equipo"] = tabla["TEAM_NAME"].fillna(tabla["ABBR"])
        tabla["LOGO_URL"] = ""
    else:
        tabla["Equipo"] = tabla["ABBR"]
        tabla["LOGO_URL"] = ""

    # Conferencia
    if "CONFERENCE" in equipos_df.columns:
        tabla = tabla.merge(
            equipos_df[["TEAM_ABBREVIATION", "CONFERENCE"]].drop_duplicates(),
            left_on="ABBR",
            right_on="TEAM_ABBREVIATION",
            how="left",
        )
        tabla = tabla.dropna(subset=["CONFERENCE"])
    else:
        return {"East": pd.DataFrame(), "West": pd.DataFrame()}

    east = tabla[tabla["CONFERENCE"] == "East"].copy()
    west = tabla[tabla["CONFERENCE"] == "West"].copy()

    # Renombrar PG/PP a W/L
    for t in (east, west):
        t.rename(columns={"PG": "W", "PP": "L"}, inplace=True)

    # Orden + posición
    east = east.sort_values(by=["W", "DIF"], ascending=[False, False]).reset_index(drop=True)
    west = west.sort_values(by=["W", "DIF"], ascending=[False, False]).reset_index(drop=True)
    east.insert(0, "#", range(1, len(east) + 1))
    west.insert(0, "#", range(1, len(west) + 1))

    east = east[["#", "ABBR", "Equipo", "LOGO_URL", "W", "L", "DIF", "last5"]].copy()
    west = west[["#", "ABBR", "Equipo", "LOGO_URL", "W", "L", "DIF", "last5"]].copy()

    return {"East": east, "West": west}


STANDINGS_CSS = """
<style>
  .standings { width:100%; border-collapse:separate; border-spacing:0 6px; }
  .standings th {
    text-align:center; color:#cfd9e6; font-weight:600; padding:8px 6px;
  }
  .standings td {
    text-align:center; color:#e6eef6; padding:10px 6px;
  }
  .row { background:#151a22; border:1px solid #222b38; }
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
  .standings .td-eq { text-align:left !important; padding-left:12px !important; }
</style>
"""


def _standings_table_html(conf_name: str, tabla: pd.DataFrame) -> str:
    if tabla.empty:
        return f"<p style='color:#9ca3af;'>No hay posiciones disponibles para {conf_name}.</p>"

    html = [
        f"<h3 style='margin-bottom:4px;'>{conf_name} Conference</h3>",
        "<table class='standings'>",
        "<thead><tr>",
        "<th>#</th><th class='left'>Equipo</th><th>W</th><th>L</th><th>DIF</th><th>Últimos 5</th>",
        "</tr></thead><tbody>",
    ]

    for _, r in tabla.iterrows():
        pills = "".join(
            f"<span class='pill {'w' if v=='W' else 'l' if v=='L' else 'n'}'>{v if v else ''}</span>"
            for v in r["last5"]
        )

        url = str(r.get("LOGO_URL", "") or "").strip()
        logo_img = (
            f"<img class='eqlogo' src='{url}' alt='logo' width='28' "
            "style='vertical-align:middle;background:transparent;border:none;'/>"
            if url
            else ""
        )

        equipo_html = (
            f"<span style='display:inline-flex;align-items:center'>"
            f"{logo_img}<span>{r['Equipo']}</span></span>"
        )

        html.append(
            f"<tr class='row'>"
            f"<td>{int(r['#'])}</td>"
            f"<td class='left td-eq'>{equipo_html}</td>"
            f"<td>{r['W']}</td><td>{r['L']}</td><td>{r['DIF']}</td>"
            f"<td>{pills}</td>"
            f"</tr>"
        )

    html.append("</tbody></table>")
    return "".join(html)


def render_standings_side_by_side(tablas: dict):
    st.markdown(STANDINGS_CSS, unsafe_allow_html=True)
    east = tablas.get("East", pd.DataFrame())
    west = tablas.get("West", pd.DataFrame())

    col_east, col_west = st.columns(2)
    with col_east:
        st.markdown(_standings_table_html("East", east), unsafe_allow_html=True)
    with col_west:
        st.markdown(_standings_table_html("West", west), unsafe_allow_html=True)


# ---------------------------------------------------
# RENDER MAIN STANDINGS
# ---------------------------------------------------
if partidos is None or partidos.empty or equipos is None or equipos.empty:
    st.info("No hay datos suficientes para mostrar las clasificaciones.")
else:
    standings = build_standings(partidos, equipos)
    render_standings_side_by_side(standings)

st.markdown("---")
st.caption("Usá el buscador de arriba o las pestañas para explorar equipos y jugadores.")

# Marcar página actual
ss._last_page = "main"
