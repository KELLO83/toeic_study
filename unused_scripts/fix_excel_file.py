import pandas as pd
import shutil
import os

# Configuration
EXCEL_FILE = "영단어.xlsx"
BACKUP_FILE = "영단어_backup.xlsx"

# Typo corrections (Wrong -> Right)
CORRECTIONS = {
    "보괂나다": "보관하다",
    "베타적": "배타적",
    "구상하다": "구성하다",
    "점사": "잠시",
}

def fix_excel():
    if not os.path.exists(EXCEL_FILE):
        print(f"Error: {EXCEL_FILE} not found.")
        return

    print(f"Creating backup: {BACKUP_FILE}...")
    shutil.copy2(EXCEL_FILE, BACKUP_FILE)

    try:
        print("Applying corrections...")
        # Dictionary to hold dataframes
        sheets = {}
        
        # Load all sheets
        xls = pd.ExcelFile(EXCEL_FILE)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            # Apply corrections
            for col in df.columns:
                # Check column headers just in case (optional)
                
                # Check content
                df[col] = df[col].apply(lambda x: x if pd.isna(x) else str(x))
                for wrong, right in CORRECTIONS.items():
                   # Apply to all columns that are strings
                   df[col] = df[col].apply(lambda x: x.replace(wrong, right) if isinstance(x, str) and wrong in x else x)
            
            sheets[sheet_name] = df

        # Write back
        print(f"Saving changes to {EXCEL_FILE}...")
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print("Done! Original file has been updated.")
        
    except Exception as e:
        print(f"Error updating Excel: {e}")
        print("Restoring backup...")
        shutil.copy2(BACKUP_FILE, EXCEL_FILE)

if __name__ == "__main__":
    fix_excel()
