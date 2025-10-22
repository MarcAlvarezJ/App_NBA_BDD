import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- Conexión Supabase ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="NBA Stats App", layout="wide")

# --- Función de fetch con paginación ---
def fetch_all(table_name: str, batch_size: int = 1000):
    all_rows = []
    start = 0
    while True:
        batch = supabase.table(table_name).select("*").range(start, start + batch_size - 1).execute().data
        if not batch:
            break
        all_rows.extend(batch)
        start += batch_size
    return pd.DataFrame(all_rows)

# --- Cargar datos ---
@st.cache_data
def load_data():
    partidos = fetch_all("partidos")
    partidos_futuros = fetch_all("partidos_futuros")
    boxscores = fetch_all("boxscores")
    equipos = fetch_all("equipos")
    jugadores = fetch_all("jugadores")

    # Crear columna PLAYER_NAME
    if "FIRST_NAME" in jugadores.columns and "LAST_NAME" in jugadores.columns:
        jugadores["PLAYER_NAME"] = jugadores["FIRST_NAME"].astype(str) + " " + jugadores["LAST_NAME"].astype(str)
    elif "PLAYER_NAME" not in jugadores.columns:
        jugadores["PLAYER_NAME"] = ""
    return partidos, partidos_futuros, boxscores, equipos, jugadores

partidos, partidos_futuros, boxscores, equipos, jugadores = load_data()

# --- Sidebar de navegación ---
st.sidebar.title("📊 Navegación")
pagina = st.sidebar.radio(
    "Ir a:",
    ["Inicio", "Líderes", "Partidos", "Predicciones"]
)

# --- Inicializar estado de buscador ---
if "jugador_sel" not in st.session_state:
    st.session_state.jugador_sel = ""

# --- Limpiar buscador al cambiar de página ---
if pagina != "Jugador":
    st.session_state.jugador_sel = ""

# --- Buscador de jugadores en la parte superior ---
st.title("🏀 NBA Stats Dashboard")
jugador_sel = st.selectbox(
    "🔍 Buscar jugador:",
    [""] + sorted(jugadores["PLAYER_NAME"].dropna().unique()),
    index=0,
    key="jugador_sel"  # vincula el selectbox al session_state
)

# --- Página dedicada al jugador ---
if st.session_state.jugador_sel:
    st.header(f"📋 Estadísticas de {st.session_state.jugador_sel}")
    filtered_jugador = boxscores[
        boxscores["PLAYER_NAME"].str.lower() == st.session_state.jugador_sel.lower()
    ]

    st.subheader("Historial de Partidos")
    cols_show = ["GAME_ID", "TEAM_ABBREVIATION", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO", "PF"]
    cols_show = [c for c in cols_show if c in filtered_jugador.columns]
    st.dataframe(filtered_jugador[cols_show])

    st.subheader("Promedios del jugador")
    promedios = filtered_jugador[["PTS","REB","AST","STL","BLK"]].mean().to_frame(name="Promedio")
    st.dataframe(promedios)

# --- Página: INICIO ---
elif pagina == "Inicio":
    st.title("🏠 Inicio - Tabla de Posiciones")
    st.dataframe(equipos)

# --- Página: LÍDERES ---
elif pagina == "Líderes":
    st.title("🏆 Líderes Estadísticos")
    st.dataframe(boxscores.groupby("PLAYER_NAME")[["PTS","REB","AST","STL","BLK"]].mean().reset_index())

# --- Página: PARTIDOS ---
elif pagina == "Partidos":
    st.title("📅 Partidos")
    st.dataframe(partidos)

# --- Página: PREDICCIONES ---
elif pagina == "Predicciones":
    st.title("🔮 Predicciones")
    st.write("Aquí se mostrarán los modelos y predicciones futuras.")
