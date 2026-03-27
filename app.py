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
    # Changed format instructions to use a bracketed tag on its own line
    system_prompt = f"""
    You are an experienced British aviation assistant. Write a structured briefing for Pilot {pilot_name}.
    TONE: Start with: "{greet} {pilot_name}, {opener}"
    FORMAT: 
    - Line 1 MUST be one of these tags: [STATUS:RED], [STATUS:AMBER], or [STATUS:GREEN]
    - Then start your numbered briefing: 1. Go/No-Go Assessment. 2. Airport Breakdown. 3. Outlook.
    DATA: {weather_context} | PLAN: {flight_plan_summary}
    """
    response = client.chat.completions.create(
        model="gemini-2.5-flash", 
        messages=[{"role": "system", "content": "Direct aviation assistant."}, {"role": "user", "content": system_prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content

# ==========================================
# 3. SETTINGS & SESSION STATE
# ==========================================
if 'pilot_name' not in st.session_state: st.session_state.pilot_name = "Tonye"
if 'auto_wind_spd' not in st.session_state: st.session_state.auto_wind_spd = 0
if 'auto_wind_dir' not in st.session_state: st.session_state.auto_wind_dir = 0

greeting_word, ai_opener = get_dynamic_greeting()

col_t, col_g = st.columns([0.85, 0.15])
with col_t: st.title(f"✈️ {greeting_word}, {st.session_state.pilot_name}")
with col_g:
    with st.popover("⚙️"):
        st.session_state.pilot_name = st.text_input("Name:", value=st.session_state.pilot_name)

# ==========================================
# 4. CROSSWIND CALCULATOR (Now with Session State)
# ==========================================
with st.expander("🌬️ Smart Crosswind Calculator"):
    st.info("Input runway heading. Wind is automatically updated from your briefing below.")
    c1, c2, c3 = st.columns(3)
    with c1: r_hdg = st.number_input("Runway Hdg", 0, 360, 250)
    with c2: w_dir = st.number_input("Wind Dir", 0, 360, st.session_state.auto_wind_dir)
    with c3: w_spd = st.number_input("Wind Spd (kt)", 0, 60, st.session_state.auto_wind_spd)
    
    xw, hw = calculate_xwind(w_spd, w_dir, r_hdg)
    st.write(f"**Crosswind:** {xw} kt | **Headwind:** {hw} kt")

# ==========================================
# 5. FLIGHT PARAMETERS
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
# 6. EXECUTION
# ==========================================
if st.button("Generate Briefing", type="primary"):
    with st.spinner("Fetching data and calculating..."):
        weather_report = ""
        first_icao_data = None
        
        for i, icao in enumerate(selected_airports):
            m_text, m_data = get_weather_data(icao, "metar")
            t_text, _ = get_weather_data(icao, "taf")
            weather_report += f"--- {icao} ---\nMETAR: {m_text}\nTAF: {t_text}\n\n"
            
            # Smart logic: Grab wind from the first airport in your list for the calculator
            if i == 0 and m_data:
                st.session_state.auto_wind_spd = m_data.get('wind', {}).get('speed_kts', 0)
                st.session_state.auto_wind_dir = m_data.get('wind', {}).get('degrees', 0)
        
        raw_output = generate_briefing(weather_report, flight_summary, st.session_state.pilot_name, (greeting_word, ai_opener))
        
        st.divider()
        
        # IMPROVED COLOR LOGIC (Removes the blank '1.' issue)
        if "[STATUS:RED]" in raw_output:
            st.error("### 🔴 NO-GO DECISION")
            display_text = raw_output.replace("[STATUS:RED]", "").strip()
        elif "[STATUS:AMBER]" in raw_output:
            st.warning("### 🟡 MARGINAL - CAUTION")
            display_text = raw_output.replace("[STATUS:AMBER]", "").strip()
        else:
            st.success("### 🟢 GO-AHEAD")
            display_text = raw_output.replace("[STATUS:GREEN]", "").strip()

        st.markdown(display_text)
        st.rerun() # Reruns to update the calculator at the top with the new wind!
