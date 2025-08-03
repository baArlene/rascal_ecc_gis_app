import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import io
import folium
from streamlit_folium import folium_static
import random
from datetime import datetime, timedelta
from streamlit.components.v1 import html # Imported html for direct embedding

# --- Function to Generate Random RASCAL Data ---
def generate_random_rascal_data(num_zones=3):
    """Generates a DataFrame with random RASCAL-like data, localized for South Africa."""
    data = []
    incident_name = f"Random Incident {random.randint(100, 999)}"
    timestamp = (datetime.now() - timedelta(minutes=random.randint(1, 60))).strftime("%Y-%m-%d %H:%M:%S")

    radionuclides = ["I-131", "Cs-137", "Sr-90", "Co-60", "Pu-239"]
    
    # Base coordinates for Koeberg, South Africa
    base_lat, base_lon = -33.586, 18.402

    for i in range(num_zones):
        zone_name = f"Zone {chr(65 + i)}" # A, B, C...
        dose_mSv = round(random.uniform(0.5, 25.0), 2) # Random dose between 0.5 and 25 mSv
        radionuclide = random.choice(radionuclides)
        radius_km = round(random.uniform(1.0, 20.0), 1) # Random radius between 1 and 20 km

        # Generate slightly offset coordinates around the base for each zone
        # Small offsets to keep zones relatively close, simulating a single incident
        lat_offset = random.uniform(-0.02, 0.02)
        lon_offset = random.uniform(-0.02, 0.02)
        latitude = round(base_lat + lat_offset, 4)
        longitude = round(base_lon + lon_offset, 4)

        data.append({
            'Zone': zone_name,
            'Dose (mSv)': dose_mSv,
            'Radionuclide': radionuclide,
            'Radius (km)': radius_km,
            'Incident': incident_name,
            'Timestamp': timestamp,
            'Latitude': latitude,
            'Longitude': longitude
        })
    return pd.DataFrame(data)

# --- Functions for Data Parsing ---

# @st.cache_data # Cache the parsing function for performance
def parse_txt(file_content):
    """Parses RASCAL-like data from a TXT string."""
    lines = file_content.strip().split('\n')
    header_lines = [line for line in lines if ':' in line]
    data_lines = [line for line in lines if ';' in line and not line.startswith('Zone;')]

    incident_name = ""
    timestamp = ""
    for h_line in header_lines:
        if "Incident:" in h_line:
            incident_name = h_line.split("Incident:")[1].strip()
        elif "Timestamp:" in h_line:
            timestamp = h_line.split("Timestamp:")[1].strip()

    data = []
    if data_lines:
        # Assuming header is fixed "Zone;Dose (mSv);Radionuclide;Radius (km);Latitude;Longitude"
        for line in data_lines:
            parts = line.split(';')
            if len(parts) == 6: # Now expecting 6 parts including lat/lon
                try:
                    data.append({
                        'Zone': parts[0].strip(),
                        'Dose (mSv)': float(parts[1].strip()),
                        'Radionuclide': parts[2].strip(),
                        'Radius (km)': float(parts[3].strip()),
                        'Latitude': float(parts[4].strip()),
                        'Longitude': float(parts[5].strip())
                    })
                except ValueError:
                    st.warning(f"Skipping malformed TXT line: {line}")
            else:
                st.warning(f"Skipping TXT line with incorrect number of columns: {line}")
    df = pd.DataFrame(data)
    df['Incident'] = incident_name
    df['Timestamp'] = timestamp
    return df

# @st.cache_data # Cache the parsing function for performance
def parse_csv(file_content):
    """Parses RASCAL-like data from a CSV string."""
    df = pd.read_csv(io.StringIO(file_content))
    # Ensure column names match expectations, adjust if necessary
    df.columns = [col.strip() for col in df.columns] # Clean up potential whitespace
    return df

