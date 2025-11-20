import tabula
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import schedule
import time
import requests
import os
from datetime import datetime
import traceback

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

        # Step 3 — Connect to Google Sheets
        print("Connecting to Google Sheets...")
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)

        sheet = client.open("Sheet1")       # Google Sheet FILE name
        worksheet = sheet.worksheet("Sheet1")  # TAB inside the sheet

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
        except:
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


# Run every 1 minute
schedule.every(1).minutes.do(update_sheet)

print("⏳ Automation started... Updates every 1 minute.")

update_sheet()  # first run

update_sheet()
