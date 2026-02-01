import pandas as pd
import sys
import os

def clean_text(text):
    if pd.isna(text):
        return ""
    return str(text).replace("'", "''").strip()

try:
    sql_lines = []
    sql_lines.append("CREATE TABLE IF NOT EXISTS toeic_word (id SERIAL PRIMARY KEY, word TEXT, meaning TEXT, sheet_name TEXT);")
    
    # Sheet 1
    try:
        df1 = pd.read_excel('c:/toeic_whisper/영단어.xlsx', sheet_name='Sheet1', header=None)
        # Assuming row 0 is header, so skip it if it looks like header, or just use slice
        # Let's inspect first row. If it contains "Word" or "단어", skip.
        start_row = 0
        if isinstance(df1.iloc[0,0], str) and ("word" in df1.iloc[0,0].lower() or "단어" in df1.iloc[0,0]):
             start_row = 1
             
        for index, row in df1.iloc[start_row:].iterrows():
            word = clean_text(row[0])
            meaning = clean_text(row[1])
            if word:
                sql_lines.append(f"INSERT INTO toeic_word (word, meaning, sheet_name) VALUES ('{word}', '{meaning}', 'Sheet1');")
    except Exception as e:
        sql_lines.append(f"-- Error reading Sheet1: {e}")

    # Sheet 2
    try:
        df2 = pd.read_excel('c:/toeic_whisper/영단어.xlsx', sheet_name='Sheet2', header=None)
        start_row = 0
        if isinstance(df2.iloc[0,0], str) and ("word" in df2.iloc[0,0].lower() or "단어" in df2.iloc[0,0]):
             start_row = 1
             
        for index, row in df2.iloc[start_row:].iterrows():
            word = clean_text(row[0])
            meaning = clean_text(row[1])
            if word:
                sql_lines.append(f"INSERT INTO toeic_word (word, meaning, sheet_name) VALUES ('{word}', '{meaning}', 'Sheet2');")
    except Exception as e:
        sql_lines.append(f"-- Error reading Sheet2: {e}")

    with open('c:/toeic_whisper/import.sql', 'w', encoding='utf-8') as f:
        f.write('\n'.join(sql_lines))
        
except Exception as e:
    with open('c:/toeic_whisper/error.txt', 'w', encoding='utf-8') as f:
        f.write(str(e))
