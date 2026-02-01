import pandas as pd
import sys

try:
    with open('result.txt', 'w', encoding='utf-8') as f:
        df1 = pd.read_excel('c:/toeic_whisper/영단어.xlsx', sheet_name='Sheet1')
        f.write(f"SHEET1_COLUMNS: {df1.columns.tolist()}\n")
        f.write(f"SHEET1_COUNT: {len(df1)}\n")
        
        try:
            df2 = pd.read_excel('c:/toeic_whisper/영단어.xlsx', sheet_name='Sheet2')
            f.write(f"SHEET2_COLUMNS: {df2.columns.tolist()}\n")
            f.write(f"SHEET2_COUNT: {len(df2)}\n")
        except Exception as e:
             f.write(f"SHEET2_ERROR: {e}\n")
             
except Exception as e:
    with open('result.txt', 'w', encoding='utf-8') as f:
        f.write(f"ERROR: {e}\n")
