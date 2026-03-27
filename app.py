import streamlit as st
import requests
from openai import OpenAI
import datetime
from fpdf import FPDF
import math

# ==========================================
# 1. PAGE SETUP & THEME
# ==========================================
st.set_page_config(page_title="Flight Briefing", page_icon="✈️", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #001529; color: #e6f7ff; }
    h1, h2, h3 { color: #ffffff !important; }
    .streamlit-expanderHeader { background-color: #002140 !important; border-radius: 5px; }
    .stButton>button { background-color: #1890ff; color: white; border-radius: 10px; width: 100%; border: none; font-weight: bold; height: 3em; }
    .stSlider label, .stTextInput label, .stDateInput label { color: #bae7ff !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. HELPERS & MATH
# ==========================================
CHECKWX_API_KEY = st.secrets["CHECKWX_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_KEY"]
client = OpenAI(api_key=GEMINI_API_KEY, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

def calculate_xwind(wind_speed, wind_dir, rwy_hdg):
    angle = abs(wind_dir - rwy_hdg)
    rad = math.radians(angle)
    xwind = abs(wind_speed * math.sin(rad))
    headwind = wind_speed * math.cos(rad)
    return round(xwind, 1), round(headwind, 1)

def get_dynamic_greeting():
    hour = datetime.datetime.now().hour
    if hour < 12: return "Morning", "Hope you slept well."
    elif 12 <= hour < 17: return "Afternoon", "Hope your day is going well."
    else: return "Evening", "Hope you've had a productive day."

def get_weather_data(icao_code, report_type="taf"):
    url = f"https://api.checkwx.com/{report_type}/{icao_code}/decoded"
    headers = {"X-API-Key": CHECKWX_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get('results', 0) > 0:
            return data['data'][0].get('raw_text', 'No data'), data['data'][0]
        return "No data published.", None
    except Exception: return "Error fetching data.", None

def generate_briefing(weather_context, flight_plan_summary, pilot_name, greeting_pack):
    greet, opener = greeting_pack
    # Instructions updated to be even more strict about the first line
    system_prompt = f"""
    You are an experienced British aviation assistant. Write a structured briefing for Pilot {pilot_name}.
    TONE: Start with: "{greet} {pilot_name}, {opener}"
    
    IMPORTANT: Line 1 of your response MUST be exactly one of: [STATUS:RED], [STATUS:AMBER], or [STATUS:GREEN].
    Do NOT add numbers like "1." or any text before these brackets. 
    
    If winds, clouds, or visibility are predicted to violate the pilot's limits during the window, you MUST use [STATUS:RED].
    
    DATA: {weather_context}
    PLAN: {flight_plan_summary}
    """
    response = client.chat.completions.create(
        model="gemini-2.5-flash", 
        messages=[{"role": "system", "content": "Direct aviation assistant."}, {"role": "user", "content": system_prompt}],
        temperature=0.2 # Dropped even lower for absolute consistency
    )
    return response.choices[0].message.content

# ==========================================
# 3. INITIALIZE MEMORY
# ==========================================
if 'pilot_name' not in st.session_state: st.session_state.pilot_name = "Tonye"
if 'auto_wind_spd' not in st.session_state: st.session_state.auto_wind_spd = 0
if 'auto_wind_dir' not in st.session_state: st.session_state.auto_wind_dir = 0
if 'last_briefing' not in st.session_state: st.session_state.last_briefing = None
if 'last_weather_raw' not in st.session_state: st.session_state.last_weather_raw = ""

greeting_word, ai_opener = get_dynamic_greeting()

# ==========================================
# 4. TOP BAR
# ==========================================
col_t, col_g = st.columns([0.85, 0.15])
with col_t: st.title(f"✈️ {greeting_word}, {st.session_state.pilot_name}")
with col_g:
    with st.popover("⚙️"):
        st.session_state.pilot_name = st.text_input("Name:", value=st.session_state.pilot_name)

# ==========================================
# 5. CROSSWIND CALCULATOR
# ==========================================
with st.expander("🌬️ Smart Crosswind Calculator"):
    c1, c2, c3 = st.columns(3)
    with c1: r_hdg = st.number_input("Runway Hdg", 0, 360, 250)
    with c2: w_dir = st.number_input("Wind Dir", 0, 360, st.session_state.auto_wind_dir)
    with c3: w_spd = st.number_input("Wind Spd (kt)", 0, 60, st.session_state.auto_wind_spd)
    xw, hw = calculate_xwind(w_spd, w_dir, r_hdg)
    st.write(f"**Crosswind:** {xw} kt | **Headwind:** {hw} kt")

# ==========================================
# 6. FLIGHT PARAMETERS
# ==========================================
with st.expander("📝 Flight Parameters", expanded=True):
    route_raw = st.text_input("Route (ICAOs):", value="EGSS, EGSX, EGMC, EGKA")
    selected_airports = [icao.strip().upper() for icao in route_raw.split(",") if icao.strip()]
    raw_date = st.date_input("Flight Date:", datetime.date.today())
    c1, c2 = st.columns(2)
    with c1:
        dep_time = st.time_input("Departure", datetime.time(9, 15))
        max_wind = st.slider("Max Wind (kts)", 5, 30, 15)
    with c2:
        ret_time = st.time_input("Return", datetime.time(13, 0))
        max_gust = st.slider("Max Gust (kts)", 5, 45, 20)
    flight_summary = f"Date: {raw_date} | Times: {dep_time}-{ret_time} | Limits: {max_wind}kt/{max_gust}kt"

# ==========================================
# 7. LOGIC
# ==========================================
if st.button("Generate Briefing", type="primary"):
    with st.spinner("Analyzing data..."):
        weather_report = ""
        for i, icao in enumerate(selected_airports):
            m_text, m_data = get_weather_data(icao, "metar")
            t_text, _ = get_weather_data(icao, "taf")
            weather_report += f"--- {icao} ---\nMETAR: {m_text}\nTAF: {t_text}\n\n"
            if i == 0 and m_data:
                st.session_state.auto_wind_spd = m_data.get('wind', {}).get('speed_kts', 0)
                st.session_state.auto_wind_dir = m_data.get('wind', {}).get('degrees', 0)
        
        briefing = generate_briefing(weather_report, flight_summary, st.session_state.pilot_name, (greeting_word, ai_opener))
        st.session_state.last_briefing = briefing
        st.session_state.last_weather_raw = weather_report
        st.rerun()

# ==========================================
# 8. THE CORRECTED DISPLAY LOGIC
# ==========================================
if st.session_state.last_briefing:
    st.divider()
    output = st.session_state.last_briefing
    
    # We grab the first line of the AI response to check for the status
    first_line = output.split('\n')[0].upper()
    
    # NEW FLEXIBLE SEARCH: Looking for "RED", "AMBER", or "GREEN" anywhere in that first line
    if "RED" in first_line:
        st.error("### 🔴 NO-GO DECISION")
    elif "AMBER" in first_line:
        st.warning("### 🟡 MARGINAL - PROCEED WITH CAUTION")
    elif "GREEN" in first_line:
        st.success("### 🟢 GO-AHEAD")
    else:
        # Failsafe: If the AI goes off-script, we assume caution (Amber) rather than a false Green
        st.warning("### 🟡 CAUTION: Status unclear, please read briefing carefully.")

    # Remove the tag line completely from the display text
    clean_text = "\n".join(output.split('\n')[1:]).strip()
    st.markdown(clean_text)
    
    with st.expander("🔍 View Raw Weather Data"):
        st.code(st.session_state.last_weather_raw)
