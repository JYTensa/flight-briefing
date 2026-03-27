import streamlit as st
import requests
from openai import OpenAI
import datetime

# ==========================================
# 1. PAGE SETUP & THEME
# ==========================================
st.set_page_config(page_title="Flight Briefing", page_icon="✈️", layout="centered")

# Custom CSS for the Navy Blue Theme
st.markdown("""
    <style>
    /* Main background */
    .stApp {
        background-color: #001529;
        color: #e6f7ff;
    }
    /* Headers */
    h1, h2, h3 {
        color: #ffffff !important;
    }
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #002140 !important;
        border-radius: 5px;
    }
    /* Button styling */
    .stButton>button {
        background-color: #1890ff;
        color: white;
        border-radius: 10px;
        border: none;
        width: 100%;
    }
    /* Input and Slider labels */
    .stSlider label, .stTextInput label {
        color: #bae7ff !important;
    }
    </style>
    """, unsafe_content_label=True, unsafe_content_type="html")

# ==========================================
# 2. API KEYS & SETUP
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

def generate_briefing(weather_context, flight_plan_summary, pilot_name):
    system_prompt = f"""
    You are a highly experienced British aviation assistant. Write a structured pre-flight briefing for Pilot {pilot_name}.
    
    TONE: Start exactly with: "Morning {pilot_name},\nHope you slept well." 
    Be professional, direct, and use British aviation phrasing.
    
    FLIGHT PLAN & LIMITS:
    {flight_plan_summary}
    
    WEATHER DATA:
    {weather_context}
    
    INSTRUCTIONS:
    1. Overall Assessment: One clear Go/No-Go sentence.
    2. Airport Breakdown: For EACH airport, provide exactly THREE bullet points (Winds, Cloud/Vis, Timing/Trends).
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
# 4. INTERACTIVE USER INTERFACE
# ==========================================
with st.expander("📝 Pilot & Flight Parameters", expanded=True):
    user_name = st.text_input("Pilot Name:", value="Tonye")
    
    st.divider()
    
    route_raw = st.text_input("Route (ICAO codes separated by commas):", value="EGSS, EGSX, EGMC, EGKA")
    selected_airports = [icao.strip().upper() for icao in route_raw.split(",") if icao.strip()]

    col1, col2 = st.columns(2)
    with col1:
        dep_time = st.time_input("Departure Time (Z)", datetime.time(9, 15))
    with col2:
        ret_time = st.time_input("Return Time (Z)", datetime.time(13, 0))

    st.write("**Personal Minimums**")
    c1, c2 = st.columns(2)
    with c1:
        max_wind = st.slider("Max Wind (kts)", 5, 30, 15)
        min_cloud = st.slider("Min Cloud (ft)", 500, 5000, 1500, step=100)
    with c2:
        max_gust = st.slider("Max Gust (kts)", 5, 45, 20)
        min_vis = st.slider("Min Vis (m)", 1000, 10000, 8000, step=500)

    flight_summary = f"""
    Route: {', '.join(selected_airports)}
    Times: {dep_time.strftime('%H%MZ')} to {ret_time.strftime('%H%MZ')}
    Limits: {max_wind}kt wind / {max_gust}kt gust. {min_cloud}ft cloud base. {min_vis}m visibility.
    """

st.title(f"✈️ Morning, {user_name}")

# ==========================================
# 5. EXECUTION
# ==========================================
if st.button("Generate Briefing", type="primary"):
    if not selected_airports:
        st.warning("Please enter at least one ICAO code.")
    else:
        with st.spinner(f"Analyzing weather for Pilot {user_name}..."):
            weather_report = ""
            for icao in selected_airports:
                m = get_weather_data(icao, "metar")
                t = get_weather_data(icao, "taf")
                weather_report += f"--- {icao} ---\nMETAR: {m}\nTAF: {t}\n\n"
            
            output = generate_briefing(weather_report, flight_summary, user_name)
            
            st.markdown("---")
            st.markdown(f"### 📋 Pre-Flight Analysis for {user_name}")
            st.markdown(output)
            
            with st.expander("🔍 View Raw Weather Data"):
                st.code(weather_report)
