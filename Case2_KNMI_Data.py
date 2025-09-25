# ------------------ #
# Importing Packages #
# ------------------ #

import openmeteo_requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import requests
from datetime import datetime, date, timedelta
import locale

import requests_cache
from retry_requests import retry
import streamlit as st
from streamlit_option_menu import option_menu

# ---------------------------------------- End

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
        0: "☀️", 1: "🌤️", 2: "🌤️", 3: "☁️", 45: "🌫️", 48: "🌨️",
        51: "🌦️", 53: "🌦️", 55: "🌧️", 56: "🌧️❄️", 57: "🌧️❄️",
        61: "🌧️", 63: "🌧️", 65: "🌧️🌧️", 66: "🌧️❄️", 67: "🌧️❄️",
        71: "❄️", 73: "❄️❄️", 75: "❄️❄️❄️", 77: "❄️",
        80: "🌦️", 81: "🌦️", 82: "⛈️", 85: "🌨️", 86: "🌨️❄️",
        95: "⛈️", 96: "⛈️🌨️", 99: "⛈️🌨️"
    }.get(code, "❓")

def wind_pijl(degree):
    dirs = ["↓","↙","←","↖","↑","↗","→","↘"]
    return dirs[round(degree / 45) % 8]

def weercode_omschrijving(code):
    mapping = {
        0: "Zonnig", 1: "Overwegend zonnig", 2: "Gedeeltelijk bewolkt", 3: "Bewolkt",
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
    overlays = {"Wind": "wind", "Temperatuur": "temp", "Neerslag": "rain", "Bewolking": "clouds"}
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
st.title("Open-Meteo Weerdata")
with st.sidebar:
    pagina = option_menu(
        menu_title = None,
        options=["Het Weer", "Back-end Data"],
        menu_icon = "cast",
        icons=["sun", "database"]
    )

zoekterm = st.text_input("Typ een plaatsnaam:")


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

#--------------- #
#Open-meteo API  #
#--------------- #

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
if zoekterm:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, #Amsterdam
        "longitude": lon, #Amsterdam
        "daily": ["temperature_2m_max", "temperature_2m_min", "weather_code"],
        "hourly": ["temperature_2m", "rain", "weather_code", "wind_speed_10m", "wind_direction_10m"],
        "models": "knmi_seamless",
    }
    responses = openmeteo.weather_api(url, params=params)

    # Process first location. Add a for-loop for multiple locations or weather models
    response = responses[0]
    print(f"Coordinates: {response.Latitude()}°N {response.Longitude()}°E")
    print(f"Elevation: {response.Elevation()} m asl")
    print(f"Timezone difference to GMT+0: {response.UtcOffsetSeconds()}s")

    # Process hourly data. The order of variables needs to be the same as requested.
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    hourly_rain = hourly.Variables(1).ValuesAsNumpy()
    hourly_weather_code = hourly.Variables(2).ValuesAsNumpy()
    hourly_wind_speed_10m = hourly.Variables(3).ValuesAsNumpy()
    hourly_wind_direction_10m = hourly.Variables(4).ValuesAsNumpy()

    hourly_data = {"date": pd.date_range(
        start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
        end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
        freq = pd.Timedelta(seconds = hourly.Interval()),
        inclusive = "left"
    )}

    hourly_data["temperature_2m"] = hourly_temperature_2m
    hourly_data["rain"] = hourly_rain
    hourly_data["weather_code"] = hourly_weather_code
    hourly_data["wind_speed_10m"] = hourly_wind_speed_10m
    hourly_data["wind_direction_10m"] = hourly_wind_direction_10m

    hourly_dataframe = pd.DataFrame(data = hourly_data)
    print("\nHourly data\n", hourly_dataframe)

    # Process daily data. The order of variables needs to be the same as requested.
    daily = response.Daily()
    daily_temperature_2m_max = daily.Variables(0).ValuesAsNumpy()
    daily_temperature_2m_min = daily.Variables(1).ValuesAsNumpy()
    daily_weather_code = daily.Variables(2).ValuesAsNumpy()

    daily_data = {"date": pd.date_range(
        start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
        end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
        freq = pd.Timedelta(seconds = daily.Interval()),
        inclusive = "left"
    )}

    daily_data["temperature_2m_max"] = daily_temperature_2m_max
    daily_data["temperature_2m_min"] = daily_temperature_2m_min
    daily_data["weather_code"] = daily_weather_code

    daily_dataframe = pd.DataFrame(data = daily_data)
    print("\nDaily data\n", daily_dataframe)

