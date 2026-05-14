import streamlit as st
import pandas as pd
import numpy as np
import networkx as nx
from io import BytesIO
import time

st.set_page_config(layout="wide")

st.title("📊 System Ageing & Sales Reversal Processor")

# =========================
# 📂 UPLOAD SECTION
# =========================

st.subheader("Upload Required Files")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### Final Billage Systems – Current Month (CSV)")
    uploaded_file1 = st.file_uploader(
        "Upload CSV File",
        type=["csv"],
        key="f1"
    )

    st.caption("""
Required Columns:
Invoice No, Invoice Date, Payment Terms, Net Outstanding,
Cust Code, Customer Name, Order Location,
Doc Amount, Total Dr Bal, Total Cr Bal

Note:
- Header can exist anywhere within first 10 rows
- Header row will be auto-detected
- Payment Terms format: 30D / 45D
""")

with col2:
    st.markdown("### Systems Ageing – Last Month (Excel)")
    uploaded_file2 = st.file_uploader(
        "Upload Excel File",
        type=["xlsx"],
        key="f2"
    )

    st.caption("""
Required Sheets:
- Ageing
- Sales Reversal

Ageing Sheet Columns:
Invoice No, Customer Code, Order Location,
Recoverable/Not Recoverable

Sales Reversal Sheet Columns:
OLDInvoice, NEWInvoice, OLD Invoice Date

Note:
- Header can exist anywhere within first 10 rows
- Sheet names must match exactly
""")

with col3:
    st.markdown("### Reversal – System (Excel)")
    uploaded_file3 = st.file_uploader(
        "Upload Excel File",
        type=["xlsx"],
        key="f3"
    )

    st.caption("""
Required Columns:
Or inv No, New Inv No,
Or inv Dt, New Dt,
Inv Amt, New amt

Note:
- Header can exist anywhere within first 10 rows
- Column names must match system format
""")

curr_date = st.date_input(
    "📅 Select Ageing Date",
    value=pd.Timestamp.today().date()
)

curr_date = pd.to_datetime(curr_date)

# =========================
# 🚀 RUN BUTTON
# =========================

run_clicked = st.button("🚀 Run Processing")

# =========================
# 📘 DOCUMENTATION
# =========================

with st.expander("🔹 What This Tool Does"):
    st.markdown("""
This tool calculates the true ageing of receivables by ensuring that invoice ageing is always tracked from the original invoice date, even when invoices are reversed and reissued.

It helps in:
- Accurate ageing reporting
- Financial risk identification
- Provision calculation
""")

with st.expander("🔹 How to Use"):
    st.markdown("""
1. Upload all required files
2. Ensure sheet names and columns match required structure
3. Select ageing date
4. Click Run
5. Download processed output
""")

with st.expander("🔹 Output Details"):
    st.markdown("""
The output Excel file contains:

1. Ageing Sheet
- Final ageing bucket
- Adjusted bucket
- Provision amount
- Recoverability status

2. Sales Reversal Sheet
- Invoice mapping chain
- Original invoice linkage
- Impacted overdue calculations
""")

with st.expander("🔹 Financial Logic"):

    st.markdown("### 1. Impacted Overdue Days")

    st.latex(
        r"\text{Impacted Overdue Days} = (\text{Selected Date} - \text{Original Invoice Date}) - \text{Payment Terms}"
    )

    st.markdown("""
- Ageing always starts from the original invoice date
- Reissued invoices do not reset ageing
- Payment terms are deducted before bucket classification
""")

    st.markdown("---")

    st.markdown("### 2. Reversal Continuity")

    st.markdown("""
- Invoice chains are tracked through reversal mappings
- Latest invoices inherit original ageing history
- Prevents ageing manipulation through invoice recreation
""")

    st.markdown("---")

    st.markdown("### 3. Bucket Classification")

    st.markdown("""
Buckets:
- Not due
- 8 to 30 days
- 31 to 60 days
- 61 to 90 days
- 91 to 180 days
- 181 to 365 days
- More than 365 days
""")

    st.markdown("---")

    st.markdown("### 4. Provision Logic")

    st.markdown("""
Provision Percentages:
- 61–90 days → 5%
- 91–180 days → 30%
- 181–365 days → 60%
- More than 365 days → 100%
""")

