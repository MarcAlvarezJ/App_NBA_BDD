import streamlit as st
import pandas as pd
from utils import (
	load_data, check_auth, init_session_state, get_current_user,
	insert_jugador, update_jugador_team, delete_jugador, get_jugador_by_id,
	get_partido_futuro, get_jugadores_por_equipo, cargar_partido_completo,
	eliminar_partido, get_partido_jugado, minutos_decimal_a_mmss, mmss_a_minutos_decimal
)

st.set_page_config(page_title="Administración | NBA Stats App", layout="wide")

# Inicializar estado de sesión
init_session_state()

# Verificar autenticación - REQUERIDA para esta página
if not check_auth():
	st.error("🔒 Acceso Restringido")
	st.warning("⚠️ Esta página solo está disponible para usuarios autenticados.")
	st.info("💡 Por favor, inicia sesión para acceder a las funciones de administración.")
	if st.button("🔐 Ir a Inicio de Sesión"):
		st.switch_page("pages/0_Login.py")
	st.stop()

# Usuario autenticado - mostrar página
user = get_current_user()
st.title("⚙️ Administración de Datos")
st.success(f"👤 Conectado como: {user.email if user else 'Usuario'}")
st.markdown("---")

# Cargar datos
_, _, _, equipos, jugadores = load_data()

# Obtener lista de equipos disponibles
team_options = []
if not equipos.empty and "TEAM_ABBREVIATION" in equipos.columns:
	team_options = sorted(equipos["TEAM_ABBREVIATION"].dropna().unique().tolist())

# Tabs para diferentes operaciones
tab1, tab2, tab3, tab4, tab5 = st.tabs([
	"➕ Agregar Jugador", 
	"✏️ Actualizar Equipo", 
	"🗑️ Eliminar Jugador", 
	"📊 Cargar Partido",
	"🗑️ Eliminar Partido"
])

# ==============================================================
# TAB 1: AGREGAR JUGADOR
# ==============================================================
with tab1:
	st.header("➕ Agregar Nuevo Jugador")
	st.info("💡 Completa el formulario para agregar un nuevo jugador a la base de datos.")
	
	with st.form("form_agregar_jugador", clear_on_submit=True):
		col1, col2 = st.columns(2)
		
		with col1:
			player_id = st.text_input("PLAYER_ID *", placeholder="Ej: 203076", help="ID único del jugador")
			first_name = st.text_input("Nombre (FIRST_NAME) *", placeholder="Ej: Anthony")
			last_name = st.text_input("Apellido (LAST_NAME) *", placeholder="Ej: Davis")
			position = st.selectbox(
				"Posición (POSITION)",
				options=["", "Guard", "Forward", "Center", "Forward-Center", "Guard-Forward", "Forward-Guard"],
				help="Posición del jugador"
			)
		
		with col2:
			height = st.text_input("Altura (HEIGHT)", placeholder="Ej: 6-10", help="Formato: pies-pulgadas (ej: 6-10)")
			weight = st.number_input("Peso (WEIGHT)", min_value=0, value=None, help="Peso en libras")
			team_abbr = st.selectbox(
				"Equipo (TEAM_ABBREVIATION)",
				options=[""] + team_options if team_options else [""],
				help="Abreviación del equipo"
			)
			age = st.number_input("Edad (AGE)", min_value=0, max_value=100, value=None)
		
		submit_add = st.form_submit_button("➕ Agregar Jugador", use_container_width=True)
		
		if submit_add:
			# Validar campos requeridos
			if not player_id or not first_name or not last_name:
				st.error("❌ Por favor, completa los campos requeridos (*)")
			else:
				# Preparar datos
				jugador_data = {
					"PLAYER_ID": str(player_id),
					"FIRST_NAME": first_name.strip(),
					"LAST_NAME": last_name.strip(),
				}
				
				# Agregar campos opcionales si están presentes
				if position:
					jugador_data["POSITION"] = position
				if height:
					jugador_data["HEIGHT"] = height.strip()
				if weight:
					jugador_data["WEIGHT"] = int(weight)
				if team_abbr:
					jugador_data["TEAM_ABBREVIATION"] = team_abbr
				if age:
					jugador_data["AGE"] = int(age)
				
				# Insertar jugador
				with st.spinner("Agregando jugador..."):
					success, message = insert_jugador(jugador_data)
					if success:
						st.success(message)
						st.balloons()
						st.rerun()
					else:
						st.error(message)

