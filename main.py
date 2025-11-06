import streamlit as st
import pandas as pd
from utils import load_data, check_auth, logout, get_current_user, init_session_state

st.set_page_config(page_title="NBA Stats App", layout="wide")

# Inicializar estado de sesión
init_session_state()

# ---------- Data ----------
partidos, partidos_futuros, boxscores, equipos, jugadores = load_data()

# ---------- Estado ----------
ss = st.session_state
ss.setdefault("jugador_sel", "")
ss.setdefault("team_sel", "")

if ss.get("_last_page") != "main":
    ss.jugador_sel = ""
    ss.team_sel = ""

# Barra superior con información del usuario y logout
col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
with col1:
	st.title("🏀 NBA Stats Dashboard")
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

st.header("🏠 Tabla de Posiciones (temporada completa)")

# ==============================================================
# ✅ BUSCADOR UNIFICADO: jugadores + equipos
# ==============================================================

# Jugadores
player_opts = [("player", n) for n in sorted(jugadores["PLAYER_NAME"].dropna().unique())]

# Equipos (abreviatura + nombre)
team_rows = (
    equipos[["TEAM_ABBREVIATION", "TEAM_NAME"]]
    .dropna()
    .drop_duplicates()
    .sort_values("TEAM_ABBREVIATION")
)
team_opts = [("team", r.TEAM_ABBREVIATION, r.TEAM_NAME) for _, r in team_rows.iterrows()]

# Opciones combinadas
options = [("",)] + player_opts + team_opts

def format_opt(opt):
    if not opt or opt[0] == "":
        return ""
    if opt[0] == "player":
        return f"👤 {opt[1]}"
    abbr, name = opt[1], (opt[2] if len(opt) > 2 else "")
    return f"🏀 {abbr} — {name}"

sel_any = st.selectbox(
    "🔎 Buscar jugador o equipo",
    options,
    format_func=format_opt,
    key="buscador_global_main"
)

# Acción de navegación
if sel_any:
    if sel_any[0] == "player":
        ss.jugador_sel = sel_any[1]
        st.switch_page("pages/4_Jugadores.py")
    elif sel_any[0] == "team":
        ss.team_sel = sel_any[1]
        st.switch_page("pages/5_Equipos.py")

# ==============================================================
# ✅ TABLA DE POSICIONES
# ==============================================================

def posiciones_tabla(partidos_df: pd.DataFrame, equipos_df: pd.DataFrame) -> pd.DataFrame:
    df = partidos_df.copy()
    req = ["GAME_ID","FECHA","LOCAL","VISITANTE","PTS_LOCAL","PTS_VISITANTE"]
    if not all(c in df.columns for c in req):
        st.warning("❗ Faltan columnas necesarias en el archivo de partidos")
        return pd.DataFrame()

    df["FECHA"] = pd.to_datetime(df["FECHA"], errors='ignore')

    home = df.assign(
        TEAM_ABBREVIATION=df["LOCAL"],
        PTS_FOR=df["PTS_LOCAL"],
        PTS_AGAINST=df["PTS_VISITANTE"],
        WIN=(df["PTS_LOCAL"] > df["PTS_VISITANTE"]).astype(int),
        LOSS=(df["PTS_LOCAL"] < df["PTS_VISITANTE"]).astype(int),
    )[["TEAM_ABBREVIATION","PTS_FOR","PTS_AGAINST","WIN","LOSS"]]

    away = df.assign(
        TEAM_ABBREVIATION=df["VISITANTE"],
        PTS_FOR=df["PTS_VISITANTE"],
        PTS_AGAINST=df["PTS_LOCAL"],
        WIN=(df["PTS_VISITANTE"] > df["PTS_LOCAL"]).astype(int),
        LOSS=(df["PTS_VISITANTE"] < df["PTS_LOCAL"]).astype(int),
    )[["TEAM_ABBREVIATION","PTS_FOR","PTS_AGAINST","WIN","LOSS"]]

    tabla = pd.concat([home, away], ignore_index=True)
    tabla = (
        tabla.groupby("TEAM_ABBREVIATION", as_index=False)
        .agg(
            PJ=("WIN","count"),
            G=("WIN","sum"),
            P=("LOSS","sum"),
            PTS_FOR=("PTS_FOR","sum"),
            PTS_AGAINST=("PTS_AGAINST","sum")
        )
    )
    tabla["DIF"] = tabla["PTS_FOR"] - tabla["PTS_AGAINST"]
    tabla = tabla.sort_values(["G","DIF"], ascending=False).reset_index(drop=True)
    tabla.insert(0, "POS", range(1, len(tabla)+1))

    if "TEAM_NAME" in equipos_df.columns:
        tabla = tabla.merge(
            equipos_df[["TEAM_ABBREVIATION","TEAM_NAME"]].drop_duplicates(),
            on="TEAM_ABBREVIATION", how="left"
        )

    return tabla[["POS","TEAM_ABBREVIATION","TEAM_NAME","PJ","G","P","PTS_FOR","PTS_AGAINST","DIF"]]

tabla = posiciones_tabla(partidos, equipos)
st.dataframe(tabla, use_container_width=True)

# ---------- Marcar página ----------
ss._last_page = "main"
