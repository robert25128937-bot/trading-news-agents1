import streamlit as st
import pandas as pd
import psycopg2
import os

st.set_page_config(page_title="Trading Intelligence Dashboard", layout="wide")

st.title("⚡ Agente de Noticias & Sentimiento Bursátil")
st.caption("Plataforma de inteligencia de mercado impulsada por Agentes Autónomos de IA en la nube")

# Botón para recargar datos de la base de datos
if st.button("🔄 Actualizar Datos"):
    st.rerun()

# Conexión a la base de datos PostgreSQL (Supabase) mediante secrets de Streamlit o variables de entorno
try:
    db_url = st.secrets["DATABASE_URL"] if "DATABASE_URL" in st.secrets else os.environ.get("DATABASE_URL")
    
    if db_url:
        conn = psycopg2.connect(db_url)
        query = "SELECT timestamp as Hora, ticker as Ticker, sentimiento as Sentimiento, impacto as Impacto, catalizador as Catalizador, plan_operativo as 'Plan Operativo', titular_original as Titular FROM noticias_procesadas ORDER BY id DESC LIMIT 50"
        df = pd.read_sql_query(query, conn)
        conn.close()
    else:
        df = pd.DataFrame()
except Exception as e:
    df = pd.DataFrame()
    st.error(f"Error conectando a la base de datos: {e}")

if not df.empty:
    # Métricas superiores
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Noticias Procesadas", len(df))
    col2.metric("Último Ticker Analizado", df.iloc[0]["Ticker"])
    col3.metric("Último Impacto Registrado", df.iloc[0]["Impacto"])

    st.divider()
    st.subheader("📰 Flujo Operativo Procesado por los Agentes")
    st.dataframe(df, use_container_width=True)
else:
    st.info("Aún no hay registros en la base de datos. Configura tus credenciales y ejecuta el pipeline de agentes para poblar el dashboard.")
