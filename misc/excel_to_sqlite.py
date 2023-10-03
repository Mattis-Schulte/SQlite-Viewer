import pandas as pd
import sqlite3


xlsx = pd.read_excel('w3schools_org_db.xlsx', sheet_name=None)
conn = sqlite3.connect('w3schools_org_db.db3')

for sheet_name, df in xlsx.items():
    df.to_sql(sheet_name, conn, if_exists='replace', index=False)

conn.close()
