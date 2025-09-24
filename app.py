import streamlit as st
import requests
import pandas as pd
from datetime import datetime, date, timedelta
import locale

# -----------------------
# Functies
# -----------------------
@st.cache_data(show_spinner=False)
def zoek_plaats(query):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 5, "addressdetails": 1}
    resp = requests.get(url, params=params, headers={"User-Agent": "streamlit-app"})
    return resp.json() if resp.status_code == 200 else []

def weercode_emoji(code):
    return {
        0: "☀️", 1: "🌤️", 2: "☁️", 3: "🌧️", 45: "🌫️", 48: "🌨️",
        51: "🌦️", 53: "🌦️", 55: "🌧️", 56: "🌧️❄️", 57: "🌧️❄️",
        61: "🌧️", 63: "🌧️", 65: "🌧️🌧️", 66: "🌧️❄️", 67: "🌧️❄️",
        71: "❄️", 73: "❄️❄️", 75: "❄️❄️❄️", 77: "❄️",
        80: "🌦️", 81: "🌦️", 82: "⛈️", 85: "🌨️", 86: "🌨️❄️",
        95: "⛈️", 96: "⛈️🌨️", 99: "⛈️🌨️"
    }.get(code, "❓")

def wind_pijl(degree):
    dirs = ["↑","↗","→","↘","↓","↙","←","↖"]
    return dirs[round(degree / 45) % 8]

def weercode_omschrijving(code):
    mapping = {
        0: "Zonnig", 1: "Overwegend zonnig", 2: "Bewolkt", 3: "Regenachtig",
        45: "Mist", 48: "IJzelmist",
        51: "Motregen licht", 53: "Motregen", 55: "Motregen zwaar",
        61: "Regen licht", 63: "Regen", 65: "Regen zwaar",
        71: "Sneeuw licht", 73: "Sneeuw", 75: "Sneeuw zwaar",
        80: "Buien licht", 81: "Buien", 82: "Hevige buien",
        95: "Onweer", 96: "Onweer met hagel", 99: "Zwaar onweer"
    }
    return mapping.get(code, "Onbekend")

def windrichting_cardinaal(degree):
    dirs = ["N", "NO", "O", "ZO", "Z", "ZW", "W", "NW"]
    return dirs[round(degree / 45) % 8]

@st.cache_data(show_spinner=False)
def haal_open_meteo(lat, lon):
    om_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,sunrise,sunset",
        "hourly": "temperature_2m,rain,weather_code,wind_speed_10m,wind_direction_10m",
        "models": "knmi_seamless",
        "timezone": "Europe/Berlin",
        "forecast_days": 10
    }
    resp = requests.get(om_url, params=params)
    return resp.json() if resp.status_code == 200 else {}

def maak_dataframes(data):
    daily, hourly = data.get("daily", {}), data.get("hourly", {})

    df_daily = pd.DataFrame({
    "Datum": daily.get("time", []),
    "Temp min (°C)": daily.get("temperature_2m_min", []),
    "Temp max (°C)": daily.get("temperature_2m_max", []),
    "Weer emoji": [weercode_emoji(c) for c in daily.get("weather_code", [])],
    "Weer tekst": [weercode_omschrijving(c) for c in daily.get("weather_code", [])],
    "Zonsopkomst": [s.split("T")[1][:5] for s in daily.get("sunrise", [])],
    "Zonsondergang": [s.split("T")[1][:5] for s in daily.get("sunset", [])]
    })


    if not hourly:
        return df_daily, pd.DataFrame()

    df_hourly = pd.DataFrame({
        "Tijd": pd.to_datetime(hourly.get("time", [])),
        "Temperatuur (°C)": hourly.get("temperature_2m", []),
        "Neerslag (mm)": hourly.get("rain", []),
        "Weer emoji": [weercode_emoji(c) for c in hourly.get("weather_code", [])],
        "Weer tekst": [weercode_omschrijving(c) for c in hourly.get("weather_code", [])],
        "Wind snelheid (km/h)": hourly.get("wind_speed_10m", []),
        "Wind richting": [windrichting_cardinaal(d) for d in hourly.get("wind_direction_10m", [])],
        "Wind pijl": [wind_pijl(d) for d in hourly.get("wind_direction_10m", [])]
    })

    return df_daily, df_hourly

