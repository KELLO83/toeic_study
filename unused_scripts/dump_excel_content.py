import pandas as pd
import sys

# Configuration
EXCEL_FILE = "영단어.xlsx"
OUTPUT_FILE = "content_dump.txt"

def dump_data():
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            # Sheet 1
            try:
                df1 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet1')
                f.write(f"=== SHEET1 ({len(df1)} rows) ===\n")
                for i, row in df1.iterrows():
                    word = str(row.iloc[0]).strip()
                    meaning = str(row.iloc[1]).strip() if len(row) > 1 else ""
                    f.write(f"{i+2}|{word}|{meaning}\n")
            except Exception as e:
                f.write(f"Sheet1 Error: {e}\n")

            f.write("\n")

            # Sheet 2
            try:
                df2 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet2')
                f.write(f"=== SHEET2 ({len(df2)} rows) ===\n")
                for i, row in df2.iterrows():
                    word = str(row.iloc[0]).strip()
                    meaning = str(row.iloc[1]).strip() if len(row) > 1 else ""
                    f.write(f"{i+2}|{word}|{meaning}\n")
            except Exception as e:
                f.write(f"Sheet2 Error: {e}\n")
        
        print(f"Successfully wrote content to {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump_data()
