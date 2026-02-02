import streamlit as st
import pandas as pd
import requests
import time
import urllib3
import io

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
API_URL = "https://propertyinformationportal.nyc.gov/parcels/api/parcels/{}/overview"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://propertyinformationportal.nyc.gov/parcels/',
    'Accept': 'application/json, text/plain, */*'
}

def clean_bbl(value):
    """
    Ensures the BBL is a 10-digit string.
    Removes dashes/spaces/decimals.
    Example: '1-00199-0025' -> '1001990025'
    """
    # Convert to string, remove decimals (e.g., 12345.0 -> 12345)
    s = str(value).split(".")[0]
    # Remove non-numeric characters
    clean = "".join(filter(str.isdigit, s))
    return clean

def get_unit_count(bbl):
    """
    Fetches unit count from NYC Property Portal API.
    """
    url = API_URL.format(bbl)
    try:
        response = requests.get(url, headers=HEADERS, verify=False, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            overview = data.get('parcelOverview', {})
            
            total_units = overview.get('numberOfTotalUnits')
            res_units = overview.get('numberOfResidentialUnits')
            
            # Return total if exists, else residential, else 0/None
            return total_units if total_units is not None else res_units
        elif response.status_code == 404:
            return "Invalid BBL"
        else:
            return f"Error {response.status_code}"
    except Exception:
        return "Connection Error"

# --- STREAMLIT UI ---
st.set_page_config(page_title="NYC Unit Scraper", layout="wide")

st.title("🏙️ NYC Property Unit Scraper")
st.markdown("Upload an Excel file with a column named **`Parcel_Number`** (BBL) to get unit counts.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        st.success("File uploaded successfully!")
        
        # Check for column
        # Allow user to select column if default name doesn't exist
        cols = df.columns.tolist()
        if 'Parcel_Number' in cols:
            target_col = 'Parcel_Number'
        else:
            st.warning("Column 'Parcel_Number' not found. Please select the column containing the BBL/Parcel ID.")
            target_col = st.selectbox("Select BBL Column", cols)

        if st.button("Start Scraping"):
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_rows = len(df)
            
            for index, row in df.iterrows():
                # Update progress
                progress = (index + 1) / total_rows
                progress_bar.progress(progress)
                
                raw_bbl = row[target_col]
                bbl = clean_bbl(raw_bbl)
                
                status_text.text(f"Processing {index + 1}/{total_rows}: {bbl}")
                
                if len(bbl) < 9: # NYC BBLs are typically 10 digits
                    units = "Invalid Format"
                else:
                    units = get_unit_count(bbl)
                
                # Create result row
                # We copy the original row to keep other data, then add new fields
                row_data = row.to_dict()
                row_data['Clean_BBL'] = bbl
                row_data['Total_Units'] = units
                results.append(row_data)
                
                # Polite delay
                time.sleep(0.05)
            
            # Finalize
            status_text.text("Done!")
            result_df = pd.DataFrame(results)
            
            st.write("### Preview Results")
            st.dataframe(result_df.head())
            
            # Download Button
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                result_df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Results as Excel",
                data=output.getvalue(),
                file_name="NYC_Units_Scraped.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error reading file: {e}")
