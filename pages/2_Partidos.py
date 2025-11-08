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

# ---------- gráfico: diferencia 0..40 ----------
def _build_diff_series_40min(df_box: pd.DataFrame, team_local: str, team_visit: str):
    minutes = list(range(0, 41))
    diff_by_min = [0] * 41
    if df_box is None or df_box.empty:
        return minutes, diff_by_min

    needed_cols = {"TEAM_ABBREVIATION", "MIN", "PTS"}
    if not needed_cols.issubset(set(df_box.columns)):
        return minutes, diff_by_min

    for _, row in df_box.iterrows():
        team = str(row["TEAM_ABBREVIATION"])
        try:
            mins = float(row["MIN"])
        except Exception:
            mins = 0.0
        try:
            pts = int(row["PTS"])
        except Exception:
            try:
                pts = int(float(row["PTS"]))
            except Exception:
                pts = 0

        minute_mark = max(0, min(40, math.ceil(mins)))
        if team == team_local:
            diff_by_min[minute_mark] += pts
        elif team == team_visit:
            diff_by_min[minute_mark] -= pts

    diff_acum = list(itertools.accumulate(diff_by_min))
    return minutes, diff_acum

# ---------- standings global ----------
def _build_standings(df_games: pd.DataFrame, equipos_df: pd.DataFrame) -> pd.DataFrame:
    if df_games is None or df_games.empty:
        return pd.DataFrame()

    df = df_games.copy()
    c_fecha = _col(df, "FECHA","fecha","DATE","date")
    c_loc   = _col(df, "LOCAL","home","HOME")
    c_vis   = _col(df, "VISITANTE","away","AWAY")
    c_pl    = _col(df, "PTS_LOCAL","pts_local","HOME_PTS")
    c_pv    = _col(df, "PTS_VISITANTE","pts_visitante","AWAY_PTS")
    if not all([c_fecha, c_loc, c_vis, c_pl, c_pv]):
        return pd.DataFrame()

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

    c_left, c_right = st.columns([1, 1.4])

    # Izquierda: gráfico + card
    with c_left:
        if team_local and team_visit:
            x, y = _build_diff_series_40min(df_game, team_local, team_visit)
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=x, y=y, mode="lines",
                    line=dict(width=3),
                    name="Dif. acumulada (Local - Visita)",
                    fill="tozeroy"
                )
            )
            fig.update_layout(
                height=280,
                margin=dict(l=10, r=10, t=60, b=10),
                xaxis_title="Minuto",
                yaxis_title="Diferencia",
                xaxis=dict(range=[0, 40], tickmode="linear", dtick=5, zeroline=True),
                yaxis=dict(zeroline=True),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            tabla = _build_standings(partidos_df, equipos)
            _render_prematch_card(tabla, team_local, team_visit)
        else:
            st.info("No tengo parciales por período para graficar la evolución del marcador.")

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

# ---------- calendario ----------
def render_calendar(partidos_df: pd.DataFrame):
    """
    Calendario mensual clásico, pero mostrando semanas donde:
    - Siempre arranca por el día 1 (si la primer semana no arranca en el 1, va vacía/cortada)
    - Nunca puede terminar en una semana donde luego del último día del mes siga la numeración por 1,2,3, etc (no mostrar días que sean del día 1 del mes siguiente)
    - Si la última fila tiene días > 27 y luego 1,2... → la semana se debe recortar para mostrar solo los días del mes (28, 29, 30, 31) y sacar esos días "1,2,.."
    - Lo mismo si la última semana arranca en 27,28.. y sigue el mes que viene.
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
    c_prev, c_label, c_next = st.columns([0.15, 0.7, 0.15])
    with c_prev:
        if st.button("◀", key="cal_prev"):
            if month == 1:
                year -= 1
                month = 12
            else:
                month -= 1
            ss["calendar_year"], ss["calendar_month"] = year, month
            st.rerun()

    with c_label:
        st.markdown(
            f"<h3 style='text-align:center;margin-bottom:0.2rem;'>{calendar.month_name[month]} {year}</h3>",
            unsafe_allow_html=True
        )

    with c_next:
        if st.button("▶", key="cal_next"):
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            ss["calendar_year"], ss["calendar_month"] = year, month
            st.rerun()

    # estilos tipo datepicker simple, personalizada
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
        width: 95vw !important;
        min-width: 80px !important;
        max-width: 200px !important;
        padding: 10px 0 !important;
        border-radius: 999px;
        border: 1px solid transparent;
        background: transparent;
        color: #e5e7eb;
        font-size: 18px;
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
    </style>
    """, unsafe_allow_html=True)

    cal = calendar.Calendar(firstweekday=0)  # 0 = lunes LUN
    weeks_raw = cal.monthdatescalendar(year, month)

    # --- APLICAR LA LÓGICA REQUERIDA ---

    # 1. Arrancar sí o sí la PRIMER SEMANA (de weeks_raw) en el día 1 del mes
    #    Si antes de ese día hay días de otro mes, ponerlos en blanco/vacío (no mostrar días previos)
    #    Hallar la posicion/índice del día 1 del mes en la primera semana
    first_week = list(weeks_raw[0])
    first_day_idx = None
    for idx, d in enumerate(first_week):
        if d.day == 1 and d.month == month:
            first_day_idx = idx
            break
    # Recortar la primera semana si arranca antes del día 1
    # Si el primer valor NO es 1 del mes, entonces ponemos los días antes de ese index en None
    if first_day_idx is not None:
        fw = []
        for idx, d in enumerate(first_week):
            if idx < first_day_idx:
                fw.append(None)
            else:
                fw.append(d)
        weeks = [fw]
    else:
        # No debería pasar, pero fallback: semana original
        weeks = [first_week]

    # 2. Incluir las semanas siguientes, menos la última, tal cual
    for i in range(1, len(weeks_raw)):
        weeks.append(list(weeks_raw[i]))

    # 3. Cortar la última semana si termina en días 1,2,3.. etc (del mes siguiente)
    #    o si la última fila es, p.ej., [28,29,30,1,2,3,4] => sólo [28,29,30]
    #    Se debe mostrar sólo hasta el último día del mes

    # Saber cantidad de días del mes actual
    _, last_day_of_month = calendar.monthrange(year, month)

    # Reprocesamos la última semana:
    if weeks:
        # Si la última semana NO contiene ningún día del mes siguiente, la dejamos tal cual
        # Sino, la recortamos en el primer día que ya no sea de este mes
        last_week = weeks[-1]
        cut_idx = None
        for idx, d in enumerate(last_week):
            # d puede ser None (lo pusimos en la primera semana)
            if d is not None and (d.month != month):
                cut_idx = idx
                break
        if cut_idx is not None:
            # Revisar lógica especial: si la última semana tiene día >=28 y después viene 1,2..
            # Queremos mostrar SOLO los días del mes anterior a ese primer día de siguiente mes
            # Ejemplo: [28,29,30,1,2,3,4] --> solo 28,29,30
            week_trimmed = []
            for idx, d in enumerate(last_week):
                if d is not None and d.month == month:
                    week_trimmed.append(d)
                else:
                    week_trimmed.append(None)
            weeks[-1] = week_trimmed
        # Si la última semana termina con días antes del 28, dejar (meses cortos)
        # Si la última semana es solo del mes (todo dentro del mes), no hacemos nada
        # Si termina con, p.ej., [29,30,31, None, None, None, None], ningún problema, todo ok

    # --- encabezado días ---
    st.markdown("<div id='nba-cal'>", unsafe_allow_html=True)
    day_labels = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
    header_cols = st.columns(7)
    for i, lab in enumerate(day_labels):
        header_cols[i].markdown(f"<div class='cal-header'>{lab}</div>", unsafe_allow_html=True)

    # --- filas del calendario ---
    for w_idx, week in enumerate(weeks):
        cols = st.columns(7)
        for i, day in enumerate(week):
            is_selected = False
            show_btn = False
            label = ""

            if day is None:
                # Primeros blancos
                cols[i].write("")
                continue

            in_month = (day.month == month)
            is_selected = (day == sel) if in_month else False
            # Mostramos SÓLO días del mes
            if in_month:
                show_btn = True
                label = str(day.day)
            else:
                # No mostrar días del mes siguiente (ni anteriores ya que se ponen como None)
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
                if st.button(label, key=f"cal_{day.isoformat()}_{w_idx}_{i}"):
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
