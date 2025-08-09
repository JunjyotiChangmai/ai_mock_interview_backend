import sqlite3

DB_Name= "app/includes/site.db"

def init_db():
    conn = sqlite3.connect(DB_Name)
    cs = conn.cursor()
    cs.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        question TEXT NOT NULL,
        answer TEXT
        )
    """)
    # Ensure session_id column exists for legacy DBs
    cs.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cs.fetchall()]
    if "session_id" not in columns:
        cs.execute("ALTER TABLE users ADD COLUMN session_id TEXT")
    conn.commit()
    conn.close()

def ins_inp(qs: str, ans: str, session_id: str | None = None):
    conn=sqlite3.connect(DB_Name)
    cursor=conn.cursor()
    cursor.execute("INSERT INTO users (session_id, question, answer) VALUES (?,?,?)",(session_id, qs, ans))
    conn.commit()
    conn.close()

# only for testing database
def view():
    conn = sqlite3.connect(DB_Name)
    cursor = conn.cursor()
    cursor.execute("SELECT id, session_id, question, answer FROM users")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"id": row[0], "session_id": row[1], "ques": row[2], "ans": row[3]}
        for row in rows
    ]