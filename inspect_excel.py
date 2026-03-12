import pandas as pd

df = pd.read_excel('토익영단어_최종8.xlsx')
with open('columns.txt', 'w', encoding='utf-8') as f:
    for i, col in enumerate(df.columns):
        f.write(f"{i}: {col}\n")
    f.write("\nFIRST ROW:\n")
    f.write(str(df.iloc[0].to_dict() if len(df) > 0 else "Empty Dataframe"))

