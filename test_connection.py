"""Quick test: database pool + tables (SQLite, MySQL, or PostgreSQL)."""

from config import DATABASE_CONFIG
from database import Database, DB_TYPE

print(f"Testing database ({DB_TYPE})...")
if DB_TYPE == "sqlite":
    print(f"SQLite file: {DATABASE_CONFIG.get('sqlite_path', 'attendance.db')}")
else:
    print(f"Host: {DATABASE_CONFIG['host']}")
    print(f"Database: {DATABASE_CONFIG['database']}")
    print(f"User: {DATABASE_CONFIG['user']}")
print()

try:
    Database.initialize_pool()
    print("[OK] Connection initialized")

    Database.create_tables()
    print("[OK] Tables created/verified")

    if Database.test_connection():
        print("[OK] Connection test successful")
        print("\nDatabase is ready to use.")
    else:
        print("[ERROR] Connection test failed")
except Exception as e:
    print(f"[ERROR] {e}")
    if DB_TYPE != "sqlite":
        print("\nCheck: server running, database exists, credentials / env vars.")
