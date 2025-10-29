import streamlit as st
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import math
import json
import streamlit.components.v1 as components


components.html("""
<script>
let watchId;

function sendPosition(lat, lon) {
  window.parent.postMessage(
    { type: 'location_update', latitude: lat, longitude: lon },
    '*'
  );
}

function startTracking() {
  if (!navigator.geolocation) {
    alert("Geolocation is not supported by your browser.");
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      console.log("Initial position:", pos.coords.latitude, pos.coords.longitude);
      sendPosition(pos.coords.latitude, pos.coords.longitude);
    },
    (err) => {
      console.error("Error getting position:", err);
      alert("Please enable GPS or Location permission and refresh.");
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );

  watchId = navigator.geolocation.watchPosition(
    (pos) => {
      sendPosition(pos.coords.latitude, pos.coords.longitude);
    },
    (err) => {
      console.error("Error watching position:", err);
    },
    { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 }
  );
}

window.addEventListener("load", () => {
  startTracking();
});
</script>
""", height=0)


# -------------------------
# Helpers
# -------------------------
def bearing_between_points(lat1, lon1, lat2, lon2):
    # Calculate bearing in degrees from point1 to point2
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    x = math.sin(delta_lon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lon)
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360) % 360

def make_arrow_divicon(angle, size=32, color="#2b83ba"):
    # DivIcon containing an arrow (➤) rotated to `angle` degrees.
    # You can replace the arrow symbol with any emoji or HTML arrow.
    html = f"""
    <div style="
      transform: rotate({angle}deg);
      font-size: {size}px;
      line-height: {size}px;
      color: {color};
      text-shadow: 0 0 2px rgba(0,0,0,0.6);
      ">
      ➤
    </div>
    """
    return folium.DivIcon(html=html, icon_size=(size, size), icon_anchor=(int(size/2), int(size/2)))

# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title="Live Navigation Demo", layout="wide")
st.title("🚗 Live Navigation Demo — Moving Arrow Tracker")

st.sidebar.header("Navigation / Controls")
destination = st.sidebar.text_input("Destination (optional, e.g., 'Chandigarh')", "")
clear_btn = st.sidebar.button("Clear Path")
st.sidebar.write("Open this app on your phone, allow location access, then press Start Tracking below.")
start_tracking = st.sidebar.button("Start Tracking")
stop_tracking = st.sidebar.button("Stop Tracking")

# session state
if "tracking" not in st.session_state:
    st.session_state.tracking = False
if "positions" not in st.session_state:
    st.session_state.positions = []  # list of (lat, lon, timestamp)
if "last_js_value" not in st.session_state:
    st.session_state.last_js_value = None

# Clear
if clear_btn:
    st.session_state.positions = []
    st.success("Cleared tracked path.")

# Start / Stop toggles
if start_tracking:
    st.session_state.tracking = True
    st.success("Tracking started — allow location permission in your browser when prompted.")
if stop_tracking:
    st.session_state.tracking = False
    st.info("Tracking stopped.")

# -------------------------
# Embedded JS component:
# Use navigator.geolocation.watchPosition to push coordinates back to Streamlit.
# The component returns the latest value when the JS posts it.
# -------------------------
html_code = """
<script>
const send = (v) => {
    // streamlit message format accepted by Streamlit's component bridge
    const payload = JSON.stringify(v);
    window.parent.postMessage({isStreamlitMessage: true, type: 'streamlit:setComponentValue', value: v}, "*");
};

function onSuccess(position) {
    const coords = {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        heading: position.coords.heading,
        speed: position.coords.speed,
        timestamp: position.timestamp
    };
    send(coords);
}

// onError hook
function onError(err) {
    const info = { error: true, message: err.message };
    send(info);
}

if (!window._watchStarted) {
    window._watchStarted = true;
    if (navigator.geolocation) {
        // high accuracy, small interval; watchPosition will call onSuccess repeatedly
        navigator.geolocation.watchPosition(onSuccess, onError, {
            enableHighAccuracy: true,
            maximumAge: 1000,
            timeout: 5000
        });
    } else {
        onError({message: "Geolocation not supported"});
    }
}
</script>
"""

# Render the invisible component (height small). It will send messages to Streamlit when position updates.
# The returned value is whatever the JS last posted (a dict), or None on first run.
latest = components.html(html_code, height=0, scrolling=False)

