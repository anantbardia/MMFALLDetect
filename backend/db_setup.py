import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "falldetection.db")
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "db_schema.sql")

def setup_database():
    print(f"Setting up SQLite database at {DB_FILE}...")
    
    # Connect to the database (creates it if it doesn't exist)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Read the schema file
    with open(SCHEMA_FILE, "r") as f:
        schema = f.read()
    
    # Execute the schema script
    try:
        cursor.executescript(schema)
        conn.commit()
        print("Database setup complete!")
    except Exception as e:
        print(f"Error setting up database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()
