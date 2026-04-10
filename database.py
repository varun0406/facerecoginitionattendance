"""
Database module: MySQL, PostgreSQL, or SQLite (file-based, no server).
"""

import logging
import os
from contextlib import contextmanager

from config import DATABASE_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _compute_duration(start: str, end: str):
    """Return (duration_str, duration_minutes) from two HH:MM:SS strings.

    Handles overnight shifts (end < start) by assuming same-day wrap at midnight.
    Returns (None, None) if either value is missing or unparseable.
    """
    if not start or not end:
        return None, None
    try:
        from datetime import datetime, timedelta
        fmt = "%H:%M:%S"
        t0 = datetime.strptime(start, fmt)
        t1 = datetime.strptime(end, fmt)
        diff = t1 - t0
        if diff.total_seconds() < 0:
            diff += timedelta(hours=24)
        total_min = int(diff.total_seconds() // 60)
        h, m = divmod(total_min, 60)
        return f"{h}h {m:02d}m", total_min
    except Exception:
        return None, None

_raw = DATABASE_CONFIG.get("db_type", "sqlite").lower()
if _raw == "sqlite":
    import sqlite3

    DB_TYPE = "sqlite"
elif _raw == "postgresql":
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor

    DB_TYPE = "postgresql"
else:
    import mysql.connector
    from mysql.connector import pooling

    DB_TYPE = "mysql"


def _sql(q: str) -> str:
    return q.replace("%s", "?") if DB_TYPE == "sqlite" else q


def _row_to_dict(row):
    if row is None:
        return None
    if DB_TYPE == "mysql":
        return row
    if DB_TYPE == "sqlite":
        return dict(row)
    return dict(row)


class Database:
    """Database connection and operations."""

    _connection_pool = None
    _sqlite_path = None

    @classmethod
    def initialize_pool(cls):
        if DB_TYPE == "sqlite" and cls._connection_pool == "sqlite" and cls._sqlite_path:
            return
        if DB_TYPE == "mysql" and cls._connection_pool is not None:
            return
        if DB_TYPE == "postgresql" and cls._connection_pool is not None:
            return
        try:
            if DB_TYPE == "sqlite":
                path = DATABASE_CONFIG.get("sqlite_path") or "attendance.db"
                if not os.path.isabs(path):
                    path = os.path.abspath(path)
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                cls._sqlite_path = path
                cls._connection_pool = "sqlite"
                logger.info("SQLite database at %s", cls._sqlite_path)
                return
            if DB_TYPE == "mysql":
                cls._connection_pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="attendance_pool",
                    pool_size=DATABASE_CONFIG["pool_size"],
                    host=DATABASE_CONFIG["host"],
                    port=DATABASE_CONFIG["port"],
                    user=DATABASE_CONFIG["user"],
                    password=DATABASE_CONFIG["password"],
                    database=DATABASE_CONFIG["database"],
                    connection_timeout=DATABASE_CONFIG["connection_timeout"],
                    autocommit=False,
                )
            else:
                cls._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    1,
                    DATABASE_CONFIG["pool_size"],
                    host=DATABASE_CONFIG["host"],
                    port=DATABASE_CONFIG["port"],
                    user=DATABASE_CONFIG["user"],
                    password=DATABASE_CONFIG["password"],
                    database=DATABASE_CONFIG["database"],
                    connect_timeout=DATABASE_CONFIG["connection_timeout"],
                )
            logger.info("Database connection pool initialized (%s)", DB_TYPE)
        except Exception as e:
            logger.error("Error initializing connection pool: %s", e)
            raise

    @classmethod
    @contextmanager
    def get_connection(cls):
        conn = None
        try:
            if DB_TYPE == "sqlite":
                if not cls._sqlite_path:
                    cls.initialize_pool()
                conn = sqlite3.connect(
                    cls._sqlite_path, check_same_thread=False, timeout=30.0
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                yield conn
                conn.commit()
            elif DB_TYPE == "mysql":
                conn = cls._connection_pool.get_connection()
                yield conn
                conn.commit()
            else:
                conn = cls._connection_pool.getconn()
                yield conn
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error("Database error: %s", e)
            raise
        finally:
            if conn:
                if DB_TYPE == "sqlite":
                    conn.close()
                elif DB_TYPE == "mysql":
                    conn.close()
                else:
                    cls._connection_pool.putconn(conn)

    @classmethod
    def create_tables(cls):
        if DB_TYPE == "sqlite":
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
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
                UNIQUE (user_id, date)
            );
            """
        elif DB_TYPE == "mysql":
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
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(create_vendor_table)
                cursor.execute(create_attendance_table)
                if DB_TYPE == "postgresql":
                    cursor.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_attendance_user_date
                        ON attendance_records(user_id, date);
                        """
                    )
                    cursor.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_attendance_date
                        ON attendance_records(date);
                        """
                    )
                logger.info("Database tables created successfully")
        except Exception as e:
            logger.error("Error creating tables: %s", e)
            raise
        cls.ensure_attendance_clock_schema()

    @classmethod
    def ensure_attendance_clock_schema(cls):
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                if DB_TYPE == "sqlite":
                    cursor.execute("PRAGMA table_info(attendance_records)")
                    cols = {row[1] for row in cursor.fetchall()}
                    if cols and "start_time" not in cols:
                        cursor.execute(
                            "ALTER TABLE attendance_records ADD COLUMN start_time VARCHAR(20)"
                        )
                        cursor.execute(
                            "ALTER TABLE attendance_records ADD COLUMN end_time VARCHAR(20)"
                        )
                        if "time" in cols:
                            cursor.execute(
                                "UPDATE attendance_records SET start_time = time "
                                "WHERE start_time IS NULL AND time IS NOT NULL"
                            )
                    try:
                        cursor.execute(
                            "CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_user_date "
                            "ON attendance_records (user_id, date)"
                        )
                    except Exception as ex:
                        logger.warning("SQLite unique index: %s", ex)
                elif DB_TYPE == "mysql":
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
                            "Could not add unique key uq_attendance_user_date: %s", ex
                        )
                else:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_name = 'attendance_records'
                          AND column_name = 'start_time'
                        """
                    )
                    has_start = cursor.fetchone()[0] > 0
                    if not has_start:
                        cursor.execute(
                            "ALTER TABLE attendance_records "
                            "ADD COLUMN IF NOT EXISTS start_time VARCHAR(20)"
                        )
                        cursor.execute(
                            "ALTER TABLE attendance_records "
                            "ADD COLUMN IF NOT EXISTS end_time VARCHAR(20)"
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
                            logger.debug("time column: %s", ex)
                    try:
                        cursor.execute(
                            "CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_user_date "
                            "ON attendance_records (user_id, date)"
                        )
                    except Exception as ex:
                        logger.warning("Could not create unique index: %s", ex)
        except Exception as e:
            logger.warning("Attendance schema migration skipped or partial: %s", e)

    @classmethod
    def ensure_checkout_type_column(cls):
        """Add checkout_type column to attendance_records if missing."""
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                if DB_TYPE == "sqlite":
                    cursor.execute("PRAGMA table_info(attendance_records)")
                    cols = {row[1] for row in cursor.fetchall()}
                    if "checkout_type" not in cols:
                        cursor.execute(
                            "ALTER TABLE attendance_records "
                            "ADD COLUMN checkout_type VARCHAR(20) DEFAULT 'face'"
                        )
                elif DB_TYPE == "mysql":
                    cursor.execute(
                        """SELECT COUNT(*) FROM information_schema.COLUMNS
                           WHERE TABLE_SCHEMA = DATABASE()
                             AND TABLE_NAME = 'attendance_records'
                             AND COLUMN_NAME = 'checkout_type'"""
                    )
                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            "ALTER TABLE attendance_records "
                            "ADD COLUMN checkout_type VARCHAR(20) DEFAULT 'face'"
                        )
                else:
                    cursor.execute(
                        """SELECT COUNT(*) FROM information_schema.columns
                           WHERE table_name = 'attendance_records'
                             AND column_name = 'checkout_type'"""
                    )
                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            "ALTER TABLE attendance_records "
                            "ADD COLUMN IF NOT EXISTS checkout_type VARCHAR(20) DEFAULT 'face'"
                        )
        except Exception as e:
            logger.warning("checkout_type column migration skipped: %s", e)

    @classmethod
    def _cursor(cls, conn, dictionary=False):
        if DB_TYPE == "mysql":
            return conn.cursor(dictionary=dictionary)
        if DB_TYPE == "sqlite":
            return conn.cursor()
        return conn.cursor(cursor_factory=RealDictCursor)

    @classmethod
    def get_vendor_by_id(cls, vendor_id):
        query = _sql(
            """
        SELECT vendor_id, name, department, address
        FROM vendor_details
        WHERE vendor_id = %s
        """
        )
        try:
            with cls.get_connection() as conn:
                cur = cls._cursor(conn, dictionary=True)
                cur.execute(query, (vendor_id,))
                return _row_to_dict(cur.fetchone())
        except Exception as e:
            logger.error("Error fetching vendor: %s", e)
            return None

    @classmethod
    def get_today_session(cls, user_id, date):
        query = _sql(
            """
        SELECT id, user_id, name, department, address, date,
               start_time, end_time, time, status
        FROM attendance_records
        WHERE user_id = %s AND date = %s
        ORDER BY id DESC
        LIMIT 1
        """
        )
        try:
            with cls.get_connection() as conn:
                cur = cls._cursor(conn, dictionary=True)
                cur.execute(query, (user_id, date))
                return _row_to_dict(cur.fetchone())
        except Exception as e:
            logger.error("Error fetching session: %s", e)
            return None

    @classmethod
    def insert_clock_in(
        cls, user_id, name, department, address, date, start_time, status="Present"
    ):
        if DB_TYPE == "postgresql":
            query = """
            INSERT INTO attendance_records
            (user_id, name, department, address, date, start_time, end_time, time, status, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
            """
        else:
            query = _sql(
                """
            INSERT INTO attendance_records
            (user_id, name, department, address, date, start_time, end_time, time, status, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, CURRENT_TIMESTAMP)
            """
            )
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                params = (
                    user_id,
                    name,
                    department,
                    address,
                    date,
                    start_time,
                    None,
                    status,
                )
                cursor.execute(query, params)
                if DB_TYPE == "mysql":
                    return cursor.lastrowid
                if DB_TYPE == "sqlite":
                    return cursor.lastrowid
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error("Error clock in: %s", e)
            return None

    @classmethod
    def update_clock_out(cls, attendance_id, end_time):
        if DB_TYPE == "mysql":
            query = """
            UPDATE attendance_records
            SET end_time = %s, synced_at = NOW()
            WHERE id = %s AND end_time IS NULL
            """
        else:
            query = _sql(
                """
            UPDATE attendance_records
            SET end_time = %s, synced_at = CURRENT_TIMESTAMP
            WHERE id = %s AND end_time IS NULL
            """
            )
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (end_time, attendance_id))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("Error clock out: %s", e)
            return False

    @classmethod
    def apply_queued_attendance(cls, record: dict) -> bool:
        event = (record.get("event") or record.get("punch_type") or "").lower()
        user_id = record.get("user_id")
        date = record.get("date")
        if user_id is None or not date:
            return False
        if event == "clock_out":
            end_time = record.get("end_time") or record.get("time")
            if not end_time:
                return False
            session = cls.get_today_session(user_id, date)
            if not session or session.get("end_time"):
                return False
            return cls.update_clock_out(session["id"], end_time)
        start_time = record.get("start_time") or record.get("time")
        if not start_time:
            return False
        name = record.get("name", "")
        department = record.get("department", "")
        address = record.get("address", "")
        status = record.get("status", "Present")
        session = cls.get_today_session(user_id, date)
        if session is None:
            row_id = cls.insert_clock_in(
                user_id, name, department, address, date, start_time, status
            )
            return row_id is not None
        return True

    @classmethod
    def get_attendance_records(cls, date=None, date_from=None, date_to=None, limit=100):
        """
        Fetch attendance records with optional filters.
        - `date`      – exact match (DD/MM/YYYY)
        - `date_from` / `date_to` – inclusive range (DD/MM/YYYY)
        - `limit`     – max rows returned
        """
        conditions = []
        params_list = []
        if date:
            conditions.append("date = %s")
            params_list.append(date)
        else:
            if date_from:
                conditions.append("date >= %s")
                params_list.append(date_from)
            if date_to:
                conditions.append("date <= %s")
                params_list.append(date_to)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = _sql(
            f"""
            SELECT * FROM attendance_records
            {where}
            ORDER BY id DESC
            LIMIT %s
            """
        )
        params_list.append(limit)
        try:
            with cls.get_connection() as conn:
                cur = cls._cursor(conn, dictionary=True)
                cur.execute(query, tuple(params_list))
                rows = cur.fetchall()
                records = rows if DB_TYPE == "mysql" else [_row_to_dict(r) for r in rows]
            enriched = []
            for r in records:
                rec = dict(r)
                st = rec.get("start_time") or rec.get("time")
                et = rec.get("end_time")
                dur_str, dur_min = _compute_duration(st, et)
                rec["duration"] = dur_str
                rec["duration_minutes"] = dur_min
                rec["start_time"] = st
                rec.setdefault("checkout_type", "face")
                enriched.append(rec)
            return enriched
        except Exception as e:
            logger.error("Error fetching attendance: %s", e)
            return []

    @classmethod
    def get_attendance_summary(cls, date=None, date_from=None, date_to=None, limit=500):
        """Per-user totals: days present and total hours for a date range or all time."""
        records = cls.get_attendance_records(date=date, date_from=date_from, date_to=date_to, limit=limit)
        summary = {}
        for r in records:
            uid = r.get("user_id")
            if uid is None:
                continue
            if uid not in summary:
                summary[uid] = {
                    "user_id": uid,
                    "name": r.get("name", ""),
                    "department": r.get("department", ""),
                    "days_present": 0,
                    "total_minutes": 0,
                    "days_complete": 0,
                }
            summary[uid]["days_present"] += 1
            dur = r.get("duration_minutes")
            if dur is not None:
                summary[uid]["total_minutes"] += dur
                summary[uid]["days_complete"] += 1
        result = []
        for s in summary.values():
            tm = s["total_minutes"]
            h, m = divmod(tm, 60)
            s["total_duration"] = f"{h}h {m:02d}m" if tm else None
            result.append(s)
        result.sort(key=lambda x: x["user_id"])
        return result

    @classmethod
    def test_connection(cls):
        if DB_TYPE == "sqlite" and not cls._sqlite_path:
            return False
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                cursor.close()
                return result is not None
        except Exception as e:
            logger.error("Connection test failed: %s", e)
            return False

    @classmethod
    def add_vendor(cls, vendor_data: dict) -> int:
        query = _sql(
            """
        INSERT INTO vendor_details
        (vendor_id, name, department, purpose, visited_by, visit_type,
         dob, gender, number, vendor_company, address, photo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        )
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    query,
                    (
                        vendor_data.get("vendor_id"),
                        vendor_data.get("name"),
                        vendor_data.get("department", ""),
                        vendor_data.get("purpose", ""),
                        vendor_data.get("visited_by", ""),
                        vendor_data.get("visit_type", ""),
                        vendor_data.get("dob", ""),
                        vendor_data.get("gender", ""),
                        vendor_data.get("number", ""),
                        vendor_data.get("vendor_company", ""),
                        vendor_data.get("address", ""),
                        vendor_data.get("photo", "NO"),
                    ),
                )
                if DB_TYPE == "postgresql":
                    return cursor.rowcount
                return cursor.lastrowid
        except Exception as e:
            logger.error("Error adding vendor: %s", e)
            raise

    @classmethod
    def update_vendor(cls, vendor_id: int, vendor_data: dict) -> bool:
        query = _sql(
            """
        UPDATE vendor_details
        SET name = %s, department = %s, purpose = %s, visited_by = %s,
            visit_type = %s, dob = %s, gender = %s, number = %s,
            vendor_company = %s, address = %s, photo = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE vendor_id = %s
        """
        )
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    query,
                    (
                        vendor_data.get("name"),
                        vendor_data.get("department", ""),
                        vendor_data.get("purpose", ""),
                        vendor_data.get("visited_by", ""),
                        vendor_data.get("visit_type", ""),
                        vendor_data.get("dob", ""),
                        vendor_data.get("gender", ""),
                        vendor_data.get("number", ""),
                        vendor_data.get("vendor_company", ""),
                        vendor_data.get("address", ""),
                        vendor_data.get("photo", "NO"),
                        vendor_id,
                    ),
                )
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("Error updating vendor: %s", e)
            return False

    @classmethod
    def delete_vendor(cls, vendor_id: int) -> bool:
        query = _sql("DELETE FROM vendor_details WHERE vendor_id = %s")
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (vendor_id,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("Error deleting vendor: %s", e)
            return False

    @classmethod
    def auto_checkout_open_sessions(cls, cutoff_hours: int = 9) -> int:
        """
        Close all attendance sessions where start_time is more than `cutoff_hours` ago
        and end_time is still NULL. Returns the number of records closed.
        """
        from datetime import datetime, timedelta
        now = datetime.now()
        closed = 0
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                # Fetch all open sessions (end_time IS NULL)
                q_select = _sql(
                    "SELECT id, date, start_time FROM attendance_records "
                    "WHERE end_time IS NULL AND start_time IS NOT NULL"
                )
                cursor.execute(q_select)
                rows = cursor.fetchall()
                for row in rows:
                    rec_id, date_str, start_str = row[0], row[1], row[2]
                    if not date_str or not start_str:
                        continue
                    try:
                        # Parse date in DD/MM/YYYY format
                        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                            try:
                                rec_date = datetime.strptime(date_str, fmt).date()
                                break
                            except ValueError:
                                continue
                        else:
                            continue
                        rec_start = datetime.strptime(
                            f"{rec_date} {start_str}", "%Y-%m-%d %H:%M:%S"
                        )
                        cutoff_dt = rec_start + timedelta(hours=cutoff_hours)
                        if now >= cutoff_dt:
                            checkout_time = cutoff_dt.strftime("%H:%M:%S")
                            q_update = _sql(
                                "UPDATE attendance_records "
                                "SET end_time = %s, checkout_type = 'auto' "
                                "WHERE id = %s"
                            )
                            cursor.execute(q_update, (checkout_time, rec_id))
                            closed += 1
                    except Exception as ex:
                        logger.debug("auto_checkout row %s: %s", rec_id, ex)
        except Exception as e:
            logger.error("auto_checkout_open_sessions error: %s", e)
        if closed:
            logger.info("Auto-checkout closed %s open session(s)", closed)
        return closed

    @classmethod
    def update_attendance_record(
        cls, record_id: int, start_time: str, end_time: str
    ) -> bool:
        """Manually update clock-in/clock-out times; marks checkout_type = 'manual'."""
        query = _sql(
            "UPDATE attendance_records "
            "SET start_time = %s, end_time = %s, checkout_type = 'manual' "
            "WHERE id = %s"
        )
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (start_time, end_time, record_id))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("Error updating attendance record %s: %s", record_id, e)
            return False

    @classmethod
    def delete_attendance_record(cls, record_id: int) -> bool:
        """Delete a single attendance record by id."""
        query = _sql("DELETE FROM attendance_records WHERE id = %s")
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (record_id,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error("Error deleting attendance record %s: %s", record_id, e)
            return False

    @classmethod
    def delete_vendor_cascade(cls, vendor_id: int) -> dict:
        """Delete vendor + all their attendance records atomically."""
        del_att = _sql(
            "DELETE FROM attendance_records WHERE user_id = %s"
        )
        del_vnd = _sql("DELETE FROM vendor_details WHERE vendor_id = %s")
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(del_att, (vendor_id,))
                att_deleted = cursor.rowcount
                cursor.execute(del_vnd, (vendor_id,))
                vnd_deleted = cursor.rowcount
            return {
                "success": vnd_deleted > 0,
                "attendance_records_deleted": att_deleted,
                "vendor_deleted": vnd_deleted > 0,
            }
        except Exception as e:
            logger.error("Error in cascade delete for vendor %s: %s", vendor_id, e)
            return {"success": False, "error": str(e)}

    @classmethod
    def get_vendor_attendance_count(cls, vendor_id: int) -> int:
        """Count of attendance records for a vendor (used in delete warning)."""
        query = _sql(
            "SELECT COUNT(*) FROM attendance_records WHERE user_id = %s"
        )
        try:
            with cls.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (vendor_id,))
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        except Exception as e:
            logger.error("Error counting attendance for vendor %s: %s", vendor_id, e)
            return 0

    @classmethod
    def get_all_vendors(cls):
        query = "SELECT * FROM vendor_details ORDER BY vendor_id"
        try:
            with cls.get_connection() as conn:
                cur = cls._cursor(conn, dictionary=True)
                cur.execute(query)
                results = cur.fetchall()
                if DB_TYPE == "mysql":
                    return results
                return [_row_to_dict(r) for r in results]
        except Exception as e:
            logger.error("Error fetching vendors: %s", e)
            return []
