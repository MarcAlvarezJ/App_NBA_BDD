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

    # Para mostrar: usar colores y negritas nice
    top_ptos = promedios.sort_values(by="PTS", ascending=False).head(10)[["PLAYER_NAME", "Equipo", "PTS"]].reset_index(drop=True)
    top_ptos["PTS"] = top_ptos["PTS"].round(1)
    top_asis = promedios.sort_values(by="AST", ascending=False).head(10)[["PLAYER_NAME", "Equipo", "AST"]].reset_index(drop=True)
    top_asis["AST"] = top_asis["AST"].round(1)
    top_reb = promedios.sort_values(by="REB", ascending=False).head(10)[["PLAYER_NAME", "Equipo", "REB"]].reset_index(drop=True)
    top_reb["REB"] = top_reb["REB"].round(1)

    # Títulos bonitos arriba de cada columna
    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown("<div style='background-color:#1d428a;padding:12px;border-radius:12px;text-align:center'><span style='color:#fff;font-weight:bold;font-size:20px;'>🏀 Puntos por partido</span></div>", unsafe_allow_html=True)
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
        st.markdown("<div style='background-color:#007A33;padding:12px;border-radius:12px;text-align:center'><span style='color:#fff;font-weight:bold;font-size:20px;'>🅰️ Asistencias por partido</span></div>", unsafe_allow_html=True)
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
        st.markdown("<div style='background-color:#FFC72C;padding:12px;border-radius:12px;text-align:center'><span style='color:#1d428a;font-weight:bold;font-size:20px;'>🧱 Rebotes por partido</span></div>", unsafe_allow_html=True)
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

    # ========== NUEVA FILA DE TRES TABLAS: ROBOS | BLOQUEOS | % TIROS LIBRES =============

    # Robos por partido
    if "STL" in boxscores.columns:
        promedios_stl = (
            boxscores_filtrado.groupby("PLAYER_NAME")["STL"].mean().reset_index()
        )
        promedios_stl["Equipo"] = promedios_stl["PLAYER_NAME"].map(equipos_jugador)
        top_stl = promedios_stl.sort_values(by="STL", ascending=False).head(10)[["PLAYER_NAME", "Equipo", "STL"]].reset_index(drop=True)
        top_stl["STL"] = top_stl["STL"].round(1)
    else:
        top_stl = None

    # Bloqueos por partido
    if "BLK" in boxscores.columns:
        promedios_blk = (
            boxscores_filtrado.groupby("PLAYER_NAME")["BLK"].mean().reset_index()
        )
        promedios_blk["Equipo"] = promedios_blk["PLAYER_NAME"].map(equipos_jugador)
        top_blk = promedios_blk.sort_values(by="BLK", ascending=False).head(10)[["PLAYER_NAME", "Equipo", "BLK"]].reset_index(drop=True)
        top_blk["BLK"] = top_blk["BLK"].round(1)
    else:
        top_blk = None

    # Porcentaje de tiros libres
    if "FTM" in boxscores.columns and "FTA" in boxscores.columns:
        tiros_libres_agg = (
            boxscores_filtrado.groupby("PLAYER_NAME")[["FTM", "FTA"]].sum().reset_index()
        )
        tiros_libres_agg["Equipo"] = tiros_libres_agg["PLAYER_NAME"].map(equipos_jugador)
        # Filtrar solo jugadores con al menos los mínimos de la imagen
        tiros_libres_agg = tiros_libres_agg[tiros_libres_agg["FTM"] >= 125]
        tiros_libres_agg = tiros_libres_agg[tiros_libres_agg["FTA"] > 0]
        # Calcular %
        tiros_libres_agg["% Efectividad"] = tiros_libres_agg["FTM"] / tiros_libres_agg["FTA"] * 100
        top_ft = tiros_libres_agg.sort_values(by="% Efectividad", ascending=False).head(10)[["PLAYER_NAME", "Equipo", "% Efectividad"]].reset_index(drop=True)
        top_ft["% Efectividad"] = top_ft["% Efectividad"].round(1)
    else:
        top_ft = None

    # Mostrar nuevas tablas (robos, bloques y tiros libres) en una fila, una al lado de la otra
    col4, col5, col6 = st.columns(3, gap="large")
    with col4:
        st.markdown("<div style='background-color:#86c5e7;padding:12px;border-radius:12px;text-align:center;margin-top:18px;'><span style='color:#1d428a;font-weight:bold;font-size:20px;'>🕵️ Robos por partido</span></div>", unsafe_allow_html=True)
        if top_stl is not None:
            st.dataframe(
                top_stl.rename(columns={
                    "PLAYER_NAME": "Jugador",
                    "Equipo": "Equipo",
                    "STL": "STL"
                }),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "STL": st.column_config.NumberColumn(format="%.1f")
                }
            )
        else:
            st.info("Robos por partido no disponibles.")
    with col5:
        st.markdown("<div style='background-color:#b296ff;padding:12px;border-radius:12px;text-align:center;margin-top:18px;'><span style='color:#1d428a;font-weight:bold;font-size:20px;'>⛔ Bloqueos por partido</span></div>", unsafe_allow_html=True)
        if top_blk is not None:
            st.dataframe(
                top_blk.rename(columns={
                    "PLAYER_NAME": "Jugador",
                    "Equipo": "Equipo",
                    "BLK": "BLK"
                }),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "BLK": st.column_config.NumberColumn(format="%.1f")
                }
            )
        else:
            st.info("Bloqueos por partido no disponibles.")
    with col6:
        st.markdown("<div style='background-color:#FFD6D6;padding:12px;border-radius:12px;text-align:center;margin-top:18px;'><span style='color:#1d428a;font-weight:bold;font-size:20px;'>🎯 % Tiros libres</span></div>", unsafe_allow_html=True)
        if top_ft is not None and not top_ft.empty:
            st.dataframe(
                top_ft.rename(columns={
                    "PLAYER_NAME": "Jugador",
                    "Equipo": "Equipo",
                    "% Efectividad": "% Efectividad"
                }),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "% Efectividad": st.column_config.NumberColumn(format="%.1f")
                }
            )
        else:
            st.info("% Tiros libres no disponible o no hay jugadores con el mínimo requerido.")

    # Footer con estilo NBA
    st.markdown("""
        <hr>
        
    """, unsafe_allow_html=True)
