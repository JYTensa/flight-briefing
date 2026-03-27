import streamlit as st
import requests
from openai import OpenAI
import datetime
from fpdf import FPDF
import io

# ==========================================
# 1. PAGE SETUP & THEME
# ==========================================
st.set_page_config(page_title="Flight Briefing", page_icon="✈️", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #001529; color: #e6f7ff; }
    h1, h2, h3 { color: #ffffff !important; }
    .streamlit-expanderHeader { background-color: #002140 !important; border-radius: 5px; }
    .stButton>button { background-color: #1890ff; color: white; border-radius: 10px; width: 100%; border: none; height: 3em; font-weight: bold; }
    .stSlider label, .stTextInput label, .stDateInput label { color: #bae7ff !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. API KEYS & HELPERS
# ==========================================
CHECKWX_API_KEY = st.secrets["CHECKWX_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_KEY"]
client = OpenAI(api_key=GEMINI_API_KEY, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

def get_date_suffix(day):
    if 11 <= day <= 13: return 'th'
    return {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')

def format_pretty_date(d):
    # Turns 2026-03-27 into "Friday 27th March"
    day_name = d.strftime('%A')
    day_num = d.day
    month_name = d.strftime('%B')
    return f"{day_name} {day_num}{get_date_suffix(day_num)} {month_name}"

def format_pretty_time(t, fmt_type):
    if fmt_type == "12h":
        return t.strftime('%I:%M %p')
    return t.strftime('%H:%M') + "Z"

def get_weather_data(icao_code, report_type="taf"):
    url = f"https://api.checkwx.com/{report_type}/{icao_code}/decoded"
    headers = {"X-API-Key": CHECKWX_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get('results', 0) > 0:
            return data['data'][0].get('raw_text', 'No raw text available')
        return f"No {report_type.upper()} data published."
    except Exception: return "Data unavailable."

def generate_briefing(weather_context, flight_plan_summary, pilot_name):
    system_prompt = f"""
    You are an experienced British aviation assistant. Write a structured briefing for Pilot {pilot_name}.
    TONE: Start with: "Morning {pilot_name}, Hope you slept well." 
    DATA: {weather_context} | PLAN: {flight_plan_summary}
    INSTRUCTIONS: 1. Clear Go/No-Go. 2. Three bullet points for EACH airport. 3. 2-sentence outlook.
    """
    response = client.chat.completions.create(
        model="gemini-2.5-flash", 
        messages=[{"role": "system", "content": "Aviation assistant."}, {"role": "user", "content": system_prompt}],
        temperature=0.5
    )
    return response.choices[0].message.content

def create_pdf(text, pilot_name, date_str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt=f"Flight Briefing: {pilot_name}", ln=True, align='C')
    pdf.set_font("Arial", "I", 10)
    pdf.cell(200, 10, txt=f"Date: {date_str}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=11)
    clean_text = text.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 7, txt=clean_text)
    return pdf.output()

# ==========================================
# 3. SETTINGS & SESSION STATE
# ==========================================
if 'pilot_name' not in st.session_state: st.session_state.pilot_name = "Tonye"
if 'time_fmt' not in st.session_state: st.session_state.time_fmt = "24h"

# Top Bar
col_title, col_gear = st.columns([0.85, 0.15])
with col_title:
    st.title(f"✈️ Morning, {st.session_state.pilot_name}")
with col_gear:
    with st.popover("⚙️"):
        st.session_state.pilot_name = st.text_input("Pilot Name:", value=st.session_state.pilot_name)
        st.session_state.time_fmt = st.radio("Time Format:", ["24h", "12h"], index=0 if st.session_state.time_fmt == "24h" else 1)

# ==========================================
# 4. PARAMETERS
# ==========================================
with st.expander("📝 Flight Parameters", expanded=True):
    route_raw = st.text_input("Route (ICAO codes):", value="EGSS, EGSX, EGMC, EGKA")
    selected_airports = [icao.strip().upper() for icao in route_raw.split(",") if icao.strip()]
    
    # Date Picker
    raw_date = st.date_input("Flight Date:", datetime.date.today())
    pretty_date = format_pretty_date(raw_date)
    st.info(f"Briefing for: **{pretty_date}**") # Shows the "Monday 27th" style instantly
    
    c1, c2 = st.columns(2)
    with c1:
        dep_time = st.time_input("Departure", datetime.time(9, 15))
        max_wind = st.slider("Max Wind (kts)", 5, 30, 15)
        min_cloud = st.slider("Min Cloud (ft)", 500, 5000, 1500, step=100)
    with c2:
        ret_time = st.time_input("Return", datetime.time(13, 0))
        max_gust = st.slider("Max Gust (kts)", 5, 45, 20)
        min_vis = st.slider("Min Vis (m)", 1000, 10000, 8000, step=500)

    # Format summary for AI
    p_dep = format_pretty_time(dep_time, st.session_state.time_fmt)
    p_ret = format_pretty_time(ret_time, st.session_state.time_fmt)
    
    flight_summary = f"""
    Flight Date: {pretty_date}
    Departure: {p_dep} | Return: {p_ret}
    Limits: {max_wind}kt wind / {max_gust}kt gust. {min_cloud}ft cloud base. {min_vis}m visibility.
    """

# ==========================================
# 5. EXECUTION
# ==========================================
if st.button("Generate Briefing", type="primary"):
    if not selected_airports:
        st.warning("Please enter at least one ICAO code.")
    else:
        with st.spinner(f"Analyzing weather for {pretty_date}..."):
            weather_report = ""
            for icao in selected_airports:
                weather_report += f"--- {icao} ---\nMETAR: {get_weather_data(icao, 'metar')}\nTAF: {get_weather_data(icao, 'taf')}\n\n"
            
            output = generate_briefing(weather_report, flight_summary, st.session_state.pilot_name)
            
            st.markdown("---")
            st.markdown(f"### 📋 Analysis for {pretty_date}")
            st.markdown(output)
            
            pdf_data = create_pdf(output, st.session_state.pilot_name, pretty_date)
            st.download_button(
                label="📥 Download PDF Briefing",
                data=bytes(pdf_data),
                file_name=f"Briefing_{raw_date}.pdf",
                mime="application/pdf"
            )
            
            with st.expander("🔍 View Raw Weather Data"):
                st.code(weather_report)
