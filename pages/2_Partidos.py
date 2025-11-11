# pages/3_Partidos.py

import math
import itertools
import calendar
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from utils import load_data, check_auth, init_session_state, minutos_decimal_a_mmss

st.set_page_config(page_title="Partidos | NBA Stats App", layout="wide")

# Inicializar estado de sesión
init_session_state()

partidos, _, boxscores, equipos, _ = load_data()
ss = st.session_state
ss.setdefault("game_sel", "")
ss.setdefault("selected_date", None)
ss.setdefault("calendar_year", None)
ss.setdefault("calendar_month", None)

st.title("📅 Partidos por calendario")

# ---------- helpers ----------
def _col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    return None

def get_team_logo(equipos_df: pd.DataFrame, abbr: str):
    """
    Devuelve la URL del logo para el TEAM_ABBREVIATION dado.
    Usa LOGO_URL si existe. Si no hay, devuelve None.
    """
    if equipos_df is None or equipos_df.empty:
        return None
    if "TEAM_ABBREVIATION" not in equipos_df.columns:
        return None
    if "LOGO_URL" in equipos_df.columns:
        sub = equipos_df.loc[equipos_df["TEAM_ABBREVIATION"] == abbr, "LOGO_URL"]
        if not sub.empty:
            url = str(sub.iloc[0]).strip()
            if url:
                return url
    return None

