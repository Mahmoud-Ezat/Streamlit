# pages/2_📊_Analysis.py
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Egypt Population - Analysis", layout="wide", page_icon="📊")

st.title("📊 Data Analysis")

# Prüft, ob DataFrame im Session-Status vorhanden ist
if 'cleaned_df' not in st.session_state or st.session_state['cleaned_df'] is None:
    st.warning("Please load data on the '🏠 Home & Data' page first.")
    st.page_link("1_🏠_Home_&_Data.py", label="Go to Home Page", icon="🏠")
    st.stop() # Stoppt die Ausführung, wenn keine Daten vorhanden sind

df = st.session_state['cleaned_df']

# --- Analyse durchführen ---
st.header("Analysis Results")

# Grundlegende Statistiken
with st.expander("Basic Statistics (Numeric Columns)"):
    try:
        # Wählt nur numerische Spalten für describe aus
        numeric_cols = df.select_dtypes(include=np.number).columns
        if not numeric_cols.empty:
            st.dataframe(df[numeric_cols].describe().applymap('{:.0f}'.format)) # Formatieren als ganze Zahl
        else:
            st.info("No numeric columns found for statistics.")
    except Exception as e:
        st.error(f"Error calculating basic statistics: {e}")


# Berechnung der Gesamtbevölkerung und Dichte (hier zur Unabhängigkeit wiederholt)
total_population_misr = None
population_density = None
pop_cols = [col for col in df.columns if col.startswith('population_')] # Pop-Spalten erneut abrufen

try:
    # Stellt sicher, dass der DataFrame nicht leer ist und 'Name' existiert
    if not df.empty and 'Name' in df.columns and pop_cols:
        # Prüft die letzte Zeile vorsichtiger (könnte Indexprobleme geben, wenn leer)
        if len(df) > 0 and df.iloc[-1]['Name'].lower() == 'miṣr':
            total_population_misr = df.iloc[-1][pop_cols]
            egypt_area_km2 = 1002450
            population_density = total_population_misr / egypt_area_km2

            st.subheader("Egypt Total Population and Density")
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Total Population:**")
                st.dataframe(total_population_misr.apply('{:.0f}'.format))
            with col2:
                st.write("**Population Density (persons/km²):**")
                st.dataframe(population_density.apply('{:.0f}'.format))

            # Speichert für potenzielle Verwendung auf der Viz-Seite, obwohl eine Neuberechnung dort auch in Ordnung ist
            st.session_state['population_density'] = population_density
            st.session_state['pop_cols_for_density'] = pop_cols # Unterscheidbarer Schlüssel

        else:
            st.warning("Die Zeile 'Miṣr' (Gesamt Ägypten) konnte für die Dichteberechnung nicht identifiziert werden.")
            if 'population_density' in st.session_state: del st.session_state['population_density']
            if 'pop_cols_for_density' in st.session_state: del st.session_state['pop_cols_for_density']

    else:
        # Fall, wenn DataFrame leer ist oder 'Name' oder Pop-Spalten fehlen
         st.warning("DataFrame ist leer oder benötigte Spalten ('Name', 'population_*') fehlen für die Dichteberechnung.")
         if 'population_density' in st.session_state: del st.session_state['population_density']
         if 'pop_cols_for_density' in st.session_state: del st.session_state['pop_cols_for_density']


except IndexError:
     st.warning("IndexError bei der Suche nach der 'Miṣr'-Zeile (DataFrame könnte leer sein).")
     if 'population_density' in st.session_state: del st.session_state['population_density']
     if 'pop_cols_for_density' in st.session_state: del st.session_state['pop_cols_for_density']
except Exception as e:
    st.error(f"Fehler bei der Berechnung der Gesamtbevölkerung/Dichte: {e}")
    if 'population_density' in st.session_state: del st.session_state['population_density']
    if 'pop_cols_for_density' in st.session_state: del st.session_state['pop_cols_for_density']


# Daten für Stadt-/Gebietsanalyse vorbereiten (Gesamtzeile ausschließen, falls gefunden)
df_analysis = df.copy()
# Prüft, ob total_population_misr berechnet wurde (d.h. die 'Miṣr'-Zeile wurde gefunden)
if total_population_misr is not None and len(df) > 1: # Stellt sicher, dass es mehr als nur die Gesamtzeile gibt
     df_analysis = df.iloc[:-1].copy()
elif len(df)>0 and 'Name' in df.columns and df.iloc[-1]['Name'].lower() != 'miṣr':
     # Wenn die letzte Zeile nicht 'Miṣr' ist, nehmen wir an, dass keine Gesamtzeile vorhanden ist
     df_analysis = df.copy()
elif len(df) <= 1 and total_population_misr is not None:
     st.warning("DataFrame enthält nur die Gesamtzeile, keine Gebietsanalyse möglich.")
     df_analysis = pd.DataFrame() # Leerer DataFrame für den Rest

