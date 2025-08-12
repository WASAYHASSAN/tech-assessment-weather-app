import streamlit as st
import streamlit.components.v1 as components
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pandas as pd
from datetime import datetime
import urllib.parse
import sqlite3, requests
import os, json
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# Page Config
st.set_page_config(page_title="Weather App", layout="wide", page_icon="⛅")


# Config & Constants
GEOCODER = Nominatim(user_agent="streamlit_weather_app")

WEATHERCODE_MAP = {
    0: ("Clear sky", "☀️"), 1: ("Mainly clear", "🌤️"), 2: ("Partly cloudy", "⛅"), 3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"), 48: ("Depositing rime fog", "🌫️"), 51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"), 55: ("Dense drizzle", "🌧️"), 56: ("Freezing drizzle", "🌧️❄️"),
    57: ("Dense freezing drizzle", "🌧️❄️"), 61: ("Slight rain", "🌧️"), 63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "⛈️"), 66: ("Light freezing rain", "🌧️❄️"), 67: ("Heavy freezing rain", "🌧️❄️"),
    71: ("Light snow", "🌨️"), 73: ("Moderate snow", "🌨️"), 75: ("Heavy snow", "❄️"), 77: ("Snow grains", "❄️"),
    80: ("Rain showers: slight", "🌦️"), 81: ("Rain showers: moderate", "🌧️"), 82: ("Rain showers: violent", "⛈️"),
    85: ("Snow showers slight", "🌨️"), 86: ("Snow showers heavy", "❄️"), 95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with slight hail", "⛈️"), 99: ("Thunderstorm with heavy hail", "⛈️"),
}


HISTORY_DB = "search_history.db"

# Helpers
def weathercode_to_text(code):
    return WEATHERCODE_MAP.get(code, ("Unknown", "❓"))

GEOCODER = Nominatim(user_agent="streamlit-weather-app")

@st.cache_data(ttl=60*15)
def geocode_location(text):
    try:
        loc = GEOCODER.geocode(text, exactly_one=True, language="en", timeout=10)
        if not loc:
            return None
        return loc.latitude, loc.longitude, loc.address
    except (GeocoderTimedOut, GeocoderServiceError):
        return None

@st.cache_data(ttl=60*10)
def reverse_geocode(lat, lon):
    try:
        loc = GEOCODER.reverse((lat, lon), exactly_one=True, language="en", timeout=10)
        return loc.address if loc else None
    except (GeocoderTimedOut, GeocoderServiceError):
        return None

@st.cache_data(ttl=60*5)
def ip_geolocate():
    """Get accurate location from browser GPS, fallback to IP lookup."""
    components.html("""
    <script>
    if (!window.location.search.includes("coords=")) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const coords = position.coords.latitude + "," + position.coords.longitude;
                const query = new URLSearchParams(window.location.search);
                query.set("coords", coords);
                window.location.search = "?" + query.toString();
            },
            function(error) {
                console.log("GPS error", error);
            }
        );
    }
    </script>
    """, height=0)

    # Read coords from URL query params
    params = st.experimental_get_query_params()
    if "coords" in params:
        try:
            lat_str, lon_str = params["coords"][0].split(",")
            lat, lon = float(lat_str), float(lon_str)
            city = reverse_geocode(lat, lon) or f"{lat:.5f}, {lon:.5f}"
            return lat, lon, city
        except Exception:
            pass

    # Fallback: IP-based lookup (use ipwho.is for better coverage)
    try:
        r = requests.get("https://ipwho.is/", timeout=6)
        if r.status_code == 200:
            j = r.json()
            if j.get("success"):
                lat = j.get("latitude")
                lon = j.get("longitude")
                city = j.get("city") or j.get("region") or j.get("country") or ""
                if lat and lon:
                    return float(lat), float(lon), city
    except Exception:
        pass

    return None, None, None

@st.cache_data(ttl=60*5)
def fetch_weather(lat, lon, daily_days=5):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "timezone": "auto",
        "daily": "temperature_2m_max,temperature_2m_min,weathercode,sunrise,sunset,precipitation_sum",
        "forecast_days": daily_days,
        "hourly": "temperature_2m,precipitation,weathercode,windspeed_10m"
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

# =========================
# 2. Geocoding Function
# =========================
def geocode_place(place_name):
    geo_url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": place_name,
        "format": "json",
        "limit": 1
    }
    r = requests.get(geo_url, params=params, timeout=10, headers={"User-Agent": "weather-travel-app"})
    r.raise_for_status()
    data = r.json()
    if not data:
        return None, None
    return float(data[0]["lat"]), float(data[0]["lon"])

# =========================
# 3. Streamlit UI
# =========================
st.title("🌍 Travel Advisory")
st.write("Enter a place name to get weather and travel advice. (search history is not updated for Travel Advisory) powered by gpt-oss-120B, HuggingFace, LangChain")

