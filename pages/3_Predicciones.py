import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
from utils import load_data, check_auth, init_session_state, minutos_decimal_a_mmss

st.set_page_config(page_title="Predicciones | NBA Stats App", layout="wide")

# Inicializar estado de sesión
init_session_state()

partidos, partidos_futuros, boxscores, equipos, jugadores = load_data()

# ==============================================================
# FUNCIONES DE CÁLCULO
# ==============================================================

def precalcular_todos_promedios(
    partidos_df: pd.DataFrame,
    boxscores_df: pd.DataFrame
) -> tuple[dict, dict, dict]:
    """
    Precalcula todos los promedios ofensivos, defensivos y desvíos de todos los equipos.
    Retorna (promedios_ofensivos, promedios_defensivos, desvios_puntos)
    donde cada uno es un diccionario {team_abbr: valores}
    """
    promedios_of = {}
    promedios_def = {}
    desvios = {}
    
    if boxscores_df.empty:
        return promedios_of, promedios_def, desvios
    
    # Obtener todos los equipos únicos
    equipos_unicos = boxscores_df["TEAM_ABBREVIATION"].dropna().unique()
    
    # Precalcular estadísticas por partido para todos los equipos
    stats_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"]
    available_cols = [col for col in stats_cols if col in boxscores_df.columns]
    
    # Agrupar por equipo y partido para calcular promedios ofensivos y desvíos
    for team in equipos_unicos:
        team_str = str(team)
        team_boxscores = boxscores_df[boxscores_df["TEAM_ABBREVIATION"] == team_str].copy()
        
        if team_boxscores.empty:
            continue
        
        # Calcular promedios ofensivos
        team_stats_per_game = team_boxscores.groupby("GAME_ID")[available_cols].sum().reset_index()
        promedios_of[team_str] = {}
        for col in available_cols:
            promedios_of[team_str][col] = team_stats_per_game[col].mean()
        
        # Calcular desvío de puntos
        if "PTS" in team_stats_per_game.columns:
            puntos_por_partido = team_stats_per_game["PTS"]
            if len(puntos_por_partido) >= 2:
                desvio = puntos_por_partido.std()
                desvios[team_str] = float(desvio) if not pd.isna(desvio) else 0.0
            else:
                desvios[team_str] = 0.0
        else:
            desvios[team_str] = 0.0
    
    # Precalcular promedios defensivos
    if not partidos_df.empty:
        # Crear un diccionario de estadísticas por partido para acceso rápido
        stats_por_partido = {}
        for game_id in boxscores_df["GAME_ID"].unique():
            game_id_str = str(game_id)
            game_boxscores = boxscores_df[boxscores_df["GAME_ID"].astype(str) == game_id_str]
            stats_por_partido[game_id_str] = {}
            for team in game_boxscores["TEAM_ABBREVIATION"].unique():
                team_str = str(team)
                team_game_stats = game_boxscores[game_boxscores["TEAM_ABBREVIATION"] == team_str]
                stats_por_partido[game_id_str][team_str] = team_game_stats[available_cols].sum().to_dict()
        
        # Para cada equipo, calcular promedios defensivos
        for team in equipos_unicos:
            team_str = str(team)
            partidos_equipo = partidos_df[
                (partidos_df["LOCAL"] == team_str) | (partidos_df["VISITANTE"] == team_str)
            ].copy()
            
            if partidos_equipo.empty:
                promedios_def[team_str] = {}
                continue
            
            rival_stats = []
            for _, partido in partidos_equipo.iterrows():
                game_id_str = str(partido["GAME_ID"])
                local = str(partido["LOCAL"])
                visitante = str(partido["VISITANTE"])
                
                # Determinar el rival
                rival = visitante if local == team_str else local
                
                # Obtener estadísticas del rival desde el diccionario precalculado
                if game_id_str in stats_por_partido and rival in stats_por_partido[game_id_str]:
                    rival_stats.append(stats_por_partido[game_id_str][rival])
            
            if rival_stats:
                df_rival_stats = pd.DataFrame(rival_stats)
                promedios_def[team_str] = {}
                for col in available_cols:
                    promedios_def[team_str][col] = df_rival_stats[col].mean()
            else:
                promedios_def[team_str] = {}
    
    return promedios_of, promedios_def, desvios


def calcular_promedios_equipo(boxscores_df: pd.DataFrame, team_abbr: str) -> dict:
    """
    Calcula los promedios ofensivos y defensivos de un equipo desde los boxscores.
    Retorna un diccionario con promedios por partido.
    """
    if boxscores_df.empty or team_abbr not in boxscores_df["TEAM_ABBREVIATION"].values:
        return {}
    
    # Filtrar boxscores del equipo
    team_boxscores = boxscores_df[boxscores_df["TEAM_ABBREVIATION"] == team_abbr].copy()
    
    # Agrupar por partido y sumar estadísticas del equipo
    stats_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"]
    available_cols = [col for col in stats_cols if col in team_boxscores.columns]
    
    team_stats_per_game = team_boxscores.groupby("GAME_ID")[available_cols].sum().reset_index()
    
    # Calcular promedios
    promedios = {}
    for col in available_cols:
        promedios[col] = team_stats_per_game[col].mean()
    
    return promedios


def calcular_desvio_puntos(boxscores_df: pd.DataFrame, team_abbr: str) -> float:
    """
    Calcula el desvío estándar de los puntajes históricos de un equipo.
    """
    if boxscores_df.empty or team_abbr not in boxscores_df["TEAM_ABBREVIATION"].values:
        return 0.0
    
    # Filtrar boxscores del equipo
    team_boxscores = boxscores_df[boxscores_df["TEAM_ABBREVIATION"] == team_abbr].copy()
    
    if team_boxscores.empty or "PTS" not in team_boxscores.columns:
        return 0.0
    
    # Agrupar por partido y sumar puntos del equipo
    puntos_por_partido = team_boxscores.groupby("GAME_ID")["PTS"].sum()
    
    if len(puntos_por_partido) < 2:
        return 0.0
    
    # Calcular desvío estándar
    desvio = puntos_por_partido.std()
    
    return float(desvio) if not pd.isna(desvio) else 0.0