# Top 10 Städte nach Bevölkerung 2023
if 'population_2023' in df_analysis.columns and not df_analysis.empty:
     st.subheader("Top 10 Cities/Areas by Population (2023)")
     try:
        # Stellt sicher, dass 'Name' und 'Status' existieren, bevor darauf zugegriffen wird
        cols_to_display = ['Name', 'population_2023']
        if 'Status' in df_analysis.columns:
            cols_to_display.insert(1, 'Status')

        top_10_cities = df_analysis.nlargest(10, 'population_2023')[cols_to_display]
        st.table(top_10_cities.style.format({'population_2023': '{:,.0f}'}).hide(axis="index"))
        st.session_state['top_10_cities'] = top_10_cities # Speichert für Viz
     except KeyError as e:
        st.error(f"Fehler beim Zugriff auf Spalten für Top 10 Städte: {e}. Benötigt: 'Name', 'population_2023'. 'Status' optional.")
        if 'top_10_cities' in st.session_state: del st.session_state['top_10_cities']
     except Exception as e:
         st.error(f"Fehler beim Finden der Top 10 Städte: {e}")
         if 'top_10_cities' in st.session_state: del st.session_state['top_10_cities']
elif not df_analysis.empty:
     st.warning("Spalte 'population_2023' nicht gefunden für die Analyse der Top 10 Städte.")
     if 'top_10_cities' in st.session_state: del st.session_state['top_10_cities']

# Berechnung und Analyse der Wachstumsrate
if 'population_1996' in df_analysis.columns and 'population_2023' in df_analysis.columns and not df_analysis.empty:
    st.subheader("Population Growth Rate (1996 - 2023)")
    try:
        pop_1996 = df_analysis['population_1996']
        pop_2023 = df_analysis['population_2023']

        # Berechnet die Wachstumsrate sicher
        # Teile durch pop_1996 nur, wo es nicht 0 oder NaN ist
        growth_rate = np.where(
            (pop_1996.notna()) & (pop_1996 != 0),
            ((pop_2023 - pop_1996) / pop_1996) * 100,
            np.nan # Setze auf NaN, wenn 1996 0 oder NaN ist
        )
        df_analysis['growth_rate'] = growth_rate
        df_analysis['growth_rate'] = df_analysis['growth_rate'].replace([np.inf, -np.inf], np.nan) # Ersetzt inf durch NaN

        cols_growth_display = ['Name', 'population_1996', 'population_2023', 'growth_rate']
        if 'Status' in df_analysis.columns:
            cols_growth_display.insert(1, 'Status')

        col1_growth, col2_growth = st.columns(2)
        with col1_growth:
             st.write("**Top 10 Areas by Growth Rate:**")
             # NaN-Werte werden standardmäßig am Ende sortiert
             top_growth_areas = df_analysis.sort_values('growth_rate', ascending=False, na_position='last').head(10)
             st.table(top_growth_areas[cols_growth_display].style.format({
                 'population_1996': '{:,.0f}',
                 'population_2023': '{:,.0f}',
                 'growth_rate': '{:.1f}%'
             }, na_rep='N/A').hide(axis="index"))
             st.session_state['top_growth_areas'] = top_growth_areas # Speichert für Viz

        with col2_growth:
             st.write("**Bottom 10 Areas by Growth Rate:**")
             low_growth_areas = df_analysis.sort_values('growth_rate', ascending=True, na_position='last').head(10)
             st.table(low_growth_areas[cols_growth_display].style.format({
                  'population_1996': '{:,.0f}',
                  'population_2023': '{:,.0f}',
                  'growth_rate': '{:.1f}%'
             }, na_rep='N/A').hide(axis="index"))
             st.session_state['low_growth_areas'] = low_growth_areas # Speichert für Viz

        # Speichert das df mit Wachstumsrate, falls von viz benötigt
        st.session_state['df_analysis_with_growth'] = df_analysis

    except Exception as e:
        st.error(f"Fehler bei der Berechnung der Wachstumsraten: {e}")
        # Lösche Session State Variablen bei Fehler
        if 'top_growth_areas' in st.session_state: del st.session_state['top_growth_areas']
        if 'low_growth_areas' in st.session_state: del st.session_state['low_growth_areas']
        if 'df_analysis_with_growth' in st.session_state: del st.session_state['df_analysis_with_growth']

elif not df_analysis.empty:
    st.warning("Spalten 'population_1996' oder 'population_2023' nicht gefunden für die Wachstumsratenanalyse.")
    # Lösche Session State Variablen, wenn Spalten fehlen
    if 'top_growth_areas' in st.session_state: del st.session_state['top_growth_areas']
    if 'low_growth_areas' in st.session_state: del st.session_state['low_growth_areas']
    if 'df_analysis_with_growth' in st.session_state: del st.session_state['df_analysis_with_growth']