# @st.cache_data # Cache the parsing function for performance
def parse_xml(file_content):
    """Parses RASCAL-like data from an XML string."""
    root = ET.fromstring(file_content)
    incident_elem = root.find('Incident')
    incident_name = incident_elem.get('name') if incident_elem is not None else "N/A"
    timestamp = incident_elem.get('timestamp') if incident_elem is not None else "N/A"

    data = []
    for zone_elem in root.findall('.//Zone'):
        try:
            data.append({
                'Zone': zone_elem.get('name'),
                'Dose (mSv)': float(zone_elem.get('dose_mSv')),
                'Radionuclide': zone_elem.get('radionuclide'),
                'Radius (km)': float(zone_elem.get('radius_km')),
                'Latitude': float(zone_elem.get('latitude')),
                'Longitude': float(zone_elem.get('longitude'))
            })
        except (TypeError, ValueError) as e:
            st.warning(f"Skipping malformed XML zone element: {zone_elem.tag} - {e}")
    df = pd.DataFrame(data)
    df['Incident'] = incident_name
    df['Timestamp'] = timestamp
    return df

# --- Protective Action Logic ---

def recommend_protective_actions(df):
    """Applies simplified logic to recommend protective actions."""
    if df.empty:
        return df

    # Define thresholds (example values)
    EVACUATE_THRESHOLD = 10.0 # mSv
    SHELTER_THRESHOLD = 5.0  # mSv
    MONITOR_THRESHOLD = 1.0  # mSv

    def get_action(dose):
        if dose >= EVACUATE_THRESHOLD:
            return "Evacuate"
        elif dose >= SHELTER_THRESHOLD:
            return "Shelter-in-Place"
        elif dose >= MONITOR_THRESHOLD:
            return "Monitor & Advise"
        else:
            return "No Immediate Action"

    def get_color(action):
        if action == "Evacuate":
            return "red"
        elif action == "Shelter-in-Place":
            return "orange"
        elif action == "Monitor & Advise":
            return "yellow"
        else:
            return "green"

    df['Recommended Action'] = df['Dose (mSv)'].apply(get_action)
    df['Action Color'] = df['Recommended Action'].apply(get_color)
    return df

# --- Streamlit App Layout ---

st.set_page_config(layout="wide", page_title="RASCAL-ECC-GIS Dashboard PoC")

# --- Authentication Setup ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

# Hardcoded credentials for PoC
CORRECT_USERNAME = "manager"
CORRECT_PASSWORD = "password123"

