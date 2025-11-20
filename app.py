import tabula
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import os
import json
from datetime import datetime
import traceback

# PDF info
PDF_URL = "https://fimex.ae/downloads/providers/pdf/invoice/DA33MA19"
PDF_FILE = "invoice.pdf"

def update_sheet():
    print("=" * 50)
    print("Fetching latest data...")

    try:
        # Step 1 — Download PDF
        pdf = requests.get(PDF_URL, timeout=20)
        if pdf.status_code != 200:
            raise Exception(f"Failed to fetch PDF (status code {pdf.status_code})")

        with open(PDF_FILE, "wb") as f:
            f.write(pdf.content)

        print("✅ PDF downloaded successfully.")

        # Step 2 — Extract table using Tabula
        print("Extracting tables from PDF...")
        tables = tabula.read_pdf(
            PDF_FILE,
            pages='all',
            multiple_tables=True,
            java_options='-Djava.awt.headless=true'
        )

        if not tables or len(tables) == 0:
            raise Exception("No tables found in PDF")

        df = tables[0]
        print(f"✅ Extracted table with {len(df)} rows and {len(df.columns)} columns.")
        print(df.head())

        # --------------------------
        # ⭐ FIX "No Code" merged column
        # --------------------------
        first_col = df.columns[0].lower().replace(" ", "")

        if first_col == "nocode":  
            print("Fixing merged 'No Code' column...")

            # Split the first column into 2 using modern Pandas syntax
            split_df = df.iloc[:, 0].str.split(" ", n=1, expand=True)

            df["No"] = split_df[0]
            df["Code"] = split_df[1]

            df = df.drop(df.columns[0], axis=1)

            # Move new columns to the beginning
            cols = ["No", "Code"] + [c for c in df.columns if c not in ["No", "Code"]]
            df = df[cols]

            print("✅ Successfully split 'No Code' → [No] + [Code]")

        # Step 3 — Connect to Google Sheets
        print("Connecting to Google Sheets...")

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        credentials_info = os.environ.get("GOOGLE_CREDENTIALS")
        if not credentials_info:
            raise Exception("GOOGLE_CREDENTIALS secret not found!")

        creds_dict = json.loads(credentials_info)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        sheet = client.open("Sheet1")
        try:
            worksheet = sheet.worksheet("Sheet1")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title="Sheet1", rows="100", cols="20")

        # Step 4 — Clean + Upload Data
        df = df.replace([float('inf'), float('-inf')], pd.NA)
        df = df.fillna("")
        df = df.astype(str)

        print("Data cleaned and ready to upload.")

        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        print("✅ Sheet updated successfully.")

        # Step 5 — Logging
        try:
            log_sheet = sheet.worksheet("Logs")
        except gspread.exceptions.WorksheetNotFound:
            log_sheet = sheet.add_worksheet(title="Logs", rows="100", cols="3")
            log_sheet.append_row(["Timestamp", "Status", "Rows Updated"])

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_sheet.append_row([timestamp, "Success ✅", str(len(df))])

    except Exception as e:
        print("❌ Error:", e)
        traceback.print_exc()

        try:
            sheet = client.open("Sheet1")
            log_sheet = sheet.worksheet("Logs")
            log_sheet.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                f"Error: {str(e)}",
                "0"
            ])
        except:
            pass



if __name__ == "__main__":
    update_sheet()
