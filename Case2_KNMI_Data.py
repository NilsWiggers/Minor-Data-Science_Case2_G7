# ------------------ #
# Importing Packages #
# ------------------ #

import openmeteo_requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import requests
from datetime import datetime
import requests_cache
from retry_requests import retry
import streamlit as st

# ------------------- #
#   Streamlit base    #
# ------------------- #

# -------------
# Pagina setup
# -------------
st.title("KNMI Weerdata")
pagina = st.sidebar.radio("Navigatiezijbalk", ["Het Weer", "Back-end Data"])

# ---------------------------------------- End


#--------------- #
#Open-meteo API  #
#--------------- #

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://api.open-meteo.com/v1/forecast"
params = {
	"latitude": 52.52,
	"longitude": 13.41,
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

st.header("Figuur 1: Het weer per gekozen locatie")

# -----------
# Functies
# -----------
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
            # Pagina: Het Weer
            # -----------------------
            if pagina == "Het Weer":
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
            # Pagina: Back-end Data
            # -----------------------
            elif pagina == "Back-end Data":
                with st.expander("📊 10-daagse weersverwachting", expanded=True):
                    if not df_daily.empty:
                        st.dataframe(df_daily)

                with st.expander("📈 Uurverwachting (10 dagen)"):
                    if not df_hourly.empty:
                        st.dataframe(df_hourly)

    else:
        st.warning("Geen resultaten gevonden.")

#endregion

# region ----- Figuur 2: 24h Weersvoorspelling (Temp & Regen)
st.header("Figuur 2: 24h Weersvoorspelling")

df_fig2 = hourly_dataframe.copy()

df_fig2["temperature_2m"] = df_fig2["temperature_2m"].round(1)

df_fig2["Local Time"] = (df_fig2["date"] + pd.to_timedelta(2, unit="h"))


#Definieer huidige tijd en de tijd 24 uur vooruit.
now = pd.Timestamp.now(tz="Europe/Amsterdam")
print(now)
next_24 = now + pd.Timedelta(hours=24)

#Filter op tussen de huidige tijd en de volgende 24h en convert datetime naar alleen uren en minuten
df_fig2 = df_fig2[(df_fig2["Local Time"] >= now) & (df_fig2["Local Time"] <= next_24)]
df_fig2["Local Time"] = df_fig2["Local Time"].dt.strftime("%H:%M") 

#print de nieuwe dataframe en zet het in streamlit
df_fig2_useddata = df_fig2[["date","Local Time","temperature_2m","rain"]]
print(df_fig2)

#Streamlit optionbox
fig2_option = st.radio(
    "**Selecteer:**", ("Dataframe", "24h Weersvoorspelling")
)

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
    


#Create figure 2 with plotly. It is a line graph showing temperature and the next 24h
fig2 = go.Figure()

if show_temp:
    fig2.add_trace(go.Scatter( 
        x=df_fig2["Local Time"], 
        y=df_fig2["temperature_2m"],
        mode = 'lines+markers',
        line=dict(color='rgba(230, 93, 32, 0.761)'), #Oranje
        fill='tozeroy',
        fillcolor='rgba(201, 90, 41, 0.49)',
        name = "Temperature (°C)",
        yaxis="y1",
        hovertemplate="<b>Temperatuur:</b> %{y} °C<br><extra></extra>"
    ))

if show_rain:
    fig2.add_trace(go.Scatter(
        x=df_fig2["Local Time"], 
        y=df_fig2["rain"],
        mode = 'lines+markers',
        line=dict(color='rgba(67, 147, 219, 0.5)'), #Blauw
        fill='tozeroy',
        fillcolor='rgba(134, 61, 153, 0.2)',
        name = "Regen (mm)",
        yaxis="y2",
        hovertemplate="<b>Regen:</b> %{y} mm<extra></extra>"
    ))

if show_wind:
    fig2.add_trace(go.Scatter(
        x=df_fig2["Local Time"], 
        y=df_fig2["wind_speed_10m"],
        mode = 'lines+markers',
        line=dict(color='rgba(155, 52, 201, 0.5)'), #Paars
        fill='tozeroy',
        fillcolor='rgba(154, 66, 194, 0.2)',
        name = "Wind Snelheid (km/h)",
        yaxis="y3",
        hovertemplate="<b>Wind Snelheid:</b> %{y} km/h<extra></extra>"
    ))    

fig2.update_layout(
    title="Weersvoorspelling 24h",
    xaxis_title="Lokale Tijd",
    xaxis=dict(domain=[0.0,0.85]),
    yaxis=dict(title="Temperatuur (°C)", range=[0, df_fig2["temperature_2m"].max()+10]),
    yaxis2=dict(title="Regen (mm)", side='right', overlaying='y', range=[0, df_fig2["rain"].max()+2]),
    yaxis3=dict(title="Wind Snelheid (km/h)", side='right', overlaying='y', position=0.98, range=[0, df_fig2["wind_speed_10m"].max()+5]),
    hovermode='x unified',
    hoverlabel=dict(
        font_size=14,
        font_family="Arial",
        font_color="black",
        bgcolor="rgba(255, 255, 255, 0.82)",
        bordercolor="rgba(0, 0, 0, 0)",  
    ),
    hoverdistance=100,
    spikedistance=100
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

if fig2_option == "24h Weersvoorspelling":
    st.plotly_chart(fig2, use_container_width=True)

#endregion

# ---------------------------------------- End

