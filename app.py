import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# -----------------------
# Functies
# -----------------------
def zoek_plaats(query):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 5, "addressdetails": 1}
    resp = requests.get(url, params=params, headers={"User-Agent": "streamlit-app"})
    if resp.status_code == 200:
        return resp.json()
    return []

def weercode_emoji(code):
    mapping = {
        0: "☀️", 1: "🌤️", 2: "☁️", 3: "🌧️", 45: "🌫️", 48: "🌨️",
        51: "🌦️", 53: "🌦️", 55: "🌧️", 56: "🌧️❄️", 57: "🌧️❄️",
        61: "🌧️", 63: "🌧️", 65: "🌧️🌧️", 66: "🌧️❄️", 67: "🌧️❄️",
        71: "❄️", 73: "❄️❄️", 75: "❄️❄️❄️", 77: "❄️",
        80: "🌦️", 81: "🌦️", 82: "⛈️", 85: "🌨️", 86: "🌨️❄️",
        95: "⛈️", 96: "⛈️🌨️", 99: "⛈️🌨️"
    }
    return mapping.get(code, "❓")

def windrichting_cardinaal(degree):
    dirs = ["N", "NO", "O", "ZO", "Z", "ZW", "W", "NW"]
    ix = round(degree / 45) % 8
    return dirs[ix]

# -----------------------
# Pagina setup
# -----------------------
st.title("Weer Dashboard NL")
pagina = st.sidebar.radio("Navigatie", ["Home", "Info"])

# -----------------------
# Plaats zoeken
# -----------------------
zoekterm = st.text_input("Typ een plaatsnaam:")

if zoekterm:
    resultaten = zoek_plaats(zoekterm)
    if resultaten:
        opties = [r["display_name"] for r in resultaten]
        keuze = st.selectbox("Kies een resultaat:", opties)

        if keuze:
            gekozen = next(r for r in resultaten if r["display_name"] == keuze)
            lat, lon = float(gekozen["lat"]), float(gekozen["lon"])
            st.subheader(f"📍 {gekozen['display_name']}")

            # -----------------------
            # Open-Meteo ophalen en cachen
            # -----------------------
            if "weerdata" not in st.session_state or st.session_state.get("last_loc") != (lat, lon):
                om_url = "https://api.open-meteo.com/v1/forecast"
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                    "hourly": "temperature_2m,rain,weather_code,wind_speed_10m,wind_direction_10m",
                    "models": "knmi_seamless",
                    "timezone": "Europe/Berlin",
                    "forecast_days": 10
                }
                resp = requests.get(om_url, params=params)
                if resp.status_code == 200:
                    st.session_state.weerdata = resp.json()
                    st.session_state.last_loc = (lat, lon)
                else:
                    st.warning("Kan Open-Meteo data niet ophalen.")

            # -----------------------
            # DataFrames maken
            # -----------------------
            data = st.session_state.get("weerdata", {})
            daily = data.get("daily", {})
            hourly = data.get("hourly", {})

            # Dagelijks
            df_daily = pd.DataFrame({
                "Datum": daily.get("time", []),
                "Temp min (°C)": daily.get("temperature_2m_min", []),
                "Temp max (°C)": daily.get("temperature_2m_max", []),
                "Weer": [weercode_emoji(c) for c in daily.get("weather_code", [])]
            })

            # Uurlijks
            if hourly:
                # vul lege arrays met 0 zodat alles even lang is
                n = len(hourly.get("time", []))
                temp = hourly.get("temperature_2m", [0]*n)
                rain = hourly.get("rain", [0]*n)
                code = hourly.get("weather_code", [0]*n)
                wind_speed = hourly.get("wind_speed_10m", [0]*n)
                wind_dir = hourly.get("wind_direction_10m", [0]*n)

                df_hourly = pd.DataFrame({
                    "Tijd": pd.to_datetime(hourly.get("time", [])),
                    "Temperatuur (°C)": temp,
                    "Neerslag (mm)": rain,
                    "Weer": [weercode_emoji(c) for c in code],
                    "Wind snelheid (km/h)": wind_speed,
                    "Wind richting": [windrichting_cardinaal(d) for d in wind_dir]
                })
            else:
                df_hourly = pd.DataFrame()

            # -----------------------
            # Pagina: Home
            # -----------------------
            if pagina == "Home":
                overlay_mapping = {
                    "wind": "wind",
                    "temperatuur": "temp",
                    "neerslag": "rain",
                    "bewolking": "clouds"
                }
                overlay_nl = st.radio("Kies een kaartlaag:", list(overlay_mapping.keys()), horizontal=True)
                overlay_windy = overlay_mapping[overlay_nl]

                windy_url = (
                    f"https://embed.windy.com/embed.html?type=map"
                    f"&lat={lat}&lon={lon}&zoom=11"
                    f"&overlay={overlay_windy}"
                    f"&product=ecmwf"
                    f"&level=surface"
                    f"&message=true"
                )

                iframe_code = f"""
                <div style="width:100%; height:550px; overflow:hidden; position:relative;">
                    <iframe 
                        src="{windy_url}" 
                        width="100%" 
                        height="600px"
                        style="border:0; position:absolute; top:-32px; left:0;">
                    </iframe>
                </div>
                """
                st.markdown(iframe_code, unsafe_allow_html=True)
                st.divider()

                # --- Actueel uur metrics ---
                if not df_hourly.empty:
                    nu = datetime.now()
                    df_hourly["verschil"] = abs(df_hourly["Tijd"] - nu)
                    huidig_idx = df_hourly["verschil"].idxmin()
                    huidig = df_hourly.loc[huidig_idx]

                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("Weer", huidig["Weer"])
                    col2.metric("Temperatuur", f"{huidig['Temperatuur (°C)']} °C")
                    col3.metric("Regen", f"{huidig['Neerslag (mm)']} mm")
                    col4.metric("Wind snelheid", f"{huidig['Wind snelheid (km/h)']} km/h")
                    col5.metric("Wind richting", huidig["Wind richting"])

            # -----------------------
            # Pagina: Info
            # -----------------------
            elif pagina == "Info":
                with st.expander("📊 10-daagse weersverwachting", expanded=True):
                    if not df_daily.empty:
                        st.dataframe(df_daily)

                with st.expander("📈 Uurverwachting (10 dagen)"):
                    if not df_hourly.empty:
                        st.dataframe(df_hourly)

    else:
        st.warning("Geen resultaten gevonden.")

