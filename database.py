"""
Database Module - Supports both MySQL and PostgreSQL
Currently configured for MySQL for local testing
"""

import logging
from contextlib import contextmanager
from config import DATABASE_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import appropriate database connector
if DATABASE_CONFIG.get('db_type', 'mysql') == 'mysql':
    import mysql.connector
    from mysql.connector import pooling
    DB_TYPE = 'mysql'
else:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    DB_TYPE = 'postgresql'

class Database:
    """Database connection and operations - supports MySQL and PostgreSQL"""
    
    _connection_pool = None
    
    @classmethod
    def initialize_pool(cls):
        """Initialize connection pool"""
        try:
            if DB_TYPE == 'mysql':
                cls._connection_pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="attendance_pool",
                    pool_size=DATABASE_CONFIG['pool_size'],
                    host=DATABASE_CONFIG['host'],
                    port=DATABASE_CONFIG['port'],
                    user=DATABASE_CONFIG['user'],
                    password=DATABASE_CONFIG['password'],
                    database=DATABASE_CONFIG['database'],
                    connection_timeout=DATABASE_CONFIG['connection_timeout'],
                    autocommit=False
                )
            else:
                cls._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    1,
                    DATABASE_CONFIG['pool_size'],
                    host=DATABASE_CONFIG['host'],
                    port=DATABASE_CONFIG['port'],
                    user=DATABASE_CONFIG['user'],
                    password=DATABASE_CONFIG['password'],
                    database=DATABASE_CONFIG['database'],
                    connect_timeout=DATABASE_CONFIG['connection_timeout']
                )
            logger.info(f"Database connection pool initialized ({DB_TYPE})")
        except Exception as e:
            logger.error(f"Error initializing connection pool: {e}")
            raise
    
    @classmethod
    @contextmanager
    def get_connection(cls):
        """Get database connection from pool"""
        conn = None
        try:
            if DB_TYPE == 'mysql':
                conn = cls._connection_pool.get_connection()
            else:
                conn = cls._connection_pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                if DB_TYPE == 'mysql':
                    conn.close()
                else:
                    cls._connection_pool.putconn(conn)
    
    @classmethod
    def create_tables(cls):
        """Create required database tables"""
        if DB_TYPE == 'mysql':
            create_vendor_table = """
            CREATE TABLE IF NOT EXISTS vendor_details (
                vendor_id INT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                department VARCHAR(100),
                purpose VARCHAR(255),
                visited_by VARCHAR(255),
                visit_type VARCHAR(50),
                dob VARCHAR(20),
                gender VARCHAR(10),
                number VARCHAR(20),
                vendor_company VARCHAR(255),
                address TEXT,
                photo VARCHAR(10) DEFAULT 'NO',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            
            create_attendance_table = """
            CREATE TABLE IF NOT EXISTS attendance_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                name VARCHAR(255) NOT NULL,
                department VARCHAR(100),
                address TEXT,
                date VARCHAR(20) NOT NULL,
                start_time VARCHAR(20) NOT NULL,
                end_time VARCHAR(20) NULL,
                time VARCHAR(20) NULL,
                status VARCHAR(20) DEFAULT 'Present',
                synced_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES vendor_details(vendor_id),
                UNIQUE KEY uq_attendance_user_date (user_id, date),
                INDEX idx_attendance_date (date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        else:
            create_vendor_table = """
            CREATE TABLE IF NOT EXISTS vendor_details (
                vendor_id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                department VARCHAR(100),
                purpose VARCHAR(255),
                visited_by VARCHAR(255),
                visit_type VARCHAR(50),
                dob VARCHAR(20),
                gender VARCHAR(10),
                number VARCHAR(20),
                vendor_company VARCHAR(255),
                address TEXT,
                photo VARCHAR(10) DEFAULT 'NO',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            create_attendance_table = """
            CREATE TABLE IF NOT EXISTS attendance_records (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                department VARCHAR(100),
                address TEXT,
                date VARCHAR(20) NOT NULL,
                start_time VARCHAR(20) NOT NULL,
                end_time VARCHAR(20) NULL,
                time VARCHAR(20) NULL,
                status VARCHAR(20) DEFAULT 'Present',
                synced_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES vendor_details(vendor_id),
                CONSTRAINT uq_attendance_user_date UNIQUE (user_id, date)
            );
            """
            
            create_indexes = """
            CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance_records(user_id, date);
            CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_records(date);
            CREATE INDEX IF NOT EXISTS idx_vendor_id ON vendor_details(vendor_id);
            """
        
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(create_vendor_table)
                cursor.execute(create_attendance_table)
                if DB_TYPE == 'postgresql':
                    cursor.execute(create_indexes)
                logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
        cls.ensure_attendance_clock_schema()
    
    @classmethod
    def ensure_attendance_clock_schema(cls):
        """Migrate legacy attendance_records rows to start_time / end_time (clock in / out)."""
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                if DB_TYPE == 'mysql':
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'attendance_records'
                          AND COLUMN_NAME = 'start_time'
                        """
                    )
                    has_start = cursor.fetchone()[0] > 0
                    if not has_start:
                        cursor.execute(
                            "ALTER TABLE attendance_records "
                            "ADD COLUMN start_time VARCHAR(20) NULL AFTER date"
                        )
                        cursor.execute(
                            "ALTER TABLE attendance_records "
                            "ADD COLUMN end_time VARCHAR(20) NULL"
                        )
                        cursor.execute(
                            "UPDATE attendance_records SET start_time = time "
                            "WHERE start_time IS NULL AND time IS NOT NULL"
                        )
                        cursor.execute(
                            "ALTER TABLE attendance_records MODIFY time VARCHAR(20) NULL"
                        )
                    try:
                        cursor.execute(
                            "ALTER TABLE attendance_records "
                            "ADD UNIQUE KEY uq_attendance_user_date (user_id, date)"
                        )
                    except Exception as ex:
                        logger.warning(
                            "Could not add unique key uq_attendance_user_date (may already exist or duplicate rows): %s",
                            ex,
                        )
                else:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_name = 'attendance_records' AND column_name = 'start_time'
                        """
                    )
                    has_start = cursor.fetchone()[0] > 0
                    if not has_start:
                        cursor.execute(
                            "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS start_time VARCHAR(20)"
                        )
                        cursor.execute(
                            "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS end_time VARCHAR(20)"
                        )
                        cursor.execute(
                            "UPDATE attendance_records SET start_time = time "
                            "WHERE start_time IS NULL AND time IS NOT NULL"
                        )
                        try:
                            cursor.execute(
                                "ALTER TABLE attendance_records ALTER COLUMN time DROP NOT NULL"
                            )
                        except Exception as ex:
                            logger.debug("time column already nullable or absent: %s", ex)
                    try:
                        cursor.execute(
                            "CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_user_date "
                            "ON attendance_records (user_id, date)"
                        )
                    except Exception as ex:
                        logger.warning("Could not create unique index on attendance_records: %s", ex)
        except Exception as e:
            logger.warning("Attendance schema migration skipped or partial: %s", e)
    
    @classmethod
    def get_vendor_by_id(cls, vendor_id):
        """Get vendor details by ID"""
        query = """
        SELECT vendor_id, name, department, address 
        FROM vendor_details 
        WHERE vendor_id = %s
        """
        try:
            with cls.get_connection() as conn:
                if DB_TYPE == 'mysql':
                    cursor = conn.cursor(dictionary=True)
                else:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(query, (vendor_id,))
                result = cursor.fetchone()
                if DB_TYPE == 'mysql':
                    return result if result else None
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error fetching vendor: {e}")
            return None
    
    @classmethod
    def get_today_session(cls, user_id, date):
        """Latest attendance row for this user and calendar date (start/stop same day)."""
        query = """
        SELECT id, user_id, name, department, address, date, start_time, end_time, time, status
        FROM attendance_records
        WHERE user_id = %s AND date = %s
        ORDER BY id DESC
        LIMIT 1
        """
        try:
            with cls.get_connection() as conn:
                if DB_TYPE == 'mysql':
                    cursor = conn.cursor(dictionary=True)
                else:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(query, (user_id, date))
                row = cursor.fetchone()
                if not row:
                    return None
                return dict(row) if DB_TYPE == 'postgresql' else row
        except Exception as e:
            logger.error(f"Error fetching session: {e}")
            return None
    
    @classmethod
    def insert_clock_in(cls, user_id, name, department, address, date, start_time, status='Present'):
        """Record start time (face-verified user). Legacy `time` mirrors start_time."""
        if DB_TYPE == 'mysql':
            query = """
            INSERT INTO attendance_records
            (user_id, name, department, address, date, start_time, end_time, time, status, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, NOW())
            """
        else:
            query = """
            INSERT INTO attendance_records
            (user_id, name, department, address, date, start_time, end_time, time, status, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
            """
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    query,
                    (user_id, name, department, address, date, start_time, start_time, status),
                )
                if DB_TYPE == 'mysql':
                    return cursor.lastrowid
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error clock in: {e}")
            return None
    
    @classmethod
    def update_clock_out(cls, attendance_id, end_time):
        """Set stop time for an open session."""
        if DB_TYPE == 'mysql':
            query = """
            UPDATE attendance_records
            SET end_time = %s, synced_at = NOW()
            WHERE id = %s AND end_time IS NULL
            """
        else:
            query = """
            UPDATE attendance_records
            SET end_time = %s, synced_at = CURRENT_TIMESTAMP
            WHERE id = %s AND end_time IS NULL
            """
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (end_time, attendance_id))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error clock out: {e}")
            return False
    
    @classmethod
    def apply_queued_attendance(cls, record: dict) -> bool:
        """Apply one offline queue record (clock in or clock out)."""
        event = (record.get('event') or record.get('punch_type') or '').lower()
        user_id = record.get('user_id')
        date = record.get('date')
        if user_id is None or not date:
            return False
        if event == 'clock_out':
            end_time = record.get('end_time') or record.get('time')
            if not end_time:
                return False
            session = cls.get_today_session(user_id, date)
            if not session or session.get('end_time'):
                return False
            return cls.update_clock_out(session['id'], end_time)
        start_time = record.get('start_time') or record.get('time')
        if not start_time:
            return False
        name = record.get('name', '')
        department = record.get('department', '')
        address = record.get('address', '')
        status = record.get('status', 'Present')
        session = cls.get_today_session(user_id, date)
        if session is None:
            row_id = cls.insert_clock_in(
                user_id, name, department, address, date, start_time, status
            )
            return row_id is not None
        return True
    
    @classmethod
    def get_attendance_records(cls, date=None, limit=100):
        """Get attendance records"""
        if date:
            query = """
            SELECT * FROM attendance_records 
            WHERE date = %s 
            ORDER BY id DESC 
            LIMIT %s
            """
            params = (date, limit)
        else:
            query = """
            SELECT * FROM attendance_records 
            ORDER BY created_at DESC 
            LIMIT %s
            """
            params = (limit,)
        
        try:
            with cls.get_connection() as conn:
                if DB_TYPE == 'mysql':
                    cursor = conn.cursor(dictionary=True)
                else:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(query, params)
                results = cursor.fetchall()
                if DB_TYPE == 'mysql':
                    return results
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching attendance: {e}")
            return []
    
    @classmethod
    def test_connection(cls):
        """Test database connection"""
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                cursor.close()
                return result is not None
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    @classmethod
    def add_vendor(cls, vendor_data: dict) -> int:
        """Add a new vendor/user"""
        query = """
        INSERT INTO vendor_details 
        (vendor_id, name, department, purpose, visited_by, visit_type, 
         dob, gender, number, vendor_company, address, photo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    vendor_data.get('vendor_id'),
                    vendor_data.get('name'),
                    vendor_data.get('department', ''),
                    vendor_data.get('purpose', ''),
                    vendor_data.get('visited_by', ''),
                    vendor_data.get('visit_type', ''),
                    vendor_data.get('dob', ''),
                    vendor_data.get('gender', ''),
                    vendor_data.get('number', ''),
                    vendor_data.get('vendor_company', ''),
                    vendor_data.get('address', ''),
                    vendor_data.get('photo', 'NO')
                ))
                return cursor.lastrowid if DB_TYPE == 'mysql' else cursor.rowcount
        except Exception as e:
            logger.error(f"Error adding vendor: {e}")
            raise
    
    @classmethod
    def update_vendor(cls, vendor_id: int, vendor_data: dict) -> bool:
        """Update vendor information"""
        query = """
        UPDATE vendor_details 
        SET name = %s, department = %s, purpose = %s, visited_by = %s,
            visit_type = %s, dob = %s, gender = %s, number = %s,
            vendor_company = %s, address = %s, photo = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE vendor_id = %s
        """
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    vendor_data.get('name'),
                    vendor_data.get('department', ''),
                    vendor_data.get('purpose', ''),
                    vendor_data.get('visited_by', ''),
                    vendor_data.get('visit_type', ''),
                    vendor_data.get('dob', ''),
                    vendor_data.get('gender', ''),
                    vendor_data.get('number', ''),
                    vendor_data.get('vendor_company', ''),
                    vendor_data.get('address', ''),
                    vendor_data.get('photo', 'NO'),
                    vendor_id
                ))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating vendor: {e}")
            return False
    
    @classmethod
    def delete_vendor(cls, vendor_id: int) -> bool:
        """Delete a vendor"""
        query = "DELETE FROM vendor_details WHERE vendor_id = %s"
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (vendor_id,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting vendor: {e}")
            return False
    
    @classmethod
    def get_all_vendors(cls):
        """Get all vendors"""
        query = "SELECT * FROM vendor_details ORDER BY vendor_id"
        try:
            with cls.get_connection() as conn:
                if DB_TYPE == 'mysql':
                    cursor = conn.cursor(dictionary=True)
                else:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(query)
                results = cursor.fetchall()
                if DB_TYPE == 'mysql':
                    return results
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching vendors: {e}")
            return []
