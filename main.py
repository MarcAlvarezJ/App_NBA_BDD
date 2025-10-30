import streamlit as st
from utils import load_data

st.set_page_config(page_title="NBA Stats App", layout="wide")

# Datos compartidos
partidos, partidos_futuros, boxscores, equipos, jugadores = load_data()

# Estado buscador
if "jugador_sel" not in st.session_state:
	st.session_state.jugador_sel = ""

"""Reset si venimos de otra página (clic en sidebar)"""
if st.session_state.get("_last_page") != "main":
	st.session_state.jugador_sel = ""

left_col, _ = st.columns([1, 8])
with left_col:
	if st.button("🏠 Inicio"):
		st.session_state.jugador_sel = ""
		st.rerun()

st.title("🏀 NBA Stats Dashboard")

# Buscador de jugadores (renderiza sección Jugador en esta misma página)
jugador_sel = st.selectbox(
	"🔍 Buscar jugador:",
	[""] + sorted(jugadores["PLAYER_NAME"].dropna().unique()),
	index=0,
	key="jugador_sel",
)

# Si hay jugador seleccionado, mostrar su ficha; si no, mostrar Inicio
if st.session_state.jugador_sel:
	jugador = st.session_state.jugador_sel
	st.header(f"📋 Estadísticas de {jugador}")
	filtered = boxscores[boxscores["PLAYER_NAME"].str.lower() == jugador.lower()].copy()

	# KPIs y promedios por juego
	metricas = [m for m in ["PTS", "REB", "AST", "STL", "BLK"] if m in filtered.columns]
	if metricas:
		promedios = filtered[metricas].mean().to_dict()
		c1, c2, c3, c4, c5 = st.columns(5)
		if "PTS" in promedios:
			c1.metric("PTS por juego", f"{promedios['PTS']:.1f}")
		if "REB" in promedios:
			c2.metric("REB por juego", f"{promedios['REB']:.1f}")
		if "AST" in promedios:
			c3.metric("AST por juego", f"{promedios['AST']:.1f}")
		if "STL" in promedios:
			c4.metric("STL por juego", f"{promedios['STL']:.1f}")
		if "BLK" in promedios:
			c5.metric("BLK por juego", f"{promedios['BLK']:.1f}")

	# Minutos promedio (soporta formato MM:SS)
	if "MIN" in filtered.columns:
		mins = filtered["MIN"].dropna()
		def to_minutes(val):
			if isinstance(val, (int, float)):
				return float(val)
			if isinstance(val, str) and ":" in val:
				try:
					mm, ss = val.split(":", 1)
					return int(mm) + int(ss) / 60.0
				except Exception:
					return None
			return None
		mins_float = mins.map(to_minutes).dropna()
		if not mins_float.empty:
			st.metric("MIN por juego", f"{mins_float.mean():.1f}")

	st.subheader("Historial de Partidos")
	cols_show = [
		"GAME_ID",
		"TEAM_ABBREVIATION",
		"MIN",
		"PTS",
		"REB",
		"AST",
		"STL",
		"BLK",
		"TO",
		"PF",
	]
	cols_show = [c for c in cols_show if c in filtered.columns]
	st.dataframe(filtered[cols_show])
else:
	st.header("🏠 Inicio - Tabla de Posiciones")
	st.dataframe(equipos)


# Marcar página actual
st.session_state._last_page = "main"