place_name = st.text_input("Enter location (e.g., New York, Paris, Tokyo):")
daily_days = st.slider("Select the number of days", 1, 7, 5)

if st.button("Get Travel Advisory") and place_name:
    try:
        # Geocode place name
        lat, lon = geocode_place(place_name)
        if lat is None or lon is None:
            st.error("Could not find the location. Try another name.")
        else:
            # Fetch weather data
            weather_data = fetch_weather(lat, lon, daily_days)

            current_weather = weather_data.get("current_weather", {})
            daily_weather = weather_data.get("daily", {})

            weather_summary = f"""
            Location: {place_name}
            Current Temp: {current_weather.get('temperature', 'N/A')}°C
            Windspeed: {current_weather.get('windspeed', 'N/A')} km/h
            Daily Highs: {daily_weather.get('temperature_2m_max', [])}
            Daily Lows: {daily_weather.get('temperature_2m_min', [])}
            Precipitation: {daily_weather.get('precipitation_sum', [])}
            Sunrise: {daily_weather.get('sunrise', [])}
            Sunset: {daily_weather.get('sunset', [])}
            """

            # Prompt for LLM
            prompt = f"""
            You are a travel and health advisor.
            Given the following weather data for {place_name}:
            {weather_summary}

            Provide:
            1. A short travel recommendation for the next {daily_days} days.
            2. Weather precautions.
            3. Health advice.
            Make it concise but helpful.
            """

            HUGGINGFACEHUB_API_TOKEN = st.secrets["HUGGINGFACEHUB_API_TOKEN"]

            llm = HuggingFaceEndpoint(
                repo_id="openai/gpt-oss-120b",
                task="text-generation"
            )
            model = ChatHuggingFace(llm=llm)
            result = model.invoke(prompt)

            st.subheader("Travel Advice")
            st.write(result.content)

    except Exception as e:
        st.error(f"Error: {e}")

def format_temp(t): return f"{t:.1f}°C"


