import sqlite3
import os

def explore_database(db_path):
    """Explore all tables and data in a SQLite database."""
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"✅ Connected to: {db_path}")
    print("=" * 60)
    
    # 1. Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cursor.fetchall()
    
    if not tables:
        print("⚠️  No tables found in the database.")
        conn.close()
        return
    
    print(f"📋 Found {len(tables)} table(s): {[t[0] for t in tables]}\n")
    
    for (table_name,) in tables:
        print(f"🗂️  TABLE: {table_name}")
        print("-" * 60)
        
        # 2. Get column info
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        print("Columns:")
        for col in columns:
            col_id, name, dtype, not_null, default, is_pk = col
            pk_label = " [PRIMARY KEY]" if is_pk else ""
            nn_label = " NOT NULL" if not_null else ""
            print(f"  - {name} ({dtype}){pk_label}{nn_label}")
        
        # 3. Row count
        cursor.execute(f"SELECT COUNT(*) FROM '{table_name}';")
        row_count = cursor.fetchone()[0]
        print(f"\nTotal rows: {row_count}")
        
        # 4. Show sample data (first 5 rows)
        if row_count > 0:
            cursor.execute(f"SELECT * FROM '{table_name}' LIMIT 5;")
            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            
            print(f"\nSample data (up to 5 rows):")
            print("  " + " | ".join(col_names))
            print("  " + "-" * 50)
            for row in rows:
                print("  " + " | ".join(str(v) for v in row))
        
        print()
    
    # 5. Database file size
    size_kb = os.path.getsize(db_path) / 1024
    print(f"💾 Database size: {size_kb:.2f} KB")
    
    conn.close()
    print("\n✅ Done!")

# ▶️ Change this to your actual database file path
explore_database("database/scheduler.db")