# =========================
# 🔍 HEADER FINDER
# =========================

def find_header_row(file, required_cols, file_type="csv", sheet_name=None):

    try:

        if file_type == "csv":

            preview = pd.read_csv(
                file,
                header=None,
                nrows=10
            )

        else:

            preview = pd.read_excel(
                file,
                sheet_name=sheet_name,
                header=None,
                nrows=10
            )

        for i in range(min(10, len(preview))):

            row_values = preview.iloc[i].astype(str).str.strip().tolist()

            if all(col in row_values for col in required_cols):
                return i

        return None

    except Exception:
        return None


# =========================
# 🚀 PROCESSING
# =========================

if run_clicked:

    log_container = st.container()

    with log_container:

        status_text = st.empty()
        progress_bar = st.progress(0)

        # =========================
        # FILE CHECK
        # =========================

        status_text.info("Checking uploaded files...")

        if uploaded_file1 is None or uploaded_file2 is None or uploaded_file3 is None:
            st.warning("Please upload all required files.")
            st.stop()

        progress_bar.progress(5)
        time.sleep(0.2)

        # =========================
        # READ CSV
        # =========================

        status_text.info("Detecting header row in current month CSV file...")

        required_cols_df1 = [
            "Invoice No",
            "Invoice Date",
            "Payment Terms",
            "Net Outstanding"
        ]

        header_row_df1 = find_header_row(
            uploaded_file1,
            required_cols_df1,
            file_type="csv"
        )

        if header_row_df1 is None:
            st.error("Could not detect header row in CSV file within first 10 rows.")
            st.stop()

        try:

            uploaded_file1.seek(0)

            df1 = pd.read_csv(
                uploaded_file1,
                header=header_row_df1,
                index_col=False
            )

        except Exception as e:
            st.error(f"Error reading current month CSV file: {e}")
            st.stop()

        progress_bar.progress(15)
        time.sleep(0.2)

        # =========================
        # READ EXCEL FILE 2
        # =========================

        status_text.info("Validating required sheets in ageing workbook...")

        try:

            excel_file_2 = pd.ExcelFile(uploaded_file2)

            required_sheets = ["Ageing", "Sales Reversal"]

            missing_sheets = [
                s for s in required_sheets
                if s not in excel_file_2.sheet_names
            ]

            if missing_sheets:
                st.error(f"Missing required sheet(s): {missing_sheets}")
                st.stop()

        except Exception as e:
            st.error(f"Error validating ageing workbook: {e}")
            st.stop()

        progress_bar.progress(20)
        time.sleep(0.2)

        # =========================
        # READ AGEING SHEET
        # =========================

        status_text.info("Detecting header row in Ageing sheet...")

        required_cols_df2 = [
            "Invoice No",
            "Customer Code",
            "Order Location"
        ]

        header_row_df2 = find_header_row(
            uploaded_file2,
            required_cols_df2,
            file_type="excel",
            sheet_name="Ageing"
        )

        if header_row_df2 is None:
            st.error("Could not detect header row in Ageing sheet.")
            st.stop()

        try:

            uploaded_file2.seek(0)

            df2 = pd.read_excel(
                uploaded_file2,
                header=header_row_df2,
                sheet_name="Ageing"
            )

        except Exception as e:
            st.error(f"Error reading Ageing sheet: {e}")
            st.stop()

        progress_bar.progress(30)
        time.sleep(0.2)

        # =========================
        # READ SALES REVERSAL
        # =========================

        status_text.info("Reading Sales Reversal sheet...")

        required_cols_df3 = [
            "OLDInvoice",
            "NEWInvoice",
            "OLD Invoice Date"
        ]

        header_row_df3 = find_header_row(
            uploaded_file2,
            required_cols_df3,
            file_type="excel",
            sheet_name="Sales Reversal"
        )

        if header_row_df3 is None:
            st.error("Could not detect header row in Sales Reversal sheet.")
            st.stop()

        try:

            uploaded_file2.seek(0)

            df3 = pd.read_excel(
                uploaded_file2,
                header=header_row_df3,
                sheet_name="Sales Reversal",
                usecols="A:M"
            )

        except Exception as e:
            st.error(f"Error reading Sales Reversal sheet: {e}")
            st.stop()

        progress_bar.progress(40)
        time.sleep(0.2)

        # =========================
        # READ REVERSAL SYSTEM FILE
        # =========================

        status_text.info("Reading reversal system workbook...")

        required_cols_df4 = [
            "Or inv No",
            "New Inv No"
        ]

        header_row_df4 = find_header_row(
            uploaded_file3,
            required_cols_df4,
            file_type="excel"
        )

        if header_row_df4 is None:
            st.error("Could not detect header row in reversal system file.")
            st.stop()

        try:

            uploaded_file3.seek(0)

            df4 = pd.read_excel(
                uploaded_file3,
                header=header_row_df4
            )

        except Exception as e:
            st.error(f"Error reading reversal system file: {e}")
            st.stop()

        progress_bar.progress(50)
        time.sleep(0.2)

        # =========================
        # COLUMN VALIDATION
        # =========================

        status_text.info("Validating required columns across all files...")

        required_df1_cols = [
            "Location Desc",
            "Cust Code",
            "Customer Name",
            "Invoice No",
            "Doc Amount",
            "Invoice Date",
            "Order Location",
            "O/S DAYS",
            "Total Dr Bal",
            "Total Cr Bal",
            "Net Outstanding",
            "Payment Terms"
        ]

        missing_df1 = [
            c for c in required_df1_cols
            if c not in df1.columns
        ]

        if missing_df1:
            st.error(f"Missing columns in current month CSV: {missing_df1}")
            st.stop()

        progress_bar.progress(55)

        # =========================
        # MAIN PROCESSING
        # =========================

        status_text.info("Initiating ageing and reversal calculations...")

        try:

            df1['Invoice Date'] = pd.to_datetime(
                df1['Invoice Date'],
                format="mixed"
            )

            df1["Invoice No"] = df1["Invoice No"].astype(str).str.strip()

            df1["Order Location"] = df1["Order Location"].astype(str).str.strip()

            df1['Payment Terms'] = (
                df1['Payment Terms']
                .astype(str)
                .str[:-1]
            )

        except Exception as e:
            st.error(f"Error during initial cleaning step: {e}")
            st.stop()

        progress_bar.progress(60)
        time.sleep(0.2)

        status_text.info("Preparing ageing dataset...")

        try:

            df1 = df1[
                ["Location Desc", "Cust Code", "Customer Name", "Invoice No",
                 "Doc Amount", "Invoice Date", "Order Location", "O/S DAYS",
                 "Total Dr Bal", "Total Cr Bal", "Net Outstanding", "Payment Terms"]
            ]

        except Exception as e:
            st.error(f"Error selecting ageing columns: {e}")
            st.stop()

        progress_bar.progress(65)
        time.sleep(0.2)

        status_text.info("Merging recoverability information...")

        try:

            df2["Invoice No"] = df2["Invoice No"].astype(str).str.strip()

            df1 = pd.merge(
                df1,
                df2[[
                    "Order Location",
                    "Customer Code",
                    "Invoice No",
                    "Recoverable/Not Recoverable"
                ]],
                left_on=["Cust Code", "Invoice No", "Order Location"],
                right_on=["Customer Code", "Invoice No", "Order Location"],
                how="left"
            )

            df1["Recoverable/Not Recoverable"] = (
                df1["Recoverable/Not Recoverable"]
                .fillna("Recoverable")
            )

        except Exception as e:
            st.error(f"Error during recoverability merge: {e}")
            st.stop()

        progress_bar.progress(72)
        time.sleep(0.2)

        status_text.info("Processing reversal chain mappings...")

        try:

            df4 = df4[
                ["Client", "Name", "Or inv No", "Or inv Dt", "Inv Amt",
                 "Cr inv No", "New Inv No", "New Dt", "New amt"]
            ]

            df3 = df3.drop(
                columns=["Month", "Impacted Overdue Days", "Ageing Bucket"],
                errors="ignore"
            )

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

        except Exception as e:
            st.error(f"Error during reversal processing: {e}")
            st.stop()

        progress_bar.progress(80)
        time.sleep(0.2)

        status_text.info("Building invoice ageing graph...")

        try:

            df3['OLD Invoice Date'] = pd.to_datetime(
                df3['OLD Invoice Date'],
                errors="coerce"
            )

            G = nx.DiGraph()

            G.add_edges_from(
                zip(df3['OLDInvoice'], df3['NEWInvoice'])
            )

            roots = [
                n for n, d in G.in_degree()
                if d == 0 or (d == 1 and G.has_edge(n, n))
            ]

            root_map = {}

            for r in roots:

                root_map[r] = r

                for d in nx.descendants(G, r):
                    root_map[d] = r

            invoice_to_date = dict(
                zip(df3['OLDInvoice'], df3['OLD Invoice Date'])
            )

        except Exception as e:
            st.error(f"Error during graph processing: {e}")
            st.stop()

        progress_bar.progress(85)
        time.sleep(0.2)

        status_text.info("Calculating ageing buckets and provisions...")

        try:

            df3['Impacted Overdue Days'] = (
                curr_date
                - df3['OLDInvoice']
                .map(root_map)
                .fillna(df3['OLDInvoice'])
                .map(invoice_to_date)
            ).dt.days

            df3['Payment Term'] = pd.to_numeric(
                df3['Payment Term'],
                errors="coerce"
            ).fillna(0)

            df3['Impacted Overdue Days'] -= df3['Payment Term']

            def Duecheck(d):
                if d <= 7:
                    return "Not due"
                if d <= 30:
                    return "8 to 30 days"
                if d <= 60:
                    return "31 to 60 days"
                if d <= 90:
                    return "61 to 90 days"
                if d <= 180:
                    return "91 to 180 days"
                if d <= 365:
                    return "181 to 365 days"
                return "more than 365 days"

            df3["Ageing Bucket"] = (
                df3["Impacted Overdue Days"]
                .apply(Duecheck)
            )

            sales_reversal = df3.copy()

            df1['Invoice Date'] = pd.to_datetime(
                df1['Invoice Date'],
                errors="coerce"
            )

            df1['Payment Terms'] = pd.to_numeric(
                df1['Payment Terms'],
                errors="coerce"
            ).fillna(0)

            df1['Impacted Overdue Days'] = (
                (curr_date - df1['Invoice Date']).dt.days
                - df1['Payment Terms']
            )

            df1["Bucket"] = (
                df1["Impacted Overdue Days"]
                .apply(Duecheck)
            )

            df1["Bucket"] = np.where(
                df1["Net Outstanding"] < 0,
                "Not due",
                df1["Bucket"]
            )

            df1 = pd.merge(
                df1,
                df3[["NEWInvoice", "Ageing Bucket"]],
                left_on="Invoice No",
                right_on="NEWInvoice",
                how="left"
            )

            df1 = (
                df1.rename(columns={"Ageing Bucket": "Adjusted Bucket"})
                .drop(columns="NEWInvoice")
            )

            df1["Adjusted Bucket"] = (
                df1["Adjusted Bucket"]
                .fillna(df1["Bucket"])
            )

            df1["Adjusted Bucket"] = np.where(
                df1["Net Outstanding"] < 0,
                "Not due",
                df1["Adjusted Bucket"]
            )

            def provcheck(b):

                b = str(b).lower().strip()

                if b == "61 to 90 days":
                    return 5

                if b == "91 to 180 days":
                    return 30

                if b == "181 to 365 days":
                    return 60

                if b == "more than 365 days":
                    return 100

                return 0

            df1["Provision"] = (
                (
                    df1["Adjusted Bucket"]
                    .apply(provcheck)
                ) / 100
            ) * df1["Net Outstanding"]

        except Exception as e:
            st.error(f"Error during ageing calculations: {e}")
            st.stop()

        progress_bar.progress(95)
        time.sleep(0.2)

        status_text.info("Generating final Excel output...")

        try:

            output = BytesIO()

            with pd.ExcelWriter(
                output,
                engine="openpyxl"
            ) as writer:

                df1.to_excel(
                    writer,
                    sheet_name="Ageing",
                    index=False
                )

                sales_reversal.to_excel(
                    writer,
                    sheet_name="Sales Reversal",
                    index=False
                )

        except Exception as e:
            st.error(f"Error while generating output file: {e}")
            st.stop()

        progress_bar.progress(100)
        time.sleep(0.2)

        status_text.success("Processing completed successfully!")

        st.download_button(
            label="📥 Download Output",
            data=output.getvalue(),
            file_name="System_Ageing_Output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