# ==============================================================
# TAB 2: ACTUALIZAR EQUIPO DE JUGADOR
# ==============================================================
with tab2:
	st.header("✏️ Actualizar Equipo de Jugador")
	st.info("💡 Selecciona un jugador y actualiza su equipo.")
	
	# Selector de jugador
	if not jugadores.empty:
		# Crear lista de jugadores para el selector
		jugadores_list = []
		if "PLAYER_ID" in jugadores.columns and "FIRST_NAME" in jugadores.columns and "LAST_NAME" in jugadores.columns:
			for _, row in jugadores.iterrows():
				player_id = str(row.get("PLAYER_ID", ""))
				first = str(row.get("FIRST_NAME", "")).strip()
				last = str(row.get("LAST_NAME", "")).strip()
				name = f"{first} {last}".strip()
				if player_id and name:
					jugadores_list.append((player_id, name))
		
		if jugadores_list:
			jugadores_list = sorted(jugadores_list, key=lambda x: x[1])
			jugador_options = {f"{name} (ID: {pid})": pid for pid, name in jugadores_list}
			
			selected_jugador_display = st.selectbox(
				"Seleccionar Jugador",
				options=[""] + list(jugador_options.keys()),
				help="Busca y selecciona el jugador a actualizar"
			)
			
			if selected_jugador_display:
				selected_player_id = jugador_options[selected_jugador_display]
				
				# Mostrar información del jugador actual
				jugador_actual = get_jugador_by_id(selected_player_id)
				
				if jugador_actual:
					st.markdown("### 📋 Información Actual del Jugador")
					col_info1, col_info2 = st.columns(2)
					with col_info1:
						st.write(f"**ID:** {jugador_actual.get('PLAYER_ID', 'N/A')}")
						st.write(f"**Nombre:** {jugador_actual.get('FIRST_NAME', '')} {jugador_actual.get('LAST_NAME', '')}")
						st.write(f"**Posición:** {jugador_actual.get('POSITION', 'N/A')}")
					with col_info2:
						st.write(f"**Equipo Actual:** {jugador_actual.get('TEAM_ABBREVIATION', 'Sin equipo')}")
						st.write(f"**Altura:** {jugador_actual.get('HEIGHT', 'N/A')}")
						st.write(f"**Edad:** {jugador_actual.get('AGE', 'N/A')}")
					
					st.markdown("---")
					
					# Formulario de actualización
					with st.form("form_actualizar_equipo"):
						nuevo_equipo = st.selectbox(
							"Nuevo Equipo (TEAM_ABBREVIATION) *",
							options=[""] + team_options if team_options else [""],
							help="Selecciona el nuevo equipo para el jugador"
						)
						
						submit_update = st.form_submit_button("✏️ Actualizar Equipo", use_container_width=True)
						
						if submit_update:
							if not nuevo_equipo:
								st.error("❌ Por favor, selecciona un equipo")
							else:
								with st.spinner("Actualizando equipo..."):
									success, message = update_jugador_team(selected_player_id, nuevo_equipo)
									if success:
										st.success(message)
										st.balloons()
										st.rerun()
									else:
										st.error(message)
				else:
					st.warning("⚠️ No se pudo cargar la información del jugador")
		else:
			st.info("📭 No hay jugadores disponibles para actualizar")
	else:
		st.warning("⚠️ No se pudieron cargar los jugadores")

# ==============================================================
# TAB 3: ELIMINAR JUGADOR
# ==============================================================
with tab3:
	st.header("🗑️ Eliminar Jugador")
	st.warning("⚠️ **ATENCIÓN:** Esta acción no se puede deshacer. Ten cuidado al eliminar jugadores.")
	
	# Selector de jugador para eliminar
	if not jugadores.empty:
		# Crear lista de jugadores para el selector
		jugadores_list = []
		if "PLAYER_ID" in jugadores.columns and "FIRST_NAME" in jugadores.columns and "LAST_NAME" in jugadores.columns:
			for _, row in jugadores.iterrows():
				player_id = str(row.get("PLAYER_ID", ""))
				first = str(row.get("FIRST_NAME", "")).strip()
				last = str(row.get("LAST_NAME", "")).strip()
				name = f"{first} {last}".strip()
				if player_id and name:
					jugadores_list.append((player_id, name))
		
		if jugadores_list:
			jugadores_list = sorted(jugadores_list, key=lambda x: x[1])
			jugador_options = {f"{name} (ID: {pid})": pid for pid, name in jugadores_list}
			
			selected_jugador_display = st.selectbox(
				"Seleccionar Jugador a Eliminar",
				options=[""] + list(jugador_options.keys()),
				help="Busca y selecciona el jugador a eliminar"
			)
			
			if selected_jugador_display:
				selected_player_id = jugador_options[selected_jugador_display]
				
				# Mostrar información del jugador
				jugador_actual = get_jugador_by_id(selected_player_id)
				
				if jugador_actual:
					st.markdown("### 📋 Información del Jugador a Eliminar")
					st.error(f"**{jugador_actual.get('FIRST_NAME', '')} {jugador_actual.get('LAST_NAME', '')}** (ID: {jugador_actual.get('PLAYER_ID', '')})")
					st.write(f"- Equipo: {jugador_actual.get('TEAM_ABBREVIATION', 'N/A')}")
					st.write(f"- Posición: {jugador_actual.get('POSITION', 'N/A')}")
					
					# Confirmación
					confirmar = st.checkbox("⚠️ Confirmo que quiero eliminar este jugador", value=False)
					
					if st.button("🗑️ Eliminar Jugador", type="primary", disabled=not confirmar, use_container_width=True):
						with st.spinner("Eliminando jugador..."):
							success, message = delete_jugador(selected_player_id)
							if success:
								st.success(message)
								st.rerun()
							else:
								st.error(message)
				else:
					st.warning("⚠️ No se pudo cargar la información del jugador")
		else:
			st.info("📭 No hay jugadores disponibles")
	else:
		st.warning("⚠️ No se pudieron cargar los jugadores")

