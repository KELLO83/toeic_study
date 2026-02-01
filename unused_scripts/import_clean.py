import pandas as pd
import psycopg2
import sys

# Configuration
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "toeic"
DB_USER = "postgres"
DB_PASS = "1234"
EXCEL_FILE = "영단어.xlsx"

# Typo corrections (Wrong -> Right)
CORRECTIONS = {
    "보괂나다": "보관하다",
    "베타적": "배타적",
    "구상하다": "구성하다",
    "점사": "잠시",  # Assuming brief context
}

def clean_text(text):
    if pd.isna(text):
        return None
    text = str(text).strip()
    # Apply corrections
    for wrong, right in CORRECTIONS.items():
        if wrong in text:
            text = text.replace(wrong, right)
    return text

def import_clean_data():
    try:
        print(f"Connecting to database {DB_NAME}...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cur = conn.cursor()
        
        # Clear existing data to avoid double-stacking if run multiple times
        # Uncomment the next line if you want to wipe the table before import
        # cur.execute("TRUNCATE TABLE toeic_word RESTART IDENTITY;")
        # print("Cleared existing data.")

        seen_words = set()
        
        # Helper to process dataframe
        def process_sheet(sheet_name):
            try:
                df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name)
                count = 0
                dup_count = 0
                for _, row in df.iterrows():
                    word = clean_text(row.iloc[0])
                    meaning = clean_text(row.iloc[1]) if len(row) > 1 else None
                    
                    if not word:
                        continue
                        
                    # Deduplication logic (Case insensitive check)
                    word_lower = word.lower()
                    if word_lower in seen_words:
                        dup_count += 1
                        continue
                    
                    seen_words.add(word_lower)
                    
                    cur.execute(
                        "INSERT INTO toeic_word (word, meaning, sheet_name) VALUES (%s, %s, %s)",
                        (word, meaning, sheet_name)
                    )
                    count += 1
                return count, dup_count
            except Exception as e:
                print(f"Error reading {sheet_name}: {e}")
                return 0, 0

        # Process Sheets
        s1_ok, s1_dup = process_sheet('Sheet1')
        s2_ok, s2_dup = process_sheet('Sheet2')

        conn.commit()
        cur.close()
        conn.close()
        
        print("\n=== Import Summary ===")
        print(f"Sheet1: Inserted {s1_ok} / Skipped {s1_dup} duplicates")
        print(f"Sheet2: Inserted {s2_ok} / Skipped {s2_dup} duplicates")
        print(f"Total Inserted: {s1_ok + s2_ok}")
        print("Typo corrections applied automatically.")

    except Exception as e:
        print(f"Database Error: {e}")

if __name__ == "__main__":
    import_clean_data()
