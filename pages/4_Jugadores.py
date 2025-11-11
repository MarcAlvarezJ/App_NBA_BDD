# pages/4_Jugadores.py
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from utils import load_data, check_auth, init_session_state, minutos_decimal_a_mmss

st.set_page_config(page_title="Jugador | NBA Stats App", layout="wide")

# Inicializar estado de sesión
init_session_state()

# ================== DATA ==================
partidos, partidos_futuros, boxscores, equipos, jugadores = load_data()

ss = st.session_state
ss.setdefault("jugador_sel", "")

st.title("👤 Ficha de Jugador")

# ================== SELECTORES ==================
# Nombres forma "FIRST LAST"; mantenemos compatibilidad con valores previos
opts = [""] + sorted(jugadores.apply(lambda r: f"{r['FIRST_NAME']} {r['LAST_NAME']}", axis=1).dropna().unique())
if ss.jugador_sel and ss.jugador_sel not in opts:
    opts = [""] + sorted(set(opts + [ss.jugador_sel]))

idx_1 = opts.index(ss.jugador_sel) if ss.jugador_sel in opts else 0
# ================== SELECTORES LADO A LADO ==================
col1, col2 = st.columns([1, 1])

with col1:
    sel_1 = st.selectbox(
        "Buscar jugador",
        opts,
        index=idx_1,
        key="jugador_selector"
    )

with col2:
    sel_2 = st.selectbox(
        "Comparar con otro jugador (opcional)",
        opts,
        index=0,
        key="jugador_selector_compare"
    )

# actualizar selección si cambió el jugador principal
if sel_1 != ss.jugador_sel:
    ss.jugador_sel = sel_1
    st.rerun()

jug_1 = ss.jugador_sel
if not jug_1:
    st.info("Elegí un jugador para ver sus estadísticas.")
    if st.button("⬅ Volver al Inicio"):
        st.switch_page("Home.py")
    st.stop()


# ================== HELPERS ==================
def to_minutes(val):
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, str) and ":" in val:
        try:
            mm, ss_ = val.split(":", 1); return int(mm) + int(ss_)/60.0
        except: return None
    return None

def safe_pct(makes, atts):
    if atts is None or atts == 0 or pd.isna(atts): return None
    if makes is None or pd.isna(makes): return None
    return (float(makes) / float(atts)) * 100.0

def parse_height_to_cm(h):
    """Convierte '6-6' -> 198.1 cm aprox."""
    if not isinstance(h, str) or "-" not in h: return None
    try:
        f, i = h.split("-"); inches = int(f)*12 + int(i)
        return round(inches * 2.54, 1)
    except: return None

def lbs_to_kg(w):
    try: return round(float(w) * 0.45359237, 1)
    except: return None

def full_name_from_row(r):
    return f"{r.get('FIRST_NAME','').strip()} {r.get('LAST_NAME','').strip()}".strip()

def find_profile_by_name(name: str):
    """Busca perfil en `jugadores` por PLAYER_ID (desde boxscores) y si no, por nombre completo."""
    pid = None
    if {"PLAYER_NAME","PLAYER_ID"}.issubset(boxscores.columns):
        bs = boxscores[boxscores["PLAYER_NAME"].str.lower() == name.lower()]
        if not bs.empty:
            pid = bs["PLAYER_ID"].dropna().astype(str).iloc[-1]
    if pid is not None and "PLAYER_ID" in jugadores.columns:
        j = jugadores[jugadores["PLAYER_ID"].astype(str) == str(pid)]
        if not j.empty: return j.iloc[0].to_dict()
    if {"FIRST_NAME","LAST_NAME"}.issubset(jugadores.columns):
        j2 = jugadores[jugadores.apply(lambda r: full_name_from_row(r).lower() == name.lower(), axis=1)]
        if not j2.empty: return j2.iloc[0].to_dict()
    return {}