def preparar_partidos(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas, asegura tipos y crea FECHA_DATE (date)."""
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()
    c_game  = _col(df, "GAME_ID", "game_id")
    c_fecha = _col(df, "FECHA", "fecha", "DATE", "date")
    c_loc   = _col(df, "LOCAL", "home", "HOME")
    c_vis   = _col(df, "VISITANTE", "away", "AWAY")
    c_pl    = _col(df, "PTS_LOCAL", "HOME_PTS")
    c_pv    = _col(df, "PTS_VISITANTE", "AWAY_PTS")
    if any(c is None for c in [c_game, c_fecha, c_loc, c_vis, c_pl, c_pv]):
        return pd.DataFrame()

    df = df[[c_game, c_fecha, c_loc, c_vis, c_pl, c_pv]].copy()
    df.columns = ["GAME_ID", "FECHA", "LOCAL", "VISITANTE", "PTS_LOCAL", "PTS_VISITANTE"]

    df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")
    df = df[df["FECHA"].notna()].copy()
    df["FECHA_DATE"] = df["FECHA"].dt.date

    df["PTS_LOCAL"] = pd.to_numeric(df["PTS_LOCAL"], errors="coerce").fillna(0).astype(int)
    df["PTS_VISITANTE"] = pd.to_numeric(df["PTS_VISITANTE"], errors="coerce").fillna(0).astype(int)
    df["MARCADOR"] = df["PTS_LOCAL"].astype(str) + " - " + df["PTS_VISITANTE"].astype(str)

    df = df.sort_values(["FECHA", "GAME_ID"]).reset_index(drop=True)
    return df

# ---------- standings global MODIFICADO ----------
def _build_standings_upto(df_games: pd.DataFrame, equipos_df: pd.DataFrame, fecha_corte, game_id_excluir=None) -> pd.DataFrame:
    if df_games is None or df_games.empty:
        return pd.DataFrame()

    df = df_games.copy()
    c_fecha = _col(df, "FECHA","fecha","DATE","date")
    c_loc   = _col(df, "LOCAL","home","HOME")
    c_vis   = _col(df, "VISITANTE","away","AWAY")
    c_pl    = _col(df, "PTS_LOCAL","pts_local","HOME_PTS")
    c_pv    = _col(df, "PTS_VISITANTE","pts_visitante","AWAY_PTS")
    c_gameid = _col(df, "GAME_ID", "game_id")
    if not all([c_fecha, c_loc, c_vis, c_pl, c_pv, c_gameid]):
        return pd.DataFrame()

    df[c_fecha] = pd.to_datetime(df[c_fecha], errors="coerce")
    if fecha_corte is not None:
        # quedate SOLO con partidos anteriores al partido seleccionado
        df = df[df[c_fecha] < fecha_corte]
    if game_id_excluir is not None:
        df = df[df[c_gameid] != game_id_excluir]

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

    # Últimos 5 partidos HASTA fecha_corte, NO incluyas partido seleccionado
    all_rows = all_rows.sort_values(c_fecha)
    last_all = {t: [] for t in tabla["ABBR"]}
    for _, r in all_rows.iterrows():
        abbr = r["ABBR"]
        res = "W" if r["WIN"] else "L"
        last_all[abbr].append(res)

    def take_last5(seq):
        tail = seq[-5:] if len(seq) >= 5 else seq
        tail = ([""] * (5 - len(tail))) + tail
        return tail

    tabla["last5"] = tabla["ABBR"].map(lambda t: take_last5(last_all.get(t, [])))

    if equipos_df is not None and not equipos_df.empty and "TEAM_NAME" in equipos_df.columns:
        tabla = tabla.merge(
            equipos_df[["TEAM_ABBREVIATION","TEAM_NAME"]].drop_duplicates(),
            left_on="ABBR", right_on="TEAM_ABBREVIATION", how="left"
        )
        tabla["Equipo"] = tabla["TEAM_NAME"].fillna(tabla["ABBR"])
    else:
        tabla["Equipo"] = tabla["ABBR"]

    tabla = tabla.sort_values(by=["PG","DIF"], ascending=[False, False]).reset_index(drop=True)
    tabla.insert(0, "#", range(1, len(tabla) + 1))
    return tabla[["#","ABBR","Equipo","PJ","PG","PP","DIF","last5"]]


def _render_prematch_card(tabla: pd.DataFrame, t_local: str, t_visit: str):
    if tabla.empty or not t_local or not t_visit:
        return

    sub = tabla[tabla["ABBR"].isin([t_local, t_visit])].copy()
    sub = sub.sort_values("#")

    st.markdown("""
    <style>
      .pm-card{background:#0f1520;border:1px solid #223049;border-radius:16px;padding:14px 16px;}
      .pm-title{font-weight:800;font-size:20px;margin-bottom:6px;}
      .pm-table{width:100%;border-collapse:separate;border-spacing:0 10px;}
      .pm-th{color:#cfd9e6;font-weight:700;text-align:left;padding:4px 6px;}
      .pm-td{color:#e6eef6;font-weight:600;padding:8px 6px;vertical-align:middle;}
      .pm-row{background:#121a27;border:1px solid #223049;border-radius:10px;}
      .pm-badges{display:inline-flex;gap:6px;}
      .pm-pill{display:inline-flex;align-items:center;justify-content:center;
               border-radius:6px;padding:2px 10px;height:22px;color:#fff;font-weight:800}
      .pm-w{background:#1f6f3f;}
      .pm-l{background:#8e2727;}
      .pm-n{background:#6b7280;}
      .pm-gp{font-weight:800;}
    </style>
    """, unsafe_allow_html=True)

    def pills(vals):
        out = []
        for v in vals:
            cls = "pm-n"; txt = ""
            if v == "W": cls, txt = "pm-w", "V"
            elif v == "L": cls, txt = "pm-l", "D"
            out.append(f"<span class='pm-pill {cls}'>{txt}</span>")
        return "".join(out)

    rows = []
    for _, r in sub.iterrows():
        rows.append(
            f"<tr class='pm-row'>"
            f"<td class='pm-td' style='width:40px;text-align:center;'>{int(r['#'])}</td>"
            f"<td class='pm-td' style='width:120px;'>{r['ABBR']}</td>"
            f"<td class='pm-td'><div class='pm-badges'>{pills(r['last5'])}</div></td>"
            f"<td class='pm-td pm-gp' style='width:70px;text-align:right;'>{int(r['PG'])}-{int(r['PP'])}</td>"
            f"</tr>"
        )

    html = (
        "<div class='pm-card'>"
        "<div class='pm-title'>Clasificación pre-partido</div>"
        "<table class='pm-table'>"
        "<thead><tr>"
        "<th class='pm-th' style='width:40px;'>#</th>"
        "<th class='pm-th' style='width:120px;'>Equipo</th>"
        "<th class='pm-th'>Último</th>"
        "<th class='pm-th' style='width:70px;text-align:right;'>G-P</th>"
        "</tr></thead>"
        "<tbody>"
        + "".join(rows) +
        "</tbody></table></div>"
    )
    st.markdown(html, unsafe_allow_html=True)

# ---------- render boxscore ----------
def render_boxscore_inline(game_id: str, partidos_df: pd.DataFrame):
    if boxscores is None or boxscores.empty:
        st.warning("No hay boxscores disponibles.")
        return

    p = partidos_df
    row = p[p["GAME_ID"].astype(str) == str(game_id)].head(1)

    header_txt = f"Partido {game_id}"
    team_local = ""
    team_visit = ""
    fecha = None
    if not row.empty:
        fecha = row.iloc[0]["FECHA"]
        ftxt = fecha.strftime("%d %b %Y") if pd.notna(fecha) else ""
        team_local = str(row.iloc[0]["LOCAL"])
        team_visit = str(row.iloc[0]["VISITANTE"])
        pl = int(row.iloc[0]["PTS_LOCAL"])
        pv = int(row.iloc[0]["PTS_VISITANTE"])
        header_txt = f"**{team_local} {pl} – {pv} {team_visit}** · {ftxt}"

    st.markdown("---")
    st.markdown(f"### 📊 {header_txt}")

    df_game = boxscores[boxscores["GAME_ID"].astype(str) == str(game_id)].copy()
    if df_game.empty:
        st.info("No se encontraron estadísticas para este partido.")
        if st.button("⬅ Volver al calendario"):
            ss["game_sel"] = ""
            st.rerun()
        return

    # Ya NO mostramos gráfico de diferencia de puntos

    # Solo mini tabla de los últimos 5 partidos de cada equipo (previos al partido seleccionado)
    c_left, c_right = st.columns([1, 1.4])

    with c_left:
        # Solo card mini tabla ultimos 5 de cada equipo HASTA fecha del partido, sin ese partido
        if team_local and team_visit and fecha is not None:
            tabla = _build_standings_upto(partidos_df, equipos, fecha, game_id_excluir=game_id)
            _render_prematch_card(tabla, team_local, team_visit)
        else:
            st.info("No se puede mostrar la mini tabla para este partido.")

    # Derecha: boxscore filtrable
    with c_right:
        choice = st.segmented_control(
            "Equipo",
            options=[team_local or "Local", team_visit or "Visitante", "Ambos"],
            default="Ambos"
        )

        df = df_game.copy()
        cols_show = [c for c in [
            "PLAYER_NAME","MIN","PTS","FGM","FGA","FG3M","FG3A","FTM","FTA",
            "REB","AST","STL","BLK","TOV","PF","PLUS_MINUS"
        ] if c in df.columns]

        if choice == (team_local or "Local"):
            df = df[df["TEAM_ABBREVIATION"] == team_local]
        elif choice == (team_visit or "Visitante"):
            df = df[df["TEAM_ABBREVIATION"] == team_visit]

        df_show = df[cols_show].rename(columns={
            "PLAYER_NAME":"Jugador","MIN":"MIN","PTS":"PTS",
            "FGM":"FGM","FGA":"FGA","FG3M":"3PM","FG3A":"3PA",
            "FTM":"FTM","FTA":"FTA","REB":"REB","AST":"AST",
            "STL":"STL","BLK":"BLK","TOV":"TOV","PF":"PF",
            "PLUS_MINUS":"+/-"
        }).copy()

        if "MIN" in df_show.columns:
            df_show["MIN"] = df_show["MIN"].apply(lambda x: minutos_decimal_a_mmss(x) if pd.notna(x) else "0:00")
        if "PTS" in df_show.columns:
            df_show = df_show.sort_values("PTS", ascending=False)

        height = 48 + 32 * len(df_show)
        st.dataframe(
            df_show.set_index(df_show.columns[0]),
            use_container_width=True,
            height=height
        )

    st.markdown("")
    if st.button("⬅ Volver al calendario"):
        ss["game_sel"] = ""
        st.rerun()

# ---------- calendario: LIMITADO AL MES DEL PRIMER Y DEL ULTIMO PARTIDO ----------
def render_calendar(partidos_df: pd.DataFrame):
    """
    Calendario mensual clásico:
    - Fila de días (Lun-Dom)
    - Cada día es un botón con el número
    - Día seleccionado resaltado
    - Limita meses a desde el mes del primer partido al mes del último partido (no puedes moverte fuera de rango)
    """
    if partidos_df is None or partidos_df.empty:
        st.info("No hay datos de partidos con las columnas esperadas.")
        return

    # Asegurar FECHA_DATE
    df = partidos_df.copy()
    if "FECHA_DATE" not in df.columns:
        if "FECHA" not in df.columns:
            st.warning("No se encuentra la columna 'FECHA' en los datos.")
            return
        df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")
        df = df[df["FECHA"].notna()].copy()
        df["FECHA_DATE"] = df["FECHA"].dt.date

    if df.empty:
        st.info("No hay fechas válidas en los datos de partidos.")
        return

    min_date = df["FECHA_DATE"].min()
    max_date = df["FECHA_DATE"].max()
    min_year = min_date.year
    min_month = min_date.month
    max_year = max_date.year
    max_month = max_date.month

    # selected_date por defecto
    if ss.get("selected_date") is None:
        ss["selected_date"] = max_date

    sel = ss["selected_date"]
    if isinstance(sel, str):
        sel = pd.to_datetime(sel).date()
        ss["selected_date"] = sel

    # mes/año visibles
    if ss.get("calendar_year") is None or ss.get("calendar_month") is None:
        ss["calendar_year"] = sel.year
        ss["calendar_month"] = sel.month

    year = ss["calendar_year"]
    month = ss["calendar_month"]

    # navegación mes
    # Limitar el rango de meses!
    c_prev, c_label, c_next = st.columns([0.15, 0.7, 0.15])
    with c_prev:
        disabled = False
        if (year < min_year) or (year == min_year and month <= min_month):
            disabled = True
        if st.button("◀", key="cal_prev", disabled=disabled):
            if not disabled:
                if month == 1:
                    year -= 1
                    month = 12
                else:
                    month -= 1
                # Tras navegar, limitar a rango
                if year < min_year or (year == min_year and month < min_month):
                    year, month = min_year, min_month
                ss["calendar_year"], ss["calendar_month"] = year, month
                st.rerun()

    with c_label:
        st.markdown(
            f"<h3 style='text-align:center;margin-bottom:0.2rem;'>{calendar.month_name[month]} {year}</h3>",
            unsafe_allow_html=True
        )

    with c_next:
        disabled = False
        if (year > max_year) or (year == max_year and month >= max_month):
            disabled = True
        if st.button("▶", key="cal_next", disabled=disabled):
            if not disabled:
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                if year > max_year or (year == max_year and month > max_month):
                    year, month = max_year, max_month
                ss["calendar_year"], ss["calendar_month"] = year, month
                st.rerun()

    # estilos tipo datepicker simple
    st.markdown("""
    <style>
      #nba-cal { margin-top: 4px; }
      #nba-cal .cal-header {
        text-align:center;
        font-weight:600;
        color:#9ca3af;
        font-size:11px;
        margin-bottom:4px;
      }
      #nba-cal .stButton > button {
        width: 95vw !important;       /* Hacer los botones MUY ANCHOS usando viewport width */
        min-width: 80px !important;   /* Ancho mínimo grande */
        max-width: 200px !important;  /* Evitar que quede gigantesco en pantallas muy grandes */
        padding: 10px 0 !important;   /* Más alto también */
        border-radius: 999px;
        border: 1px solid transparent;
        background: transparent;
        color: #e5e7eb;
        font-size: 18px;            /* Más grande la letra */
        box-shadow: none;
        margin-left: auto;
        margin-right: auto;
        display: block;
      }
      #nba-cal .stButton > button:hover {
        background: #111827;
        border-color: #4f46e5;
        color: #a5b4fc;
      }
      #nba-cal .day-selected > button {
        background: #2563eb !important;
        border-color: #2563eb !important;
        color: #ffffff !important;
        font-weight: 700 !important;
      }
      #nba-cal .day-outside {
        color: #4b5563 !important;
      }
      #nba-cal .day-dot {
        display:block;
        text-align:center;
        font-size:8px;
        line-height:8px;
        color:#60a5fa;
        margin-top:-2px;
      }
    </style>
    """, unsafe_allow_html=True)

    cal = calendar.Calendar(firstweekday=0)  # 0 = lunes
    weeks = cal.monthdatescalendar(year, month)

    # encabezado días
    st.markdown("<div id='nba-cal'>", unsafe_allow_html=True)
    day_labels = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
    header_cols = st.columns(7)
    for i, lab in enumerate(day_labels):
        header_cols[i].markdown(f"<div class='cal-header'>{lab}</div>", unsafe_allow_html=True)

    # filas del calendario
    for w_idx, week in enumerate(weeks):
        cols = st.columns(7)
        for i, day in enumerate(week):
            in_month = (day.month == month)
            is_selected = (day == sel)
            # fuera del mes Y fuera del rango general -> vacío
            if ((year == min_year and month == min_month and day.month < min_month) or 
                (year == max_year and month == max_month and day.month > max_month)):
                cols[i].write("")
                continue
            # restricción: no muestres días fuera del rango total
            if day < min_date or day > max_date:
                cols[i].write("")
                continue

            btn_classes = []
            if is_selected:
                btn_classes.append("day-selected")
            if not in_month:
                btn_classes.append("day-outside")
            class_attr = " ".join(btn_classes) if btn_classes else ""

            with cols[i]:
                st.markdown(f"<div class='{class_attr}'>", unsafe_allow_html=True)
                if st.button(str(day.day), key=f"cal_{day.isoformat()}_{w_idx}_{i}"):
                    ss["selected_date"] = day
                    ss["game_sel"] = ""
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # Partidos del día seleccionado
    st.markdown("### 🏀 Partidos del día seleccionado")
    show_games_for_date(df, ss["selected_date"])

def show_games_for_date(partidos_df: pd.DataFrame, fecha):
    if fecha is None:
        st.info("Elegí una fecha para ver los partidos.")
        return

    games = partidos_df[partidos_df["FECHA_DATE"] == fecha].copy()
    if games.empty:
        st.info("No hay partidos para este día.")
        return

    for _, g in games.iterrows():
        game_id = g["GAME_ID"]
        local = g["LOCAL"]
        visit = g["VISITANTE"]
        marcador = g["MARCADOR"]

        logo_local = get_team_logo(equipos, local)
        logo_visit = get_team_logo(equipos, visit)

        with st.container():
            c1, c2, c3, c4 = st.columns([0.5, 1, 1, 1])

            with c1:
                if logo_local:
                    st.image(logo_local, width=32)
                st.markdown(f"**{local}**")
            with c2:
                if st.button(marcador, key=f"score_{game_id}", use_container_width=True):
                    ss["game_sel"] = game_id
                    st.rerun()
            with c3:
                if logo_visit:
                    st.image(logo_visit, width=32)
                st.markdown(f"**{visit}**")
            with c4:
                st.markdown(g["FECHA"].strftime("%d/%m/%Y"))

        st.markdown("<hr style='border-color:#1f2937;'>", unsafe_allow_html=True)

# ---------- estilos globales ----------
st.markdown("""
<style>
  .stButton > button {
    background: transparent !important;
    border-radius: 8px !important;
    border: 1px solid #374151 !important;
    padding: 2px 6px !important;
    font-weight: 700 !important;
    box-shadow: none !important;
    min-width: 120px !important;
    max-width: 200px !important;
    width: 131% !important;
  }
  .stButton > button:hover {
    background: #111827 !important;
    color: #a5b4fc !important;
  }
</style>
""", unsafe_allow_html=True)

# ---------- datos + UI ----------
dfp = preparar_partidos(partidos)
if dfp.empty:
    st.info("No hay datos de partidos con las columnas esperadas.")
else:
    if ss["game_sel"]:
        render_boxscore_inline(ss["game_sel"], dfp)
    else:
        render_calendar(dfp)

st.markdown("---")
if st.button("⬅ Volver al Inicio"):
    st.switch_page("main.py")