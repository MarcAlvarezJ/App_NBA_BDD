# pages/3_Partidos.py
import math
import itertools
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

st.title("📅 Partidos por jornadas")

# ---------- helpers ----------
def _col(df, *names):
    for n in names:
        if n in df.columns:
            return n
    return None

def preparar_partidos(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas, ordena por fecha y calcula JORNADA (1..48)."""
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

    df = df[[c_game,c_fecha,c_loc,c_vis,c_pl,c_pv]].copy()
    df.columns = ["GAME_ID","FECHA","LOCAL","VISITANTE","PTS_LOCAL","PTS_VISITANTE"]
    df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")
    df = df.sort_values(["FECHA","GAME_ID"]).reset_index(drop=True)

    # progresivo por equipo (para armar "jornadas")
    long_home = df[["GAME_ID","FECHA","LOCAL"]].rename(columns={"LOCAL":"TEAM"})
    long_away = df[["GAME_ID","FECHA","VISITANTE"]].rename(columns={"VISITANTE":"TEAM"})
    long = pd.concat([long_home,long_away], ignore_index=True).sort_values(["TEAM","FECHA","GAME_ID"])
    long["N_PARTIDO"] = long.groupby("TEAM").cumcount() + 1

    h = long.merge(df[["GAME_ID","LOCAL","VISITANTE"]], on="GAME_ID", how="right")
    n_home = h[h["TEAM"] == h["LOCAL"]][["GAME_ID","N_PARTIDO"]].rename(columns={"N_PARTIDO":"N_HOME"})
    n_away = h[h["TEAM"] == h["VISITANTE"]][["GAME_ID","N_PARTIDO"]].rename(columns={"N_PARTIDO":"N_AWAY"})

    out = df.merge(n_home, on="GAME_ID", how="left").merge(n_away, on="GAME_ID", how="left")
    out["JORNADA"] = out[["N_HOME","N_AWAY"]].max(axis=1).astype("Int64")
    out = out[out["JORNADA"].notna() & (out["JORNADA"] <= 48)].copy()

    out["Marcador"] = out["PTS_LOCAL"].astype(int).astype(str) + " - " + out["PTS_VISITANTE"].astype(int).astype(str)
    return out.sort_values(["JORNADA","FECHA","GAME_ID"]).reset_index(drop=True)

def render_header():
    hc = st.columns([2, 1, 2, 2])
    hc[0].markdown('<div class="hdr" style="text-align:right;">Local</div>', unsafe_allow_html=True)
    hc[1].markdown('<div class="hdr" style="text-align:center;">Marcador</div>', unsafe_allow_html=True)
    hc[2].markdown('<div class="hdr" style="text-align:left;">Visitante</div>', unsafe_allow_html=True)
    hc[3].markdown('<div class="hdr" style="text-align:right;">Fecha</div>', unsafe_allow_html=True)

def render_fila_partido(r, key_suffix):
    """Fila de partido. Click en el marcador para ver boxscore (misma página)."""
    f = r["FECHA"].strftime("%d/%m/%Y") if pd.notnull(r["FECHA"]) else ""
    col1, col2, col3, col4 = st.columns([2, 1, 2, 2])

    with col1:
        st.markdown(f'<div class="cell-right">{r["LOCAL"]}</div>', unsafe_allow_html=True)
    with col2:
        if st.button(r["Marcador"], key=f"g_{r['GAME_ID']}_{key_suffix}", use_container_width=True):
            st.session_state["game_sel"] = r["GAME_ID"]
            st.rerun()
    with col3:
        st.markdown(f'<div class="cell-left">{r["VISITANTE"]}</div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="cell-right date">{f}</div>', unsafe_allow_html=True)

# ---------- gráfico: diferencia 0..40 ----------
def _build_diff_series_40min(df_box: pd.DataFrame, team_local: str, team_visit: str):
    """
    Serie de diferencia por minuto (0..40) siguiendo tu regla:
    - Cada jugador aporta todos sus PTS en el minuto ceil(MIN).
    - Se suman por equipo en ese minuto.
    - Dif puntual (local - visita) y luego acumulado.
    Devuelve (minutes, diff_acum)
    """
    minutes = list(range(0, 41))  # 0..40
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

# ---------- standings compactos para 2 equipos ----------
def _build_standings(df_games: pd.DataFrame, equipos_df: pd.DataFrame) -> pd.DataFrame:
    """Tabla de posiciones global (PJ/PG/PP/DIF + últimos 5) para todos los equipos."""
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

    # últimos 5
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
    """Dibuja la tarjetita 'Clasificación pre-partido' para ambos equipos."""
    if tabla.empty or not t_local or not t_visit:
        return

    sub = tabla[tabla["ABBR"].isin([t_local, t_visit])].copy()
    # mantener orden por ranking (#)
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

# ---------- render partido (misma página) ----------
def render_boxscore_inline(game_id: str):
    """Render del boxscore y gráfico debajo, en la misma página."""
    if boxscores is None or boxscores.empty:
        st.warning("No hay boxscores disponibles.")
        return

    # Info del encabezado desde 'partidos'
    p = partidos.copy()
    c_game  = _col(p, "GAME_ID","game_id")
    c_fecha = _col(p, "FECHA","fecha","DATE","date")
    c_loc   = _col(p, "LOCAL","home","HOME")
    c_vis   = _col(p, "VISITANTE","away","AWAY")
    c_pl    = _col(p, "PTS_LOCAL","HOME_PTS")
    c_pv    = _col(p, "PTS_VISITANTE","AWAY_PTS")

    header_txt = f"Partido {game_id}"
    team_local = ""
    team_visit = ""
    if all([c_game,c_fecha,c_loc,c_vis,c_pl,c_pv]):
        row = p[p[c_game].astype(str) == str(game_id)].head(1)
        if not row.empty:
            fecha = pd.to_datetime(row.iloc[0][c_fecha], errors="coerce")
            ftxt = fecha.strftime("%d %b %Y") if pd.notna(fecha) else ""
            team_local = str(row.iloc[0][c_loc])
            team_visit = str(row.iloc[0][c_vis])
            header_txt = f"**{team_local} {int(row.iloc[0][c_pl])} – {int(row.iloc[0][c_pv])} {team_visit}** · {ftxt}"

    st.markdown("---")
    st.markdown(f"### 📊 {header_txt}")

    # Filtrar boxscore del juego
    df_game = boxscores[boxscores["GAME_ID"].astype(str) == str(game_id)].copy()
    if df_game.empty:
        st.info("No se encontraron estadísticas para este partido.")
        st.markdown("")
        if st.button("⬅ Volver a la lista de partidos"):
            st.session_state["game_sel"] = ""
            st.rerun()
        return

    # ====== LAYOUT: Izquierda gráfico + card / Derecha tabla ======
    c_left, c_right = st.columns([1, 1.4])

    # ---------- IZQUIERDA: gráfico de diferencia 0..40 + CLASIFICACIÓN ----------
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
                margin=dict(l=10, r=10, t=90, b=10),  # ← más espacio arriba
                xaxis_title="Minuto",
                yaxis_title="Diferencia",
                xaxis=dict(range=[0, 40], tickmode="linear", dtick=5, zeroline=True),
                yaxis=dict(zeroline=True),
                showlegend=False,
            )

            st.plotly_chart(fig, use_container_width=True)

            # 👇 AHORA el card queda justo DEBAJO del gráfico, en la columna izquierda
            tabla = _build_standings(partidos, equipos)
            _render_prematch_card(tabla, team_local, team_visit)
        else:
            st.info("No tengo parciales por período para graficar la evolución del marcador.")

    # ---------- DERECHA: filtro equipo + tabla ----------
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

        # Convertir MIN a formato mm:ss para display
        if "MIN" in df_show.columns:
            df_show["MIN"] = df_show["MIN"].apply(lambda x: minutos_decimal_a_mmss(x) if pd.notna(x) else "0:00")

        if "PTS" in df_show.columns:
            df_show = df_show.sort_values("PTS", ascending=False)

        height = 48 + 32 * len(df_show)
        st.dataframe(
            df_show.set_index(df_show.columns[0]),  # usar nombre del jugador como índice
            use_container_width=True,
            height=height
        )


    # Botón volver
    st.markdown("")
    if st.button("⬅ Volver a la lista de partidos"):
        st.session_state["game_sel"] = ""
        st.rerun()


# ---------- estilos ----------
st.markdown("""
<style>
  .hdr {
    font-weight:700;
    color:#cfd9e6;
    padding-bottom:20px;   /* antes era 8px */
    padding-top:10px;      /* sube el texto */
    margin-top:10px;      /* lo empuja hacia arriba */
}
  .cell-right {text-align:right;font-weight:600;}
  .cell-left  {text-align:left;font-weight:600;}
  .date {color:#9aa4b8;}
  /* El marcador se ve como texto clickeable */
  .stButton > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 0 !important;
    font-weight: 800 !important;
    cursor: pointer;
  }
  .stButton > button:hover { text-decoration: underline !important; color:#a8b7ff !important; }
  /* línea separadora entre filas + espacio chico bajo título */
  [data-testid="stHorizontalBlock"] { border-bottom: 1px solid #243249; margin: 0; }
  h3 + div[data-testid="stHorizontalBlock"] { margin-top: 6px; }
</style>
""", unsafe_allow_html=True)

# ---------- datos ----------
dfj = preparar_partidos(partidos)
if dfj.empty:
    st.info("No hay datos de partidos con las columnas esperadas.")
    st.stop()

# ---------- UI ----------
modo = st.segmented_control("Vista", options=["Jornada única","Todas (1–48)"], default="Jornada única")

if ss["game_sel"]:
    render_boxscore_inline(ss["game_sel"])
else:
    if modo == "Jornada única":
        j = st.slider("Jornada", min_value=1, max_value=48, value=1, step=1)
        sub = dfj[dfj["JORNADA"] == j]
        st.subheader(f"Jornada {j}")
        if sub.empty:
            st.info("Sin partidos en esta jornada.")
        else:
            render_header()
            for idx, (_, r) in enumerate(sub.iterrows()):
                render_fila_partido(r, idx)
    else:
        for j in range(1, 49):
            sub = dfj[dfj["JORNADA"] == j]
            with st.expander(f"Jornada {j} — {len(sub)} partidos", expanded=(j==1)):
                if sub.empty:
                    st.caption("Sin partidos.")
                else:
                    render_header()
                    for idx, (_, r) in enumerate(sub.iterrows()):
                        render_fila_partido(r, f"{j}_{idx}")
