"""
Quick test script to verify MySQL connection
"""

from config import DATABASE_CONFIG
from database import Database

print("Testing MySQL Connection...")
print(f"Host: {DATABASE_CONFIG['host']}")
print(f"Database: {DATABASE_CONFIG['database']}")
print(f"User: {DATABASE_CONFIG['user']}")
print()

try:
    Database.initialize_pool()
    print("[OK] Connection pool initialized")
    
    Database.create_tables()
    print("[OK] Tables created/verified")
    
    if Database.test_connection():
        print("[OK] Connection test successful!")
        print("\nDatabase is ready to use!")
    else:
        print("[ERROR] Connection test failed")
except Exception as e:
    print(f"[ERROR] Error: {e}")
    print("\nPlease check:")
    print("1. MySQL server is running")
    print("2. Database 'attendance' exists")
    print("3. Credentials in config.py are correct")

