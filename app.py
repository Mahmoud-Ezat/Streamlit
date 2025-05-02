# app.py
import streamlit as st
import requests
import bs4
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import re
import matplotlib.pyplot as plt
import seaborn as sns
import sqlite3 # Keep if you want to interact with the DB, otherwise optional for display

# --- Page Configuration ---
st.set_page_config(page_title="Egypt Population Analysis", layout="wide")

# --- Caching Functions ---
# Cache the data loading and cleaning process to speed up the app
@st.cache_data(ttl=3600) # Cache data for 1 hour
def load_and_clean_data(url):
    """
    Scrapes population data from the given URL, cleans it, and returns a pandas DataFrame.
    """
    try:
        output = requests.get(url, timeout=10) # Added timeout
        output.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL: {e}")
        return None

    bs_output = BeautifulSoup(markup=output.text, features="lxml") # Using lxml parser

    table_output = bs_output.find(name='table', attrs={'id': 'tl'})
    if table_output is None:
        st.error("Could not find the data table with id='tl' on the page.")
        return None

    # --- Extract Table Headers ---
    try:
        table_columns = [x.get_text(strip=True) for x in table_output.find_all('th')]
        # Keep only the relevant columns based on typical row length later
    except Exception as e:
        st.error(f"Error extracting table headers: {e}")
        return None

    # --- Extract Table Body Data ---
    table_body = table_output.find('tbody') # More specific
    if table_body is None:
         st.error("Could not find the table body (tbody).")
         return None

    Egypt_AD = []
    try:
        rows = table_body.find_all('tr')
        for row in rows:
            td = row.find_all('td')
            # Extract text, strip whitespace, exclude the last column (arrow) if present
            td_values = [val.get_text(strip=True) for val in td]
            if td_values and td_values[-1] == '→': # Check if the last element is the arrow
                 Egypt_AD.append(td_values[:-1])
            elif td_values : # Append if not empty, even if no arrow
                 Egypt_AD.append(td_values)


    except Exception as e:
        st.error(f"Error extracting table rows: {e}")
        return None

    if not Egypt_AD:
        st.warning("No data rows extracted from the table.")
        return None

    # Adjust columns to match data length (important!)
    num_data_cols = len(Egypt_AD[0]) if Egypt_AD else 0
    if num_data_cols > 0:
        table_columns = table_columns[:num_data_cols]
    else:
        st.error("Could not determine the number of data columns.")
        return None

    if len(table_columns) != num_data_cols:
         st.error(f"Header columns ({len(table_columns)}) don't match data columns ({num_data_cols}). Please check scraping logic.")
         st.write("Headers found:", table_columns)
         st.write("First data row:", Egypt_AD[0] if Egypt_AD else "None")
         return None


    # --- Create DataFrame ---
    try:
        egypt_data = pd.DataFrame(data=Egypt_AD, columns=table_columns)
    except Exception as e:
        st.error(f"Error creating DataFrame: {e}")
        return None

    # --- Data Cleaning --- (Adapted from Notebook)
    def clean_numeric_column(col):
        # Make sure col is treated as Series with string type first
        col_str = col.astype(str)
        cleaned_col = col_str.str.replace(",", "", regex=False).str.strip()
        # Handle potential non-string values during replace before converting
        cleaned_col = cleaned_col.replace("...", np.nan, regex=False)
        return pd.to_numeric(cleaned_col, errors="coerce")


    for col in egypt_data.columns:
        if 'Population' in col:
            # Use .copy() to avoid SettingWithCopyWarning if egypt_data is a slice
            egypt_data[col] = clean_numeric_column(egypt_data[col].copy())

    # Clean Name column (remove brackets)
    egypt_data['Name'] = egypt_data['Name'].apply(
        lambda x: re.sub(r'\s*\[.*?\]', '', str(x)).strip() if pd.notna(x) else x
    )

    # Drop duplicates
    egypt_data = egypt_data.drop_duplicates()

    # Clean text columns (Status, Native)
    def clean_text_column(text):
        if pd.isna(text):
            return None
        text = str(text)
        # Keep basic alphanumeric, Arabic unicode range, hyphens, and spaces
        text = re.sub(r"[^\\w\\s\\u0600-\\u06FF\\-]", "", text)
        text = re.sub(r"\\s+", " ", text).strip()
        return text if text else None # Return None if empty after cleaning

    for col in ['Status', 'Native']:
        if col in egypt_data.columns:
            egypt_data[col] = egypt_data[col].apply(clean_text_column)

    # --- Handle Missing Values ---
    # Store means before filling NaNs to use later if needed
    means = {}
    for col in egypt_data.columns:
        if egypt_data[col].dtype in ['float64', 'int64']:
            means[col] = egypt_data[col].mean() # Calculate mean *before* filling
            egypt_data[col] = egypt_data[col].fillna(means[col])

    # Store modes before filling NaNs - MODIFIED BLOCK
    modes = {} # Make sure modes dict is defined before the loop
    for col in ['Status', 'Native']:
         if col in egypt_data.columns and egypt_data[col].isna().sum() > 0:
            # Calculate mode safely
            calculated_mode = egypt_data[col].mode()
            if not calculated_mode.empty:
                mode_val = calculated_mode[0] # Get the first mode if it exists
            else:
                # Handle case where the column has no mode (e.g., all NaN or empty after cleaning)
                st.warning(f"Could not calculate mode for column '{col}' (might be all NaN or empty). Filling NaNs with 'Unknown'.")
                mode_val = 'Unknown' # Use a default value

            modes[col] = mode_val
            egypt_data[col] = egypt_data[col].fillna(mode_val)


    # --- Clean and Rename Columns ---
    def clean_column_name(col_name):
        # Remove dates, special characters, extra spaces, keep Population keyword
        cleaned = re.sub(r'\d{4}-\d{2}-\d{2}', '', col_name) # Remove YYYY-MM-DD
        cleaned = re.sub(r'[()\[\]]+', '', cleaned) # Remove brackets/parentheses
        cleaned = re.sub(r'\s+', '', cleaned).strip() # Remove spaces
        return cleaned

    def extract_year(column_name):
        match = re.search(r'\d{4}', column_name)
        return int(match.group(0)) if match else None

    column_mapping = {}
    new_columns = []
    original_pop_cols = [] # Keep track of original population columns
    for col in egypt_data.columns:
        year = extract_year(col)
        cleaned_name = clean_column_name(col)
        if year and 'Population' in col:
            new_name = f'population_{year}'
            column_mapping[col] = new_name
            new_columns.append(new_name)
            original_pop_cols.append(col) # Store original name
        else:
            # Check if column name already exists after cleaning potential other columns
            final_cleaned_name = cleaned_name
            counter = 1
            while final_cleaned_name in new_columns:
                 final_cleaned_name = f"{cleaned_name}_{counter}"
                 counter += 1

            column_mapping[col] = final_cleaned_name
            new_columns.append(final_cleaned_name)


    egypt_data = egypt_data.rename(columns=column_mapping)

    # Add original means and modes to dataframe attributes for potential display
    egypt_data.attrs['nan_fill_means'] = means
    egypt_data.attrs['nan_fill_modes'] = modes
    egypt_data.attrs['original_pop_cols'] = original_pop_cols


    # Reset index after cleaning and dropping duplicates
    egypt_data.reset_index(drop=True, inplace=True)

    return egypt_data

