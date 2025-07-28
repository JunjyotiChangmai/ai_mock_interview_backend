import sqlite3

DB_Name= "app/includes/site.db"

def init_db():
    conn = sqlite3.connect(DB_Name)
    cs = conn.cursor()
    cs.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT                          
        )
    """)
    conn.commit()
    conn.close()

def ins_inp(qs:str,ans:str):
    conn=sqlite3.connect(DB_Name)
    cursor=conn.cursor()
    cursor.execute("INSERT INTO users (question,answer) VALUES (?,?)",(qs,ans))
    conn.commit()
    conn.close()

# only for testing database
def view():
    conn = sqlite3.connect(DB_Name)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"id":row[0],"ques": row[1], "ans": row[2]}
        for row in rows
    ]