# ==============================================================
# TAB 4: CARGAR DATOS DE PARTIDO
# ==============================================================
with tab4:
	st.header("📊 Cargar Datos de Partido")
	st.info("💡 Selecciona un partido futuro y carga las estadísticas de todos los jugadores.")
	
	# Cargar partidos futuros
	partidos, partidos_futuros, _, equipos, jugadores = load_data()
	
	if partidos_futuros.empty:
		st.warning("⚠️ No hay partidos futuros disponibles.")
	else:
		# Selector de partido futuro - ordenar por fecha descendente (más reciente primero)
		partidos_list = []
		for _, row in partidos_futuros.iterrows():
			game_id = str(row.get("GAME_ID", ""))
			fecha = str(row.get("FECHA", ""))
			local = str(row.get("LOCAL", ""))
			visitante = str(row.get("VISITANTE", ""))
			if game_id:
				# Intentar parsear la fecha para ordenar correctamente
				try:
					fecha_parsed = pd.to_datetime(fecha, errors='coerce')
					partidos_list.append((game_id, fecha, local, visitante, fecha_parsed))
				except:
					partidos_list.append((game_id, fecha, local, visitante, None))
		
		# Ordenar por fecha descendente (más reciente primero)
		partidos_list.sort(key=lambda x: x[4] if x[4] is not None and pd.notna(x[4]) else pd.Timestamp.min)
		
		if partidos_list:
			partidos_options = {
				f"{local} vs {visitante} ({fecha}) - ID: {game_id}": game_id
				for game_id, fecha, local, visitante, _ in partidos_list
			}
			
			selected_partido_display = st.selectbox(
				"Seleccionar Partido Futuro",
				options=[""] + list(partidos_options.keys()),
				help="Selecciona el partido para el cual cargar los datos"
			)
			
			if selected_partido_display:
				selected_game_id = partidos_options[selected_partido_display]
				partido_info = get_partido_futuro(selected_game_id)
				
				if partido_info:
					local_team = partido_info.get("LOCAL", "")
					visitante_team = partido_info.get("VISITANTE", "")
					fecha_partido = partido_info.get("FECHA", "")
					
					st.markdown("### 📋 Información del Partido")
					st.write(f"**GAME_ID:** {selected_game_id}")
					st.write(f"**Fecha:** {fecha_partido}")
					st.write(f"**Local:** {local_team}")
					st.write(f"**Visitante:** {visitante_team}")
					st.markdown("---")
					
					# Inicializar lista de jugadores agregados en session_state
					if f"jugadores_agregados_{selected_game_id}" not in st.session_state:
						st.session_state[f"jugadores_agregados_{selected_game_id}"] = []
					
					# Obtener jugadores disponibles de cada equipo
					jugadores_local_disponibles = get_jugadores_por_equipo(local_team)
					jugadores_visitante_disponibles = get_jugadores_por_equipo(visitante_team)
					
					# Formulario para cargar boxscores
					with st.form("form_cargar_partido"):
						st.markdown("### 📊 Estadísticas de Jugadores")
						st.info("💡 Agrega jugadores usando los botones de abajo. Solo agrega los jugadores que participaron en el partido.")
						
						# Secciones para agregar jugadores
						col_add_local, col_add_visitante = st.columns(2)
						
						with col_add_local:
							st.markdown(f"#### 🏠 Agregar Jugador - {local_team}")
							if jugadores_local_disponibles:
								jugadores_local_opts = {
									f"{j.get('FIRST_NAME', '')} {j.get('LAST_NAME', '')} (ID: {j.get('PLAYER_ID', '')})": j
									for j in jugadores_local_disponibles
									if j.get('PLAYER_ID')
								}
								jugador_local_sel = st.selectbox(
									"Seleccionar jugador",
									options=[""] + list(jugadores_local_opts.keys()),
									key=f"sel_local_{selected_game_id}"
								)
								if st.form_submit_button(f"➕ Agregar Jugador Local", key=f"add_local_{selected_game_id}"):
									if jugador_local_sel:
										jugador = jugadores_local_opts[jugador_local_sel]
										player_id = str(jugador.get("PLAYER_ID", ""))
										# Verificar que no esté ya agregado
										if not any(p.get("PLAYER_ID") == player_id and p.get("TEAM") == local_team 
												  for p in st.session_state[f"jugadores_agregados_{selected_game_id}"]):
											st.session_state[f"jugadores_agregados_{selected_game_id}"].append({
												"PLAYER_ID": player_id,
												"PLAYER_NAME": f"{jugador.get('FIRST_NAME', '')} {jugador.get('LAST_NAME', '')}".strip(),
												"TEAM": local_team
											})
											st.rerun()
							else:
								st.info("No hay jugadores disponibles para este equipo")
						
						with col_add_visitante:
							st.markdown(f"#### ✈️ Agregar Jugador - {visitante_team}")
							if jugadores_visitante_disponibles:
								jugadores_visitante_opts = {
									f"{j.get('FIRST_NAME', '')} {j.get('LAST_NAME', '')} (ID: {j.get('PLAYER_ID', '')})": j
									for j in jugadores_visitante_disponibles
									if j.get('PLAYER_ID')
								}
								jugador_visitante_sel = st.selectbox(
									"Seleccionar jugador",
									options=[""] + list(jugadores_visitante_opts.keys()),
									key=f"sel_visitante_{selected_game_id}"
								)
								if st.form_submit_button(f"➕ Agregar Jugador Visitante", key=f"add_visitante_{selected_game_id}"):
									if jugador_visitante_sel:
										jugador = jugadores_visitante_opts[jugador_visitante_sel]
										player_id = str(jugador.get("PLAYER_ID", ""))
										# Verificar que no esté ya agregado
										if not any(p.get("PLAYER_ID") == player_id and p.get("TEAM") == visitante_team 
												  for p in st.session_state[f"jugadores_agregados_{selected_game_id}"]):
											st.session_state[f"jugadores_agregados_{selected_game_id}"].append({
												"PLAYER_ID": player_id,
												"PLAYER_NAME": f"{jugador.get('FIRST_NAME', '')} {jugador.get('LAST_NAME', '')}".strip(),
												"TEAM": visitante_team
											})
											st.rerun()
							else:
								st.info("No hay jugadores disponibles para este equipo")
					
					# Mostrar jugadores agregados y sus estadísticas
					jugadores_agregados = st.session_state.get(f"jugadores_agregados_{selected_game_id}", [])
					
					if jugadores_agregados:
						st.markdown("---")
						st.markdown("### 📊 Estadísticas de Jugadores Agregados")
						
						# Separar jugadores por equipo
						jugadores_local_agregados = [j for j in jugadores_agregados if j.get("TEAM") == local_team]
						jugadores_visitante_agregados = [j for j in jugadores_agregados if j.get("TEAM") == visitante_team]
						
						# Jugadores del equipo local
						if jugadores_local_agregados:
							st.markdown(f"#### 🏠 Equipo Local: {local_team}")
							for idx, jugador_info in enumerate(jugadores_local_agregados):
								player_id = str(jugador_info.get("PLAYER_ID", ""))
								player_name = jugador_info.get("PLAYER_NAME", "")
								
								col_del, col_exp = st.columns([1, 19])
								with col_del:
									if st.button("🗑️", key=f"del_{selected_game_id}_{player_id}", help="Eliminar jugador"):
										st.session_state[f"jugadores_agregados_{selected_game_id}"] = [
											j for j in st.session_state[f"jugadores_agregados_{selected_game_id}"]
											if not (j.get("PLAYER_ID") == player_id and j.get("TEAM") == local_team)
										]
										st.rerun()
								
								with col_exp:
									with st.expander(f"👤 {player_name} (ID: {player_id})", expanded=False):
										col1, col2, col3, col4 = st.columns(4)
										
										with col1:
											# Input de minutos en formato mm:ss
											min_val_decimal = st.session_state.get(f"min_{selected_game_id}_{player_id}", 0.0)
											min_val_mmss = minutos_decimal_a_mmss(min_val_decimal) if min_val_decimal > 0 else "0:00"
											minutos_input = st.text_input("MIN (mm:ss)", value=min_val_mmss, key=f"min_input_{selected_game_id}_{player_id}", help="Formato: mm:ss (ej: 25:30)")
											# Guardar en session_state como decimal
											st.session_state[f"min_{selected_game_id}_{player_id}"] = mmss_a_minutos_decimal(minutos_input)
											pts = st.number_input("PTS", min_value=0, value=st.session_state.get(f"pts_{selected_game_id}_{player_id}", 0), key=f"pts_{selected_game_id}_{player_id}")
											fgm = st.number_input("FGM", min_value=0, value=st.session_state.get(f"fgm_{selected_game_id}_{player_id}", 0), key=f"fgm_{selected_game_id}_{player_id}")
											fga = st.number_input("FGA", min_value=0, value=st.session_state.get(f"fga_{selected_game_id}_{player_id}", 0), key=f"fga_{selected_game_id}_{player_id}")
										
										with col2:
											fg3m = st.number_input("FG3M", min_value=0, value=st.session_state.get(f"fg3m_{selected_game_id}_{player_id}", 0), key=f"fg3m_{selected_game_id}_{player_id}")
											fg3a = st.number_input("FG3A", min_value=0, value=st.session_state.get(f"fg3a_{selected_game_id}_{player_id}", 0), key=f"fg3a_{selected_game_id}_{player_id}")
											ftm = st.number_input("FTM", min_value=0, value=st.session_state.get(f"ftm_{selected_game_id}_{player_id}", 0), key=f"ftm_{selected_game_id}_{player_id}")
											fta = st.number_input("FTA", min_value=0, value=st.session_state.get(f"fta_{selected_game_id}_{player_id}", 0), key=f"fta_{selected_game_id}_{player_id}")
										
										with col3:
											reb = st.number_input("REB", min_value=0, value=st.session_state.get(f"reb_{selected_game_id}_{player_id}", 0), key=f"reb_{selected_game_id}_{player_id}")
											ast = st.number_input("AST", min_value=0, value=st.session_state.get(f"ast_{selected_game_id}_{player_id}", 0), key=f"ast_{selected_game_id}_{player_id}")
											stl = st.number_input("STL", min_value=0, value=st.session_state.get(f"stl_{selected_game_id}_{player_id}", 0), key=f"stl_{selected_game_id}_{player_id}")
											blk = st.number_input("BLK", min_value=0, value=st.session_state.get(f"blk_{selected_game_id}_{player_id}", 0), key=f"blk_{selected_game_id}_{player_id}")
										
										with col4:
											tov = st.number_input("TOV", min_value=0, value=st.session_state.get(f"tov_{selected_game_id}_{player_id}", 0), key=f"tov_{selected_game_id}_{player_id}")
											pf = st.number_input("PF", min_value=0, value=st.session_state.get(f"pf_{selected_game_id}_{player_id}", 0), key=f"pf_{selected_game_id}_{player_id}")
						
						# Jugadores del equipo visitante
						if jugadores_visitante_agregados:
							st.markdown(f"#### ✈️ Equipo Visitante: {visitante_team}")
							for idx, jugador_info in enumerate(jugadores_visitante_agregados):
								player_id = str(jugador_info.get("PLAYER_ID", ""))
								player_name = jugador_info.get("PLAYER_NAME", "")
								
								col_del, col_exp = st.columns([1, 19])
								with col_del:
									if st.button("🗑️", key=f"del_v_{selected_game_id}_{player_id}", help="Eliminar jugador"):
										st.session_state[f"jugadores_agregados_{selected_game_id}"] = [
											j for j in st.session_state[f"jugadores_agregados_{selected_game_id}"]
											if not (j.get("PLAYER_ID") == player_id and j.get("TEAM") == visitante_team)
										]
										st.rerun()
								
								with col_exp:
									with st.expander(f"👤 {player_name} (ID: {player_id})", expanded=False):
										col1, col2, col3, col4 = st.columns(4)
										
										with col1:
											# Input de minutos en formato mm:ss
											min_val_decimal = st.session_state.get(f"min_v_{selected_game_id}_{player_id}", 0.0)
											min_val_mmss = minutos_decimal_a_mmss(min_val_decimal) if min_val_decimal > 0 else "0:00"
											minutos_input = st.text_input("MIN (mm:ss)", value=min_val_mmss, key=f"min_input_v_{selected_game_id}_{player_id}", help="Formato: mm:ss (ej: 25:30)")
											# Guardar en session_state como decimal
											st.session_state[f"min_v_{selected_game_id}_{player_id}"] = mmss_a_minutos_decimal(minutos_input)
											pts = st.number_input("PTS", min_value=0, value=st.session_state.get(f"pts_v_{selected_game_id}_{player_id}", 0), key=f"pts_v_{selected_game_id}_{player_id}")
											fgm = st.number_input("FGM", min_value=0, value=st.session_state.get(f"fgm_v_{selected_game_id}_{player_id}", 0), key=f"fgm_v_{selected_game_id}_{player_id}")
											fga = st.number_input("FGA", min_value=0, value=st.session_state.get(f"fga_v_{selected_game_id}_{player_id}", 0), key=f"fga_v_{selected_game_id}_{player_id}")
										
										with col2:
											fg3m = st.number_input("FG3M", min_value=0, value=st.session_state.get(f"fg3m_v_{selected_game_id}_{player_id}", 0), key=f"fg3m_v_{selected_game_id}_{player_id}")
											fg3a = st.number_input("FG3A", min_value=0, value=st.session_state.get(f"fg3a_v_{selected_game_id}_{player_id}", 0), key=f"fg3a_v_{selected_game_id}_{player_id}")
											ftm = st.number_input("FTM", min_value=0, value=st.session_state.get(f"ftm_v_{selected_game_id}_{player_id}", 0), key=f"ftm_v_{selected_game_id}_{player_id}")
											fta = st.number_input("FTA", min_value=0, value=st.session_state.get(f"fta_v_{selected_game_id}_{player_id}", 0), key=f"fta_v_{selected_game_id}_{player_id}")
										
										with col3:
											reb = st.number_input("REB", min_value=0, value=st.session_state.get(f"reb_v_{selected_game_id}_{player_id}", 0), key=f"reb_v_{selected_game_id}_{player_id}")
											ast = st.number_input("AST", min_value=0, value=st.session_state.get(f"ast_v_{selected_game_id}_{player_id}", 0), key=f"ast_v_{selected_game_id}_{player_id}")
											stl = st.number_input("STL", min_value=0, value=st.session_state.get(f"stl_v_{selected_game_id}_{player_id}", 0), key=f"stl_v_{selected_game_id}_{player_id}")
											blk = st.number_input("BLK", min_value=0, value=st.session_state.get(f"blk_v_{selected_game_id}_{player_id}", 0), key=f"blk_v_{selected_game_id}_{player_id}")
										
										with col4:
											tov = st.number_input("TOV", min_value=0, value=st.session_state.get(f"tov_v_{selected_game_id}_{player_id}", 0), key=f"tov_v_{selected_game_id}_{player_id}")
											pf = st.number_input("PF", min_value=0, value=st.session_state.get(f"pf_v_{selected_game_id}_{player_id}", 0), key=f"pf_v_{selected_game_id}_{player_id}")
						
						# Calcular totales para mostrar (desde session_state)
						pts_local_display = sum(
							st.session_state.get(f"pts_{selected_game_id}_{j.get('PLAYER_ID')}", 0)
							for j in jugadores_local_agregados
						)
						pts_visitante_display = sum(
							st.session_state.get(f"pts_v_{selected_game_id}_{j.get('PLAYER_ID')}", 0)
							for j in jugadores_visitante_agregados
						)
						
						# Mostrar resumen
						st.markdown("---")
						st.markdown("### 📈 Resumen del Partido")
						col_res1, col_res2 = st.columns(2)
						with col_res1:
							st.metric("Puntos Local", pts_local_display)
						with col_res2:
							st.metric("Puntos Visitante", pts_visitante_display)
						
						# Botón para guardar
						if st.button("💾 Guardar Partido y Mover a Jugados", key=f"save_{selected_game_id}", use_container_width=True, type="primary"):
							# Reconstruir boxscores_data desde los valores en session_state
							boxscores_data_final = []
							
							# Boxscores del equipo local
							for jugador_info in jugadores_local_agregados:
								player_id = str(jugador_info.get("PLAYER_ID", ""))
								player_name = jugador_info.get("PLAYER_NAME", "")
								
								boxscore = {
									"GAME_ID": selected_game_id,
									"TEAM_ABBREVIATION": local_team,
									"PLAYER_ID": player_id,
									"PLAYER_NAME": player_name,
									"MIN": st.session_state.get(f"min_{selected_game_id}_{player_id}", 0.0),
									"PTS": st.session_state.get(f"pts_{selected_game_id}_{player_id}", 0),
									"FGM": st.session_state.get(f"fgm_{selected_game_id}_{player_id}", 0),
									"FGA": st.session_state.get(f"fga_{selected_game_id}_{player_id}", 0),
									"FG3M": st.session_state.get(f"fg3m_{selected_game_id}_{player_id}", 0),
									"FG3A": st.session_state.get(f"fg3a_{selected_game_id}_{player_id}", 0),
									"FTM": st.session_state.get(f"ftm_{selected_game_id}_{player_id}", 0),
									"FTA": st.session_state.get(f"fta_{selected_game_id}_{player_id}", 0),
									"REB": st.session_state.get(f"reb_{selected_game_id}_{player_id}", 0),
									"AST": st.session_state.get(f"ast_{selected_game_id}_{player_id}", 0),
									"STL": st.session_state.get(f"stl_{selected_game_id}_{player_id}", 0),
									"BLK": st.session_state.get(f"blk_{selected_game_id}_{player_id}", 0),
									"TOV": st.session_state.get(f"tov_{selected_game_id}_{player_id}", 0),
									"PF": st.session_state.get(f"pf_{selected_game_id}_{player_id}", 0)
								}
								boxscores_data_final.append(boxscore)
							
							# Boxscores del equipo visitante
							for jugador_info in jugadores_visitante_agregados:
								player_id = str(jugador_info.get("PLAYER_ID", ""))
								player_name = jugador_info.get("PLAYER_NAME", "")
								
								boxscore = {
									"GAME_ID": selected_game_id,
									"TEAM_ABBREVIATION": visitante_team,
									"PLAYER_ID": player_id,
									"PLAYER_NAME": player_name,
									"MIN": st.session_state.get(f"min_v_{selected_game_id}_{player_id}", 0.0),
									"PTS": st.session_state.get(f"pts_v_{selected_game_id}_{player_id}", 0),
									"FGM": st.session_state.get(f"fgm_v_{selected_game_id}_{player_id}", 0),
									"FGA": st.session_state.get(f"fga_v_{selected_game_id}_{player_id}", 0),
									"FG3M": st.session_state.get(f"fg3m_v_{selected_game_id}_{player_id}", 0),
									"FG3A": st.session_state.get(f"fg3a_v_{selected_game_id}_{player_id}", 0),
									"FTM": st.session_state.get(f"ftm_v_{selected_game_id}_{player_id}", 0),
									"FTA": st.session_state.get(f"fta_v_{selected_game_id}_{player_id}", 0),
									"REB": st.session_state.get(f"reb_v_{selected_game_id}_{player_id}", 0),
									"AST": st.session_state.get(f"ast_v_{selected_game_id}_{player_id}", 0),
									"STL": st.session_state.get(f"stl_v_{selected_game_id}_{player_id}", 0),
									"BLK": st.session_state.get(f"blk_v_{selected_game_id}_{player_id}", 0),
									"TOV": st.session_state.get(f"tov_v_{selected_game_id}_{player_id}", 0),
									"PF": st.session_state.get(f"pf_v_{selected_game_id}_{player_id}", 0)
								}
								boxscores_data_final.append(boxscore)
							
							if not boxscores_data_final:
								st.error("❌ No hay datos de boxscore para guardar. Agrega al menos un jugador.")
							else:
								with st.spinner("Guardando datos del partido..."):
									# Calcular totales finales
									pts_local_final = sum(b.get("PTS", 0) for b in boxscores_data_final if b.get("TEAM_ABBREVIATION") == local_team)
									pts_visitante_final = sum(b.get("PTS", 0) for b in boxscores_data_final if b.get("TEAM_ABBREVIATION") == visitante_team)
									
									# Cargar partido completo en el orden correcto:
									# 1. Crear partido en partidos (para FK)
									# 2. Insertar boxscores
									# 3. Eliminar de partidos_futuros
									success, message = cargar_partido_completo(
										selected_game_id,
										boxscores_data_final,
										pts_local_final,
										pts_visitante_final
									)
									
									if success:
										st.success(message)
										st.balloons()
										# Limpiar session_state
										if f"jugadores_agregados_{selected_game_id}" in st.session_state:
											del st.session_state[f"jugadores_agregados_{selected_game_id}"]
										# Limpiar todos los valores de estadísticas de este partido
										for key in list(st.session_state.keys()):
											if key.startswith(f"min_{selected_game_id}_") or key.startswith(f"min_input_{selected_game_id}_") or \
											   key.startswith(f"pts_{selected_game_id}_") or \
											   key.startswith(f"fgm_{selected_game_id}_") or key.startswith(f"fga_{selected_game_id}_") or \
											   key.startswith(f"fg3m_{selected_game_id}_") or key.startswith(f"fg3a_{selected_game_id}_") or \
											   key.startswith(f"ftm_{selected_game_id}_") or key.startswith(f"fta_{selected_game_id}_") or \
											   key.startswith(f"reb_{selected_game_id}_") or key.startswith(f"ast_{selected_game_id}_") or \
											   key.startswith(f"stl_{selected_game_id}_") or key.startswith(f"blk_{selected_game_id}_") or \
											   key.startswith(f"tov_{selected_game_id}_") or key.startswith(f"pf_{selected_game_id}_"):
												del st.session_state[key]
										st.rerun()
									else:
										st.error(message)
					else:
						st.info("📭 Agrega jugadores usando los selectores de arriba para comenzar a cargar estadísticas.")
				else:
					st.error(f"❌ No se pudo cargar la información del partido {selected_game_id}")
		else:
			st.info("📭 No hay partidos futuros disponibles para cargar")

