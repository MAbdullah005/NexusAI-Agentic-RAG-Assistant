import sys
import json
import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../database/chatbot_conv.db"))

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "action and sql required"}))
        sys.exit(1)

    action = sys.argv[1] # "query" or "run"
    sql = sys.argv[2]
    params = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute(sql, params)
        if action == "query":
            rows = cursor.fetchall()
            col_names = [d[0] for d in cursor.description] if cursor.description else []
            res = [dict(zip(col_names, r)) for r in rows]
            print(json.dumps(res))
        else:
            conn.commit()
            print(json.dumps({"status": "ok", "lastrowid": cursor.lastrowid, "rowcount": cursor.rowcount}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()