# The above component doesn't directly return the posted value (some Streamlit versions).
# But the posts set the "value" of the component; check session_state via 'last_js_value' fallback later.
# We rely on the message being delivered to Streamlit and accessible as 'latest' or via streamlit's component value.
# For robustness, accept 'latest' if not None and JSON-like.
if latest:
    try:
        js_val = latest
        # in many Streamlit versions, latest will already be a dict
        if isinstance(js_val, str):
            js_val = json.loads(js_val)
    except Exception:
        js_val = None
else:
    # If component didn't produce a return, try reading from window messages via a tiny fallback
    js_val = None

# The HTML code posts messages directly to the Streamlit frontend; streamlit may supply them as the "value" of component.
# For robust operation across environments, also try to read st.session_state.last_js_value if JS set it earlier.
# (Some Streamlit versions update component value differently; this tries to be tolerant.)
if js_val is None and st.session_state.last_js_value:
    js_val = st.session_state.last_js_value

# If we did get a position from the JS, append to positions (only when tracking)
if js_val and isinstance(js_val, dict) and not js_val.get("error"):
    # structure: {latitude, longitude, accuracy, heading, speed, timestamp}
    # Only append when tracking is active
    if st.session_state.tracking:
        lat = float(js_val.get("latitude"))
        lon = float(js_val.get("longitude"))
        ts = js_val.get("timestamp") or st.time()
        # Avoid duplicates: only append if moved by some small threshold (e.g., >2 meters)
        append_point = True
        if st.session_state.positions:
            last_lat, last_lon, _ = st.session_state.positions[-1]
            # simple distance approx
            dlat = (lat - last_lat) * 111139  # meters approx
            dlon = (lon - last_lon) * 111139 * math.cos(math.radians(lat))
            dist_m = math.sqrt(dlat**2 + dlon**2)
            if dist_m < 1.0:
                append_point = False
        if append_point:
            st.session_state.positions.append((lat, lon, ts))
            st.session_state.last_js_value = js_val

# -------------------------
# Map rendering
# -------------------------
st.subheader("Live Map")
if not st.session_state.positions:
    st.info("No GPS points yet. Press **Start Tracking**, allow location permission in your browser, then move (or walk/drive) to see the moving arrow.")
else:
    # Use last position as center
    last_lat, last_lon, _ = st.session_state.positions[-1]
    m = folium.Map(location=[last_lat, last_lon], zoom_start=17, control_scale=True)

    # Draw path
    path_coords = [(p[0], p[1]) for p in st.session_state.positions]
    folium.PolyLine(locations=path_coords, color="blue", weight=4, opacity=0.8).add_to(m)

    # Start marker
    start_lat, start_lon, _ = st.session_state.positions[0]
    folium.Marker([start_lat, start_lon], popup="Start", icon=folium.Icon(color="green", icon="play")).add_to(m)

    # Destination marker if provided (geocode)
    if destination:
        try:
            geolocator = Nominatim(user_agent="live_nav_app")
            dest = geolocator.geocode(destination)
            if dest:
                folium.Marker([dest.latitude, dest.longitude], popup=f"Destination: {destination}", icon=folium.Icon(color="red", icon="flag")).add_to(m)
        except Exception:
            pass

    # Arrow marker at current position, rotated towards previous point
    if len(st.session_state.positions) >= 2:
        lat1, lon1, _ = st.session_state.positions[-2]
        lat2, lon2, _ = st.session_state.positions[-1]
        angle = bearing_between_points(lat1, lon1, lat2, lon2)
    else:
        angle = 0

    arrow_icon = make_arrow_divicon(angle, size=36, color="#ff6600")
    folium.Marker([last_lat, last_lon], icon=arrow_icon, popup="You (live)").add_to(m)

    # Show map
    st_folium(m, width=900, height=650)

# -------------------------
# Extra UI: show last few points & simple stats
# -------------------------
with st.expander("Tracking details"):
    st.write(f"Tracking: {'ON' if st.session_state.tracking else 'OFF'}")
    st.write("Number of points:", len(st.session_state.positions))
    if st.session_state.positions:
        st.write("Last position:", st.session_state.positions[-1])

st.write("Tip: For best results open this page on your phone, grant location permissions, and keep the browser active in foreground. On desktop GPS accuracy will often be low; mobile gives accurate results.")


