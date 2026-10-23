import streamlit as st
import pandas as pd
import re
from pathlib import Path

st.set_page_config(page_title="Bunawan Flood Data Dashboard", page_icon="🌧️", layout="wide")

st.title("🌧️ Bunawan Flood Data Dashboard")
st.write("Explore flood records, affected families, reported damages, water levels, and weather information.")

# Keep FloodData 3.xlsx in the same folder as this app.py file.
DEFAULT_FILE = Path(__file__).parent / "FloodData 3.xlsx"

@st.cache_data
def load_data(uploaded_file=None):
    if uploaded_file is not None:
        data = pd.read_excel(uploaded_file)
    elif DEFAULT_FILE.exists():
        data = pd.read_excel(DEFAULT_FILE)
    else:
        return pd.DataFrame()

    # Remove empty columns and clean column names
    data = data.loc[:, ~data.columns.astype(str).str.startswith("Unnamed")]
    data.columns = data.columns.astype(str).str.strip()

    # Some date/weather values appear only on the first row of a group in the Excel file.
    # Fill these down so the related barangay rows can be filtered by date.
    for col in ["Month", "Day", "Year", "Month.1", "Day.1", "Year.1",
                "Weather", "Temperature(°C)", "Rainfall (mm)", "Wind", "Pressure"]:
        if col in data.columns:
            data[col] = data[col].ffill()

    # Convert numeric fields safely
    for col in ["Day", "Year", "Day.1", "Year.1", "Flood Occurrence",
                "No. of Families affected", "Damage Infrastructure",
                "Damage Agriculture", "Rainfall (mm)"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    # Create a date column from the main event date fields
    if all(col in data.columns for col in ["Year", "Month", "Day"]):
        month_numbers = {
            "January": 1, "February": 2, "March": 3, "April": 4,
            "May": 5, "June": 6, "July": 7, "August": 8,
            "September": 9, "October": 10, "November": 11, "December": 12
        }
        month_num = data["Month"].astype(str).str.strip().str.title().map(month_numbers)
        data["Date"] = pd.to_datetime(
            {"year": data["Year"], "month": month_num, "day": data["Day"]},
            errors="coerce"
        )
    else:
        data["Date"] = pd.NaT

    # Turn values such as "4 ft.", "3ft", and "4.5 ft" into numbers for charts
    if "Water Level" in data.columns:
        data["Water Level (ft)"] = data["Water Level"].astype(str).apply(
            lambda x: float(re.search(r"\d+(?:\.\d+)?", x).group())
            if re.search(r"\d+(?:\.\d+)?", x) else None
        )

    if "Barangay" in data.columns:
        data["Barangay"] = data["Barangay"].astype(str).str.strip()
    return data


with st.sidebar:
    st.header("Data and Filters")
    uploaded_file = st.file_uploader("Upload Excel dataset (optional)", type=["xlsx", "xls"])

data = load_data(uploaded_file)

if data.empty:
    st.error("I cannot find the Excel file. Put 'FloodData 3.xlsx' in the same folder as app.py, or upload it using the sidebar.")
    st.stop()

# Filter by year and barangay
filtered = data.copy()
if "Year" in filtered.columns:
    years = sorted(filtered["Year"].dropna().astype(int).unique().tolist())
    if years:
        with st.sidebar:
            selected_years = st.multiselect("Select year(s)", years, default=years)
        filtered = filtered[filtered["Year"].isin(selected_years)]

if "Barangay" in filtered.columns:
    barangays = sorted(filtered["Barangay"].dropna().unique().tolist())
    with st.sidebar:
        selected_barangays = st.multiselect("Select barangay(s)", barangays, default=barangays)
    if selected_barangays:
        filtered = filtered[filtered["Barangay"].isin(selected_barangays)]
    else:
        filtered = filtered.iloc[0:0]

if filtered.empty:
    st.warning("No records match the selected filters.")
    st.stop()

# KPI cards
k1, k2, k3, k4 = st.columns(4)
k1.metric("Barangay Records", f"{len(filtered):,}")

if "No. of Families affected" in filtered.columns:
    families = filtered["No. of Families affected"].sum()
    k2.metric("Families Affected (sum)", f"{families:,.0f}")
else:
    k2.metric("Families Affected", "N/A")

damage_cols = [c for c in ["Damage Infrastructure", "Damage Agriculture"] if c in filtered.columns]
if damage_cols:
    total_damage = sum(pd.to_numeric(filtered[c], errors="coerce").fillna(0).sum() for c in damage_cols)
    k3.metric("Reported Damage (sum)", f"₱{total_damage:,.0f}")
else:
    k3.metric("Reported Damage", "N/A")

if "Water Level (ft)" in filtered.columns:
    avg_level = filtered["Water Level (ft)"].mean()
    k4.metric("Average Water Level", f"{avg_level:.1f} ft" if pd.notna(avg_level) else "N/A")
else:
    k4.metric("Average Water Level", "N/A")

st.caption("Note: totals are calculated from the selected rows. If the source file repeats event-level figures across barangays, check the original records before interpreting totals as municipality-wide totals.")

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Frequency", "Barangay Analysis", "Data Table"])

with tab1:
    st.subheader("Overview of selected records")
    left, right = st.columns(2)

    with left:
        if "Barangay" in filtered.columns:
            counts = filtered["Barangay"].value_counts().sort_values(ascending=False)
            st.write("**Records by barangay**")
            st.bar_chart(counts)

    with right:
        if "Month" in filtered.columns:
            month_order = ["January", "February", "March", "April", "May", "June",
                           "July", "August", "September", "October", "November", "December"]
            monthly = filtered["Month"].astype(str).str.strip().str.title().value_counts()
            monthly = monthly.reindex(month_order).dropna()
            st.write("**Records by month**")
            st.bar_chart(monthly)

    if "Flood Cause" in filtered.columns:
        st.write("**Reported flood causes**")
        causes = filtered["Flood Cause"].astype(str).str.strip().replace("", "Not stated").value_counts().head(10)
        st.bar_chart(causes)

with tab2:
    st.subheader("Flood record frequency and seasonal occurrence")
    st.write("This section counts the rows in the dataset. It does not automatically mean each row is a separate flood event.")
    if "Year" in filtered.columns:
        yearly = filtered.dropna(subset=["Year"]).groupby("Year").size().sort_index()
        st.write("**Records by year**")
        st.line_chart(yearly)

    if "Month" in filtered.columns:
        month_order = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        monthly = filtered["Month"].astype(str).str.strip().str.title().value_counts()
        monthly = monthly.reindex(month_order).dropna()
        st.write("**Records by month**")
        st.bar_chart(monthly)

    st.info("Season labels depend on the rule used in your study. Do not assume a month is dry or rainy based only on its name; verify the season definition and local weather evidence used by your research.")

with tab3:
    st.subheader("Compare barangays")
    if "Barangay" in filtered.columns:
        agg = {}
        for col in ["No. of Families affected", "Damage Infrastructure", "Damage Agriculture"]:
            if col in filtered.columns:
                agg[col] = "sum"
        if agg:
            summary = filtered.groupby("Barangay", dropna=False).agg(agg).sort_index()
            st.dataframe(summary, use_container_width=True)

    if "Water Level (ft)" in filtered.columns and "Barangay" in filtered.columns:
        st.write("**Water level by barangay (average of recorded values)**")
        water = filtered.groupby("Barangay")["Water Level (ft)"].mean().dropna().sort_values(ascending=False)
        st.bar_chart(water)

with tab4:
    st.subheader("Filtered dataset")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download filtered data as CSV",
        data=csv,
        file_name="bunawan_filtered_flood_data.csv",
        mime="text/csv"
    )

st.divider()
st.caption("For research use: validate the date, flood-event grouping, seasonal labels, and damage totals with the original MDRRMO records before presenting results.")
