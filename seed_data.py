import sqlite3
import random
from datetime import datetime, timedelta
from database import get_db_connection

def seed_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear tables to start fresh
    cursor.execute("DELETE FROM tasks")
    cursor.execute("DELETE FROM interviews")
    cursor.execute("DELETE FROM application_history")
    cursor.execute("DELETE FROM applications")
    cursor.execute("DELETE FROM resumes")
    cursor.execute("DELETE FROM users")

    # Create a test user
    import bcrypt
    real_hash = bcrypt.hashpw("password123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                   ("testuser", "test@example.com", real_hash))
    user_id = cursor.lastrowid

    # Create resumes (dummy paths since we can't easily create PDFs via script,
    # but we'll make them look real in the DB)
    resume_names = ["Resume_v1", "Resume_v2", "Resume_Projects", "Resume_SWE"]
    resume_ids = []
    for r_name in resume_names:
        path = f"resumes/{user_id}_{r_name.replace(' ', '_')}.pdf"
        cursor.execute("INSERT INTO resumes (user_id, resume_name, file_path, file_type) VALUES (?, ?, ?, ?)",
                       (user_id, r_name, path, "pdf"))
        resume_ids.append(cursor.lastrowid)

    # Companies
    companies = [
        ("Google", "Software Engineer"), ("Microsoft", "SWE Intern"), ("Amazon", "SDE I"),
        ("Meta", "Frontend Engineer"), ("Apple", "iOS Developer"), ("Netflix", "Backend Engineer"),
        ("TCS", "System Engineer"), ("Infosys", "Developer"), ("Wipro", "Project Engineer"),
        ("Adobe", "Product Engineer"), ("Oracle", "Cloud Engineer"), ("Salesforce", "Developer"),
        ("Uber", "SWE"), ("Lyft", "SWE"), ("Airbnb", "SWE"), ("Dropbox", "SWE"),
        ("Spotify", "Backend"), ("Twitch", "Frontend"), ("Shopify", "Backend"), ("Stripe", "SWE"),
        ("Square", "SWE"), ("Palantir", "SWE"), ("Snowflake", "SWE"), ("Datadog", "SWE"),
        ("Cloudflare", "SWE"), ("Crowdstrike", "SWE"), ("Okta", "SWE"), ("Zscaler", "SWE"),
        ("Zoom", "SWE"), ("Slack", "SWE"), ("Atlassian", "SWE"), ("HubSpot", "SWE"),
        ("Monday.com", "SWE"), ("Asana", "SWE"), ("Notion", "SWE")
    ]

    indices = list(range(35))
    random.shuffle(indices)

    offers_indices = indices[:2]
    rejections_indices = indices[2:17]
    oa_indices = indices[17:29]
    others_indices = indices[29:]

    for i in range(35):
        company, role = companies[i]
        days_ago = random.randint(0, 180)
        app_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')

        if i in offers_indices:
            stage = "Offer"
            status = "Offer"
        elif i in rejections_indices:
            stage = "Rejected"
            status = "Rejected"
        elif i in oa_indices:
            stage = "Online Assessment"
            status = "Active"
        else:
            stage = random.choice(["Applied", "Recruiter Call", "Technical Interview", "HR Interview"])
            status = "Active"

        resume_id = random.choice(resume_ids)

        cursor.execute('''
            INSERT INTO applications (user_id, company, role, location, job_type, application_date, job_url, salary, current_stage, overall_status, resume_id, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, company, role, "Remote", "Full-time", app_date, f"https://jobs.{company.lower()}.com", "Competitive", stage, status, resume_id, "Sample notes"))

        app_id = cursor.lastrowid

        cursor.execute("INSERT INTO application_history (application_id, stage, notes) VALUES (?, ?, ?)",
                       (app_id, "Applied", "Application submitted"))
        if stage != "Applied":
            cursor.execute("INSERT INTO application_history (application_id, stage, notes) VALUES (?, ?, ?)",
                           (app_id, stage, f"Moved to {stage}"))

        if i in offers_indices or (i in rejections_indices and random.random() > 0.5) or (i in oa_indices and random.random() > 0.5):
            num_rounds = random.randint(1, 3)
            for r in range(1, num_rounds + 1):
                int_days_offset = random.randint(5, 30)
                int_date = (datetime.strptime(app_date, '%Y-%m-%d') + timedelta(days=int_days_offset)).strftime('%Y-%m-%d')
                rating = 2 if days_ago > 120 else (3 if days_ago > 60 else random.randint(3, 5))
                topics = random.sample(["DSA", "DBMS", "OS", "CN", "OOP", "System Design", "Behavioral"], random.randint(1, 3))

                cursor.execute('''
                    INSERT INTO interviews (application_id, round, date, time, mode, result, rating, topics, went_well, improvement, meeting_link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (app_id, f"Round {r}", int_date, "10:00 AM", "Online", "Completed", rating, ", ".join(topics), "Solved most questions", "Need to practice OS", "zoom.us/j/123"))

    conn.commit()
    conn.close()
    print("Database seeded with scenario data successfully.")

if __name__ == "__main__":
    seed_data()
