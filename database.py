import sqlite3
import hashlib
import bcrypt
from datetime import datetime
import os

def get_db_connection():
    conn = sqlite3.connect('career_tracker.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    # Resumes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resumes (
            resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resume_name TEXT NOT NULL,
            file_path TEXT,
            upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_type TEXT,
            ats_text TEXT,
            version INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # Migration: Ensure upload_date column exists
    try:
        cursor.execute(
            "ALTER TABLE resumes ADD COLUMN upload_date DATETIME DEFAULT CURRENT_TIMESTAMP"
        )
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Migration: Ensure file_type column exists
    try:
        cursor.execute(
            "ALTER TABLE resumes ADD COLUMN file_type TEXT"
        )
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Migration: Ensure ats_text column exists
    try:
        cursor.execute(
            "ALTER TABLE resumes ADD COLUMN ats_text TEXT"
        )
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Applications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            location TEXT,
            job_type TEXT,
            application_date DATE,
            job_url TEXT,
            salary TEXT,
            current_stage TEXT,
            overall_status TEXT,
            resume_id INTEGER,
            notes TEXT,
            job_description TEXT,
            match_score INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (resume_id) REFERENCES resumes (resume_id)
        )
    ''')

    # Migration: Ensure overall_status column exists
    try:
        cursor.execute(
            "ALTER TABLE applications ADD COLUMN job_description TEXT"
        )
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute(
            "ALTER TABLE applications ADD COLUMN match_score INTEGER"
        )
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute(
            "ALTER TABLE resumes ADD COLUMN version INTEGER DEFAULT 1"
        )
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Application History table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS application_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            stage TEXT NOT NULL,
            changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (application_id) REFERENCES applications (application_id)
        )
    ''')

    # Match Analyses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS match_analyses (
            analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            resume_id INTEGER NOT NULL,
            score INTEGER,
            analysis_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES applications (application_id),
            FOREIGN KEY (resume_id) REFERENCES resumes (resume_id)
        )
    ''')

    # Interviews table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interviews (
            interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            round TEXT NOT NULL,
            date DATE NOT NULL,
            time TEXT,
            mode TEXT,
            result TEXT,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            topics TEXT,
            went_well TEXT,
            improvement TEXT,
            meeting_link TEXT,
            FOREIGN KEY (application_id) REFERENCES applications (application_id)
        )
    ''')

    # Migration: Ensure google_event_id column exists in interviews
    try:
        cursor.execute("ALTER TABLE interviews ADD COLUMN google_event_id TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Migration: Ensure google_event_id column exists in tasks
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN google_event_id TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.commit()
    conn.close()


def hash_password(password):
    return bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')


def check_password(password, hashed):
    return bcrypt.checkpw(
        password.encode('utf-8'),
        hashed.encode('utf-8')
    )


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