# --- Custom Styling for Login Page ---
st.markdown("""
    <style>
    .login-left {
        background: url('https://upload.wikimedia.org/wikipedia/commons/thumb/e/ed/BlankMap-World-v2-light-grey.svg/2000px-BlankMap-World-v2-light-grey.svg.png') no-repeat center center;
        background-size: cover;
        padding: 30px;
        height: 400px;
        border-radius: 8px;
        color: white;
    }

    .login-overlay {
        background-color: rgba(0, 0, 0, 0.6);
        padding: 20px;
        height: 100%;
        border-radius: 8px;
    }

    .login-right {
        padding: 30px;
        border-left: 2px solid #ccc;
    }

    @media screen and (max-width: 768px) {
        .login-left, .login-right {
            border-left: none !important;
            height: auto;
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- Login Page (Split Layout) ---
if not st.session_state['authenticated']:
    col1, col2 = st.columns([1, 1])

    # Left: Title + Branding + Description
    with col1:
        st.markdown("""
            <div class="login-left">
                <div class="login-overlay">
                    <h1 style='font-size: 26px;'>☢️ RASCAL-ECC-GIS Integration</h1>
                    <p style='font-size: 15px;'>
                        A prototype dashboard for managing radiological incidents using simulated GIS data from RASCAL.
                    </p>
                    <ul style='font-size: 14px;'>
                        <li>📍 Real-time map overlay</li>
                        <li>📄 Incident decision panel</li>
                        <li>🛡️ Emergency action logic</li>
                    </ul>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Right: Login Form with border
    with col2:
        st.markdown("<div class='login-right'>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>🔐 Secure Login</h3>", unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")

            if submit:
                if username == CORRECT_USERNAME and password == CORRECT_PASSWORD:
                    st.session_state['authenticated'] = True
                    st.session_state['username'] = username
                    st.success("Login successful! Redirecting...")
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()


# If authenticated, show logout button
with st.sidebar:
    st.markdown("## ☢️ Dashboard", unsafe_allow_html=True)

    # Show user info
    if st.session_state.get("authenticated") and st.session_state.get("username"):
        st.markdown(f"👤 **User:** `{st.session_state['username']}`")
        st.markdown(f"🕒 **Session:** `{datetime.now().strftime('%Y-%m-%d %H:%M')}`")

    st.markdown("---", unsafe_allow_html=True)

    # ✨ HTML-styled links (no bullets, no underline)
    st.markdown("""
        <div class='sidebar-links' style='margin-top: 2px;'>
            <a href="#data-source--incident-overview" style="text-decoration: none; display: block; margin-bottom: 10px; font-size: 16px;">📁 Data Upload</a>
            <a href="#simulated-gis-visualization" style="text-decoration: none; display: block; margin-bottom: 10px; font-size: 16px;">🗺️ GIS Map</a>
            <a href="#decision-making-interface" style="text-decoration: none; display: block; margin-bottom: 10px; font-size: 16px;">🧭 Decisions</a>
            <a href="#detailed-processed-rascal-data" style="text-decoration: none; display: block; margin-bottom: 10px; font-size: 16px;">📄 RASCAL Table</a>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    logout_col = st.columns([1, 2, 1])[1]
    with logout_col:
        if st.button("🔓 Logout"):
            st.session_state['authenticated'] = False
            st.session_state['parsed_data'] = pd.DataFrame()
            st.session_state['username'] = None
            st.success("You’ve been logged out.")
            st.rerun()
            
    st.markdown("""
        <style>
        .sidebar-links a:hover {
            color: #f63366;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

# Initialize parsed_data in session_state if not present
if 'parsed_data' not in st.session_state:
    st.session_state['parsed_data'] = pd.DataFrame()

# --- Data Source & Incident Overview (Now full width) ---
st.header("Data Source & Incident Overview")
st.markdown("Upload a RASCAL output file or generate random data.")

uploaded_file = st.file_uploader(
    "Choose a RASCAL output file (.txt, .csv, .xml)",
    type=["txt", "csv", "xml"]
)

if uploaded_file is None:
    if st.button("Generate Random Data"):
        st.session_state['parsed_data'] = generate_random_rascal_data()
        uploaded_file = None 
        st.rerun() # Rerun to update the display with new data
else:
    # If a file is uploaded, process it and store in session state
    file_content = uploaded_file.getvalue().decode("utf-8")
    current_parsed_data = pd.DataFrame()

    try:
        if uploaded_file.name.endswith(".txt"):
            current_parsed_data = parse_txt(file_content)
        elif uploaded_file.name.endswith(".csv"):
            current_parsed_data = parse_csv(file_content)
        elif uploaded_file.name.endswith(".xml"):
            current_parsed_data = parse_xml(file_content)
        else:
            st.error("Unsupported file type. Please upload a .txt, .csv, or .xml file.")
        
        # Only update session state if new data is actually parsed from the upload
        if not current_parsed_data.empty and not current_parsed_data.equals(st.session_state['parsed_data']):
            st.session_state['parsed_data'] = current_parsed_data
            st.rerun() # Rerun to update the display with new data
    except Exception as e:
        st.error(f"Error processing file: {e}. Please check file format.")
        st.session_state['parsed_data'] = pd.DataFrame() # Clear data on error
        st.rerun()


# Display Incident Overview if data is available
if not st.session_state['parsed_data'].empty:
    st.subheader("Current Incident Summary:")
    incident_name = st.session_state['parsed_data']['Incident'].iloc[0]
    timestamp = st.session_state['parsed_data']['Timestamp'].iloc[0]
    max_dose = st.session_state['parsed_data']['Dose (mSv)'].max()
    num_zones = len(st.session_state['parsed_data'])
    
    st.info(f"**Incident:** {incident_name}\n"
            f"**Timestamp:** {timestamp}\n"
            f"**Number of Zones:** {num_zones}\n"
            f"**Highest Dose:** {max_dose:.2f} mSv")
    
    st.divider() # Visual separator

else:
    st.warning("No RASCAL data loaded. Please upload a file or generate random data.")


# --- Simulated GIS Visualization (Now full width) ---
st.header("Simulated GIS Visualization") # Renumbered

# Inject custom CSS to make the iframe fill the width
st.markdown(
    """
    <style>
    iframe {
        width: 100% !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

if not st.session_state['parsed_data'].empty:
    recommended_df = recommend_protective_actions(st.session_state['parsed_data'].copy())

    # Calculate map center based on the first zone's coordinates or average if multiple
    if not recommended_df.empty and 'Latitude' in recommended_df.columns and 'Longitude' in recommended_df.columns:
        map_center_lat = recommended_df['Latitude'].mean()
        map_center_lon = recommended_df['Longitude'].mean()
    else:
        # Fallback to Koeberg if coordinates are missing (shouldn't happen with random data)
        map_center_lat, map_center_lon = -33.586, 18.402 

    # Add a loading spinner while map is being generated
    with st.spinner("Generating map..."):
        m = folium.Map(location=[map_center_lat, map_center_lon], zoom_start=9)

        # Add markers/circles for each zone
        for index, row in recommended_df.iterrows():
            zone_radius_meters = row['Radius (km)'] * 1000 # Convert km to meters for Folium circle
            action_color = row['Action Color']
            action_text = row['Recommended Action']
            zone_name = row['Zone']
            dose_value = row['Dose (mSv)']
            zone_lat = row['Latitude']
            zone_lon = row['Longitude']

            # Add a circle marker for the zone
            folium.Circle(
                location=[zone_lat, zone_lon],
                radius=zone_radius_meters,
                color=action_color,
                fill=True,
                fill_color=action_color,
                fill_opacity=0.4,
                popup=f"<b>Zone:</b> {zone_name}<br>"
                      f"<b>Dose:</b> {dose_value:.2f} mSv<br>"
                      f"<b>Action:</b> {action_text}<br>"
                      f"<b>Radius:</b> {row['Radius (km)']} km"
            ).add_to(m)

            # Add a text label or a more precise marker if needed
            folium.Marker(
                location=[zone_lat, zone_lon], # Use zone-specific coordinates
                icon=folium.DivIcon(html=f"""<div style="font-size: 10pt; color: black; font-weight: bold;">{zone_name}</div>""")
            ).add_to(m)

        # Get the HTML representation of the Folium map
        # Use m._repr_html_() for direct HTML string, render() is for saving to file
        map_html = m._repr_html_() 
        html(map_html, height=600, scrolling=False)
 
    st.markdown("""
    **Legend:**
    * 🔴 **Red:** Evacuate (Immediate danger, clear the area)
    * 🟠 **Orange:** Shelter-in-Place (Seek indoor protection)
    * 🟡 **Yellow:** Monitor & Advise (Increased vigilance, follow guidance)
    * 🟢 **Green:** No Immediate Action (Normal operations, low risk)
    """)
    st.markdown("""
    *(Note: In a full integration, this map would dynamically update within the ECC-GIS system,
    highlighting actual affected areas based on precise GIS data.)*
    """)
else:
    st.info("Map will appear here once RASCAL data is loaded.")
    # Display a placeholder map centered on Koeberg
    m_placeholder = folium.Map(location=[-33.586, 18.402], zoom_start=9)
    placeholder_map_html = m_placeholder._repr_html_()
    html(placeholder_map_html, height=600, scrolling=False)

# --- New Full-Width Section for Processed Data Table ---
if not st.session_state['parsed_data'].empty:
    st.markdown("---") # Separator for the new section
    st.header("Detailed Processed RASCAL Data") 
    st.markdown("Below is the full, parsed RASCAL output data for the current incident.")
    st.dataframe(st.session_state['parsed_data'][['Zone', 'Dose (mSv)', 'Radionuclide', 'Radius (km)', 'Latitude', 'Longitude', 'Incident', 'Timestamp']], use_container_width=True)

# --- New Full-Width Section for Decision-Making Interface ---
if not st.session_state['parsed_data'].empty:
    st.markdown("---") # Separator for the new section
    st.header("Decision-Making Interface") # Renumbered
    st.markdown("Review the recommended actions and simulate approval for each zone.")

    recommended_df = recommend_protective_actions(st.session_state['parsed_data'].copy())
    
    selected_actions = {}
    # Create columns for the grid layout
    num_cols = 3 # You can adjust this number (e.g., 2, 3, or 4) based on how many zones you expect
    cols = st.columns(num_cols)

    for index, row in recommended_df.iterrows():
        with cols[index % num_cols]: # Place each zone's controls in a column
            st.subheader(f"Zone: {row['Zone']}")
            st.markdown(f"**Radius:** {row['Radius (km)']} km")
            st.markdown(f"**Dose:** {row['Dose (mSv)']:.2f} mSv")
            st.markdown(f"**Recommended Action:** :orange[{row['Recommended Action']}]")
            
            # Simulate "Adjust" functionality
            if f"adjusted_dose_{row['Zone']}" not in st.session_state:
                st.session_state[f"adjusted_dose_{row['Zone']}"] = row['Dose (mSv)']

            action_option = st.radio(
                "Decision:",
                ("Approve", "Adjust", "Reject"),
                key=f"action_{row['Zone']}_{st.session_state['parsed_data']['Incident'].iloc[0]}",
                horizontal=True
            )
            
            if action_option == "Adjust":
                new_dose = st.slider(
                    f"Adjust Dose (mSv)", # Simplified label as zone is in subheader
                    min_value=0.0,
                    max_value=25.0,
                    value=st.session_state[f"adjusted_dose_{row['Zone']}"],
                    step=0.1,
                    key=f"slider_dose_{row['Zone']}_{st.session_state['parsed_data']['Incident'].iloc[0]}"
                )
                st.session_state[f"adjusted_dose_{row['Zone']}"] = new_dose
                selected_actions[row['Zone']] = f"Adjusted (New Dose: {new_dose:.2f} mSv)"
            else:
                selected_actions[row['Zone']] = action_option
            
            st.markdown("---") # Separator for each zone in the grid

    # Submit Decisions button outside the loop, after all zones are processed
    if st.button("Submit All Decisions", key="submit_all_decisions"):
        st.success("All decisions submitted! (In a real system, these would be logged to the database).")
        st.json(selected_actions) # Show what would be logged



st.markdown("---")
st.subheader("Next Steps for Full Implementation")
st.markdown("""
This prototype demonstrates the core capabilities. A full implementation would involve:
* **Robust File Monitoring:** A dedicated Python service continuously monitoring RASCAL output directories.
* **Advanced Parsing & Validation:** Handling more complex RASCAL output structures and error checking.
* **Precise GIS Integration:** Direct communication with the ECC-GIS (e.g., ArcGIS Server) to update spatial layers based on approved actions, rather than just a simulated map. This would involve using ESRI's APIs (e.g., ArcGIS API for Python or JavaScript) to interact with existing map services and feature layers.
* **Database Write-back:** Securely writing approved actions to the existing SQL Server database (`DB_PAM`).
* **User Authentication & Authorization:** Integrating with existing security protocols.
* **Comprehensive Error Handling & Logging.**
* **Scalability & Performance Optimization.**
""")
