import os
import requests
import json
from datetime import datetime
import psycopg2
from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DE CREDENCIALES (DESDE VARIABLES DE ENTORNO)
# ---------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
FMP_API_KEY = os.environ.get("FMP_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")  # URL de conexión de Supabase (PostgreSQL)

# ---------------------------------------------------------
# 2. CONEXIÓN A LA BASE DE DATOS EN LA NUBE
# ---------------------------------------------------------
def inicializar_base_datos():
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL no configurada. Saltando conexión a BD.")
        return
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS noticias_procesadas (
            id SERIAL PRIMARY KEY,
            timestamp TEXT,
            ticker TEXT,
            sentimiento TEXT,
            impacto TEXT,
            catalizador TEXT,
            plan_operativo TEXT,
            titular_original TEXT
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

# ---------------------------------------------------------
# 3. DEFINICIÓN DEL EQUIPO DE AGENTES EN CREWAI
# ---------------------------------------------------------
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    api_key=OPENAI_API_KEY
)

news_analyst_agent = Agent(
    role="Analista Senior de Noticias Bursátiles y Sentimiento",
    goal="Filtrar el ruido mediático, identificar los tickers principales y determinar el impacto cuantitativo del titular.",
    backstory="Eres un analista de datos bursátiles cuantitativos especializado en procesar noticias en tiempo real.",
    verbose=False,
    allow_delegation=False,
    llm=llm
)

trading_strategist_agent = Agent(
    role="Estratega de Trading y Gestión de Riesgo",
    goal="Generar una hipótesis operativa concisa en formato JSON para el trader.",
    backstory="Eres un trader institucional experto en transformar el sesgo de las noticias en planes de entrada y salida rápida.",
    verbose=False,
    allow_delegation=False,
    llm=llm
)

def analizar_noticia_con_agentes(titular: str, texto: str, fuente: str):
    task_analisis = Task(
        description=f"""Analiza esta noticia de {fuente}:
        TITULAR: {titular}
        TEXTO: {texto}

        Determina:
        1. Ticker afectado (ej: $NVDA, $AAPL, $SPY). Si no hay uno claro, pon $MACRO.
        2. Catalizador principal (máximo 5 palabras).
        3. Sentimiento: Alcista, Bajista o Neutral.
        4. Score de Impacto: Del 1 al 10.""",
        expected_output="Resumen analítico preliminar.",
        agent=news_analyst_agent
    )

    task_estrategia = Task(
        description="""Con base en el análisis anterior, genera un objeto JSON válido con la siguiente estructura exacta sin formato markdown alrededor:
        {
          "ticker": "$TICKER",
          "sentimiento": "🟢 Alcista (+0.80)" o "🔴 Bajista (-0.75)" o "⚪ Neutral",
          "impacto": "X/10",
          "catalizador": "Texto corto",
          "plan_operativo": "Acción sugerida para el trader en 1 o 2 oraciones."
        }""",
        expected_output="JSON estricto con las claves: ticker, sentimiento, impacto, catalizador, plan_operativo",
        agent=trading_strategist_agent
    )

    crew = Crew(
        agents=[news_analyst_agent, trading_strategist_agent],
        tasks=[task_analisis, task_estrategia],
        process=Process.sequential,
        verbose=False
    )

    return str(crew.kickoff())

# ---------------------------------------------------------
# 4. CONECTOR A LA API DE NOTICIAS (FMP) Y PIPELINE
# ---------------------------------------------------------
def obtener_noticias_fmp(limit: int = 3):
    url = f"https://financialmodelingprep.com/api/v3/stock_news?limit={limit}&apikey={FMP_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"Error al conectar con la API: {e}")
        return []

def ejecutar_pipeline_ingesta():
    inicializar_base_datos()
    print("🔎 Buscando noticias recientes en la API...")
    noticias = obtener_noticias_fmp(limit=3)
    
    if not noticias:
        print("No se obtuvieron noticias de la API.")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    for item in noticias:
        titular = item.get("title", "")
        texto = item.get("text", "")
        site = item.get("site", "Market Source")
        
        print(f"\n📰 Procesando: {titular[:60]}...")
        resultado_json_str = analizar_noticia_con_agentes(titular, texto, site)
        
        try:
            clean_json = resultado_json_str.replace("```json", "").replace("```", "").strip()
            datos = json.loads(clean_json)
            
            cursor.execute("""
                INSERT INTO noticias_procesadas (timestamp, ticker, sentimiento, impacto, catalizador, plan_operativo, titular_original)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                datetime.now().strftime("%H:%M:%S"),
                datos.get("ticker", "$MACRO"),
                datos.get("sentimiento", "Neutral"),
                datos.get("impacto", "5/10"),
                datos.get("catalizador", "Noticia de mercado"),
                datos.get("plan_operativo", "Monitorear acción del precio"),
                titular
            ))
            conn.commit()
            print("✅ Noticia procesada y guardada en Supabase.")
            
        except json.JSONDecodeError:
            print("⚠️ No se pudo parsear la respuesta del agente como JSON.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    ejecutar_pipeline_ingesta()
