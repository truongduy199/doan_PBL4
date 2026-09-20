"""Script khởi tạo cơ sở dữ liệu SQLite và chạy migrations."""
import sqlite3
import os

def init_db(db_path="var/db/parking.sqlite3"):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    for sql_file in sorted(os.listdir("migrations")):
        if sql_file.endswith(".sql"):
            with open(os.path.join("migrations", sql_file), "r", encoding="utf-8") as f:
                conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()