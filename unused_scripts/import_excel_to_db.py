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

def clean_text(text):
    if pd.isna(text):
        return None
    return str(text).strip()

def import_data():
    try:
        print(f"Connecting to database {DB_NAME} at {DB_HOST}...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cur = conn.cursor()
        print("Connected successfully.")

        # Sheet 1
        print(f"Reading {EXCEL_FILE} - Sheet1...")
        try:
            df1 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet1')
            count = 0
            for _, row in df1.iterrows():
                # Assuming 1st column is Word, 2nd is Meaning. Adjust if needed.
                word = clean_text(row.iloc[0])
                meaning = clean_text(row.iloc[1]) if len(row) > 1 else None
                
                if word:
                    cur.execute(
                        "INSERT INTO toeic_word (word, meaning, sheet_name) VALUES (%s, %s, %s)",
                        (word, meaning, 'Sheet1')
                    )
                    count += 1
            print(f"Inserted {count} rows from Sheet1.")
        except Exception as e:
            print(f"Error processing Sheet1: {e}")

        # Sheet 2
        print(f"Reading {EXCEL_FILE} - Sheet2...")
        try:
            df2 = pd.read_excel(EXCEL_FILE, sheet_name='Sheet2')
            count = 0
            for _, row in df2.iterrows():
                word = clean_text(row.iloc[0])
                meaning = clean_text(row.iloc[1]) if len(row) > 1 else None
                
                if word:
                    cur.execute(
                        "INSERT INTO toeic_word (word, meaning, sheet_name) VALUES (%s, %s, %s)",
                        (word, meaning, 'Sheet2')
                    )
                    count += 1
            print(f"Inserted {count} rows from Sheet2.")
        except Exception as e:
            print(f"Error processing Sheet2: {e}")

        conn.commit()
        cur.close()
        conn.close()
        print("Import completed independently.")

    except ImportError:
        print("Error: Missing libraries. Please run: pip install pandas openpyxl psycopg2-binary")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    import_data()