# ==============================================================
# TAB 5: ELIMINAR PARTIDO
# ==============================================================
with tab5:
	st.header("🗑️ Eliminar Partido")
	st.warning("⚠️ **ATENCIÓN:** Esta acción eliminará todos los boxscores del partido y lo moverá de vuelta a partidos futuros. Esta acción no se puede deshacer fácilmente.")
	
	# Cargar partidos jugados
	partidos, _, _, equipos, jugadores = load_data()
	
	if partidos.empty:
		st.warning("⚠️ No hay partidos jugados disponibles.")
	else:
		# Selector de partido jugado - ordenar por fecha descendente (más reciente primero)
		partidos_list = []
		for _, row in partidos.iterrows():
			game_id = str(row.get("GAME_ID", ""))
			fecha = str(row.get("FECHA", ""))
			local = str(row.get("LOCAL", ""))
			visitante = str(row.get("VISITANTE", ""))
			pts_local = row.get("PTS_LOCAL", 0)
			pts_visitante = row.get("PTS_VISITANTE", 0)
			if game_id:
				# Intentar parsear la fecha para ordenar correctamente
				try:
					fecha_parsed = pd.to_datetime(fecha, errors='coerce')
					partidos_list.append((game_id, fecha, local, visitante, pts_local, pts_visitante, fecha_parsed))
				except:
					partidos_list.append((game_id, fecha, local, visitante, pts_local, pts_visitante, None))
		
		# Ordenar por fecha descendente (más reciente primero)
		partidos_list.sort(key=lambda x: x[6] if x[6] is not None and pd.notna(x[6]) else pd.Timestamp.min, reverse=True)
		
		if partidos_list:
			partidos_options = {
				f"{local} {pts_local} - {pts_visitante} {visitante} ({fecha}) - ID: {game_id}": game_id
				for game_id, fecha, local, visitante, pts_local, pts_visitante, _ in partidos_list
			}
			
			selected_partido_display = st.selectbox(
				"Seleccionar Partido a Eliminar",
				options=[""] + list(partidos_options.keys()),
				help="Selecciona el partido que deseas eliminar"
			)
			
			if selected_partido_display:
				selected_game_id = partidos_options[selected_partido_display]
				partido_info = get_partido_jugado(selected_game_id)
				
				if partido_info:
					st.markdown("### 📋 Información del Partido a Eliminar")
					st.error(f"**GAME_ID:** {selected_game_id}")
					st.write(f"**Fecha:** {partido_info.get('FECHA', 'N/A')}")
					st.write(f"**Local:** {partido_info.get('LOCAL', 'N/A')} - **Puntos:** {partido_info.get('PTS_LOCAL', 0)}")
					st.write(f"**Visitante:** {partido_info.get('VISITANTE', 'N/A')} - **Puntos:** {partido_info.get('PTS_VISITANTE', 0)}")
					st.markdown("---")
					
					# Confirmación
					confirmar = st.checkbox("⚠️ Confirmo que quiero eliminar este partido y todos sus boxscores", value=False)
					
					if st.button("🗑️ Eliminar Partido", type="primary", disabled=not confirmar, use_container_width=True):
						with st.spinner("Eliminando partido..."):
							success, message = eliminar_partido(selected_game_id)
							if success:
								st.success(message)
								st.balloons()
								st.rerun()
							else:
								st.error(message)
				else:
					st.error(f"❌ No se pudo cargar la información del partido {selected_game_id}")
		else:
			st.info("📭 No hay partidos jugados disponibles")

# Footer
st.markdown("---")
if st.button("⬅ Volver al Dashboard"):
	st.switch_page("Home.py")

