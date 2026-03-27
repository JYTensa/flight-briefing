import streamlit as st
import requests
from openai import OpenAI
import datetime

# ==========================================
# 1. PAGE SETUP
# ==========================================
st.set_page_config(page_title="Tonye's Flight Briefing", page_icon="✈️", layout="centered")

# ==========================================
# 2. API KEYS & SETUP (Using Secrets)
# ==========================================
CHECKWX_API_KEY = st.secrets["CHECKWX_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_KEY"]

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# ==========================================
# 3. DATA FUNCTIONS
# ==========================================
def get_weather_data(icao_code, report_type="taf"):
    url = f"https://api.checkwx.com/{report_type}/{icao_code}/decoded"
    headers = {"X-API-Key": CHECKWX_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get('results', 0) > 0:
            return data['data'][0].get('raw_text', 'No raw text available')
        return f"No {report_type.upper()} data published."
    except Exception as e:
        return f"Error: {e}"

def generate_briefing(weather_context, flight_plan_summary):
    system_prompt = f"""
    You are a highly experienced British aviation assistant. Write a detailed but structured pre-flight briefing for Pilot Tonye.
    
    TONE: Start exactly with: "Morning Tonye,\nHope you slept well." Be professional and direct. 
    If weather violates limits, use phrases like "not satisfactory conditions".
    
    FLIGHT PLAN & LIMITS:
    {flight_plan_summary}
    
    WEATHER DATA:
    {weather_context}
    
    INSTRUCTIONS:
    1. Overall Assessment: One clear Go/No-Go sentence based on his minimums.
    2. Airport Breakdown: For EACH airport provided, give exactly THREE bullet points:
        - Bullet 1: Wind analysis (speed/gusts) vs limits.
        - Bullet 2: Cloud/Visibility vs limits.
        - Bullet 3: Timing/Trends during his specific flight window.
    3. Outlook: A brief 1-2 sentence outlook for tomorrow.
    """

    response = client.chat.completions.create(
        model="gemini-2.5-flash", 
        messages=[
            {"role": "system", "content": "You are a precise aviation weather assistant."},
            {"role": "user", "content": system_prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content


# ==========================================
# 4. STREAMLIT APP INTERFACE
# ==========================================
st.title("✈️ Morning, Tonye")
st.write("Check your VFR minimums against the latest CheckWX data.")

# Interactive Flight Plan Box
with st.expander("📝 Current Flight Parameters", expanded=True):
    flight_plan = st.text_area(
        "Edit your flight plan or limits here before generating:",
        value="Route: Stansted (EGSS) to Shoreham (EGKA) via North Weald (EGSX) and Southend (EGMC).\nTime: 0915Z to 1300Z\nLimits: Max wind 15kt steady / 20kt gust. Min cloud 1500ft. Min Vis 8000m.",
        height=100
    )

# The Big Button
if st.button("Generate Briefing", type="primary"):
    with st.spinner("Fetching METARs & TAFs and analyzing..."):
        
        airports = ["EGSS", "EGSX", "EGMC", "EGKA"]
        compiled_weather = ""
        
        for icao in airports:
            metar = get_weather_data(icao, "metar")
            taf = get_weather_data(icao, "taf")
            compiled_weather += f"--- {icao} ---\nMETAR: {metar}\nTAF: {taf}\n\n"
        
        briefing = generate_briefing(compiled_weather, flight_plan)
        
        st.markdown("---")
        st.markdown("### 📋 Pre-Flight Analysis")
        st.markdown(briefing)