def serie_promedios(df: pd.DataFrame) -> pd.Series:
    out = {}
    for col in ["PTS","REB","AST","STL","BLK","TOV","PF","PLUS_MINUS"]:
        if col in df.columns:
            out[col] = pd.to_numeric(df[col], errors="coerce").dropna().mean()
    if "MIN" in df.columns:
        mins = df["MIN"].dropna().map(to_minutes).dropna()
        if not mins.empty: out["MIN"] = mins.mean()
    # FG%
    if "FG_PCT" in df.columns:
        val = pd.to_numeric(df["FG_PCT"], errors="coerce").dropna().mean()
        out["FG_PCT"] = val*100 if val <= 1 else val
    elif {"FGM","FGA"}.issubset(df.columns):
        out["FG_PCT"] = safe_pct(df["FGM"].mean(), df["FGA"].mean())
    # 3P%
    if "FG3_PCT" in df.columns:
        val = pd.to_numeric(df["FG3_PCT"], errors="coerce").dropna().mean()
        out["FG3_PCT"] = val*100 if val <= 1 else val
    elif {"FG3M","FG3A"}.issubset(df.columns):
        out["FG3_PCT"] = safe_pct(df["FG3M"].mean(), df["FG3A"].mean())
    # FT%
    if "FT_PCT" in df.columns:
        val = pd.to_numeric(df["FT_PCT"], errors="coerce").dropna().mean()
        out["FT_PCT"] = val*100 if val <= 1 else val
    elif {"FTM","FTA"}.issubset(df.columns):
        out["FT_PCT"] = safe_pct(df["FTM"].mean(), df["FTA"].mean())
    # Equipo (último en boxscores)
    team = None
    for c in ["TEAM_NAME","TEAM_ABBREVIATION"]:
        if c in df.columns and not df[c].dropna().empty:
            team = df[c].dropna().iloc[-1]; break
    if team: out["TEAM"] = team
    return pd.Series(out)

def resumen_jugador(name: str) -> pd.Series:
    d = boxscores[boxscores["PLAYER_NAME"].str.lower() == name.lower()].copy()
    if d.empty: return pd.Series(name=name)
    return serie_promedios(d)

def fmt(v, key):
    # Si es MIN, convertir a formato mm:ss
    if key == "MIN" and v is not None and not pd.isna(v):
        return minutos_decimal_a_mmss(v)
    if v is None or pd.isna(v): return "—"
    if key in ("FG_PCT","FG3_PCT","FT_PCT"): return f"{v:.1f}%"
    return f"{float(v):.1f}"

lower_better = {"TOV","PF"}  # menos es mejor

def card(label, value):
    st.markdown(f"""
    <div style="
        background:#141826; border:1px solid #22304a;
        border-radius:14px; padding:12px 16px; height:100%;">
        <div style="font-size:.9rem; color:#9aa3b2">{label}</div>
        <div style="font-size:1.6rem; font-weight:800; margin-top:4px;">{value}</div>
    </div>
    """, unsafe_allow_html=True)

def kpi_row(label, key, s1, s2, jug_1, jug_2):
    col1, col2 = st.columns(2)
    v1 = s1.get(key, None)
    v2 = s2.get(key, None) if s2 is not None else None
    c1 = c2 = "transparent"
    if v2 is not None and v1 is not None and not pd.isna(v1) and not pd.isna(v2):
        if key in lower_better:
            if v1 < v2: c1, c2 = "#113B1C", "#3B1111"
            elif v1 > v2: c1, c2 = "#3B1111", "#113B1C"
        else:
            if v1 > v2: c1, c2 = "#113B1C", "#3B1111"
            elif v1 < v2: c1, c2 = "#3B1111", "#113B1C"
    box_css = """
    <div style="
        background:{bg};
        border:1px solid #22304a;
        border-radius:12px;
        padding:10px 14px;">
        <div style="font-size:.85rem;color:#9aa3b2;">{label}</div>
        <div style="font-size:1.4rem;font-weight:700;margin-top:2px;">{val}</div>
    </div>
    """
    with col1:
        st.markdown(box_css.format(bg=c1, label=f"{label} — {jug_1}", val=fmt(v1, key)), unsafe_allow_html=True)
    with col2:
        if s2 is None:
            st.markdown(box_css.format(bg="transparent", label="Sin comparación", val="—"), unsafe_allow_html=True)
        else:
            st.markdown(box_css.format(bg=c2, label=f"{label} — {jug_2}", val=fmt(v2, key)), unsafe_allow_html=True)