def calcular_probabilidad_victoria(
    pts_pred_local: float,
    pts_pred_visit: float,
    desvio_local: float,
    desvio_visit: float
) -> tuple[float, float]:
    """
    Calcula la probabilidad de victoria de cada equipo usando distribución normal.
    
    Asume que los puntajes siguen una distribución normal:
    - Local: N(pts_pred_local, desvio_local²)
    - Visitante: N(pts_pred_visit, desvio_visit²)
    
    La diferencia D = puntos_local - puntos_visit sigue:
    D ~ N(pts_pred_local - pts_pred_visit, desvio_local² + desvio_visit²)
    
    Probabilidad de que local gane = P(D > 0)
    
    Returns:
        tuple: (prob_local, prob_visit)
    """
    # Diferencia de medias
    diferencia_media = pts_pred_local - pts_pred_visit
    
    # Desvío de la diferencia (suma de varianzas)
    desvio_diferencia = np.sqrt(desvio_local**2 + desvio_visit**2)
    
    if desvio_diferencia == 0:
        # Si no hay variabilidad, la probabilidad es 1 o 0 según quién tenga más puntos
        if diferencia_media > 0:
            return 1.0, 0.0
        elif diferencia_media < 0:
            return 0.0, 1.0
        else:
            return 0.5, 0.5
    
    # Calcular probabilidad usando la distribución normal estándar
    # P(D > 0) = 1 - Φ(-diferencia_media / desvio_diferencia)
    z_score = -diferencia_media / desvio_diferencia
    prob_local = 1 - norm.cdf(z_score)
    prob_visit = 1 - prob_local
    
    return float(prob_local), float(prob_visit)


def calcular_promedios_defensivos(partidos_df: pd.DataFrame, boxscores_df: pd.DataFrame, team_abbr: str) -> dict:
    """
    Calcula los promedios defensivos de un equipo (puntos y estadísticas que recibe).
    """
    if partidos_df.empty or boxscores_df.empty:
        return {}
    
    # Obtener todos los partidos donde participó el equipo
    partidos_equipo = partidos_df[
        (partidos_df["LOCAL"] == team_abbr) | (partidos_df["VISITANTE"] == team_abbr)
    ].copy()
    
    if partidos_equipo.empty:
        return {}
    
    # Para cada partido, obtener las estadísticas del rival
    stats_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"]
    available_cols = [col for col in stats_cols if col in boxscores_df.columns]
    
    rival_stats = []
    
    for _, partido in partidos_equipo.iterrows():
        game_id = str(partido["GAME_ID"])
        local = str(partido["LOCAL"])
        visitante = str(partido["VISITANTE"])
        
        # Determinar el rival
        rival = visitante if local == team_abbr else local
        
        # Obtener estadísticas del rival en ese partido
        rival_box = boxscores_df[
            (boxscores_df["GAME_ID"].astype(str) == game_id) &
            (boxscores_df["TEAM_ABBREVIATION"] == rival)
        ]
        
        if not rival_box.empty:
            rival_game_stats = rival_box[available_cols].sum().to_dict()
            rival_stats.append(rival_game_stats)
    
    if not rival_stats:
        return {}
    
    # Calcular promedios defensivos
    df_rival_stats = pd.DataFrame(rival_stats)
    promedios_def = {}
    for col in available_cols:
        promedios_def[col] = df_rival_stats[col].mean()
    
    return promedios_def


def predecir_estadisticas_partido(
    promedios_of: dict,
    promedios_def: dict,
    team_local: str,
    team_visit: str
) -> tuple[dict, dict]:
    """
    Predice las estadísticas del partido basándose en:
    - Ofensiva del equipo local vs Defensiva del equipo visitante
    - Ofensiva del equipo visitante vs Defensiva del equipo local
    
    NOTA: Los tiros (FGM, FGA, FG3M, FG3A, FTM, FTA) NO se calculan aquí,
    se derivan de los puntos predichos en distribuir_estadisticas_jugadores.
    
    Retorna (stats_local, stats_visit)
    """
    # Obtener promedios precalculados
    of_local = promedios_of.get(team_local, {})
    of_visit = promedios_of.get(team_visit, {})
    def_local = promedios_def.get(team_local, {})
    def_visit = promedios_def.get(team_visit, {})
    
    # Predicción: promedio simple entre ofensiva propia y defensiva rival
    stats_local = {}
    stats_visit = {}
    
    # Solo calcular estadísticas básicas (no tiros)
    stats_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF"]
    
    for col in stats_cols:
        # Para el equipo local: promedio entre su ofensiva y la defensiva del visitante
        if col in of_local and col in def_visit:
            stats_local[col] = (of_local[col] + def_visit[col]) / 2
        elif col in of_local:
            stats_local[col] = of_local[col]
        elif col in def_visit:
            stats_local[col] = def_visit[col]
        else:
            stats_local[col] = 0
        
        # Para el equipo visitante: promedio entre su ofensiva y la defensiva del local
        if col in of_visit and col in def_local:
            stats_visit[col] = (of_visit[col] + def_local[col]) / 2
        elif col in of_visit:
            stats_visit[col] = of_visit[col]
        elif col in def_local:
            stats_visit[col] = def_local[col]
        else:
            stats_visit[col] = 0
    
    # Aplicar ventaja de localía: +2% para local, -2% para visitante
    for col in stats_cols:
        if stats_local[col] > 0:
            stats_local[col] = stats_local[col] * 1.02  # Sumar 2%
        if stats_visit[col] > 0:
            stats_visit[col] = stats_visit[col] * 0.98  # Restar 2%
    
    return stats_local, stats_visit