# DB Functions
def init_history_db():
    conn = sqlite3.connect(HISTORY_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit(); conn.close()

def add_to_history(query):
    conn = sqlite3.connect(HISTORY_DB)
    conn.execute("INSERT OR IGNORE INTO history (query) VALUES (?)", (query,))
    conn.commit(); conn.close()

def get_history():
    conn = sqlite3.connect(HISTORY_DB)
    rows = conn.execute("SELECT query FROM history ORDER BY created_at DESC").fetchall()
    conn.close(); return [r[0] for r in rows]

def delete_from_history_by_name(query):
    conn = sqlite3.connect(HISTORY_DB)
    conn.execute("DELETE FROM history WHERE query=?", (query,))
    conn.commit(); conn.close()


# Input Parsing Helpers
def handle_coordinates_input(coords_text):
    parts = coords_text.split(",")
    if len(parts) < 2:
        raise ValueError("Need both lat and lon separated by comma.")
    lat_val = float(parts[0].strip())
    lon_val = float(parts[1].strip())
    name = f"{lat_val:.5f}, {lon_val:.5f}"
    rev = reverse_geocode(lat_val, lon_val)
    if rev: name = rev
    return lat_val, lon_val, name

def handle_city_input(city_text):
    geo = geocode_location(city_text)
    if not geo:
        raise ValueError(f"Could not geocode location: '{city_text}'")
    return geo


def display_weather(lat, lon, display_name):
    weather_json = fetch_weather(lat, lon, daily_days=5)
    current = weather_json.get("current_weather", {})
    daily = weather_json.get("daily", {})

    st.markdown("---")
    st.subheader(f"Weather for: {display_name}")
    tz = weather_json.get("timezone", "auto")
    time_of_obs = current.get("time")
    if time_of_obs:
        st.caption(f"Observed at: {time_of_obs} ({tz})")

    wc = current.get("weathercode")
    desc, emoji = weathercode_to_text(wc)
    temp = current.get("temperature")
    wind = current.get("windspeed")
    wind_dir = current.get("winddirection")

    col_a, col_b, col_c = st.columns([1, 1, 2])
    with col_a:
        st.markdown(f"### {emoji} {desc}")
        if temp is not None:
            st.markdown(f"#### {format_temp(temp)}")
    with col_b:
        if wind is not None:
            st.metric("Wind", f"{wind} km/h")
        if wind_dir is not None:
            st.text(f"Direction: {wind_dir}°")
    with col_c:
        sunrise = daily.get("sunrise", [None])[0]
        sunset = daily.get("sunset", [None])[0]
        if sunrise and sunset:
            st.write("**Sun**")
            st.write(f"• Sunrise: {sunrise}")
            st.write(f"• Sunset: {sunset}")

    # 5-day forecast
    st.markdown("## 5-Day Forecast")
    df = pd.DataFrame({
        "date": daily.get("time", []),
        "tmax": daily.get("temperature_2m_max", []),
        "tmin": daily.get("temperature_2m_min", []),
        "weathercode": daily.get("weathercode", []),
        "sunrise": daily.get("sunrise", []),
        "sunset": daily.get("sunset", []),
        "precip_mm": daily.get("precipitation_sum", [])
    })
    cols = st.columns(len(df))
    for i, row in df.iterrows():
        with cols[i]:
            try:
                pretty = datetime.fromisoformat(row["date"]).strftime("%a %d %b")
            except:
                pretty = row["date"]
            desc, emoji = weathercode_to_text(int(row["weathercode"]))
            st.markdown(f"**{pretty}**")
            st.markdown(f"{emoji} {desc}")
            st.markdown(f"High: **{format_temp(row['tmax'])}**")
            st.markdown(f"Low:  {format_temp(row['tmin'])}")
            if pd.notna(row["precip_mm"]):
                st.write(f"Precip: {row['precip_mm']:.1f} mm")
            if pd.notna(row["sunrise"]) and pd.notna(row["sunset"]):
                st.write(f"Sunrise: {row['sunrise'].split('T')[-1]}")
                st.write(f"Sunset: {row['sunset'].split('T')[-1]}")


st.title("🌤️ Weather Update")
st.markdown("Enter any location or coordinates, then click **Get weather**.")

with st.sidebar:
    st.header("Options")
    input_mode = st.radio("How will you provide location?", [
        "City / Address / Zip / Landmark",
        "Coordinates (lat, lon)",
        "Use my current location (IP)"
    ])

col1, col2 = st.columns([3, 1])
with col1:
    if input_mode != "Use my current location (IP)":
        user_text = st.text_input("Enter location:", placeholder="City or lat,lon")
    else:
        user_text = ""
with col2:
    use_loc_btn = st.button("Use my location (IP)" if input_mode == "Use my current location (IP)" else "Get weather")

lat = lon = display_name = None
error = None

if input_mode == "Use my current location (IP)" and use_loc_btn:
    ip_loc = ip_geolocate()
    if ip_loc:
        lat, lon, city = ip_loc
        display_name = f"{city} (approx. from IP)"
    else:
        error = "Could not determine location from IP."
elif use_loc_btn:
    try:
        if input_mode == "Coordinates (lat, lon)":
            lat, lon, display_name = handle_coordinates_input(user_text)
        elif input_mode == "City / Address / Zip / Landmark":
            lat, lon, display_name = handle_city_input(user_text)
    except ValueError as e:
        error = str(e)

if use_loc_btn and error:
    st.error(error)

if lat and lon:
    add_to_history(display_name)
    display_weather(lat, lon, display_name)


def get_youtube_videos(query, max_results=3):
    """Fetch YouTube videos related to the location."""
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={urllib.parse.quote(query)}&key={YOUTUBE_API_KEY}&maxResults={max_results}&type=video"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        videos = [
            {
                "title": item["snippet"]["title"],
                "video_id": item["id"]["videoId"],
                "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"]
            }
            for item in data.get("items", [])
        ]
        return videos
    return []



def get_unsplash_images(query, count=3):
    """Fetch images from Unsplash API."""
    url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(query)}&client_id={UNSPLASH_ACCESS_KEY}&per_page={count}"
    response = requests.get(url)


    if response.status_code == 200:
        data = response.json()
        return [img["urls"]["regular"] for img in data.get("results", [])]
    return []




# Explore Section
st.subheader("🌍 Explore More About the Location")

location_input = st.text_input("Enter a location to explore:")

if location_input:
    st.write(f"Showing info for **{location_input}**")



    # Google Map Embed

    st.markdown(
        f'<iframe src="https://www.google.com/maps?q={urllib.parse.quote(location_input)}&output=embed" '
        'width="100%" height="400" style="border:0;"></iframe>',
        unsafe_allow_html=True
    )

    # YouTube Videos
    st.markdown("### Related YouTube Videos")
    videos = get_youtube_videos(location_input)


    for v in videos:
    
        st.markdown(f"**{v['title']}**")
        st.video(f"https://www.youtube.com/watch?v={v['video_id']}")

    # Unsplash Images (Additional)
    st.markdown("### Images for searched location: ")
    images = get_unsplash_images(location_input)
    for img_url in images:
        st.image(img_url, use_container_width=True)



HISTORY_DB = "search_history.db"

def init_history_db():
    conn = sqlite3.connect(HISTORY_DB)
    
    cur = conn.cursor()


    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_to_history(query):


    conn = sqlite3.connect(HISTORY_DB)
    cur = conn.cursor()

    try:
        cur.execute("INSERT OR IGNORE INTO history (query) VALUES (?)", (query,))
        conn.commit()
    except Exception:
        pass
    conn.close()