# ===== Percentiles de liga para el radar =====
def _fg_pct_from(df):
    """Serie FG% (0–100) a partir de columnas disponibles."""
    if "FG_PCT" in df.columns:
        s = pd.to_numeric(df["FG_PCT"], errors="coerce")
        return s.where(s > 1, s * 100.0)
    if {"FGM","FGA"}.issubset(df.columns):
        makes = pd.to_numeric(df["FGM"], errors="coerce")
        atts  = pd.to_numeric(df["FGA"], errors="coerce")
        pct = (makes / atts) * 100.0
        pct[atts == 0] = np.nan
        return pct
    return pd.Series([np.nan] * len(df), index=df.index)

def build_league_averages(boxscores: pd.DataFrame) -> pd.DataFrame:
    df = boxscores.copy()
    df = df.assign(__FG_PCT__=_fg_pct_from(df))
    metrics = [m for m in ["PTS","REB","AST","STL","BLK","__FG_PCT__"] if (m in df.columns or m=="__FG_PCT__")]
    league = (
        df.groupby("PLAYER_NAME")[metrics]
          .mean(numeric_only=True)
          .rename(columns={"__FG_PCT__": "FG_PCT"})
    )
    return league

LEAGUE = build_league_averages(boxscores)

def radar_labels_keys():
    return [
        ("PTS", "PTS"),
        ("REB", "REB"),
        ("AST", "AST"),
        ("STL", "STL"),
        ("BLK", "BLK"),
        ("FG%", "FG_PCT"),
    ]

def build_radar_percentiles(player_name: str, league: pd.DataFrame):
    """labels y percentiles (0–100) por métrica vs liga."""
    if player_name not in league.index: return [], []
    labels, values = [], []
    for label, key in radar_labels_keys():
        if key not in league.columns: continue
        col = league[key].dropna()
        if col.empty or pd.isna(league.at[player_name, key]): continue
        pct_series = col.rank(pct=True, ascending=True)  # mayor valor => mayor percentil
        val = float(pct_series.loc[player_name] * 100.0)
        labels.append(label); values.append(val)
    return labels, values
def plot_radar(labels, values1, values2=None, name1="Jugador A", name2=None, size=2.2):
    import numpy as np
    import matplotlib.pyplot as plt

    N = len(labels)
    if N < 3:
        st.info("No hay suficientes métricas para dibujar el radar (se necesitan ≥ 3).")
        return

    angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    v1 = values1 + values1[:1]

    # --- figura compacta (círculo) ---
    fig = plt.figure(figsize=(size, size))
    fig.patch.set_alpha(0)
    ax = plt.subplot(111, polar=True)
    ax.set_facecolor('none')

    # === estilo dark
    grid_c = '#2a3348'
    text_c = '#d7deea'
    spine_c = '#3a4461'
    ax.spines['polar'].set_color(spine_c)
    ax.spines['polar'].set_linewidth(0.8)
    ax.grid(color=grid_c, linestyle='-', linewidth=0.5)

    fs_axis = 9
    fs_ticks = 8
    fs_legend = 9

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color=text_c, fontsize=fs_axis)
    ax.set_rlabel_position(0)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20","40","60","80","100"], color=text_c, fontsize=fs_ticks)
    ax.set_ylim(0, 100)

    # líneas
    ax.plot(angles, v1, linewidth=1.6, linestyle='solid', label=name1)
    ax.fill(angles, v1, alpha=0.14)

    if values2 is not None:
        v2 = values2 + values2[:1]
        ax.plot(angles, v2, linewidth=1.6, linestyle='solid', label=name2)
        ax.fill(angles, v2, alpha=0.14)

    # >>> reserva espacio a la derecha para la leyenda (no deforma el círculo)
    # deja ~30% de ancho libre a la derecha del eje para ubicar la leyenda
    plt.subplots_adjust(left=0.03, right=0.70, top=0.98, bottom=0.03)

    # leyenda fuera del eje, centrada verticalmente a la derecha
    leg = ax.legend(
        loc="center left",
        bbox_to_anchor=(1.20, 0.50),  # fuera del círculo, bien a la derecha
        frameon=False,
        fontsize=fs_legend,
        handlelength=2.4,
        labelspacing=0.5,
        borderaxespad=0.0,
    )
    for t in leg.get_texts():
        t.set_color(text_c)

    # no achicar márgenes (ya los controlamos con subplots_adjust)
    st.pyplot(fig, use_container_width=False)



