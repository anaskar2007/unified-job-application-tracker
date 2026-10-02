import sqlite3

def migrate_db():
    conn = sqlite3.connect('career_tracker.db')
    cursor = conn.cursor()

    print("Running database migrations...")

    # 1. Add job_description to applications
    try:
        cursor.execute("ALTER TABLE applications ADD COLUMN job_description TEXT")
        print("Added column 'job_description' to applications.")
    except sqlite3.OperationalError:
        print("Column 'job_description' already exists.")

    # 2. Add match_score to applications
    try:
        cursor.execute("ALTER TABLE applications ADD COLUMN match_score INTEGER")
        print("Added column 'match_score' to applications.")
    except sqlite3.OperationalError:
        print("Column 'match_score' already exists.")

    # 3. Add version to resumes
    try:
        cursor.execute("ALTER TABLE resumes ADD COLUMN version INTEGER DEFAULT 1")
        print("Added column 'version' to resumes.")
    except sqlite3.OperationalError:
        print("Column 'version' already exists.")

    # 4. Create match_analyses table
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
    print("Ensured 'match_analyses' table exists.")

    conn.commit()
    conn.close()
    print("Migrations completed successfully.")

if __name__ == "__main__":
    migrate_db()
