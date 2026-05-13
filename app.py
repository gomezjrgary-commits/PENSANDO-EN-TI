import streamlit as st
import pandas as pd
import sqlite3
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- CONFIGURACIÓN DE PÁGINA PARA MÓVIL ---
st.set_page_config(
    page_title="Pensando en Ti - Cobranza",
    page_icon="💎",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- ESTILO VISUAL ---
st.markdown("""
    <style>
    .stButton>button {
        background-color: #f7a1f5; /* Rosa del logo */
        color: black;
        border-radius: 12px;
        width: 100%;
        height: 3em;
        font-weight: bold;
    }
    .stMetric {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #f7a1f5;
    }
    </style>
    """, unsafe_allow_html=True)

# --- BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('cobranza_v3.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prestamos
                 (id INTEGER PRIMARY KEY, cliente TEXT, monto_original REAL, 
                  saldo REAL, fecha TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pagos
                 (id INTEGER PRIMARY KEY, prestamo_id INTEGER, monto_pago REAL, 
                  multa REAL, fecha_pago TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS retiros
                 (id INTEGER PRIMARY KEY, monto_retiro REAL, motivo TEXT, fecha TEXT)''')
    conn.commit()
    conn.close()

# --- FUNCIÓN DE CORREO ---
def enviar_reporte(nombre_archivo):
    # Nota: Estos datos se configuran en "Secrets" de Streamlit Cloud
    try:
        remitente = st.secrets["EMAIL_EMISOR"]
        password = st.secrets["EMAIL_PASSWORD"]
        destinatario = st.secrets["EMAIL_RECEPTOR"]

        msg = MIMEMultipart()
        msg['From'] = remitente
        msg['To'] = destinatario
        msg['Subject'] = f"Corte de Caja - {datetime.now().strftime('%d/%m/%Y')}"
        
        msg.attach(MIMEText("Adjunto reporte de cobranza 'Pensando en Ti'.", 'plain'))
        
        with open(nombre_archivo, "rb") as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {nombre_archivo}")
            msg.attach(part)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())
        server.quit()
        return True
    except:
        return False

# --- LÓGICA DE INTERFAZ ---
init_db()

# Logo
try:
    st.image("182032.jpg", use_container_width=True)
except:
    st.title("💎 PENSANDO EN TI")

menu = ["🏠 Inicio", "➕ Nuevo Préstamo", "💰 Cobrar", "📤 Retiros y Corte"]
choice = st.sidebar.radio("Navegación", menu)

if choice == "🏠 Inicio":
    conn = sqlite3.connect('cobranza_v3.db')
    ingresos = pd.read_sql_query("SELECT SUM(monto_pago + multa) as t FROM pagos", conn)['t'][0] or 0
    egresos = pd.read_sql_query("SELECT SUM(monto_retiro) as t FROM retiros", conn)['t'][0] or 0
    
    st.metric("Efectivo en Caja", f"${ingresos - egresos:,.2f}")
    
    st.write("### Cuentas Pendientes")
    activos = pd.read_sql_query("SELECT cliente, saldo FROM prestamos WHERE saldo > 0", conn)
    st.dataframe(activos, use_container_width=True)
    conn.close()

elif choice == "➕ Nuevo Préstamo":
    st.subheader("Registrar Nuevo Crédito")
    with st.form("p_form"):
        cliente = st.text_input("Nombre del Cliente")
        monto = st.number_input("Cantidad Prestada ($)", min_value=0.0, step=100.0)
        if st.form_submit_button("Guardar"):
            total = monto * 1.15 # 15% Interés
            conn = sqlite3.connect('cobranza_v3.db')
            c = conn.cursor()
            c.execute("INSERT INTO prestamos (cliente, monto_original, saldo, fecha) VALUES (?,?,?,?)",
                      (cliente, monto, total, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            conn.close()
            st.success(f"Registrado. Total a cobrar: ${total}")

elif choice == "💰 Cobrar":
    st.subheader("Registrar Abono")
    conn = sqlite3.connect('cobranza_v3.db')
    df = pd.read_sql_query("SELECT id, cliente, saldo FROM prestamos WHERE saldo > 0", conn)
    
    if not df.empty:
        opciones = {f"{r['cliente']} (Debe: ${r['saldo']})": r['id'] for i, r in df.iterrows()}
        sel = st.selectbox("Cliente", list(opciones.keys()))
        abono = st.number_input("Monto del pago", min_value=0.0)
        multa = st.number_input("Multa ($20)", min_value=0.0, step=20.0)
        
        if st.button("Confirmar Pago"):
            p_id = opciones[sel]
            c = conn.cursor()
            c.execute("UPDATE prestamos SET saldo = saldo - ? WHERE id = ?", (abono, p_id))
            c.execute("INSERT INTO pagos (prestamo_id, monto_pago, multa, fecha_pago) VALUES (?,?,?,?)",
                      (p_id, abono, multa, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            st.balloons()
            st.success("Pago registrado correctamente.")
    conn.close()

elif choice == "📤 Retiros y Corte":
    st.subheader("Salidas de Dinero")
    monto_r = st.number_input("Monto a retirar de caja", min_value=0.0)
    motivo = st.text_input("Concepto (Gasolina, Depósito, etc.)")
    
    if st.button("Registrar Retiro"):
        conn = sqlite3.connect('cobranza_v3.db')
        c = conn.cursor()
        c.execute("INSERT INTO retiros (monto_retiro, motivo, fecha) VALUES (?,?,?)",
                  (monto_r, motivo, datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        conn.close()
        st.warning("Retiro guardado.")

    st.write("---")
    if st.button("📧 Enviar Corte al Correo"):
        conn = sqlite3.connect('cobranza_v3.db')
        reporte = pd.read_sql_query("SELECT * FROM pagos", conn)
        reporte.to_excel("Corte_Caja.xlsx", index=False)
        if enviar_reporte("Corte_Caja.xlsx"):
            st.success("¡Correo enviado!")
        else:
            st.error("Error al enviar. Verifica tus Secrets.")
        conn.close()