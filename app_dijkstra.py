import streamlit as st
import networkx as nx
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# -----------------------------------------------------
# 🌍 Setup geolocator
# -----------------------------------------------------
geolocator = Nominatim(user_agent="dijkstra_app")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)


# -----------------------------------------------------
# ✨ Time Formatting Helper
# -----------------------------------------------------
def format_duration(distance_km):
    # assume average speed of 50 km/h
    hours = distance_km / 50
    minutes = hours * 60
    if minutes < 60:
        return f"{int(minutes)} min"
    else:
        h = int(minutes // 60)
        m = int(minutes % 60)
        return f"{h} hr {m} min" if m else f"{h} hr"


# -----------------------------------------------------
# 🗺️ Visualization Function
# -----------------------------------------------------
def visualize_graph_folium(G, path=None, total_distance=None):
    if not G.nodes:
        return folium.Map(location=(20, 0), zoom_start=2)

    node_positions = {
        node: data.get("pos") for node, data in G.nodes(data=True) if "pos" in data
    }

    avg_lat = sum(lat for lat, _ in node_positions.values()) / len(node_positions)
    avg_lon = sum(lon for _, lon in node_positions.values()) / len(node_positions)
    m = folium.Map(location=(avg_lat, avg_lon), zoom_start=5, tiles="CartoDB dark_matter")

    # Draw all edges (roads)
    for u, v, data in G.edges(data=True):
        if u in node_positions and v in node_positions:
            latlngs = [node_positions[u], node_positions[v]]
            folium.PolyLine(
                latlngs, color="gray", weight=2, opacity=0.5
            ).add_to(m)

            # Midpoint label for distance
            mid_lat = (latlngs[0][0] + latlngs[1][0]) / 2
            mid_lon = (latlngs[0][1] + latlngs[1][1]) / 2
            dist = data.get("weight", 0)
            folium.map.Marker(
                [mid_lat, mid_lon],
                icon=folium.DivIcon(
                    html=f"<div style='font-size:11px;color:#bbb;text-align:center;'>{dist:.1f} km</div>"
                ),
            ).add_to(m)

    # Add all nodes
    for node, (lat, lon) in node_positions.items():
        folium.CircleMarker(
            (lat, lon),
            radius=6,
            color="#2196f3",
            fill=True,
            fill_color="#2196f3",
            fill_opacity=0.9,
            popup=node,
        ).add_to(m)

    # Highlight the shortest path
    if path:
        coords = [node_positions[n] for n in path if n in node_positions]
        if coords:
            # Glowing blue path for shortest route
            folium.PolyLine(
                coords,
                color="#00e5ff",
                weight=8,
                opacity=0.9,
                dash_array="10",
            ).add_to(m)

            # Animated shadow glow (dual layer)
            folium.PolyLine(
                coords,
                color="#80deea",
                weight=14,
                opacity=0.3,
            ).add_to(m)

            # Start & End markers
            folium.CircleMarker(
                coords[0],
                radius=8,
                color="lime",
                fill=True,
                fill_color="lime",
                popup=f"🚦 Start: {path[0]}",
            ).add_to(m)

            folium.CircleMarker(
                coords[-1],
                radius=8,
                color="red",
                fill=True,
                fill_color="red",
                popup=f"🏁 End: {path[-1]}",
            ).add_to(m)

            # Distance popup at midpoint
            if total_distance:
                mid_lat = sum(lat for lat, _ in coords) / len(coords)
                mid_lon = sum(lon for _, lon in coords) / len(coords)
                folium.Marker(
                    (mid_lat, mid_lon),
                    icon=folium.DivIcon(
                        html=f"""
                        <div style="
                            background: rgba(27,38,59,0.95);
                            padding: 8px 14px;
                            border-radius: 12px;
                            border: 1px solid #00e5ff;
                            color: #00e5ff;
                            font-weight: 600;
                            font-size: 13px;
                            white-space: nowrap;
                            text-align: center;
                            box-shadow: 0 0 12px #00e5ff;
                            transform: translate(-50%, -50%);
                            ">
                            ✨ Shortest Path: {total_distance:.2f} km
                        </div>
                        <style>
                        @keyframes pulse {{
                            0% {{ box-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff; }}
                            100% {{ box-shadow: 0 0 20px #00e5ff, 0 0 40px #00e5ff; }}
                        }}
                        </style>
                        """
                    ),
            ).add_to(m)

    return m


# -----------------------------------------------------
# ⚙️ Streamlit Config
# -----------------------------------------------------
st.set_page_config(page_title="Smart Dijkstra Path Finder", layout="wide")
st.markdown(
    """
    <h1 style="text-align:center;color:#00e5ff;text-shadow:0 0 10px #00e5ff;">🧭 Smart Shortest Path Finder (Dijkstra)</h1>
    """,
    unsafe_allow_html=True,
)

if "G" not in st.session_state:
    st.session_state.G = nx.Graph()
G = st.session_state.G

# -----------------------------------------------------
# 🎛️ Sidebar Controls
# -----------------------------------------------------
st.sidebar.header("Graph Controls")
mode = st.sidebar.radio(
    "Mode",
    ["Add Place", "Add Road (Edge)", "Set Start", "Set End", "Find Shortest Path"],
)

# -----------------------------------------------------
# 📍 Add Place (auto geocode)
# -----------------------------------------------------
if mode == "Add Place":
    st.sidebar.subheader("Add a Place")
    place_name = st.sidebar.text_input("Enter place name (e.g., Chandigarh, Delhi, Mumbai)")
    if st.sidebar.button("Add Place"):
        if place_name:
            try:
                location = geocode(place_name)
                if location:
                    lat, lon = location.latitude, location.longitude
                    G.add_node(place_name, pos=(lat, lon))
                    st.sidebar.success(f"✅ Added {place_name} ({lat:.4f}, {lon:.4f})")
                else:
                    st.sidebar.error("❌ Place not found.")
            except Exception as e:
                st.sidebar.error(f"Error: {e}")
        else:
            st.sidebar.warning("Please enter a place name.")

# -----------------------------------------------------
# 🛣️ Add Edge Between Two Nodes
# -----------------------------------------------------
elif mode == "Add Road (Edge)":
    if len(G.nodes) < 2:
        st.sidebar.warning("Add at least 2 places first.")
    else:
        n1 = st.sidebar.selectbox("From", list(G.nodes))
        n2 = st.sidebar.selectbox("To", list(G.nodes))
        dist = st.sidebar.number_input("Distance (km)", min_value=0.0)
        if st.sidebar.button("Add Edge"):
            if n1 != n2:
                G.add_edge(n1, n2, weight=dist)
                st.sidebar.success(f"🛣️ Added road: {n1} ↔ {n2} ({dist} km)")
            else:
                st.sidebar.error("Cannot connect a place to itself.")

# -----------------------------------------------------
# 🚦 Set Start / End Nodes
# -----------------------------------------------------
elif mode == "Set Start":
    if len(G.nodes) == 0:
        st.sidebar.warning("Add places first.")
    else:
        start_node = st.sidebar.selectbox("Select Start Place", list(G.nodes))
        if st.sidebar.button("Set as Start"):
            st.session_state.start_node = start_node
            st.sidebar.success(f"Start set to {start_node}")

elif mode == "Set End":
    if len(G.nodes) == 0:
        st.sidebar.warning("Add places first.")
    else:
        end_node = st.sidebar.selectbox("Select End Place", list(G.nodes))
        if st.sidebar.button("Set as End"):
            st.session_state.end_node = end_node
            st.sidebar.success(f"End set to {end_node}")
# -----------------------------------------------------
# 🧮 Find Shortest Path
# -----------------------------------------------------
elif mode == "Find Shortest Path":
    start = st.session_state.get("start_node")
    end = st.session_state.get("end_node")

    if not start or not end:
        st.sidebar.error("Please set both start and end places first.")
    else:
        if st.sidebar.button("Find Path"):
            try:
                path = nx.dijkstra_path(G, start, end, weight="weight")
                total_distance = nx.dijkstra_path_length(G, start, end, weight="weight")
                time_estimate = format_duration(total_distance)

                # 🧠 Save results to session_state so they persist
                st.session_state.path_result = {
                    "path": path,
                    "distance": total_distance,
                    "time": time_estimate,
                }

                st.sidebar.success("✅ Path calculated successfully!")

            except nx.NetworkXNoPath:
                st.sidebar.error("❌ No connection between these places.")
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

        # 🖥️ Display results if available
        if "path_result" in st.session_state:
            result = st.session_state.path_result
            path = result["path"]
            total_distance = result["distance"]
            time_estimate = result["time"]

            st.markdown(
                f"""
                <div style='background:#1b263b;border:2px solid #00e5ff;border-radius:12px;
                padding:20px;color:white;margin:10px 0;box-shadow:0 0 12px #00e5ff;'>
                <h3 style='color:#00e5ff;text-align:center;'>🌟 Shortest Path Found!</h3>
                <p><b>🚦 Start:</b> {start}</p>
                <p><b>🏁 End:</b> {end}</p>
                <p><b>📏 Distance:</b> {total_distance:.2f} km</p>
                <p><b>⏱ Estimated Time:</b> {time_estimate}</p>
                <p><b>🛣 Path:</b> {' ➡️ '.join(path)}</p>
                <p><b>🚗 Mode of Transport:</b> Road (Average Speed 50 km/h)</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 🌍 Show map with highlighted route
            m = visualize_graph_folium(G, path=path, total_distance=total_distance)
            st.markdown("### 🌍 Map Visualization")
            st_folium(m, width=1000, height=600)

# -----------------------------------------------------
# 🗺️ Always show current map
# -----------------------------------------------------
if len(G.nodes) > 0:
    m = visualize_graph_folium(G)
    st.markdown("### 🧭 Current Map View")
    st_folium(m, width=1000, height=600)
else:
    st.info("Start by adding some places using their names.")
