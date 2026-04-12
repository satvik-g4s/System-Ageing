import streamlit as st
import pandas as pd
import numpy as np
import networkx as nx
from io import BytesIO

st.set_page_config(layout="wide")

st.title("📊 System Ageing & Sales Reversal Processor")

# =========================
# 📂 UPLOAD SECTION
# =========================

st.subheader("📂 Upload Required Files")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### Final Billage Systems – Current Month (CSV)")
    uploaded_file1 = st.file_uploader("", type=["csv"], key="f1")

    st.caption("""
Required Columns:
Invoice No, Invoice Date, Payment Terms, Net Outstanding,
Cust Code, Customer Name, Order Location,
Doc Amount, Total Dr Bal, Total Cr Bal

Note:
- Header starts from row 3
- Payment Terms format: 30D / 45D
""")

with col2:
    st.markdown("### Systems Ageing – Last Month (Excel)")
    uploaded_file2 = st.file_uploader("", type=["xlsx"], key="f2")

    st.caption("""
Sheet: Ageing  
Columns:
Invoice No, Customer Code, Order Location,
Recoverable/Not Recoverable

Sheet: Sales Reversal  
Columns:
OLDInvoice, NEWInvoice, OLD Invoice Date

Note:
- Sheet names must match exactly
""")

with col3:
    st.markdown("### Reversal – System (Excel)")
    uploaded_file3 = st.file_uploader("", type=["xlsx"], key="f3")

    st.caption("""
Required Columns:
Or inv No, New Inv No,
Or inv Dt, New Dt,
Inv Amt, New amt

Note:
- Column names must match system format
""")

curr_date = st.date_input("📅 Select Ageing Date", value=pd.Timestamp.today().date())
curr_date = pd.to_datetime(curr_date)

# RUN BUTTON BELOW UPLOADS
run_clicked = st.button("🚀 Run Processing")

# =========================
# 📘 SEPARATE GUIDE BOXES
# =========================

with st.expander("🔹 What This Tool Does"):
    st.markdown("""
This tool calculates the **true ageing of receivables** by ensuring that invoice ageing is always tracked from the **original invoice date**, even when invoices are reversed and reissued.

It helps in:
- Accurate ageing reporting  
- Financial risk identification  
- Provision calculation  
""")

with st.expander("🔹 How to Use"):
    st.markdown("""
1. Upload all three required files  
2. Ensure column names match the required format  
3. Select the ageing date  
4. Click **Run Processing**  
5. Download the output file  
""")

with st.expander("🔹 Output Details"):
    st.markdown("""
The tool generates an Excel file with:

**1. Ageing Sheet**
- Final ageing bucket  
- Adjusted bucket  
- Provision amount  

**2. Sales Reversal Sheet**
- Invoice mapping history  
- Used for audit and validation  
""")

with st.expander("🔹 Financial Logic"):

    st.markdown("### 1. Impacted Overdue Days")
    st.latex(r"\text{Impacted Overdue Days} = (\text{Selected Date} - \text{Original Invoice Date}) - \text{Payment Terms}")

    st.markdown("""
- Ageing is calculated from the **original invoice date**, not the latest invoice number  
- Payment terms are deducted to capture only the **overdue period**  
- This ensures that delays are measured correctly irrespective of invoice replacements  
""")

    st.markdown("---")

    st.markdown("### 2. Invoice Continuity (Reversals Handling)")
    st.markdown("""
- When an invoice is replaced by another (due to reversal or rebooking), the system continues ageing from the **first issued invoice**  
- The ageing does **not reset** when a new invoice is created  
- This prevents artificial reduction of ageing due to operational adjustments  
""")

    st.markdown("---")

    st.markdown("### 3. Ageing Bucket Classification")
    st.markdown("""
Invoices are classified based on **Impacted Overdue Days**:

- Not due → ≤ 7 days  
- 8 to 30 days  
- 31 to 60 days  
- 61 to 90 days  
- 91 to 180 days  
- 181 to 365 days  
- More than 365 days  

This classification helps in assessing **delay severity and risk level**
""")

    st.markdown("---")

    st.markdown("### 4. Adjusted Ageing (Post Reversal Impact)")
    st.markdown("""
- If an invoice has a linked history (through reversals), its bucket is adjusted based on the **original ageing chain**  
- If no linkage exists, standard ageing is used  
- Final bucket reflects the **true ageing position**
""")

    st.markdown("---")

    st.markdown("### 5. Credit Balance Treatment")
    st.markdown("""
- If **Net Outstanding < 0**:
  → Automatically classified as **"Not due"**  

- This ensures credit balances are not treated as overdue risk  
""")

    st.markdown("---")

    st.markdown("### 6. Provision Calculation")
    st.markdown("""
Provision is calculated based on **Adjusted Ageing Bucket**:

- 61–90 days → 5%  
- 91–180 days → 30%  
- 181–365 days → 60%  
- More than 365 days → 100%  
- Others → 0%  

Provision is applied on **Net Outstanding Amount**
""")

    st.markdown("---")

    st.markdown("### 7. Recoverability Status")
    st.markdown("""
- If an invoice exists in previous ageing:
  → Previous **Recoverable / Not Recoverable** status is retained  

- If not found:
  → Default status = **Recoverable**  

This ensures continuity in financial classification across periods  
""")

# =========================
# 🚀 PROCESSING
# =========================

