# ------------------ #
# Importing Packages #
# ------------------ #

import openmeteo_requests
import pandas as pd
import plotly.express as px
import seaborn as sns
import requests_cache
from retry_requests import retry
import streamlit as st

# --------------- #
# Open-meteo API  #
# --------------- #

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
	"hourly": ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation"],
	"models": "knmi_seamless",
	"timezone": "Europe/Berlin",
}
responses = openmeteo.weather_api(url, params=params)

# Process first location. Add a for-loop for multiple locations or weather models
response = responses[0]
print(f"Coordinates: {response.Latitude()}°N {response.Longitude()}°E")
print(f"Elevation: {response.Elevation()} m asl")
print(f"Timezone: {response.Timezone()}{response.TimezoneAbbreviation()}")
print(f"Timezone difference to GMT+0: {response.UtcOffsetSeconds()}s")

# Process hourly data. The order of variables needs to be the same as requested.
hourly = response.Hourly()
hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
hourly_dew_point_2m = hourly.Variables(2).ValuesAsNumpy()
hourly_precipitation = hourly.Variables(3).ValuesAsNumpy()

hourly_data = {"date": pd.date_range(
	start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
	end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
	freq = pd.Timedelta(seconds = hourly.Interval()),
	inclusive = "left"
)}

hourly_data["temperature_2m"] = hourly_temperature_2m
hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m
hourly_data["dew_point_2m"] = hourly_dew_point_2m
hourly_data["precipitation"] = hourly_precipitation

hourly_dataframe = pd.DataFrame(data = hourly_data)
print("\nHourly data\n", hourly_dataframe)

# ---------------------------------------- End

# --------------- #
#     Figures     #
# --------------- #

#Figure code here

# ---------------------------------------- End

# --------------- #
#    Streamlit    #
# --------------- #

st.title("KNMI Weerdata")
# Sidebar inputs
st.sidebar.header("Location & Settings")
latitude = st.sidebar.number_input("Latitude", value=52.52, format="%.4f")
longitude = st.sidebar.number_input("Longitude", value=13.41, format="%.4f")
timezone = st.sidebar.text_input("Timezone", "Europe/Berlin")

st.dataframe(hourly_dataframe)

st.write("This is a test")
st.write("GODOOODOAOGAGOA")

st.write("This is a biggggoe test")

# ---------------------------------------- End