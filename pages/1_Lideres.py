import streamlit as st
from utils import load_data, check_auth, init_session_state

st.set_page_config(
    page_title="Líderes | NBA Stats App",
    page_icon="🏆",
    layout="wide"
)

# Inicializar estado de sesión
init_session_state()
_, _, boxscores, _, _ = load_data()

# ENCABEZADO CON ESTILO
st.markdown("""
    <h1 style='text-align: center; color: #1d428a; margin-bottom: 0;'>🏆 Líderes Estadísticos NBA</h1>
    <h3 style='text-align: center; color: #C9082A; font-weight:400; margin-top:0;'>Temporada Regular</h3>
""", unsafe_allow_html=True)

# Métricas clave para mostrar
metricas_cols = {
    "Puntos por partido": "PTS",
    "Asistencias por partido": "AST",
    "Rebotes por partido": "REB"
}

# CHEQUEO PREVIO DE COLUMNAS
faltantes = [nombre for nombre, col in metricas_cols.items() if col not in boxscores.columns]
requisitos = ["PLAYER_NAME", "TEAM_ABBREVIATION", "GAME_ID"]
faltan_requisitos = any(col not in boxscores.columns for col in requisitos)
if faltantes:
    st.info(f"⚠️ Faltan las métricas: {faltantes}")
elif faltan_requisitos:
    st.info("⚠️ No se encontraron columnas necesarias en los datos.")
else:
    # Calcular partidos jugados por equipo
    juegos_por_equipo = boxscores.groupby("TEAM_ABBREVIATION")["GAME_ID"].nunique()
    partidos_maximos = juegos_por_equipo.max()

    # Calcular partidos jugados por jugador (por equipo), quedarnos con el equipo más jugado
    juegos_jugador_equipo = (
        boxscores.groupby(["PLAYER_NAME", "TEAM_ABBREVIATION"])["GAME_ID"].nunique().reset_index()
    )
    idx_max_games = juegos_jugador_equipo.groupby("PLAYER_NAME")["GAME_ID"].idxmax()
    juegos_jugador = juegos_jugador_equipo.loc[idx_max_games][["PLAYER_NAME", "TEAM_ABBREVIATION", "GAME_ID"]]
    juegos_dict = juegos_jugador.set_index("PLAYER_NAME")["GAME_ID"].to_dict()

    # Filtrar solo jugadores que hayan jugado >= 70% de partidos
    min_games = int(partidos_maximos * 0.7)
    jugadores_validos = [p for p, games in juegos_dict.items() if games >= min_games]
    boxscores_filtrado = boxscores[boxscores["PLAYER_NAME"].isin(jugadores_validos)]

    # Calcular promedios por partido
    promedios = (
        boxscores_filtrado.groupby("PLAYER_NAME")[list(metricas_cols.values())]
        .mean()
        .reset_index()
    )
    equipos_jugador = juegos_jugador.set_index("PLAYER_NAME")["TEAM_ABBREVIATION"].to_dict()
    promedios["Equipo"] = promedios["PLAYER_NAME"].map(equipos_jugador)

    # Para mostrar: usar colores oscuros y sin border-radius
    top_ptos = promedios.sort_values(by="PTS", ascending=False).head(10)[["PLAYER_NAME", "Equipo", "PTS"]].reset_index(drop=True)
    top_ptos["PTS"] = top_ptos["PTS"].round(1)
    top_asis = promedios.sort_values(by="AST", ascending=False).head(10)[["PLAYER_NAME", "Equipo", "AST"]].reset_index(drop=True)
    top_asis["AST"] = top_asis["AST"].round(1)
    top_reb = promedios.sort_values(by="REB", ascending=False).head(10)[["PLAYER_NAME", "Equipo", "REB"]].reset_index(drop=True)
    top_reb["REB"] = top_reb["REB"].round(1)

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown(
            "<div style='background-color:#121a33;padding:12px;text-align:center'>"
            "<span style='color:#fff;font-weight:bold;font-size:20px;'>🏀 Puntos por partido</span></div>",
            unsafe_allow_html=True
        )
        st.dataframe(
            top_ptos.rename(columns={
                "PLAYER_NAME": "Jugador",
                "Equipo": "Equipo",
                "PTS": "PTS"
            }),
            hide_index=True,
            use_container_width=True,
            column_config={
                "PTS": st.column_config.NumberColumn(format="%.1f")
            }
        )
    with col2:
        st.markdown(
            "<div style='background-color:#015624;padding:12px;text-align:center'>"
            "<span style='color:#fff;font-weight:bold;font-size:20px;'>🎯 Asistencias por partido</span></div>",
            unsafe_allow_html=True
        )
        st.dataframe(
            top_asis.rename(columns={
                "PLAYER_NAME": "Jugador",
                "Equipo": "Equipo",
                "AST": "AST"
            }),
            hide_index=True,
            use_container_width=True,
            column_config={
                "AST": st.column_config.NumberColumn(format="%.1f")
            }
        )
    with col3:
        st.markdown(
            "<div style='background-color:#3b2707;padding:12px;text-align:center'>"
            "<span style='color:#fff;font-weight:bold;font-size:20px;'>🧱 Rebotes por partido</span></div>",
            unsafe_allow_html=True
        )
        st.dataframe(
            top_reb.rename(columns={
                "PLAYER_NAME": "Jugador",
                "Equipo": "Equipo",
                "REB": "REB"
            }),
            hide_index=True,
            use_container_width=True,
            column_config={
                "REB": st.column_config.NumberColumn(format="%.1f")
            }
        )

    # Footer con estilo NBA
    st.markdown("""
        <hr>
        <div style='text-align:center;color:#1d428a;font-weight:500;font-size:15px;opacity:0.7;'>
            Datos filtrados por jugadores que participaron en al menos el 70% de los partidos del equipo.<br>
            NBA Stats App | Creado con <span style="color:#e74c3c;">❤</span> por <b>tu equipo de datos</b>
        </div>
    """, unsafe_allow_html=True)