def obtener_jugadores_equipo_min_10min(boxscores_df: pd.DataFrame, jugadores_df: pd.DataFrame, team_abbr: str) -> pd.DataFrame:
    """
    Obtiene los jugadores del equipo que promedian mínimo 10 minutos.
    Solo incluye jugadores que actualmente están en el equipo según jugadores_df.
    Retorna un DataFrame con los promedios de cada jugador.
    """
    if boxscores_df.empty or jugadores_df.empty:
        return pd.DataFrame()
    
    # PRIMERO: Filtrar jugadores que actualmente están en el equipo
    if "TEAM_ABBREVIATION" in jugadores_df.columns:
        # Obtener nombres de jugadores actuales del equipo
        jugadores_actuales = jugadores_df[jugadores_df["TEAM_ABBREVIATION"] == team_abbr].copy()
        
        # Crear lista de nombres de jugadores actuales
        if "FIRST_NAME" in jugadores_actuales.columns and "LAST_NAME" in jugadores_actuales.columns:
            jugadores_actuales["PLAYER_NAME"] = (
                jugadores_actuales["FIRST_NAME"].astype(str) + " " + 
                jugadores_actuales["LAST_NAME"].astype(str)
            )
        elif "PLAYER_NAME" not in jugadores_actuales.columns:
            return pd.DataFrame()
        
        nombres_actuales = set(jugadores_actuales["PLAYER_NAME"].str.strip().str.lower())
    else:
        # Si no hay columna TEAM_ABBREVIATION, no podemos filtrar
        return pd.DataFrame()
    
    if not nombres_actuales:
        return pd.DataFrame()
    
    # Filtrar boxscores del equipo
    team_boxscores = boxscores_df[boxscores_df["TEAM_ABBREVIATION"] == team_abbr].copy()
    
    if team_boxscores.empty:
        return pd.DataFrame()
    
    # Filtrar solo jugadores que están actualmente en el equipo
    team_boxscores["PLAYER_NAME_NORM"] = team_boxscores["PLAYER_NAME"].str.strip().str.lower()
    team_boxscores = team_boxscores[team_boxscores["PLAYER_NAME_NORM"].isin(nombres_actuales)].copy()
    
    if team_boxscores.empty:
        return pd.DataFrame()
    
    # Calcular promedios por jugador
    stats_cols = ["MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV", "PF", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA"]
    available_cols = [col for col in stats_cols if col in team_boxscores.columns]
    
    if not available_cols:
        return pd.DataFrame()
    
    # Convertir MIN a numérico si es necesario
    if "MIN" in team_boxscores.columns:
        team_boxscores["MIN"] = pd.to_numeric(team_boxscores["MIN"], errors="coerce")
    
    promedios_jugadores = team_boxscores.groupby("PLAYER_NAME")[available_cols].mean().reset_index()
    
    # Filtrar jugadores con mínimo 10 minutos promedio
    if "MIN" in promedios_jugadores.columns:
        promedios_jugadores = promedios_jugadores[promedios_jugadores["MIN"] >= 10].copy()
    
    if promedios_jugadores.empty:
        return pd.DataFrame()
    
    # Agregar información del jugador si está disponible
    if "PLAYER_ID" not in promedios_jugadores.columns and "PLAYER_ID" in team_boxscores.columns:
        player_ids = team_boxscores.groupby("PLAYER_NAME")["PLAYER_ID"].first().reset_index()
        promedios_jugadores = promedios_jugadores.merge(player_ids, on="PLAYER_NAME", how="left")
    
    return promedios_jugadores


def calcular_proporciones_puntos(promedios_jugadores: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula las proporciones históricas de cómo cada jugador obtiene sus puntos:
    - Puntos de triples (FG3M * 3)
    - Puntos de libres (FTM * 1)
    - Puntos de dobles (FGM - FG3M) * 2
    """
    if promedios_jugadores.empty:
        return pd.DataFrame()
    
    props = promedios_jugadores.copy()
    
    # Calcular puntos por tipo de tiro
    if "FG3M" in props.columns:
        props["PTS_3P"] = props["FG3M"] * 3
    else:
        props["PTS_3P"] = 0
    
    if "FTM" in props.columns:
        props["PTS_FT"] = props["FTM"] * 1
    else:
        props["PTS_FT"] = 0
    
    if "FGM" in props.columns and "FG3M" in props.columns:
        props["PTS_2P"] = (props["FGM"] - props["FG3M"]) * 2
    elif "FGM" in props.columns:
        props["PTS_2P"] = props["FGM"] * 2
    else:
        props["PTS_2P"] = 0
    
    # Calcular total de puntos y proporciones
    if "PTS" in props.columns:
        total_pts = props["PTS"]
    else:
        total_pts = props["PTS_3P"] + props["PTS_FT"] + props["PTS_2P"]
    
    # Calcular proporciones (evitar división por cero)
    props["PROP_3P"] = np.where(total_pts > 0, props["PTS_3P"] / total_pts, 0)
    props["PROP_FT"] = np.where(total_pts > 0, props["PTS_FT"] / total_pts, 0)
    props["PROP_2P"] = np.where(total_pts > 0, props["PTS_2P"] / total_pts, 0)
    
    # Calcular porcentajes de tiro históricos
    if "FG3A" in props.columns and "FG3M" in props.columns:
        props["FG3_PCT"] = np.where(props["FG3A"] > 0, props["FG3M"] / props["FG3A"], 0)
    else:
        props["FG3_PCT"] = 0
    
    if "FGA" in props.columns and "FGM" in props.columns:
        if "FG3A" in props.columns and "FG3M" in props.columns:
            fga_2p = props["FGA"] - props["FG3A"]
            fgm_2p = props["FGM"] - props["FG3M"]
        else:
            fga_2p = props["FGA"]
            fgm_2p = props["FGM"]
        props["FG2_PCT"] = np.where(fga_2p > 0, fgm_2p / fga_2p, 0)
    else:
        props["FG2_PCT"] = 0
    
    if "FTA" in props.columns and "FTM" in props.columns:
        props["FT_PCT"] = np.where(props["FTA"] > 0, props["FTM"] / props["FTA"], 0)
    else:
        props["FT_PCT"] = 0
    
    return props


def distribuir_estadisticas_jugadores(
    stats_equipo: dict,
    promedios_jugadores: pd.DataFrame
) -> pd.DataFrame:
    """
    Distribuye las estadísticas del equipo entre los jugadores basándose en sus promedios.
    Los minutos deben sumar 240 (48*5).
    Los valores se mantienen en decimales.
    Los tiros (FGM, FGA, FG3M, FG3A, FTM, FTA) se calculan desde los puntos predichos.
    """
    if promedios_jugadores.empty:
        return pd.DataFrame()
    
    # Crear copia para trabajar
    pred_jugadores = promedios_jugadores.copy()
    
    # Calcular proporciones de puntos
    pred_jugadores = calcular_proporciones_puntos(pred_jugadores)
    
    # Estadísticas a distribuir (excluyendo MIN y tiros que se manejan por separado)
    stats_cols = ["PTS", "REB", "AST", "STL", "BLK", "TOV", "PF"]
    available_stats = [col for col in stats_cols if col in pred_jugadores.columns and col in stats_equipo]
    
    # Calcular proporciones basadas en la suma de los promedios de los jugadores
    for stat in available_stats:
        if stat in pred_jugadores.columns:
            suma_promedios = pred_jugadores[stat].sum()
            if suma_promedios > 0:
                # Calcular proporción de cada jugador
                pred_jugadores[f"{stat}_prop"] = pred_jugadores[stat] / suma_promedios
                # Distribuir estadística predicha
                pred_jugadores[f"{stat}_pred"] = pred_jugadores[f"{stat}_prop"] * stats_equipo[stat]
            else:
                pred_jugadores[f"{stat}_pred"] = 0.0
    
    # Asegurar que la suma de cada estadística sea exactamente igual a stats_equipo
    for stat in available_stats:
        if stat in stats_equipo and f"{stat}_pred" in pred_jugadores.columns:
            suma_actual = pred_jugadores[f"{stat}_pred"].sum()
            objetivo = stats_equipo[stat]
            if abs(suma_actual - objetivo) > 0.001:
                diferencia = objetivo - suma_actual
                if len(pred_jugadores) > 0:
                    pred_jugadores.loc[pred_jugadores.index[-1], f"{stat}_pred"] += diferencia
    
    # Calcular tiros desde los puntos predichos
    if "PTS_pred" in pred_jugadores.columns:
        # Distribuir puntos por tipo
        pred_jugadores["PTS_3P_pred"] = pred_jugadores["PTS_pred"] * pred_jugadores["PROP_3P"]
        pred_jugadores["PTS_FT_pred"] = pred_jugadores["PTS_pred"] * pred_jugadores["PROP_FT"]
        pred_jugadores["PTS_2P_pred"] = pred_jugadores["PTS_pred"] * pred_jugadores["PROP_2P"]
        
        # Calcular tiros metidos
        pred_jugadores["FG3M_pred"] = pred_jugadores["PTS_3P_pred"] / 3.0
        pred_jugadores["FTM_pred"] = pred_jugadores["PTS_FT_pred"] / 1.0
        pred_jugadores["FGM_2P_pred"] = pred_jugadores["PTS_2P_pred"] / 2.0
        pred_jugadores["FGM_pred"] = pred_jugadores["FGM_2P_pred"] + pred_jugadores["FG3M_pred"]
        
        # Calcular tiros intentados basándose en porcentajes históricos
        pred_jugadores["FG3A_pred"] = np.where(
            pred_jugadores["FG3_PCT"] > 0,
            pred_jugadores["FG3M_pred"] / pred_jugadores["FG3_PCT"],
            0.0
        )
        pred_jugadores["FTA_pred"] = np.where(
            pred_jugadores["FT_PCT"] > 0,
            pred_jugadores["FTM_pred"] / pred_jugadores["FT_PCT"],
            0.0
        )
        pred_jugadores["FGA_2P_pred"] = np.where(
            pred_jugadores["FG2_PCT"] > 0,
            pred_jugadores["FGM_2P_pred"] / pred_jugadores["FG2_PCT"],
            0.0
        )
        pred_jugadores["FGA_pred"] = pred_jugadores["FGA_2P_pred"] + pred_jugadores["FG3A_pred"]
    
    # Distribuir minutos: deben sumar 240
    if "MIN" in pred_jugadores.columns:
        suma_min_promedios = pred_jugadores["MIN"].sum()
        if suma_min_promedios > 0:
            # Calcular proporción de minutos
            pred_jugadores["MIN_prop"] = pred_jugadores["MIN"] / suma_min_promedios
            # Distribuir 240 minutos
            pred_jugadores["MIN_pred"] = pred_jugadores["MIN_prop"] * 240.0
        else:
            # Si no hay minutos, distribuir equitativamente
            n_jugadores = len(pred_jugadores)
            if n_jugadores > 0:
                pred_jugadores["MIN_pred"] = 240.0 / n_jugadores
            else:
                pred_jugadores["MIN_pred"] = 0.0
        
        # Asegurar que la suma sea exactamente 240 (ajustar el último jugador si es necesario)
        suma_actual = pred_jugadores["MIN_pred"].sum()
        if abs(suma_actual - 240.0) > 0.001:
            diferencia = 240.0 - suma_actual
            # Ajustar el último jugador
            if len(pred_jugadores) > 0:
                pred_jugadores.loc[pred_jugadores.index[-1], "MIN_pred"] += diferencia
    
    # Crear DataFrame final con las predicciones
    resultado = pd.DataFrame()
    resultado["PLAYER_NAME"] = pred_jugadores["PLAYER_NAME"]
    
    # Agregar MIN predicho (en decimales)
    if "MIN_pred" in pred_jugadores.columns:
        resultado["MIN"] = pred_jugadores["MIN_pred"]
    
    # Agregar estadísticas predichas (en decimales)
    for stat in available_stats:
        if f"{stat}_pred" in pred_jugadores.columns:
            resultado[stat] = pred_jugadores[f"{stat}_pred"]
    
    # Agregar tiros predichos (en decimales)
    if "FGM_pred" in pred_jugadores.columns:
        resultado["FGM"] = pred_jugadores["FGM_pred"]
    if "FGA_pred" in pred_jugadores.columns:
        resultado["FGA"] = pred_jugadores["FGA_pred"]
    if "FG3M_pred" in pred_jugadores.columns:
        resultado["FG3M"] = pred_jugadores["FG3M_pred"]
    if "FG3A_pred" in pred_jugadores.columns:
        resultado["FG3A"] = pred_jugadores["FG3A_pred"]
    if "FTM_pred" in pred_jugadores.columns:
        resultado["FTM"] = pred_jugadores["FTM_pred"]
    if "FTA_pred" in pred_jugadores.columns:
        resultado["FTA"] = pred_jugadores["FTA_pred"]
    
    # Agregar PLAYER_ID si está disponible
    if "PLAYER_ID" in pred_jugadores.columns:
        resultado["PLAYER_ID"] = pred_jugadores["PLAYER_ID"]
    
    return resultado


def predecir_boxscore_completo(
    boxscores_df: pd.DataFrame,
    jugadores_df: pd.DataFrame,
    promedios_of: dict,
    promedios_def: dict,
    team_local: str,
    team_visit: str
) -> tuple[pd.DataFrame, dict, dict]:
    """
    Predice el boxscore completo del partido usando datos precalculados.
    Retorna (boxscore_predicho, stats_local, stats_visit)
    """
    # Predecir estadísticas por equipo usando datos precalculados
    stats_local, stats_visit = predecir_estadisticas_partido(
        promedios_of, promedios_def, team_local, team_visit
    )
    
    # Obtener jugadores con mínimo 10 minutos
    jugadores_local = obtener_jugadores_equipo_min_10min(boxscores_df, jugadores_df, team_local)
    jugadores_visit = obtener_jugadores_equipo_min_10min(boxscores_df, jugadores_df, team_visit)
    
    # Limitar a los 12 jugadores con más minutos promedio (si hay más de 12)
    if not jugadores_local.empty and "MIN" in jugadores_local.columns:
        jugadores_local = jugadores_local.sort_values("MIN", ascending=False).head(12)
    if not jugadores_visit.empty and "MIN" in jugadores_visit.columns:
        jugadores_visit = jugadores_visit.sort_values("MIN", ascending=False).head(12)
    
    # Distribuir estadísticas entre jugadores
    boxscore_local = distribuir_estadisticas_jugadores(stats_local, jugadores_local)
    boxscore_visit = distribuir_estadisticas_jugadores(stats_visit, jugadores_visit)
    
    # Agregar TEAM_ABBREVIATION
    if not boxscore_local.empty:
        boxscore_local["TEAM_ABBREVIATION"] = team_local
    if not boxscore_visit.empty:
        boxscore_visit["TEAM_ABBREVIATION"] = team_visit
    
    # Combinar ambos equipos
    if not boxscore_local.empty and not boxscore_visit.empty:
        boxscore_completo = pd.concat([boxscore_local, boxscore_visit], ignore_index=True)
    elif not boxscore_local.empty:
        boxscore_completo = boxscore_local.copy()
    elif not boxscore_visit.empty:
        boxscore_completo = boxscore_visit.copy()
    else:
        boxscore_completo = pd.DataFrame()
    
    return boxscore_completo, stats_local, stats_visit


def predecir_puntos_rapido(
    promedios_of: dict,
    promedios_def: dict,
    team_local: str,
    team_visit: str
) -> tuple[float, float]:
    """
    Predice solo los puntos de un partido de forma rápida usando datos precalculados.
    Retorna (pts_local, pts_visit)
    """
    # Obtener promedios precalculados
    of_local = promedios_of.get(team_local, {})
    of_visit = promedios_of.get(team_visit, {})
    def_local = promedios_def.get(team_local, {})
    def_visit = promedios_def.get(team_visit, {})
    
    # Predicción: promedio simple
    pts_local = 0.0
    pts_visit = 0.0
    
    if "PTS" in of_local and "PTS" in def_visit:
        pts_local = (of_local["PTS"] + def_visit["PTS"]) / 2
    elif "PTS" in of_local:
        pts_local = of_local["PTS"]
    elif "PTS" in def_visit:
        pts_local = def_visit["PTS"]
    
    if "PTS" in of_visit and "PTS" in def_local:
        pts_visit = (of_visit["PTS"] + def_local["PTS"]) / 2
    elif "PTS" in of_visit:
        pts_visit = of_visit["PTS"]
    elif "PTS" in def_local:
        pts_visit = def_local["PTS"]
    
    # Aplicar ventaja de localía: +2% para local, -2% para visitante
    if pts_local > 0:
        pts_local = pts_local * 1.02  # Sumar 2%
    if pts_visit > 0:
        pts_visit = pts_visit * 0.98  # Restar 2%
    
    return float(pts_local), float(pts_visit)


def calcular_record_actual(partidos_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula el record actual de cada equipo (PJ, PG, PP).
    """
    if partidos_df.empty:
        return pd.DataFrame()
    
    # Verificar columnas necesarias
    c_loc = None
    c_vis = None
    c_pl = None
    c_pv = None
    
    for col in partidos_df.columns:
        if col.upper() in ["LOCAL", "HOME"]:
            c_loc = col
        elif col.upper() in ["VISITANTE", "AWAY", "VISITOR"]:
            c_vis = col
        elif col.upper() in ["PTS_LOCAL", "HOME_PTS"]:
            c_pl = col
        elif col.upper() in ["PTS_VISITANTE", "AWAY_PTS", "VISITOR_PTS"]:
            c_pv = col
    
    if not all([c_loc, c_vis, c_pl, c_pv]):
        return pd.DataFrame()
    
    # Crear filas para local y visitante
    home = partidos_df.assign(
        TEAM=partidos_df[c_loc],
        WIN=(partidos_df[c_pl] > partidos_df[c_pv]).astype(int),
        LOSS=(partidos_df[c_pl] < partidos_df[c_pv]).astype(int)
    )[["TEAM", "WIN", "LOSS"]]
    
    away = partidos_df.assign(
        TEAM=partidos_df[c_vis],
        WIN=(partidos_df[c_pv] > partidos_df[c_pl]).astype(int),
        LOSS=(partidos_df[c_pv] < partidos_df[c_pl]).astype(int)
    )[["TEAM", "WIN", "LOSS"]]
    
    # Combinar y agregar
    all_games = pd.concat([home, away], ignore_index=True)
    record = all_games.groupby("TEAM", as_index=False).agg(
        PJ=("WIN", "count"),
        PG=("WIN", "sum"),
        PP=("LOSS", "sum")
    )
    
    return record


def predecir_temporada_completa(
    partidos_df: pd.DataFrame,
    partidos_futuros_df: pd.DataFrame,
    promedios_of: dict,
    promedios_def: dict,
    desvios: dict
) -> pd.DataFrame:
    """
    Predice la temporada completa sumando probabilidades de victoria de partidos futuros.
    Usa datos precalculados para mayor velocidad.
    Retorna tabla de posiciones final predicha.
    """
    if partidos_futuros_df.empty:
        return pd.DataFrame()
    
    # Calcular record actual
    record_actual = calcular_record_actual(partidos_df)
    
    # Inicializar record predicho con el actual
    if not record_actual.empty:
        record_predicho = record_actual.copy()
    else:
        # Si no hay partidos jugados, inicializar con ceros
        equipos_unicos = set()
        if "LOCAL" in partidos_futuros_df.columns:
            equipos_unicos.update(partidos_futuros_df["LOCAL"].dropna())
        if "VISITANTE" in partidos_futuros_df.columns:
            equipos_unicos.update(partidos_futuros_df["VISITANTE"].dropna())
        
        record_predicho = pd.DataFrame({
            "TEAM": list(equipos_unicos),
            "PJ": 0,
            "PG": 0,
            "PP": 0
        })
    
    # Crear diccionario para acceso rápido
    record_dict = {}
    for _, row in record_predicho.iterrows():
        team = str(row["TEAM"])
        record_dict[team] = {
            "PJ": int(row["PJ"]),
            "PG": float(row["PG"]),
            "PP": float(row["PP"])
        }
    
    # Procesar cada partido futuro
    for _, partido in partidos_futuros_df.iterrows():
        local = str(partido.get("LOCAL", ""))
        visitante = str(partido.get("VISITANTE", ""))
        
        if not local or not visitante or local == "None" or visitante == "None":
            continue
        
        # Predecir puntos usando datos precalculados
        pts_local, pts_visit = predecir_puntos_rapido(
            promedios_of, promedios_def, local, visitante
        )
        
        # Obtener desvíos precalculados
        desvio_local = desvios.get(local, 0.0)
        desvio_visit = desvios.get(visitante, 0.0)
        
        # Calcular probabilidades
        prob_local, prob_visit = calcular_probabilidad_victoria(
            pts_local, pts_visit, desvio_local, desvio_visit
        )
        
        # Agregar probabilidades al record
        if local not in record_dict:
            record_dict[local] = {"PJ": 0, "PG": 0.0, "PP": 0.0}
        if visitante not in record_dict:
            record_dict[visitante] = {"PJ": 0, "PG": 0.0, "PP": 0.0}
        
        record_dict[local]["PJ"] += 1
        record_dict[local]["PG"] += prob_local
        record_dict[local]["PP"] += prob_visit
        
        record_dict[visitante]["PJ"] += 1
        record_dict[visitante]["PG"] += prob_visit
        record_dict[visitante]["PP"] += prob_local
    
    # Convertir a DataFrame
    record_final = pd.DataFrame([
        {
            "TEAM": team,
            "PJ": record_dict[team]["PJ"],
            "PG": record_dict[team]["PG"],
            "PP": record_dict[team]["PP"]
        }
        for team in record_dict
    ])
    
    return record_final


def construir_tabla_posiciones_final(
    record_predicho: pd.DataFrame,
    equipos_df: pd.DataFrame
) -> dict:
    """
    Construye la tabla de posiciones final ordenada dividida por conferencia.
    Retorna un diccionario con 'East' y 'West', cada uno con un DataFrame.
    """
    if record_predicho.empty:
        return {"East": pd.DataFrame(), "West": pd.DataFrame()}
    
    tabla = record_predicho.copy()
    
    # Agregar nombres de equipos
    if not equipos_df.empty and "TEAM_NAME" in equipos_df.columns:
        tabla = tabla.merge(
            equipos_df[["TEAM_ABBREVIATION", "TEAM_NAME"]].drop_duplicates(),
            left_on="TEAM",
            right_on="TEAM_ABBREVIATION",
            how="left"
        )
        tabla["Equipo"] = tabla["TEAM_NAME"].fillna(tabla["TEAM"])
    else:
        tabla["Equipo"] = tabla["TEAM"]
    
    # Agregar conferencia
    if "CONFERENCE" in equipos_df.columns:
        tabla = tabla.merge(
            equipos_df[["TEAM_ABBREVIATION", "CONFERENCE"]].drop_duplicates(),
            left_on="TEAM",
            right_on="TEAM_ABBREVIATION",
            how="left"
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
    
    # Ordenar por W (victorias predichas) descendente
    east = east.sort_values("W", ascending=False).reset_index(drop=True)
    west = west.sort_values("W", ascending=False).reset_index(drop=True)
    
    # Agregar número de posición
    east.insert(0, "#", range(1, len(east) + 1))
    west.insert(0, "#", range(1, len(west) + 1))
    
    # Formatear columnas
    east["W"] = east["W"].round(1)
    east["L"] = east["L"].round(1)
    
    west["W"] = west["W"].round(1)
    west["L"] = west["L"].round(1)
    
    # Seleccionar columnas finales (sin PJ)
    east = east[["#", "Equipo", "W", "L"]].copy()
    west = west[["#", "Equipo", "W", "L"]].copy()
    
    return {"East": east, "West": west}


# ==============================================================
# UI
# ==============================================================

st.title("🔮 Predicciones")

# Precalcular todos los promedios una sola vez
with st.spinner("Precalculando estadísticas de equipos..."):
    promedios_ofensivos, promedios_defensivos, desvios_puntos = precalcular_todos_promedios(
        partidos, boxscores
    )

if partidos_futuros.empty:
    st.info("No hay partidos futuros disponibles para predecir.")
    st.stop()

# Tabs para partido individual y temporada completa
tab1, tab2 = st.tabs(["📊 Predicción de Partido", "🏆 Predicción de Temporada"])

with tab1:
    # Seleccionar partido futuro
    st.subheader("Seleccionar Partido")
    
    # Preparar opciones de partidos futuros
    partidos_futuros_display = partidos_futuros.copy()
    if "FECHA" in partidos_futuros_display.columns:
        partidos_futuros_display["FECHA"] = pd.to_datetime(partidos_futuros_display["FECHA"], errors="coerce")
        partidos_futuros_display = partidos_futuros_display.sort_values("FECHA")

    # Crear string de display para cada partido
    def format_partido(row):
        fecha_str = ""
        if "FECHA" in row and pd.notna(row["FECHA"]):
            try:
                fecha_str = pd.to_datetime(row["FECHA"]).strftime("%d/%m/%Y")
            except:
                fecha_str = str(row["FECHA"])
        
        local = str(row.get("LOCAL", ""))
        visitante = str(row.get("VISITANTE", ""))
        game_id = str(row.get("GAME_ID", ""))
        
        return f"{fecha_str} - {local} vs {visitante} ({game_id})"

    partidos_futuros_display["display"] = partidos_futuros_display.apply(format_partido, axis=1)

    # Selector de partido
    opciones_partidos = [""] + partidos_futuros_display["display"].tolist()
    partido_seleccionado = st.selectbox(
        "Elegir partido futuro",
        opciones_partidos,
        index=0
    )

    if not partido_seleccionado:
        st.info("Selecciona un partido para ver la predicción.")
    else:
        # Extraer información del partido seleccionado
        idx_seleccionado = opciones_partidos.index(partido_seleccionado) - 1
        partido_row = partidos_futuros_display.iloc[idx_seleccionado]

        game_id = str(partido_row["GAME_ID"])
        team_local = str(partido_row["LOCAL"])
        team_visit = str(partido_row["VISITANTE"])
        fecha = partido_row.get("FECHA", "")

        # Mostrar información del partido
        st.markdown("---")
        st.subheader(f"📊 Predicción: {team_local} vs {team_visit}")

        if pd.notna(fecha):
            try:
                fecha_str = pd.to_datetime(fecha).strftime("%d de %B de %Y")
                st.caption(f"Fecha programada: {fecha_str}")
            except:
                st.caption(f"Fecha programada: {fecha}")

        # Calcular predicción
        with st.spinner("Calculando predicción..."):
            try:
                boxscore_pred, stats_local, stats_visit = predecir_boxscore_completo(
                    boxscores, jugadores, promedios_ofensivos, promedios_defensivos, team_local, team_visit
                )
                
                if boxscore_pred.empty:
                    st.warning("No se pudieron calcular las predicciones. Verifica que haya suficientes datos históricos.")
                else:
                    # Obtener desvíos precalculados y calcular probabilidades
                    desvio_local = desvios_puntos.get(team_local, 0.0)
                    desvio_visit = desvios_puntos.get(team_visit, 0.0)
                    
                    pts_local_pred = stats_local.get("PTS", 0)
                    pts_visit_pred = stats_visit.get("PTS", 0)
                    
                    prob_local, prob_visit = calcular_probabilidad_victoria(
                        pts_local_pred, pts_visit_pred, desvio_local, desvio_visit
                    )
                    
                    # Mostrar resultado predicho
                    st.markdown("### Resultado Predicho")
                    col1, col2, col3 = st.columns([2, 1, 2])
                    with col1:
                        st.markdown(f"### {team_local}")
                        st.markdown(f"## {pts_local_pred:.1f}")
                        st.markdown(f"**Probabilidad de victoria: {prob_local*100:.1f}%**")
                    with col2:
                        st.markdown("## vs")
                    with col3:
                        st.markdown(f"### {team_visit}")
                        st.markdown(f"## {pts_visit_pred:.1f}")
                        st.markdown(f"**Probabilidad de victoria: {prob_visit*100:.1f}%**")
                    
                    # Mostrar boxscore predicho
                    st.markdown("---")
                    st.subheader("Boxscore Predicho")
                    
                    # Filtro de equipo
                    choice = st.segmented_control(
                        "Equipo",
                        options=[team_local, team_visit, "Ambos"],
                        default="Ambos"
                    )
                    
                    df_show = boxscore_pred.copy()
                    
                    if choice == team_local:
                        df_show = df_show[df_show["TEAM_ABBREVIATION"] == team_local]
                    elif choice == team_visit:
                        df_show = df_show[df_show["TEAM_ABBREVIATION"] == team_visit]
                    
                    # Preparar columnas para mostrar
                    cols_show = [c for c in [
                        "PLAYER_NAME", "MIN", "PTS", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA",
                        "REB", "AST", "STL", "BLK", "TOV", "PF"
                    ] if c in df_show.columns]
                    
                    df_display = df_show[cols_show].copy()
                    
                    # Ordenar por puntos antes de formatear
                    if "PTS" in df_display.columns:
                        df_display = df_display.sort_values("PTS", ascending=False)
                    
                    # Renombrar columnas para display
                    rename_map = {
                        "PLAYER_NAME": "Jugador",
                        "MIN": "MIN",
                        "PTS": "PTS",
                        "FGM": "FGM",
                        "FGA": "FGA",
                        "FG3M": "3PM",
                        "FG3A": "3PA",
                        "FTM": "FTM",
                        "FTA": "FTA",
                        "REB": "REB",
                        "AST": "AST",
                        "STL": "STL",
                        "BLK": "BLK",
                        "TOV": "TOV",
                        "PF": "PF"
                    }
                    df_display = df_display.rename(columns=rename_map)
                    
                    # Formatear MIN en formato mm:ss
                    if "MIN" in df_display.columns:
                        # Convertir a float primero si es string
                        if df_display["MIN"].dtype == 'object':
                            df_display["MIN"] = pd.to_numeric(df_display["MIN"], errors='coerce')
                        df_display["MIN"] = df_display["MIN"].apply(
                            lambda x: minutos_decimal_a_mmss(x) if pd.notna(x) else "0:00"
                        )
                    
                    # Formatear valores numéricos para mostrar con 2 decimales (excluyendo MIN)
                    numeric_cols = ["PTS", "FGM", "FGA", "3PM", "3PA", "FTM", "FTA", 
                                   "REB", "AST", "STL", "BLK", "TOV", "PF"]
                    for col in numeric_cols:
                        if col in df_display.columns:
                            # Convertir a float primero si es string
                            if df_display[col].dtype == 'object':
                                df_display[col] = pd.to_numeric(df_display[col], errors='coerce')
                            df_display[col] = df_display[col].apply(
                                lambda x: f"{float(x):.2f}" if pd.notna(x) else "0.00"
                            )
                    
                    # Mostrar tabla
                    height = 48 + 32 * len(df_display)
                    st.dataframe(
                        df_display.set_index("Jugador"),
                        use_container_width=True,
                        height=height
                    )
                    
                    # Mostrar estadísticas del equipo
                    st.markdown("---")
                    st.subheader("Estadísticas del Equipo (Predichas)")
                    
                    col_local, col_visit = st.columns(2)
                    
                    with col_local:
                        st.markdown(f"### {team_local}")
                        stats_local_df = pd.DataFrame([stats_local]).T
                        stats_local_df.columns = ["Valor"]
                        stats_local_df.index.name = "Estadística"
                        # Formatear valores con 2 decimales
                        stats_local_df["Valor"] = stats_local_df["Valor"].apply(
                            lambda x: f"{float(x):.2f}" if pd.notna(x) else "0.00"
                        )
                        st.dataframe(stats_local_df, use_container_width=True)
                    
                    with col_visit:
                        st.markdown(f"### {team_visit}")
                        stats_visit_df = pd.DataFrame([stats_visit]).T
                        stats_visit_df.columns = ["Valor"]
                        stats_visit_df.index.name = "Estadística"
                        # Formatear valores con 2 decimales
                        stats_visit_df["Valor"] = stats_visit_df["Valor"].apply(
                            lambda x: f"{float(x):.2f}" if pd.notna(x) else "0.00"
                        )
                        st.dataframe(stats_visit_df, use_container_width=True)
            
            except Exception as e:
                st.error(f"Error al calcular la predicción: {str(e)}")
                import traceback
                with st.expander("Detalles del error"):
                    st.code(traceback.format_exc())

with tab2:
    st.subheader("🏆 Predicción de Temporada Completa")
    st.markdown("Calculando predicciones para todos los partidos futuros y proyectando la tabla de posiciones final...")
    
    with st.spinner("Calculando predicciones de temporada completa..."):
        try:
            # Calcular predicciones de temporada usando datos precalculados
            record_predicho = predecir_temporada_completa(
                partidos, partidos_futuros, promedios_ofensivos, promedios_defensivos, desvios_puntos
            )
            
            if record_predicho.empty:
                st.warning("No se pudieron calcular las predicciones de temporada.")
            else:
                # Construir tabla de posiciones final dividida por conferencia
                tablas_final = construir_tabla_posiciones_final(record_predicho, equipos)
                
                if not tablas_final["East"].empty or not tablas_final["West"].empty:
                    st.markdown("### Tabla de Posiciones Final (Predicha)")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("🏀 Eastern Conference")
                        if not tablas_final["East"].empty:
                            st.dataframe(tablas_final["East"], use_container_width=True, hide_index=True)
                        else:
                            st.info("No hay datos disponibles")
                    
                    with col2:
                        st.subheader("🏀 Western Conference")
                        if not tablas_final["West"].empty:
                            st.dataframe(tablas_final["West"], use_container_width=True, hide_index=True)
                        else:
                            st.info("No hay datos disponibles")
                    
                else:
                    st.warning("No se pudo construir la tabla de posiciones.")
        except Exception as e:
            st.error(f"Error al calcular las predicciones de temporada: {str(e)}")
            import traceback
            with st.expander("Detalles del error"):
                st.code(traceback.format_exc())