# ================== CÁLCULO ==================
s1 = resumen_jugador(jug_1)
s2 = resumen_jugador(sel_2) if sel_2 and sel_2 != jug_1 else None

# ======== PERFIL(ES) ========
def render_profile(name: str):
    prof = find_profile_by_name(name)
    age = prof.get("AGE", "—")
    pos = prof.get("POSITION", "—")
    height = prof.get("HEIGHT", None)
    weight = prof.get("WEIGHT", None)
    team_abbr = prof.get("TEAM_ABBREVIATION", prof.get("TEAM","—"))

    h_cm = parse_height_to_cm(height) if height else None
    w_kg = lbs_to_kg(weight) if weight is not None else None

    height_txt = f"{height} ({h_cm:.1f} cm)" if (height and h_cm) else (height or "—")
    weight_txt = f"{weight} lb ({w_kg:.1f} kg)" if (weight is not None and w_kg is not None) else (f"{weight} lb" if weight is not None else "—")

    st.markdown(f"""
    <div style="background:#141826;border:1px solid #22304a;border-radius:14px;padding:14px 16px;">
      <div style="font-size:1.2rem;font-weight:800;margin-bottom:4px;">{name}</div>
      <div style="display:flex;gap:18px;flex-wrap:wrap;font-size:.95rem;">
        <div><b>Equipo:</b> {team_abbr if team_abbr else '—'}</div>
        <div><b>Posición:</b> {pos}</div>
        <div><b>Edad:</b> {age}</div>
        <div><b>Altura:</b> {height_txt}</div>
        <div><b>Peso:</b> {weight_txt}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ================== RENDER ==================
if s2 is None:
    # ---------- 1 JUGADOR ----------
    render_profile(jug_1)

    # Radar percentiles
    st.markdown("### 🕸️ Radar de atributos (percentil de liga)")
    labels, val1 = build_radar_percentiles(jug_1, LEAGUE)
    plot_radar(labels, val1, None, name1=jug_1)

    st.markdown("### 📄 Estadísticas")
    if "TEAM" in s1.index: st.caption(f"Equipo (último en boxscores): **{s1['TEAM']}**")

    bloques = [
        ("🧭 Promedios por juego",
         [("PTS por juego","PTS"), ("REB por juego","REB"), ("AST por juego","AST"),
          ("STL por juego","STL"), ("BLK por juego","BLK"), ("MIN por juego","MIN")]),
        ("🎯 Porcentajes de tiro",
         [("FG%","FG_PCT"), ("3P%","FG3_PCT"), ("FT%","FT_PCT")]),
        ("⚠️ Control de balón",
         [("Pérdidas (TOV)","TOV"), ("Fouls (PF)","PF"), ("Plus/Minus","PLUS_MINUS")]),
    ]
    for titulo, pares in bloques:
        st.markdown(f"### {titulo}")
        pares_presentes = [(lbl,k) for lbl,k in pares if k in s1.index]
        if not pares_presentes:
            st.caption("Sin datos disponibles."); continue
        ncols = 4
        for i in range(0, len(pares_presentes), ncols):
            row = pares_presentes[i:i+ncols]
            cols = st.columns(len(row))
            for c, (lbl, k) in zip(cols, row):
                with c: card(lbl, fmt(s1.get(k), k))

    # Historial
    st.divider()
    st.subheader("📜 Historial de partidos")
    d = boxscores[boxscores["PLAYER_NAME"].str.lower() == jug_1.lower()].copy()
    cols = [c for c in ["GAME_ID","TEAM_ABBREVIATION","MIN","PTS","FGM","FGA","FG3M","FG3A","FTM","FTA",
                        "REB","AST","STL","BLK","TOV","PF","PLUS_MINUS"] if c in d.columns]
    # Convertir MIN a formato mm:ss para display
    d_display = d[cols].copy()
    if "MIN" in d_display.columns:
        d_display["MIN"] = d_display["MIN"].apply(lambda x: minutos_decimal_a_mmss(x) if pd.notna(x) else "0:00")
    st.dataframe(d_display, use_container_width=True, height=480)

else:
    # ---------- COMPARACIÓN ----------
    cprof1, cprof2 = st.columns(2)
    with cprof1: render_profile(jug_1)
    with cprof2: render_profile(sel_2)

    # Radar comparativo (percentiles comunes)
    st.markdown("### 🕸️ Radar comparativo (percentil de liga)")
    labels1, v1_all = build_radar_percentiles(jug_1, LEAGUE)
    labels2, v2_all = build_radar_percentiles(sel_2, LEAGUE)
    comunes = [l for l in labels1 if l in labels2]
    if len(comunes) >= 3:
        v1 = [v1_all[labels1.index(l)] for l in comunes]
        v2 = [v2_all[labels2.index(l)] for l in comunes]
        plot_radar(comunes, v1, v2, name1=jug_1, name2=sel_2)
    else:
        st.info("No hay suficientes métricas en común para el radar (se necesitan ≥ 3).")

    colA, colB = st.columns([1,1])
    with colA:
        st.subheader(f"📄 Estadísticas de {jug_1}")
        if "TEAM" in s1.index: st.caption(f"Equipo (boxscores): **{s1['TEAM']}**")
    with colB:
        st.subheader(f"🆚 Comparado con {sel_2}")
        if "TEAM" in s2.index: st.caption(f"Equipo (boxscores): **{s2['TEAM']}**")

    st.markdown("### 🧭 Promedios por juego")
    for lbl, key in [("PTS por juego","PTS"), ("REB por juego","REB"), ("AST por juego","AST"),
                     ("STL por juego","STL"), ("BLK por juego","BLK"), ("MIN por juego","MIN")]:
        if key in s1.index or key in s2.index:
            kpi_row(lbl, key, s1, s2, jug_1, sel_2)

    st.markdown("### 🎯 Porcentajes de tiro")
    for lbl, key in [("FG%","FG_PCT"), ("3P%","FG3_PCT"), ("FT%","FT_PCT")]:
        if key in s1.index or key in s2.index:
            kpi_row(lbl, key, s1, s2, jug_1, sel_2)

    st.markdown("### ⚠️ Control de balón")
    for lbl, key in [("Pérdidas (TOV) ↓ mejor","TOV"),
                     ("Fouls (PF) ↓ mejor","PF"),
                     ("Plus/Minus","PLUS_MINUS")]:
        if key in s1.index or key in s2.index:
            kpi_row(lbl, key, s1, s2, jug_1, sel_2)

    # Historial doble
    st.divider()
    st.subheader("📜 Historial de partidos")
    def hist_df(name):
        d = boxscores[boxscores["PLAYER_NAME"].str.lower() == name.lower()].copy()
        cols = [c for c in ["GAME_ID","TEAM_ABBREVIATION","MIN","PTS","FGM","FGA","FG3M","FG3A","FTM","FTA",
                            "REB","AST","STL","BLK","TOV","PF","PLUS_MINUS"] if c in d.columns]
        d_display = d[cols].copy()
        # Convertir MIN a formato mm:ss para display
        if "MIN" in d_display.columns:
            d_display["MIN"] = d_display["MIN"].apply(lambda x: minutos_decimal_a_mmss(x) if pd.notna(x) else "0:00")
        return d_display
    c1, c2 = st.columns(2)
    with c1:
        st.caption(jug_1); st.dataframe(hist_df(jug_1), use_container_width=True, height=420)
    with c2:
        st.caption(sel_2); st.dataframe(hist_df(sel_2), use_container_width=True, height=420)

# ================== VOLVER ==================
st.divider()
if st.button("⬅ Volver al Inicio"):
    st.switch_page("Home.py")
