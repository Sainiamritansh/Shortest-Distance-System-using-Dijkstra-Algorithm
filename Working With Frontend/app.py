# app.py
import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Smart Shortest Path Finder", layout="wide")
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjIzNjIyOWE0YzBiZTQ4ZDFiNWNkZmM5ZWI5OTUyNTM2IiwiaCI6Im11cm11cjY0In0="  # 🔑 Replace with your own OpenRouteService key

# -------------------------------
# LOAD EXTERNAL FILES
# -------------------------------
def load_css(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except UnicodeDecodeError:
        with open(file_name, "r", encoding="latin-1") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def load_html(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f.read(), unsafe_allow_html=True)
    except UnicodeDecodeError:
        with open(file_name, "r", encoding="latin-1") as f:
            st.markdown(f.read(), unsafe_allow_html=True)



load_css("style.css")
load_html("header.html")

# -------------------------------
# HELPERS
# -------------------------------
geolocator = Nominatim(user_agent="smart_shortest_path_app", timeout=10)
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1, max_retries=2, error_wait_seconds=2.0)

def geocode_location(text):
    if not text or not text.strip():
        return None
    try:
        loc = geocode(text)
        if loc:
            return (loc.latitude, loc.longitude)
    except Exception:
        time.sleep(1)
        try:
            loc = geolocator.geocode(text)
            if loc:
                return (loc.latitude, loc.longitude)
        except Exception:
            return None
    return None

def detect_ip_location():
    try:
        resp = requests.get("https://ipinfo.io/json", timeout=6)
        resp.raise_for_status()
        payload = resp.json()
        loc = payload.get("loc")
        if loc:
            lat, lon = map(float, loc.split(","))
            return (lat, lon)
    except Exception:
        return None

def ors_route(start, end, profile="driving-car"):
    if not ORS_API_KEY or "YOUR_API_KEY_HERE" in ORS_API_KEY:
        raise RuntimeError("Please set your OpenRouteService API key in app.py")

    url = f"https://api.openrouteservice.org/v2/directions/{profile}/geojson"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    body = {"coordinates": [[start[1], start[0]], [end[1], end[0]]]}
    resp = requests.post(url, json=body, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()

# -------------------------------
# SIDEBAR
# -------------------------------
st.sidebar.title("🧭 Route Planner")
st.sidebar.markdown("Enter locations (leave current blank to auto-detect):")

current_location_input = st.sidebar.text_input("📍 Current Location (optional):")
destination_input = st.sidebar.text_input("🎯 Destination (required):")

travel_mode = st.sidebar.selectbox(
    "🚦 Travel Mode",
    ("driving-car", "cycling-regular", "foot-walking"),
    index=0,
    format_func=lambda v: {"driving-car": "🚗 Driving", "cycling-regular": "🚴 Cycling", "foot-walking": "🚶 Walking"}[v]
)

find_button = st.sidebar.button("Find Shortest Path")

# -------------------------------
# MAIN ROUTE LOGIC
# -------------------------------
if find_button:
    st.session_state.pop("route_data", None)
    if not destination_input.strip():
        st.sidebar.error("Please enter a destination.")
    else:
        start_coords, start_label = None, None

        # Manual or auto detect location
        if current_location_input.strip():
            with st.spinner("Geocoding current location..."):
                start_coords = geocode_location(current_location_input.strip())
                start_label = current_location_input.strip()
        else:
            with st.spinner("Auto-detecting location (IP-based)..."):
                start_coords = detect_ip_location()
                start_label = "Auto-detected (IP)"

        if not start_coords:
            st.error("❌ Could not determine your start location automatically. Please enter it manually.")
        else:
            with st.spinner("Geocoding destination..."):
                dest_coords = geocode_location(destination_input.strip())

            if not dest_coords:
                st.error("❌ Could not find destination. Try adding city/country.")
            else:
                try:
                    with st.spinner("Requesting route from OpenRouteService..."):
                        route_geojson = ors_route(start_coords, dest_coords, profile=travel_mode)
                        features = route_geojson.get("features", [])
                        if not features:
                            st.error("❌ No route found.")
                        else:
                            props = features[0].get("properties", {})
                            summary = props.get("summary", {})
                            distance_km = summary.get("distance", 0) / 1000
                            duration_min = summary.get("duration", 0) / 60
                            coords_lonlat = features[0]["geometry"]["coordinates"]
                            coords_latlon = [(c[1], c[0]) for c in coords_lonlat]

                            st.session_state.route_data = {
                                "start_label": start_label,
                                "dest_label": destination_input.strip(),
                                "start_coords": start_coords,
                                "dest_coords": dest_coords,
                                "distance_km": distance_km,
                                "duration_min": duration_min,
                                "coords_latlon": coords_latlon,
                                "mode": travel_mode,
                            }
                            st.success("✅ Route found successfully!")
                except Exception as e:
                    st.error(f"Error fetching route: {e}")

                    
# --- helper for pretty duration ---
def format_duration(minutes):
    if minutes < 60:
        return f"{int(minutes)} min"

    hours = int(minutes // 60)
    mins = int(minutes % 60)

    if hours < 24:
        if mins == 0:
            return f"{hours} hr" if hours == 1 else f"{hours} hrs"
        return f"{hours} hr {mins} min" if hours == 1 else f"{hours} hrs {mins} min"
    else:
        days = hours // 24
        hours = hours % 24
        result = f"{days} day" if days == 1 else f"{days} days"
        if hours > 0:
            result += f" {hours} hr"
        if mins > 0:
            result += f" {mins} min"
        return result

# --- helper for better distance formatting ---
def format_distance(km):
    if km < 1:
        return f"{km*1000:.0f} m"
    elif km < 100:
        return f"{km:.2f} km"
    else:
        return f"{km:.1f} km"


# -------------------------------
# DISPLAY RESULTS
# -------------------------------
if "route_data" in st.session_state:
    data = st.session_state.route_data
    st.markdown(f"""
    <div class="result-card">
      <h3>🗺️ Route</h3>
      <p><b>From:</b> {data['start_label']} &nbsp;&nbsp; <b>To:</b> {data['dest_label']}</p>
      <p><b>📏 Distance:</b> {format_distance(data['distance_km'])} &nbsp;&nbsp; <b>⏱️ Time:</b>{format_duration(data['duration_min'])}
</p>
      <p><b>🚦 Mode:</b> { {'driving-car':'Driving','cycling-regular':'Cycling','foot-walking':'Walking'}[data['mode']] }</p>
    </div>
    """, unsafe_allow_html=True)

    # Map
    try:
        m = folium.Map(location=data["start_coords"], zoom_start=10, control_scale=True)
        folium.Marker(data["start_coords"], popup=f"Start: {data['start_label']}", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(data["dest_coords"], popup=f"Destination: {data['dest_label']}", icon=folium.Icon(color="red")).add_to(m)
        folium.PolyLine(data["coords_latlon"], weight=5, color="blue", opacity=0.8).add_to(m)
        st.markdown("### 🌍 Interactive Map")
        st_folium(m, width=1000, height=600)
    except Exception as e:
        st.error(f"Failed to render map: {e}")

st.markdown("""<hr><div class="footer">Made with ❤️ by <b>Amritansh Saini</b></div>""", unsafe_allow_html=True)
