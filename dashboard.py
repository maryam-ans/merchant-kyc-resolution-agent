import streamlit as st
import pandas as pd

df = pd.read_csv("audit_log.csv")
st.set_page_config(page_title="KYC Resolution Agent", layout="wide")
st.title("Audit Log Dashboard")

st.header("Overview")
col1, col2, col3, col4 = st.columns(4)

name_mismatch_df = df[df['category'] == "name_mismatch"]

with col1:
    st.metric("📋 Total Merchants", len(df))

with col2:
    st.metric("⚠️ Name Mismatch Count", len(name_mismatch_df))
## I could have done this or other same outcome but different writing ways
# st.metric("Name Mismatch Count", (df['category'] == "name_mismatch").sum())

with col3:
    revenue = df[df['action'] != 'no_action']
    gmv_total = revenue['estimated_monthly_gmv'].sum()
    st.metric("💰 Est. GMV Unblocked (Rs)", f"{gmv_total:,.0f}")

with col4:
    resolved_count = len(df[df['verification_result'] == 'resolved'])
    resolved_pct = (resolved_count / len(name_mismatch_df) * 100) if len(name_mismatch_df) else 0
    st.metric("✅ Resolved After Verify", resolved_count, delta=f"{resolved_pct:.0f}% of mismatches")

st.caption("GMV figures are simulated estimates, not confirmed revenue.")
st.divider()

st.header("Failure Categories")
counts = df['category'].value_counts().sort_values(ascending=False)  ##add sort to sort it
st.bar_chart(counts)
st.divider()

st.header("🔍 Name Mismatch Spotlight")
st.caption("Your flagship feature — deep dive into each caught mismatch")

for _, row in name_mismatch_df.iterrows():
    with st.expander(f"{row['merchant_id']} — {row['verification_result']}"):
        st.write(f"**Mismatch details:** {row['name_mismatch_details']}")
        st.write(f"**AI-generated fix:** {row['action_detail']}")
        st.write(f"**Estimated monthly GMV:** Rs {row['estimated_monthly_gmv']:,.0f}")

st.divider()

st.header("Full Audit Trail")

selected_categories = st.multiselect(
    "Filter by category",
    options=df['category'].unique(),
    default=df['category'].unique()
)
filtered_df = df[df['category'].isin(selected_categories)]
st.dataframe(filtered_df, use_container_width=True)