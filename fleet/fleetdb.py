import sqlite3

# Connect to SQLite (creates file if it doesn't exist)
conn = sqlite3.connect("mydatabase.db")
cursor = conn.cursor()

# 1️⃣ Create table (if not exists)
cursor.execute("""
CREATE TABLE IF NOT EXISTS single_id (
    id INTEGER PRIMARY KEY
)
""")
conn.commit()

# 2️⃣ Insert or replace a single ID
def set_id(new_id):
    cursor.execute("REPLACE INTO single_id (id) VALUES (?)", (new_id,))
    conn.commit()
    print(f"ID set to {new_id}")

# 3️⃣ Update ID (if row exists)
def update_id(new_id):
    cursor.execute("UPDATE single_id SET id = ?", (new_id,))
    conn.commit()
    print(f"ID updated to {new_id}")

# 4️⃣ Retrieve ID
def get_id():
    cursor.execute("SELECT id FROM single_id")
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        return None

# Example usage
# print(get_id())            # Insert or replace
# print("Current ID:", get_id())

# update_id(456)         # Update
# print("Updated ID:", get_id())

# Close connection
def close_db(conn):
    conn.close()
    
print(get_id())
# set_id(1)