# --- Main App Logic ---
st.title("🇪🇬 Egypt Population Data Analysis")
st.caption("Data Source: [City Population](https://www.citypopulation.de/en/egypt/admin/)")

# Load data using the cached function
url = "https://www.citypopulation.de/en/egypt/admin/"
df = load_and_clean_data(url)

if df is not None:
    st.success("Data loaded and cleaned successfully!")

    # --- Display Data ---
    st.header("Cleaned Population Data")
    st.dataframe(df.head(10))
    st.write(f"Shape of the cleaned data: {df.shape}")

    # Display info about NaN filling if values were filled
    if 'nan_fill_means' in df.attrs and df.attrs['nan_fill_means']:
         with st.expander("NaN Filling Information (Numeric Columns - Mean)"):
              st.json(df.attrs['nan_fill_means'])
              # Use original column names for clarity
              if 'original_pop_cols' in df.attrs:
                   orig_means = {orig_col: mean for orig_col, mean in zip(df.attrs['original_pop_cols'], df.attrs['nan_fill_means'].values())}
                   st.write("Original columns and mean used for filling:")
                   st.json(orig_means)


    if 'nan_fill_modes' in df.attrs and df.attrs['nan_fill_modes']:
         with st.expander("NaN Filling Information (Categorical Columns - Mode)"):
              st.json(df.attrs['nan_fill_modes'])


    # --- Data Analysis ---
    st.header("Data Analysis")

    # Basic Statistics
    with st.expander("Basic Statistics (Numeric Columns)"):
        st.dataframe(df.describe().applymap('{:.0f}'.format)) # Format to integer

    # Total Population and Density
    try:
         # Ensure population columns exist and the last row is the total
         pop_cols = [col for col in df.columns if col.startswith('population_')]
         if df.iloc[-1]['Name'].lower() == 'miṣr' and pop_cols: # Check if last row is total Egypt
              total_population_misr = df.iloc[-1][pop_cols]
              egypt_area_km2 = 1002450  # Approximate area

              st.subheader("Egypt Total Population and Density")
              col1, col2 = st.columns(2)
              with col1:
                   st.write("**Total Population:**")
                   st.dataframe(total_population_misr.apply('{:.0f}'.format))
              with col2:
                   population_density = total_population_misr / egypt_area_km2
                   st.write("**Population Density (persons/km²):**")
                   st.dataframe(population_density.apply('{:.0f}'.format))
         else:
              st.warning("Could not identify the 'Miṣr' (Egypt total) row for density calculation.")
              total_population_misr = None # Set to None if not found
              population_density = None

    except Exception as e:
         st.error(f"Error calculating total population/density: {e}")
         total_population_misr = None
         population_density = None


    # Prepare data for city/area analysis (exclude total row if found)
    df_analysis = df.copy()
    if total_population_misr is not None:
         df_analysis = df.iloc[:-1].copy() # Exclude last row

    # Top 10 Cities by Population 2023
    if 'population_2023' in df_analysis.columns:
         st.subheader("Top 10 Cities/Areas by Population (2023)")
         top_10_cities = df_analysis.nlargest(10, 'population_2023')[['Name', 'Status','population_2023']]
         st.table(top_10_cities.style.format({'population_2023': '{:,.0f}'})) # Format numbers
    else:
         st.warning("Column 'population_2023' not found for Top 10 Cities analysis.")


    # Growth Rate Calculation and Analysis
    if 'population_1996' in df_analysis.columns and 'population_2023' in df_analysis.columns:
        # Avoid division by zero or NaN issues
        pop_1996 = df_analysis['population_1996']
        pop_2023 = df_analysis['population_2023']

        # Calculate growth rate safely, replace inf/-inf/nan with 0 or NaN if preferred
        df_analysis['growth_rate'] = ((pop_2023 - pop_1996) / pop_1996) * 100
        df_analysis['growth_rate'] = df_analysis['growth_rate'].replace([np.inf, -np.inf], np.nan) # Replace inf with NaN
        #df_analysis['growth_rate'] = df_analysis['growth_rate'].fillna(0) # Optional: fill NaN rates with 0

        st.subheader("Population Growth Rate (1996 - 2023)")

        col1, col2 = st.columns(2)
        with col1:
             st.write("**Top 10 Areas by Growth Rate:**")
             # Sort descending, handle NaNs by placing them last/first or dropping
             top_growth_areas = df_analysis.sort_values('growth_rate', ascending=False, na_position='last').head(10)
             st.table(top_growth_areas[['Name', 'Status', 'population_1996', 'population_2023', 'growth_rate']].style.format({
                 'population_1996': '{:,.0f}',
                 'population_2023': '{:,.0f}',
                 'growth_rate': '{:.1f}%'
             }).hide(axis="index")) # Use hide index for cleaner table
        with col2:
             st.write("**Bottom 10 Areas by Growth Rate:**")
             # Sort ascending, handle NaNs
             low_growth_areas = df_analysis.sort_values('growth_rate', ascending=True, na_position='last').head(10)
             st.table(low_growth_areas[['Name', 'Status', 'population_1996', 'population_2023', 'growth_rate']].style.format({
                  'population_1996': '{:,.0f}',
                  'population_2023': '{:,.0f}',
                  'growth_rate': '{:.1f}%'
             }).hide(axis="index"))
    else:
        st.warning("Columns 'population_1996' or 'population_2023' not found for growth rate analysis.")


    # --- Visualization ---
    st.header("Visualizations")

    # Use tabs for different plots
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Density Trend",
        "Top Growth Areas",
        "Bottom Growth Areas",
        "Top Populated Cities",
        "Population 1996 vs 2023"
    ])

    with tab1:
        st.subheader("Population Density Trend")
        if population_density is not None:
            try:
                years = [int(col.split('_')[-1]) for col in pop_cols] # Extract years from column names
                population_density_values = population_density.values

                fig1, ax1 = plt.subplots(figsize=(7, 5))
                ax1.plot(years, population_density_values, marker='o', color='b', linestyle='-', linewidth=2, markersize=8)
                ax1.set_xlabel('Year')
                ax1.set_ylabel("Population Density (persons/km²)")
                ax1.set_title("Population Density in Egypt Over the Years")
                ax1.grid(True)
                ax1.set_xticks(years) # Ensure all years are shown as ticks
                st.pyplot(fig1)
            except Exception as e:
                st.error(f"Error creating density plot: {e}")
        else:
            st.info("Population density data not available for plotting.")


    with tab2:
        st.subheader("Top 10 Areas by Growth Rate (%)")
        if 'growth_rate' in df_analysis.columns:
             try:
                # Use the previously calculated top_growth_areas, ensure it's sorted
                top_growth_sorted = top_growth_areas.sort_values('growth_rate', ascending=False)

                fig2, ax2 = plt.subplots(figsize=(10, 5))
                # Use seaborn for potentially better aesthetics
                sns.barplot(y='Name', x='growth_rate', data=top_growth_sorted, palette='viridis', ax=ax2, dodge=False)
                ax2.set_xlabel('Growth Rate (%)')
                ax2.set_ylabel('Area')
                ax2.set_title('Top 10 Areas by Population Growth Rate (1996 - 2023)')
                ax2.grid(axis='x', linestyle='--', alpha=0.5)
                plt.tight_layout() # Adjust layout
                st.pyplot(fig2)
             except Exception as e:
                 st.error(f"Error creating top growth plot: {e}")
        else:
             st.info("Growth rate data not available for plotting.")


    with tab3:
         st.subheader("Bottom 10 Areas by Growth Rate (%)")
         if 'growth_rate' in df_analysis.columns:
              try:
                # Use the previously calculated low_growth_areas, ensure it's sorted
                low_growth_sorted = low_growth_areas.sort_values('growth_rate', ascending=True)

                fig3, ax3 = plt.subplots(figsize=(12, 6))
                bars = ax3.barh(
                    low_growth_sorted['Name'],
                    low_growth_sorted['growth_rate'],
                    color='salmon' # Different color for bottom
                )
                # Add text labels to bars
                ax3.bar_label(bars, fmt='%.1f%%', padding=3)

                ax3.set_xlabel('Growth Rate (%)', fontsize=12)
                ax3.set_ylabel('Area', fontsize=12)
                ax3.set_title('Bottom 10 Areas by Population Growth Rate (1996 - 2023)', fontsize=14)
                ax3.grid(axis='x', linestyle='--', alpha=0.5)
                plt.tight_layout()
                st.pyplot(fig3)

              except Exception as e:
                  st.error(f"Error creating bottom growth plot: {e}")
         else:
              st.info("Growth rate data not available for plotting.")


    with tab4:
        st.subheader("Top 10 Cities/Areas by Population (2023)")
        if 'population_2023' in df_analysis.columns:
             try:
                # Use previously calculated top_10_cities, ensure sorted
                top_10_cities_sorted = top_10_cities.sort_values('population_2023', ascending=False)

                fig4, ax4 = plt.subplots(figsize=(12, 6))
                colors = plt.cm.viridis(np.linspace(0, 1, len(top_10_cities_sorted)))
                ax4.bar(top_10_cities_sorted['Name'], top_10_cities_sorted['population_2023'], color=colors)
                ax4.set_xlabel('City/Area')
                ax4.set_ylabel('Population in 2023 (Millions)')
                ax4.set_title('Top 10 Cities/Areas by Population in 2023')
                plt.xticks(rotation=45, ha='right')
                ax4.grid(axis='y', linestyle='--', alpha=0.5)
                # Format y-axis to millions for readability
                ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',').replace(',','M', 1)[:-7] if x >= 1e6 else format(int(x), ',')))
                plt.tight_layout()
                st.pyplot(fig4)
             except Exception as e:
                  st.error(f"Error creating top cities plot: {e}")
        else:
             st.info("Population 2023 data not available for plotting.")


    with tab5:
        st.subheader("Population Comparison: 1996 vs 2023")
        if 'population_1996' in df_analysis.columns and 'population_2023' in df_analysis.columns:
             try:
                fig5, ax5 = plt.subplots(figsize=(8, 6))
                sns.scatterplot(
                    data=df_analysis, # Use the analysis df (without total)
                    x='population_1996',
                    y='population_2023',
                    color='dodgerblue',
                    edgecolor='black',
                    alpha=0.7, # Add transparency
                    ax=ax5
                )
                ax5.set_title('Population in 1996 vs 2023 (Excluding Egypt Total)')
                ax5.set_xlabel('Population 1996')
                ax5.set_ylabel('Population 2023')
                ax5.grid(True, linestyle='--', alpha=0.5)
                # Optional: Add a line y=x for reference
                lims = [
                    min(ax5.get_xlim()[0], ax5.get_ylim()[0]),
                    max(ax5.get_xlim()[1], ax5.get_ylim()[1]),
                     ]
                ax5.plot(lims, lims, 'r--', alpha=0.75, zorder=0, label='y=x (No Change)')
                ax5.set_xlim(lims)
                ax5.set_ylim(lims)
                ax5.legend()
                plt.tight_layout()
                st.pyplot(fig5)
             except Exception as e:
                 st.error(f"Error creating scatter plot: {e}")

        else:
            st.info("Population 1996 or 2023 data not available for scatter plot.")


    # --- Optional: Raw Text Extraction Display ---
    # (From the last cell of notebook's cleaning phase)
    with st.expander("Cleaned Text Artifacts from Page Paragraphs"):
        try:
            response_text = requests.get(url, timeout=10)
            response_text.raise_for_status()
            soup_text = BeautifulSoup(response_text.content, 'lxml')
            all_divs = soup_text.find_all('p') # Assuming <p> tags were intended
            cleaned_texts = []

            # Re-define clean_html_artifacts here or import if modularized
            def clean_html_artifacts(text):
                if pd.isna(text) or str(text).strip() == '':
                    return None
                soup = BeautifulSoup(str(text), 'lxml') # Use lxml
                for tag in soup(['script', 'style']):
                    tag.decompose()
                cleaned_text = soup.get_text(separator=' ', strip=True)
                cleaned_text = re.sub(r'&[a-zA-Z0-9#]+;', ' ', cleaned_text) # Remove HTML entities
                cleaned_text = re.sub(r'<[^>]+>', '', cleaned_text) # Remove any remaining tags
                return cleaned_text if cleaned_text.strip() else None

            for p_tag in all_divs:
                 raw_text = p_tag.get_text(separator=' ', strip=True)
                 cleaned = clean_html_artifacts(raw_text)
                 if cleaned:
                      cleaned_texts.append(cleaned)

            for i, text in enumerate(cleaned_texts[:5]): # Show first 5 non-empty cleaned paragraphs
                 st.write(f"**Paragraph {i+1}:**")
                 st.write(text)
                 st.markdown("---")

        except Exception as e:
             st.warning(f"Could not extract/clean text artifacts: {e}")


else:
    st.error("Failed to load or process data. Please check the URL or the website structure.")
