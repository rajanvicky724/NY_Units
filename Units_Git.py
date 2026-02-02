import streamlit as st
import pandas as pd
import requests
import time
import urllib3
import io
import random

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
# We use a session to maintain cookies (makes us look like a real browser)
session = requests.Session()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://propertyinformationportal.nyc.gov/parcels/',
    'Origin': 'https://propertyinformationportal.nyc.gov',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache'
}

# Apply headers to the session
session.headers.update(HEADERS)

def clean_bbl(value):
    """
    Ensures the BBL is a 10-digit string.
    """
    s = str(value).split(".")[0]
    clean = "".join(filter(str.isdigit, s))
    return clean

def get_unit_count(bbl):
    """
    Fetches unit count using a persistent session.
    """
    url = f"https://propertyinformationportal.nyc.gov/parcels/api/parcels/{bbl}/overview"
    
    # Retry logic (tries 3 times before failing)
    for attempt in range(3):
        try:
            # We add a random parameter to prevent caching issues
            response = session.get(url, verify=False, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                overview = data.get('parcelOverview', {})
                total = overview.get('numberOfTotalUnits')
                res = overview.get('numberOfResidentialUnits')
                val = total if total is not None else res
                return val if val is not None else 0
                
            elif response.status_code == 404:
                return "Invalid BBL"
            
            elif response.status_code == 403:
                # If blocked (403), wait longer and try again
                time.sleep(2)
                continue
                
        except Exception as e:
            # Wait and retry on connection error
            time.sleep(1)
            continue
            
    return "Connection Error"

# --- STREAMLIT UI ---
st.set_page_config(page_title="NYC Unit Scraper", layout="wide")
st.title("🏙️ NYC Property Unit Scraper (Enhanced)")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        st.success("File uploaded!")
        
        # Select Column
        cols = df.columns.tolist()
        default_idx = cols.index('Parcel_Number') if 'Parcel_Number' in cols else 0
        target_col = st.selectbox("Select BBL Column", cols, index=default_idx)

        if st.button("Start Scraping"):
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_rows = len(df)
            
            # Initial request to "wake up" the session cookies
            try:
                session.get("https://propertyinformationportal.nyc.gov/parcels/", verify=False)
            except:
                pass

            for index, row in df.iterrows():
                progress = (index + 1) / total_rows
                progress_bar.progress(progress)
                
                raw_bbl = row[target_col]
                bbl = clean_bbl(raw_bbl)
                
                status_text.text(f"Processing {index + 1}/{total_rows}: {bbl}")
                
                if len(bbl) < 9:
                    units = "Invalid Format"
                else:
                    units = get_unit_count(bbl)
                
                row_data = row.to_dict()
                row_data['Clean_BBL'] = bbl
                row_data['Total_Units'] = units
                results.append(row_data)
                
                # Random delay between 0.5s and 1.5s to look human
                time.sleep(random.uniform(0.5, 1.5))
            
            status_text.text("Done!")
            result_df = pd.DataFrame(results)
            st.write("### Preview Results")
            st.dataframe(result_df.head())
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                result_df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Results",
                data=output.getvalue(),
                file_name="NYC_Units_Scraped.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error: {e}")
