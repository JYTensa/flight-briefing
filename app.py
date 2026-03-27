import streamlit as st
import requests
from openai import OpenAI

# ==========================================
# 1. PAGE SETUP
# ==========================================
# This must be the very first Streamlit command
st.set_page_config(page_title="Tonye's Flight Briefing", page_icon="✈️")


# ==========================================
# 2. API KEYS & SETUP
# ==========================================
# We use st.secrets so your keys stay hidden on the server
# We ask Streamlit for the "labels", not the actual keys
CHECKWX_API_KEY = st.secrets["CHECKWX_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_KEY"]

# Initialize the AI client
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
        return f"Error fetching {report_type.upper()} for {icao_code}: {e}"

def generate_briefing(weather_context, flight_plan):
    system_prompt = f"""
    You are a highly experienced British aviation assistant. Write a detailed but highly structured pre-flight briefing for Pilot Tonye.
    
    TONE: Start exactly with: "Morning Tonye,\nHope you slept well." Be polite, professional, and direct. Use phrases like "wishful for me to hope" or "not satisfactory conditions" if the weather violates his limits.
    
    FLIGHT PLAN & LIMITS:
    {flight_plan}
    
    WEATHER DATA:
    {weather_context}
    
    INSTRUCTIONS:
    1. Overall Assessment: Open with a single, clear Go/No-Go sentence based strictly on his personal minimums.
    2. Airport Breakdown: For EACH airport (Stansted, North Weald, Southend, Shoreham), you MUST provide exactly THREE bullet points. Do not write paragraphs.
        - Bullet 1: Wind analysis (speed, gusts, direction) compared to his limits.
        - Bullet 2: Cloud base and visibility analysis compared to his limits.
        - Bullet 3: Timing and trends (how it develops specifically during his 0915Z-1300Z window).
    3. Missing Data: If an airport is missing data, use your 3 bullets to briefly state what is missing and advise caution.
    4. Outlook: Conclude with a brief 1-2 sentence outlook for tomorrow.
    """

    response = client.chat.completions.create(
        model="gemini-2.5-flash", 
        messages=[
            {"role": "system", "content": "You are a precise and structured aviation weather assistant."},
            {"role": "user", "content": system_prompt}
        ],
        temperature=0.6 # Lowered slightly to make the AI follow the 3-bullet rule more strictly
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