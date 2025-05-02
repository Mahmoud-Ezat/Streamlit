import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(page_title="تحليل تعداد سكان مصر", layout="wide")
st.title("📊 تحليل تعداد سكان مصر (1996 - 2023)")

st.sidebar.title("ℹ️ عن المشروع")
st.sidebar.info("هذا التطبيق يعرض تحليل بيانات التعداد السكاني لمصر بين عامي 1996 و2023 بناءً على بيانات وزارة التخطيط.")

egypt_population_df = pd.read_csv('./cleaned_egypt_population_wide.csv')
egypt_population_df = pd.DataFrame(egypt_population_df)

egypt_area = 1002450  # كم²
total_population_misr = egypt_population_df.iloc[-1][['population_1996', 'population_2006', 'population_2017', 'population_2023']]
population_density = total_population_misr / egypt_area

egypt_data_without_total = egypt_population_df.iloc[:-1].copy()

top_10_cities = egypt_data_without_total.nlargest(10, 'population_2023')[['Name', 'population_2023']]

egypt_population_df['growth_rate'] = ((egypt_population_df['population_2023'] - egypt_population_df['population_1996']) /
                                     egypt_population_df['population_1996']) * 100
top_growth_areas = egypt_population_df.nlargest(10, 'growth_rate')[['Name', 'Status', 'population_1996', 'population_2023', 'growth_rate']]
low_growth_areas = egypt_population_df.nsmallest(10, 'growth_rate')[['Name', 'Status', 'population_1996', 'population_2023', 'growth_rate']]

st.subheader("📈 الكثافة السكانية في مصر (نسمة/كم²)")
years = ['1996', '2006', '2017', '2023']
population_density_values = population_density.values
density_df = pd.DataFrame({'Year': years, 'Density': population_density_values})
st.line_chart(density_df.set_index('Year'))
st.dataframe(density_df)

st.subheader("🚀 أعلى 10 مناطق من حيث معدل النمو السكاني (1996 - 2023)")
st.bar_chart(top_growth_areas.set_index('Name')['growth_rate'])

st.subheader("📉 أقل 10 مناطق من حيث معدل النمو السكاني (1996 - 2023)")
st.bar_chart(low_growth_areas.set_index('Name')['growth_rate'])

st.subheader("🏙️ أعلى 10 مدن من حيث عدد السكان في 2023")
st.bar_chart(top_10_cities.set_index('Name'))

st.subheader("🔎 علاقة عدد السكان بين 1996 و2023")
st.scatter_chart(
    data=egypt_population_df.iloc[:-1],
    x='population_1996',
    y='population_2023',
)
