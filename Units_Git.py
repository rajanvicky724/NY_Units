import streamlit as st
import pandas as pd
import requests
import io

# --- CONFIGURATION ---
# NYC Open Data PLUTO Dataset API Endpoint
# This is the official API for NYC property data
API_URL = "https://data.cityofnewyork.us/resource/64uk-42ks.json"

def clean_bbl(value):
    """
    Ensures the BBL is a 10-digit string.
    """
    s = str(value).split(".")[0]
    clean = "".join(filter(str.isdigit, s))
    return clean

def fetch_units_batch(bbl_list):
    """
    Fetches data for MANY BBLs at once using SoQL (SQL for APIs).
    This is much faster and cleaner than scraping.
    """
    # Convert list of BBLs to a string for the query: '1001990025','1001990026',...
    bbl_string = ",".join([f"'{bbl}'" for bbl in bbl_list])
    
    # We query where BBL is in our list
    # We ask for fields: bbl, unitsres (residential), unitstotal (total)
    params = {
        "$select": "bbl, unitsres, unitstotal",
        "$where": f"bbl in({bbl_string})",
        "$limit": 50000  # Max limit per call
    }
    
    try:
        response = requests.get(API_URL, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        return []

# --- STREAMLIT UI ---
st.set_page_config(page_title="NYC Unit Lookup", layout="wide")
st.title("🏙️ NYC Unit Lookup (via Open Data)")
st.markdown("This tool checks the **NYC PLUTO Database** (Open Data) instead of scraping.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        
        cols = df.columns.tolist()
        default_idx = cols.index('Parcel_Number') if 'Parcel_Number' in cols else 0
        target_col = st.selectbox("Select BBL Column", cols, index=default_idx)

        if st.button("Get Units"):
            with st.spinner("Processing..."):
                # 1. Prepare BBLs
                df['Clean_BBL'] = df[target_col].apply(clean_bbl)
                all_bbls = df['Clean_BBL'].unique().tolist()
                
                # 2. Batch Request (Chunks of 200 to avoid URL length limits)
                # PLUTO API works best when we ask for chunks of data
                chunk_size = 200
                api_results = []
                
                progress_bar = st.progress(0)
                
                for i in range(0, len(all_bbls), chunk_size):
                    chunk = all_bbls[i:i + chunk_size]
                    data = fetch_units_batch(chunk)
                    api_results.extend(data)
                    
                    # Update progress
                    progress_bar.progress(min((i + chunk_size) / len(all_bbls), 1.0))
                
                # 3. Convert API data to DataFrame
                # The API returns lowercase keys: 'bbl', 'unitsres', 'unitstotal'
                lookup_df = pd.DataFrame(api_results)
                
                if not lookup_df.empty:
                    # Ensure BBL is string for matching
                    lookup_df['bbl'] = lookup_df['bbl'].astype(str)
                    
                    # Rename columns for clarity
                    lookup_df = lookup_df.rename(columns={
                        'bbl': 'Clean_BBL',
                        'unitstotal': 'Total_Units',
                        'unitsres': 'Res_Units'
                    })
                    
                    # 4. Merge with original data
                    final_df = pd.merge(df, lookup_df[['Clean_BBL', 'Total_Units', 'Res_Units']], 
                                      on='Clean_BBL', 
                                      how='left')
                    
                    # Fill missing values (Not Found in PLUTO)
                    final_df['Total_Units'] = final_df['Total_Units'].fillna("Not Found")
                else:
                    final_df = df.copy()
                    final_df['Total_Units'] = "No Data"

            st.success("Done!")
            
            st.write("### Results Preview")
            st.dataframe(final_df.head())
            
            # Download
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Excel",
                data=output.getvalue(),
                file_name="NYC_PLUTO_Units.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error: {e}")