def get_history():
    conn = sqlite3.connect(HISTORY_DB)
    rows = conn.execute("SELECT query FROM history ORDER BY created_at DESC").fetchall()
    conn.close()


    return [r[0] for r in rows]

def delete_from_history_by_name(query):
    conn = sqlite3.connect(HISTORY_DB)
    conn.execute("DELETE FROM history WHERE query=?", (query,))
    conn.commit()
    conn.close()

# Initialize DB
init_history_db()


st.sidebar.markdown("---")
st.sidebar.subheader("Search History")

if display_name and lat is not None and lon is not None:
    add_to_history(display_name)

# Show history list
history_list = get_history()
if history_list:
    selected_hist = st.sidebar.selectbox("Select from history", history_list)

    if st.sidebar.button("Load from history"):
        geo = geocode_location(selected_hist)
        if geo:


            lat, lon, display_name = geo
            st.session_state["from_history"] = {
                "lat": lat,
                "lon": lon,
                "display_name": display_name
            }
            st.rerun()




    delete_choice = st.sidebar.selectbox("Delete a search", history_list)


    if st.sidebar.button("Delete Selected"):
        delete_from_history_by_name(delete_choice)
        st.sidebar.success(f"Deleted '{delete_choice}' from history.")
        st.rerun()

else:
    st.sidebar.info("No history yet.")

if "from_history" in st.session_state:
    lat = st.session_state["from_history"]["lat"]
    lon = st.session_state["from_history"]["lon"]
    display_name = st.session_state["from_history"]["display_name"]
    try:
        weather_json = fetch_weather(lat, lon, daily_days=5)
    except Exception as e:


        st.exception(f"Error fetching weather: {e}")
        st.stop()

    current = weather_json.get("current_weather", {})
    daily = weather_json.get("daily", {})

    st.markdown("---")
    st.subheader(f"Weather for: {display_name}")

    wc = current.get("weathercode")
    desc, emoji = weathercode_to_text(wc)
    temp = current.get("temperature")
    wind = current.get("windspeed")

    st.markdown(f"### {emoji} {desc}")
    if temp is not None:
        st.markdown(f"#### {temp:.1f}°C")
    if wind is not None:
        st.metric("Wind", f"{wind} km/h")




    st.markdown("## 5-Day Forecast")


    df = pd.DataFrame({
        "date": daily.get("time", []),
        "tmax": daily.get("temperature_2m_max", []),
        "tmin": daily.get("temperature_2m_min", []),
        "weathercode": daily.get("weathercode", []),
        "sunrise": daily.get("sunrise", []),
        "sunset": daily.get("sunset", []),
        "precip_mm": daily.get("precipitation_sum", [])
    })
    cols = st.columns(len(df))
    for i, row in df.iterrows():
        with cols[i]:


            try:
            
                pretty = datetime.fromisoformat(row["date"]).strftime("%a %d %b")
            except:
                pretty = row["date"]
            wc = int(row["weathercode"])
            desc, emoji = weathercode_to_text(wc)
            st.markdown(f"**{pretty}**")
            st.markdown(f"{emoji} {desc}")
            st.markdown(f"High: **{row['tmax']:.1f}°C**")
            st.markdown(f"Low:  {row['tmin']:.1f}°C")
            if pd.notna(row["precip_mm"]):
                st.write(f"Precip: {row['precip_mm']:.1f} mm")
            if pd.notna(row["sunrise"]) and pd.notna(row["sunset"]):
                st.write(f"Sunrise: {row['sunrise'].split('T')[-1]}")
                st.write(f"Sunset: {row['sunset'].split('T')[-1]}")

    del st.session_state["from_history"]



def init_history_db():
    conn = sqlite3.connect(HISTORY_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            created_at INTEGER
        )
    """)
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(HISTORY_DB)
    df = pd.read_sql_query("SELECT id, query, created_at FROM history ORDER BY id DESC", conn)
    conn.close()
    return df

def export_history():
    df = get_history()
    if df.empty:
        st.error("⚠ No search history to export.")
        return None
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    return output

# Example UI
st.title("Search History Exporter")

if st.button("Export Search History"):
    export_file = export_history()
    if export_file:
        st.download_button(
            label="📥 Download CSV",
            data=export_file,
            file_name="search_history.csv",
            mime="text/csv"
        )



st.markdown("---")

if st.button("INFO"):
    description = """The Product Manager Accelerator Program is designed to support PM professionals through every stage of their careers. From students looking for entry-level jobs to Directors looking to take on a leadership role, our program has helped over hundreds of students fulfill their career aspirations.

Our Product Manager Accelerator community are ambitious and committed. Through our program they have learnt, honed and developed new PM and leadership skills, giving them a strong foundation for their future endeavors."""

    st.info(description)

st.markdown("---")
st.write("Developed by Wasay Hassan")