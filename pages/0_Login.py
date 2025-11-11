import streamlit as st
from utils import login, check_auth, init_session_state, get_current_user

st.set_page_config(page_title="Inicio de Sesión | NBA Stats App", layout="centered")

# Inicializar estado de sesión
init_session_state()

st.title("🏀 NBA Stats App")
st.markdown("### Inicio de Sesión")

# Mostrar estado actual
if check_auth():
	st.success("✅ Ya estás autenticado")
	user = get_current_user()
	if user:
		st.info(f"👤 Sesión activa: {user.email}")
	st.markdown("---")
else:
	st.info("💡 Puedes usar la aplicación de forma anónima, pero iniciar sesión te da acceso a funcionalidades adicionales.")
	st.markdown("---")

# Formulario de login
with st.form("login_form"):
	email = st.text_input("📧 Email", placeholder="tu@email.com")
	password = st.text_input("🔒 Contraseña", type="password", placeholder="••••••••")
	submit_button = st.form_submit_button("Iniciar Sesión", use_container_width=True)

if submit_button:
	if not email or not password:
		st.error("Por favor, completa todos los campos")
	else:
		with st.spinner("Iniciando sesión..."):
			success, message = login(email, password)
			if success:
				st.success(message)
				st.balloons()
				st.rerun()
			else:
				st.error(message)

st.markdown("---")
if not check_auth():
	st.info("💡 Si no tienes una cuenta, contacta al administrador para registrarte.")
	st.info("💡 Puedes usar la aplicación sin iniciar sesión, pero algunas funcionalidades estarán limitadas según las políticas RLS configuradas en Supabase.")
else:
	if st.button("⬅ Volver al Dashboard"):
		st.switch_page("Home.py")