def embed_windy(lat, lon, overlay):
    overlays = {"wind": "wind", "temperatuur": "temp", "neerslag": "rain", "bewolking": "clouds"}
    url = (f"https://embed.windy.com/embed.html?type=map&lat={lat}&lon={lon}&zoom=11"
           f"&overlay={overlays[overlay]}&product=ecmwf&level=surface&message=true")
    return f"""
    <div style="width:100%; height:550px; overflow:hidden; position:relative;">
        <iframe src="{url}" width="100%" height="600px" style="border:0; position:absolute; top:-32px; left:0;">
        </iframe>
    </div>
    """

# -----------------------
# Pagina setup
# -----------------------
st.title("Weer Dashboard NL")
pagina = st.sidebar.radio("Navigatie", ["Home", "Info"])
zoekterm = st.text_input("Typ een plaatsnaam:")

if zoekterm:
    resultaten = zoek_plaats(zoekterm)

    if not resultaten:
        st.warning("Geen resultaten gevonden.")
    else:
        opties = [r["display_name"] for r in resultaten]
        keuze = st.selectbox("Kies een resultaat:", opties)
        gekozen = next(r for r in resultaten if r["display_name"] == keuze)
        lat, lon = float(gekozen["lat"]), float(gekozen["lon"])

        data = haal_open_meteo(lat, lon)
        df_daily, df_hourly = maak_dataframes(data)

        vandaag = date.today()
        locale.setlocale(locale.LC_TIME, "nl_NL.UTF-8")

        # -----------------------
