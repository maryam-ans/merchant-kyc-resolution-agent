import streamlit as st
import pandas as pd

df = pd.read_csv("audit_log.csv")
st.title("Audit Log Dashboard")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Merchants", len(df))

with col2:
    name_mismatch_df = df[df['category'] == "name_mismatch"]
    st.metric("Name Mismatch Count", len(name_mismatch_df))
## I  could have done this or other same outcome but different writing ways
# st.metric("Name Mismatch Count", (df['category'] == "name_mismatch").sum())

with col3:
    revenue = df[df['action'] != 'no_action']
    gmv_total = revenue['estimated_monthly_gmv'].sum()
    st.metric("Est. GMV Unblocked (Rs)", f"{gmv_total:,.0f}")   


counts = df['category'].value_counts().sort_values(ascending=False) ##add sort to sort it
st.bar_chart(counts)
st.dataframe(df)