# ---------------------------------------- End

# --------------------------------- #
#            Figures                #
# --------------------------------- #

# region ----- Figuur 1: Het weer per gekozen locatie ----- 

# -----------------------
# Home pagina
# -----------------------
if pagina == "Het Weer":
    if zoekterm:

        st.header("Figuur 1: Het weer per gekozen locatie")

        # Kaartlaag
        overlay = st.radio("Kies een kaartlaag:", ["Wind", "Temperatuur", "Neerslag", "Bewolking"], horizontal=True)
        st.markdown(embed_windy(lat, lon, overlay), unsafe_allow_html=True)

        # Multiselect voor visualisaties
        opties = ["Huidig weer", "Uurverwachting", "10-daagse voorspelling", "Visualisatie 24h voorspelling"]
        gekozen_opties = st.multiselect("Kies welke visualisaties je wilt zien:", opties, default=None)
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
                schakelaar = st.radio("", ["Weersverwachtingen 24 uur", "Weersverwachtingen 48 uur"], horizontal=True)
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

if pagina == "Back-end Data":
    if zoekterm:
        st.title("Exploratory Data Analysis - Weersverwachting")

        # --- DAGELIJKSE DATA ---
        with st.expander("10-daagse weersverwachting", expanded=True):
            if not df_daily.empty:
                st.subheader("Beschrijving van variabelen (dagelijks)")
                st.markdown("""
                - **Datum**: Datum van de voorspelling  
                - **Temp min (°C)**: Minimale temperatuur  
                - **Temp max (°C)**: Maximale temperatuur  
                - **Weer emoji**: Weersvoorspelling in emojis
                - **Weer tekst**: Weersvoorspelling in tekst                      
                - **Zonsopkomst**: Tijd van zonsopkomst
                - **Zonsondergang**: Tijd van zonsondergang
                """)

                st.dataframe(df_daily)

                st.subheader("Samenvatting")
                st.write(df_daily.describe())

                # --- Dropdown voor visualisaties ---
                keuze = st.selectbox(
                    "📊 Kies een visualisatie:",
                    ["Temperatuurtrends", "Histogram weersituaties", "Zon op/onder"]
                )

                if keuze == "Temperatuurtrends":
                    fig = px.line(
                        df_daily,
                        x="Datum",
                        y=["Temp max (°C)", "Temp min (°C)"],
                        labels={"value": "Temperatuur (°C)", "Datum": "Datum"},
                        title="Dagelijkse temperatuurtrends"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                elif keuze == "Histogram weersituaties":
                    fig_hist = px.histogram(
                        df_daily,
                        x="Weer tekst",
                        title="Verdeling van weersvoorspellingen",
                        labels={"Weer emoji": "Weertype (emoji)"}
                    )
                    st.plotly_chart(fig_hist, use_container_width=True)

                elif keuze == "Zon op/onder":
                    # Data voorbereiden
                    df_daily["Zonsopkomst_dt"] = pd.to_datetime(
                        df_daily["Datum"].astype(str) + " " + df_daily["Zonsopkomst"].astype(str)
                    )
                    df_daily["Zonsondergang_dt"] = pd.to_datetime(
                        df_daily["Datum"].astype(str) + " " + df_daily["Zonsondergang"].astype(str)
                    )

                    df_sun = df_daily.melt(
                        id_vars=["Datum"],
                        value_vars=["Zonsopkomst_dt", "Zonsondergang_dt"],
                        var_name="Event",
                        value_name="Tijd"
                    )

                    fig_sun = px.line(
                        df_sun,
                        x="Datum",
                        y="Tijd",
                        color="Event",
                        labels={"Tijd": "Tijdstip", "Datum": "Datum", "Event": "Zon positie"},
                        title="Zonsopkomst en Zonsondergang per dag"
                    )
                    st.plotly_chart(fig_sun, use_container_width=True)


        # --- UURDATA ---
        with st.expander("Uurverwachting (10 dagen)", expanded=False):
            if not df_hourly.empty:
                st.subheader("Beschrijving van variabelen (per uur)")
                st.markdown("""
                - **Tijd**: Datum + tijdstip van de voorspelling  
                - **Temperatuur (°C)**: Temperatuur                  
                - **Neerslag (mm)**: Neerslag
                - **Weer emoji**: Weersvoorspelling in emojis  
                - **Weer tekst**: Weersvoorspelling in tekst 
                - **Wind snelheid (km/h)**: Windsnelheid  
                - **Wind richting**: Richting van de wind
                - **Wind pijl**: Richting van de wind met pijlen            
                """)

                st.dataframe(df_hourly)

                st.subheader("Samenvatting")
                st.write(df_hourly.describe())

                # --- Uurvariabelen visualiseren ---
                st.subheader("Visualisaties")
                variable = st.selectbox(
                    "Kies variabele om te plotten:",
                    ["Temperatuur (°C)", "Wind richting", "Neerslag (mm)", "Wind snelheid (km/h)","Histogram weersituaties"]
                )

                if variable == "Histogram weersituaties":
                    fig_hist = px.histogram(
                        df_hourly,
                        x="Weer tekst",
                        title="Verdeling van weersvoorspellingen",
                        labels={"Weer emoji": "Weertype (emoji)"}
                    )
                    st.plotly_chart(fig_hist, use_container_width=True)
                else:
                    fig2 = px.line(
                        df_hourly,
                        x="Tijd",
                        y=variable,
                        labels={"Tijd": "Datum + Tijd", variable: variable},
                        title=f"Uurtrend van {variable}"
                    )
                    st.plotly_chart(fig2, use_container_width=True)

    else:
        st.write("Typ eerst een plaatsnaam!")
#endregion

# region ----- Figuur 2: 24h Weersvoorspelling (Temp & Regen)
if pagina == "Het Weer":
    if zoekterm:
        if "Visualisatie 24h voorspelling" in gekozen_opties:
            st.header("Figuur 2: 24h Weersvoorspelling")

            df_fig2 = hourly_dataframe.copy()

            df_fig2["temperature_2m"] = df_fig2["temperature_2m"].round(1)

            df_fig2["Local Time"] = (df_fig2["date"] + pd.to_timedelta(2, unit="h"))


            #Definieer huidige tijd en de tijd 24 uur vooruit.

            now = pd.Timestamp.now(tz="Europe/Amsterdam")
            next_24 = now + pd.Timedelta(hours=24)

            # Filter aankomende 24h
            df_fig2 = df_fig2[(df_fig2["Local Time"] >= now) & (df_fig2["Local Time"] <= next_24)]

            # Streamlit optionbox
            fig2_option = st.radio(
                "**Selecteer:**", ("24h Weersvoorspelling", "Dataframe")
            )

            df_fig2_useddata = df_fig2[["date", "Local Time", "temperature_2m", "rain"]]

            if fig2_option == "Dataframe":
                show_temp = False
                show_rain = False
                show_wind = False
                st.dataframe(df_fig2_useddata)

            else:
                st.write("**Enable/Disable options**")
                show_temp = st.checkbox("Show Temperature", value=True)
                show_rain = st.checkbox("Show Rain", value=False)
                show_wind = st.checkbox("Show Wind", value=False)
                
            today = now.date()
            df_fig2 = df_fig2.copy()
            df_fig2 = df_fig2.sort_values("Local Time").reset_index(drop=True)

            # Split uren vandaag en morgen (voor de slider)
            hours_today = df_fig2[df_fig2["Local Time"] >= now]
            hours_tomorrow = df_fig2[df_fig2["Local Time"] < now].copy()
            hours_tomorrow["Local Time"] += pd.Timedelta(days=1)
            future_hours = pd.concat([hours_today, hours_tomorrow]).reset_index(drop=True)

            # Streamlit slider
            if fig2_option == "24h Weersvoorspelling":
                hour_index = st.select_slider(
                    "**Selecteer het uur**",
                    options=future_hours.index,
                    format_func=lambda x: future_hours.loc[x, "Local Time"].strftime("%H:%M")
                    )
                row = future_hours.loc[hour_index]
            else:
                row = future_hours.loc[0]     

            #Figuur 2 maken met plotly. Het is een lijngrafiek die de temperatuur, wind en regen laat zien in de komende 24 uur
            fig2 = go.Figure()

            if show_temp:
                fig2.add_trace(go.Scatter( 
                    x=df_fig2["Local Time"], 
                    y=df_fig2["temperature_2m"],
                    mode='lines+markers',
                    line=dict(color='rgba(230, 93, 32, 0.761)'),
                    fill='tozeroy',
                    fillcolor='rgba(201, 90, 41, 0.49)',
                    name="Temperature (°C)",
                    yaxis="y1"
                ))

            if show_rain:
                fig2.add_trace(go.Scatter(
                    x=df_fig2["Local Time"], 
                    y=df_fig2["rain"],
                    mode='lines+markers',
                    line=dict(color='rgba(67, 147, 219, 0.5)'),
                    fill='tozeroy',
                    fillcolor='rgba(134, 61, 153, 0.2)',
                    name="Regen (mm)",
                    yaxis="y2"
                ))

            if show_wind:
                fig2.add_trace(go.Scatter(
                    x=df_fig2["Local Time"], 
                    y=df_fig2["wind_speed_10m"],
                    mode='lines+markers',
                    line=dict(color='rgba(155, 52, 201, 0.5)'),
                    fill='tozeroy',
                    fillcolor='rgba(154, 66, 194, 0.2)',
                    name="Wind Snelheid (km/h)",
                    yaxis="y3"
                ))

            fig2.update_layout(
                title="Weersvoorspelling 24h",
                xaxis_title="Lokale Tijd",
                xaxis=dict(domain=[0.0, 0.85]),
                yaxis=dict(title="Temperatuur (°C)", range=[0, df_fig2["temperature_2m"].max()+20]),
                yaxis2=dict(title="Regen (mm)", side='right', overlaying='y', range=[0, df_fig2["rain"].max()+2]),
                yaxis3=dict(title="Wind Snelheid (km/h)", side='right', overlaying='y', position=0.98, range=[0, df_fig2["wind_speed_10m"].max()+15]),
                hovermode=False,  # Disable hover because slider controls info
            )

            if show_temp == False:
                if show_wind == False:
                    fig2.update_layout(yaxis2=dict(showgrid=True))
                elif (show_rain and show_wind) == True:
                    fig2.update_layout(yaxis2=dict(showgrid=True)) 
                    fig2.update_layout(yaxis3=dict(showgrid=False)) 
                else:
                    fig2.update_layout(yaxis3=dict(showgrid=True, position=0.87)) 
            else:
                fig2.update_layout(yaxis1=dict(showgrid=True))
                fig2.update_layout(yaxis2=dict(showgrid=False))
                fig2.update_layout(yaxis3=dict(showgrid=False))

            fig2.update_xaxes(
                showspikes=True, 
                spikecolor="grey", 
                spikemode="across", 
                spikesnap="data",
                spikethickness=2,
                spikedash='solid'
            )  

            # --- ADD vertical line and annotation dynamically AFTER slider selection ---
            fig2.add_vline(
                x=row["Local Time"],
                line_width=2,
                line_dash="dash",
                line_color="grey"
            )
            
            # Annotatie box met informatie over de geselecteerde tijd
            info_text = f"<b>{row['Local Time'].strftime('%H:%M')}</b><br>"
            if show_temp:
                info_text += f"🌡️ Temp: {row['temperature_2m']:.1f} °C<br>"
            if show_rain:
                info_text += f"🌧️ Rain: {row['rain']:.1f} mm<br>"
            if show_wind:
                info_text += f"💨 Wind: {row['wind_speed_10m']:.0f} km/h"

            fig2.add_annotation(
                x=row["Local Time"],
                y=max(
                    row["temperature_2m"] if show_temp else 0,
                    row["rain"] if show_rain else 0,
                    row["wind_speed_10m"] if show_wind else 0
                ) + 5,
                text=info_text,
                showarrow=False,
                align="left",
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="black"
            )

            # Show figure
            if fig2_option == "24h Weersvoorspelling":
                st.plotly_chart(fig2, use_container_width=True)
    
#endregion

# ---------------------------------------- End