# Home pagina
# -----------------------
        if pagina == "Home":
            # Kaartlaag
            overlay = st.radio("Kies een kaartlaag:", ["wind", "temperatuur", "neerslag", "bewolking"], horizontal=True)
            st.markdown(embed_windy(lat, lon, overlay), unsafe_allow_html=True)

            # Multiselect voor visualisaties
            opties = ["Huidig weer", "Uurverwachting", "10-daagse voorspelling"]
            gekozen_opties = st.multiselect("Kies welke visualisaties je wilt zien:", opties, default=opties)
            st.subheader(f"{gekozen['display_name']}")

            nu = datetime.now()
            huidig = df_hourly.iloc[int(nu.strftime('%H'))]
            huidig_d = df_daily.iloc[0]  # eerste dag, kan uitgebreid worden naar huidige datum

            col1, col2 = st.columns([1,4])

            # --- Huidig weer ---
            if "Huidig weer" in gekozen_opties:
                with col1:
                    st.markdown(f"""
                    <style>
                    .weather-card {{
                        background: linear-gradient(100deg, #8fa3c6, #334e7c);
                        color: #f0f0f0;
                        border-radius: 15px;
                        padding: 20px;
                        text-align: center;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
                        width: 320px;
                        font-family: Arial, sans-serif;
                    }}
                    .weather-card h2 {{ margin: 0 0 10px 0; font-size: 22px; }}
                    .weather-main {{ font-size: 40px; margin: 10px 0; }}
                    .weather-info {{ display: flex; justify-content: space-around; margin-top: 15px; font-size: 18px; }}
                    .weather-info div {{ flex: 1; text-align: center; }}
                    
                    </style>

                    <div style="display:flex; justify-content:center; margin-top:15px;">
                        <div class="weather-card">
                            <h2 style="margin:0; font-size:22px;">Huidig Weer</h2>
                            <div style="font-size:16px; color:#d0d0d0; margin-top:-15px;">{vandaag.strftime('%A %d %B')}</div>
                            <div style="font-size:16px; color:#d0d0d0; margin-top:0px;">{nu.strftime("%H:%M")}</div>
                            <div class="weather-main">{huidig['Weer emoji']}<br>{huidig['Weer tekst']}</div>
                            <div class="weather-info">{huidig_d['Zonsopkomst']}🌅 - {huidig_d['Zonsondergang']}🌇</div>
                            <div class="weather-info">
                                <div><br><b>{huidig['Temperatuur (°C)']}°C</b></div>
                                <div><br><b>{huidig['Wind pijl']} {huidig['Wind richting']}</b></div>
                            </div>
                            <div class="weather-info">
                                <div><br><b>💧{huidig['Neerslag (mm)']} mm</b></div>
                                <div><br><b>{huidig['Wind snelheid (km/h)']} km/h</b></div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # --- Uurverwachting ---
            if "Uurverwachting" in gekozen_opties:
                with col2:
                    schakelaar = st.radio("dummy_label", ["Weersverwachtingen 24 uur", "Weersverwachtingen 48 uur"], horizontal=True)
                    uren = 24 if schakelaar == "Weersverwachtingen 24 uur" else 48

                    if not df_hourly.empty:
                        start_idx = int(nu.strftime("%H"))
                        eind_idx = start_idx + uren
                        df_subset = df_hourly.iloc[start_idx:eind_idx][['Weer emoji', 'Temperatuur (°C)', 'Neerslag (mm)','Wind pijl','Wind richting','Wind snelheid (km/h)']]
                        df_subset.index = [f"{(start_idx+i)%24}:00 ({(start_idx+i)//24+1})" for i in range(len(df_subset))]
                        st.write(df_subset.T.astype(str))

            # --- 10-daagse voorspelling ---
            if "10-daagse voorspelling" in gekozen_opties:
                st.header("10-daagse weersverwachtingen")
                cols = st.columns(min(10, len(df_daily)))

                st.markdown("""
                <style>
                .fade-card {
                    background: linear-gradient(135deg, #1e3a5f 0%, #334e7c 100%);
                    color: #f0f0f0;
                    border-radius: 12px;
                    padding: 12px;
                    text-align: center;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.4);
                    transform: translateY(10px);
                    opacity: 0;
                    animation: fadeIn 0.5s forwards;
                    font-family: Arial, sans-serif;
                    letter-spacing: 0.5px;
                }
                .fade-card .date { font-weight:bold; font-size:16px; line-height:1.2; margin-bottom:3px; }
                .fade-card .subdate { font-size:14px; color:#d0d0d0; margin-bottom:5px; }
                .fade-card .emoji { font-size:28px; font-weight:bold; margin:5px 0; }
                .fade-card .temp-max { font-size:28px; font-weight:bold; margin:-5px 0; color:orange; }
                .fade-card .temp-min { font-size:18px; font-weight:bold; margin:3px 0; }
                .fade-card .desc { font-size:12px; color:#d0d0d0; margin-top:3px; }
                @keyframes fadeIn { to { opacity:1; transform: translateY(0); } }
                </style>
                """, unsafe_allow_html=True)

                for i, row in enumerate(df_daily.head(10).itertuples()):
                    dag = vandaag + timedelta(days=i+1)
                    with cols[i]:
                        st.markdown(f"""
                        <div class="fade-card" style="animation-delay:{i*0.05}s;">
                            <div class="date">{dag.strftime('%A')}</div>
                            <div class="subdate">{dag.strftime('%d %B')}</div>
                            <div class="emoji">{row._4}</div>
                            <div class="temp-max">{row._3}°</div>
                            <div class="temp-min">{row._2}°</div>
                            <div class="desc">{row._5}</div>
                        </div>
                        """, unsafe_allow_html=True)


        elif pagina == "Info":
            with st.expander("📊 10-daagse weersverwachting", expanded=True):
                if not df_daily.empty: st.dataframe(df_daily)
            with st.expander("📈 Uurverwachting (10 dagen)"):
                if not df_hourly.empty: st.dataframe(df_hourly)