if run_clicked:

    if uploaded_file1 is None or uploaded_file2 is None or uploaded_file3 is None:
        st.warning("Please upload all required files.")
        st.stop()

    df1 = pd.read_csv(uploaded_file1, header=2, index_col=False)

    df1['Invoice Date'] = pd.to_datetime(df1['Invoice Date'], format="mixed")
    df1["Invoice No"] = df1["Invoice No"].str.strip()
    df1["Order Location"] = df1["Order Location"].str.strip()
    df1['Payment Terms'] = df1['Payment Terms'].str[:-1]

    df1 = df1[
        ["Location Desc", "Cust Code", "Customer Name", "Invoice No",
         "Doc Amount", "Invoice Date", "Order Location", "O/S DAYS",
         "Total Dr Bal", "Total Cr Bal", "Net Outstanding", "Payment Terms"]
    ]

    df2 = pd.read_excel(uploaded_file2, header=1, sheet_name="Ageing")
    df2["Invoice No"] = df2["Invoice No"].str.strip()

    df1 = pd.merge(
        df1,
        df2[["Order Location", "Customer Code", "Invoice No", "Recoverable/Not Recoverable"]],
        left_on=["Cust Code", "Invoice No", "Order Location"],
        right_on=["Customer Code", "Invoice No", "Order Location"],
        how="left"
    )

    df1["Recoverable/Not Recoverable"] = df1["Recoverable/Not Recoverable"].fillna("Recoverable")

    df3 = pd.read_excel(uploaded_file2, header=1, sheet_name="Sales Reversal", usecols="A:M")

    df4 = pd.read_excel(uploaded_file3)
    df4 = df4[
        ["Client", "Name", "Or inv No", "Or inv Dt", "Inv Amt",
         "Cr inv No", "New Inv No", "New Dt", "New amt"]
    ]

    df3 = df3.drop(columns=["Month", "Impacted Overdue Days", "Ageing Bucket"])

    df4 = pd.merge(
        df4,
        df1[["Invoice No", "Payment Terms"]],
        left_on="New Inv No",
        right_on="Invoice No",
        how="left"
    )

    df4 = df4.drop(columns="Invoice No")
    df4 = df4.iloc[:, :df3.shape[1]]
    df4.columns = df3.columns
    df3 = pd.concat([df3, df4], ignore_index=True)

    df3['OLD Invoice Date'] = pd.to_datetime(df3['OLD Invoice Date'], errors="coerce")

    G = nx.DiGraph()
    G.add_edges_from(zip(df3['OLDInvoice'], df3['NEWInvoice']))

    roots = [n for n, d in G.in_degree() if d == 0 or (d == 1 and G.has_edge(n, n))]

    root_map = {}
    for r in roots:
        root_map[r] = r
        for d in nx.descendants(G, r):
            root_map[d] = r

    invoice_to_date = dict(zip(df3['OLDInvoice'], df3['OLD Invoice Date']))

    df3['Impacted Overdue Days'] = (
        curr_date
        - df3['OLDInvoice'].map(root_map).fillna(df3['OLDInvoice']).map(invoice_to_date)
    ).dt.days

    df3['Payment Term'] = pd.to_numeric(df3['Payment Term'], errors="coerce").fillna(0)
    df3['Impacted Overdue Days'] -= df3['Payment Term']

    def Duecheck(d):
        if d <= 7: return "Not due"
        if d <= 30: return "8 to 30 days"
        if d <= 60: return "31 to 60 days"
        if d <= 90: return "61 to 90 days"
        if d <= 180: return "91 to 180 days"
        if d <= 365: return "181 to 365 days"
        return "more than 365 days"

    df3["Ageing Bucket"] = df3["Impacted Overdue Days"].apply(Duecheck)
    sales_reversal = df3.copy()

    df1['Invoice Date'] = pd.to_datetime(df1['Invoice Date'], errors="coerce")
    df1['Payment Terms'] = pd.to_numeric(df1['Payment Terms'], errors="coerce").fillna(0)

    df1['Impacted Overdue Days'] = (
        (curr_date - df1['Invoice Date']).dt.days - df1['Payment Terms']
    )

    df1["Bucket"] = df1["Impacted Overdue Days"].apply(Duecheck)
    df1["Bucket"] = np.where(df1["Net Outstanding"] < 0, "Not due", df1["Bucket"])

    df1 = pd.merge(
        df1,
        df3[["NEWInvoice", "Ageing Bucket"]],
        left_on="Invoice No",
        right_on="NEWInvoice",
        how="left"
    )

    df1 = df1.rename(columns={"Ageing Bucket": "Adjusted Bucket"}).drop(columns="NEWInvoice")
    df1["Adjusted Bucket"] = df1["Adjusted Bucket"].fillna(df1["Bucket"])
    df1["Adjusted Bucket"] = np.where(df1["Net Outstanding"] < 0, "Not due", df1["Adjusted Bucket"])

    def provcheck(b):
        b = str(b).lower().strip()
        if b == "61 to 90 days": return 5
        if b == "91 to 180 days": return 30
        if b == "181 to 365 days": return 60
        if b == "more than 365 days": return 100
        return 0

    df1["Provision"] = (df1["Adjusted Bucket"].apply(provcheck) / 100) * df1["Net Outstanding"]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df1.to_excel(writer, sheet_name="Ageing", index=False)
        sales_reversal.to_excel(writer, sheet_name="Sales Reversal", index=False)

    st.success("Processing Completed!")

    st.download_button(
        "📥 Download Output",
        data=output.getvalue(),
        file_name="System_Ageing_Output.xlsx"
    )
