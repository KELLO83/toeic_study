import pandas as pd
import sys
import traceback

# Configuration
EXCEL_FILE = "영단어.xlsx"
OUTPUT_FILE = "validation_output.txt"

def check_data():
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Checking {EXCEL_FILE}...\n")
        try:
            # Sheet 1
            df1 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet1')
            f.write(f"\n[Sheet1 Analysis]\n")
            f.write(f"Total Rows: {len(df1)}\n")
            
            missing_word = df1.iloc[:, 0].isnull().sum()
            missing_meaning = df1.iloc[:, 1].isnull().sum()
            if missing_word > 0:
                f.write(f"WARNING: Found {missing_word} rows with missing WORD in Sheet1.\n")
            if missing_meaning > 0:
                f.write(f"WARNING: Found {missing_meaning} rows with missing MEANING in Sheet1.\n")
                
            for i, row in df1.iterrows():
                word = row.iloc[0]
                if not isinstance(word, str) and not pd.isna(word):
                     f.write(f" - Row {i+2}: Word '{word}' is not a text/string.\n")

            # Sheet 2
            try:
                df2 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet2')
                f.write(f"\n[Sheet2 Analysis]\n")
                f.write(f"Total Rows: {len(df2)}\n")
                
                missing_word2 = df2.iloc[:, 0].isnull().sum()
                missing_meaning2 = df2.iloc[:, 1].isnull().sum()
                if missing_word2 > 0:
                    f.write(f"WARNING: Found {missing_word2} rows with missing WORD in Sheet2.\n")
                if missing_meaning2 > 0:
                    f.write(f"WARNING: Found {missing_meaning2} rows with missing MEANING in Sheet2.\n")

            except Exception as e:
                f.write(f"Sheet2 Error: {e}\n")

            f.write("\n[Validation Complete] If no warnings above, data looks good.\n")

        except Exception as e:
            f.write(f"Error reading file: {e}\n")
            f.write(traceback.format_exc())

if __name__ == "__main__":
    check_data()
