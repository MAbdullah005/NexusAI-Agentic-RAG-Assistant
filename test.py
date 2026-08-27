import sqlite3
import os
DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "chatbot_conv.db")

os.makedirs(DB_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor=conn.cursor()
data=cursor.execute("""
ALTER TABLE documents ADD COLUMN filename TEXT DEFAULT NULL;
""")

for d in data:
    print(d)

conn.commit()

conn.close()