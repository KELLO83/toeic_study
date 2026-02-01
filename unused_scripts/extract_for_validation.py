import pandas as pd
import json
import sys

file_path = 'c:/toeic_whisper/영단어.xlsx'
output_path = 'c:/toeic_whisper/extracted_data.json'

try:
    data = {}
    
    # Read Sheet1
    df1 = pd.read_excel(file_path, sheet_name='Sheet1')
    data['Sheet1'] = df1.to_dict(orient='records')
    
    # Read Sheet2
    try:
        df2 = pd.read_excel(file_path, sheet_name='Sheet2')
        data['Sheet2'] = df2.to_dict(orient='records')
    except Exception as e:
        data['Sheet2_Error'] = str(e)
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("DONE")
    
except Exception as e:
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({"error": str(e)}, f, ensure_ascii=False)
    print("ERROR")
