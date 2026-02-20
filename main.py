import streamlit as st
import pandas as pd
import numpy as np
import networkx as nx
from io import BytesIO

st.set_page_config(layout="wide", page_title="System Ageing")

st.title("System Ageing")

col1, col2, col3 = st.columns(3)

with col1:
    uploaded_file1 = st.file_uploader(
        "Final Billage Systems – Current Month (CSV)",
        type=["csv"],
        key="final_billage"
    )

with col2:
    uploaded_file2 = st.file_uploader(
        "Systems Ageing – Last Month (Excel)",
        type=["xlsx"],
        key="system_ageing"
    )

with col3:
    uploaded_file3 = st.file_uploader(
        "Reversal – System (Excel)",
        type=["xlsx"],
        key="reversal_system"
    )
curr_date = st.date_input("📅 Select Ageing Date",value=pd.Timestamp.today().date())
curr_date = pd.to_datetime(curr_date)
if st.button("Run"):
    if uploaded_file1 is None or uploaded_file2 is None or uploaded_file3 is None:
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

    df1["Provision"] = (df1["Bucket"].apply(provcheck) / 100) * df1["Net Outstanding"]
    df1["Net Outstanding"] = np.where(df1["Net Outstanding"] < 0, "Not due", df1["Net Outstanding"])

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df1.to_excel(writer, sheet_name="Ageing", index=False)
        sales_reversal.to_excel(writer, sheet_name="Sales Reversal", index=False)

    st.download_button(
        "Download Output",
        data=output.getvalue(),
        file_name="System_Ageing_Output.xlsx"
    )
