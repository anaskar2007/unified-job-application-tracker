import json
import mysql.connector
from opencats_connector import send_resume_to_opencats
import streamlit as st
from ui_components import render_card, render_badge, render_kpi_card, render_section_header
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from database import get_db_connection, check_password, hash_password
from ai.jd_resume_analyzer import analyze_resume
from ai.jd_matcher import extract_jd_requirements, calculate_match_score, generate_explainable_report
import bcrypt
import os
import base64
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# --- Page Config ---
st.set_page_config(page_title="Career Progress Tracker", layout="wide", page_icon="💼")

# --- Constants ---
RESUME_FOLDER = "resumes"
if not os.path.exists(RESUME_FOLDER):
    os.makedirs(RESUME_FOLDER)

# --- CSS for Modern SaaS UI ---
st.markdown("""
<style>
    :root {
        --primary: #3b82f6;
        --primary-hover: #2563eb;
        --bg-main: #000000;
        --bg-card: #111111;
        --text-main: #ffffff;
        --text-muted: #a1a1aa;
        --border-color: #27272a;
        --sidebar-bg: #0a0a0a;
        --radius-lg: 12px;
        --radius-md: 8px;
        --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.5);
    }

    /* Main container styling */
    .stApp {
        background-color: var(--bg-main) !important;
        color: var(--text-main) !important;
    }

    /* Force ALL text colors to white/muted */
    .stApp [data-testid="stMarkdownContainer"] p,
    .stApp [data-testid="stMarkdownContainer"] span,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp label, .stApp .stText, .stApp .stMetric {
        color: var(--text-main) !important;
    }

    .stApp [data-testid="stMarkdownContainer"] .small,
    .stApp .st-muted {
        color: var(--text-muted) !important;
    }

    /* Input field styling - Force black bg and white text */
    .stTextInput input, .stTextArea textarea, .stDateInput input,
    .stTimeInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #1a1a1a !important;
        color: white !important;
        border: 1px solid var(--border-color) !important;
    }

    /* Card styling */
    .st-card, .kpi-card {
        background-color: var(--bg-card) !important;
        padding: 1.5rem;
        border-radius: var(--radius-lg);
        border: 1px solid var(--border-color) !important;
        box-shadow: var(--shadow-sm);
        margin-bottom: 1rem;
        color: var(--text-main) !important;
    }

    /* Sidebar Navigation Styling */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--border-color) !important;
    }

    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: var(--text-main) !important;
    }

    /* Style the radio buttons to look like a nav menu */
    .stRadio div[role="radiogroup"] label {
        padding: 0.5rem 1rem;
        border-radius: var(--radius-md);
        transition: all 0.2s;
        cursor: pointer;
        color: var(--text-main) !important;
    }

    .stRadio div[role="radiogroup"] label:hover {
        background-color: #1a1a1a;
    }

    /* Analysis Result Cards */
    .analysis-card {
        background-color: var(--bg-card) !important;
        color: var(--text-main) !important;
        padding: 1rem;
        border-radius: var(--radius-lg);
        border-left: 5px solid var(--primary) !important;
        box-shadow: var(--shadow-sm);
        margin-bottom: 1rem;
    }
    .analysis-card-header {
        font-weight: 700;
        color: var(--text-main) !important;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
</style>
""", unsafe_allow_html=True)

def get_badge_class(stage):
    stage = stage.lower()
    if "applied" in stage or "active" in stage: return "badge-active"
    if "interview" in stage or "call" in stage: return "badge-interview"
    if "oa" in stage or "assessment" in stage or "challenge" in stage: return "badge-oa"
    if "offer" in stage: return "badge-offer"
    if "rejected" in stage: return "badge-rejected"
    if "saved" in stage: return "badge-saved"
    return "badge-other"

# --- Auth State ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None

# --- Auth Functions ---
def login_page():
    st.title("💼 Unified Job Application Tracker")
    tab1, tab2 = st.tabs(["Login", "Create New Account"])

    with tab1:
        with st.form("login_form"):
            u = st.text_input("Username", key="login_username")
            p = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Login", key="login_submit"):
                conn = get_db_connection()
                user = conn.execute("SELECT * FROM users WHERE username = ?", (u,)).fetchone()
                conn.close()
                if user and check_password(p, user['password_hash']):
                    st.session_state.authenticated = True
                    st.session_state.user_id = user['user_id']
                    st.session_state.username = user['username']
                    st.rerun()
                else:
                    st.error("Invalid username or password")

    with tab2:
        with st.form("register_form"):
            ru = st.text_input("Username", key="reg_username")
            re = st.text_input("Email", key="reg_email")
            rp = st.text_input("Password", type="password", key="reg_password")
            rpc = st.text_input("Confirm Password", type="password", key="reg_confirm_password")
            if st.form_submit_button("Register", key="reg_submit"):
                if not (ru and re and rp and rpc):
                    st.warning("Please fill all fields")
                elif rp != rpc:
                    st.error("Passwords do not match")
                else:
                    try:
                        conn = get_db_connection()
                        # Check if username or email exists
                        existing_user = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (ru, re)).fetchone()
                        if existing_user:
                            if existing_user['username'] == ru:
                                st.error("Username is already taken")
                            else:
                                st.error("Email is already registered")
                        else:
                            phash = hash_password(rp)
                            conn.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (ru, re, phash))
                            conn.commit()
                            st.success("Account created successfully. You can now log in.")
                        conn.close()
                    except Exception as e:
                        st.error(f"Error: {e}")

def logout():
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.rerun()

# --- MAIN APP ---
def main_app():
    st.sidebar.title(f"Welcome, {st.session_state.username}!")
    if st.sidebar.button("Logout", key="sidebar_logout_btn"):
        logout()

    nav = st.sidebar.radio("Navigation",
        ["Dashboard", "Applications", "Interviews", "Resumes", "Analytics", "Reminders", "AI Resume Analyzer", "Settings"],
        key="main_nav")

    user_id = st.session_state.user_id

    if nav == "Dashboard":
        render_dashboard(user_id)
    elif nav == "Applications":
        render_applications(user_id)
    elif nav == "Interviews":
        render_interviews(user_id)
    elif nav == "Resumes":
        render_resumes(user_id)
    elif nav == "Analytics":
        render_analytics(user_id)
    elif nav == "Reminders":
        render_reminders(user_id)
    elif nav == "Settings":
        render_settings(user_id)
    elif nav == "AI Resume Analyzer":
        render_ai_analyzer(user_id)


# --- Components ---
def render_dashboard(user_id):
    render_section_header("🚀 Career Dashboard", "Overview of your application pipeline and progress")

    conn = get_db_connection()
    apps_df = pd.read_sql_query("SELECT * FROM applications WHERE user_id = ?", conn, params=(user_id,))
    conn.close()

    if apps_df.empty:
        st.info("No applications found. Start by adding one!")
        return

    col1, col2, col3, col4, col5 = st.columns(5)
    total = len(apps_df)
    active = len(apps_df[apps_df['overall_status'] == 'Active'])
    offers = len(apps_df[apps_df['overall_status'] == 'Offer'])
    rejected = len(apps_df[apps_df['overall_status'] == 'Rejected'])
    oa_count = len(apps_df[apps_df['current_stage'].str.contains('Assessment|OA|Challenge', case=False, na=False)])

    col1.markdown(render_kpi_card("Total Apps", total), unsafe_allow_html=True)
    col2.markdown(render_kpi_card("Active", active), unsafe_allow_html=True)
    col3.markdown(render_kpi_card("OA/Tests", oa_count), unsafe_allow_html=True)
    col4.markdown(render_kpi_card("Offers", offers), unsafe_allow_html=True)
    col5.markdown(render_kpi_card("Rejections", rejected), unsafe_allow_html=True)

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="st-card">', unsafe_allow_html=True)
        st.subheader("Applications by Status")
        status_counts = apps_df['overall_status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig = px.pie(status_counts, values='Count', names='Status', hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True, key="dashboard_status_pie")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="st-card">', unsafe_allow_html=True)
        st.subheader("Application Timeline")
        apps_df['application_date'] = pd.to_datetime(apps_df['application_date'])
        timeline_df = apps_df.set_index('application_date').resample('M').size().reset_index(name='Count')
        fig = px.line(timeline_df, x='application_date', y='Count', markers=True)
        fig.update_xaxes(dtick="M1", tickformat="%b %Y")
        st.plotly_chart(fig, use_container_width=True, key="dashboard_timeline_line")
        st.markdown('</div>', unsafe_allow_html=True)

def render_applications(user_id):
    st.markdown("## 📋 Application Management")

    with st.expander("➕ Add New Application", expanded=False):
        with st.form("add_app_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            company = c1.text_input("Company Name*", key="add_app_company")
            role = c2.text_input("Job Title*", key="add_app_role")
            c3, c4 = st.columns(2)
            loc = c3.text_input("Location", key="add_app_loc")
            jtype = c4.selectbox("Job Type", ["Internship", "Full-time", "Part-time", "Other"], key="add_app_type")
            c5, c6 = st.columns(2)
            date = c5.date_input("Application Date", datetime.now(), key="add_app_date")
            url = c6.text_input("Job URL", key="add_app_url")
            salary = st.text_input("Salary/Stipend (Optional)", key="add_app_salary")
            jd_text = st.text_area("Job Description", placeholder="Paste the complete JD here...", key="add_app_jd")

            conn = get_db_connection()
            resumes_df = pd.read_sql_query("SELECT resume_id, resume_name FROM resumes WHERE user_id = ?", conn, params=(user_id,))
            conn.close()
            resume_options = {r['resume_name']: r['resume_id'] for r in resumes_df.to_dict('records')} if not resumes_df.empty else {}
            selected_resume_name = st.selectbox("Resume Used", options=list(resume_options.keys()), key="add_app_resume")

            notes = st.text_area("Notes", key="add_app_notes")
            c7, c8 = st.columns(2)
            overall_status = c7.selectbox("Overall Status", ["Active", "Offer", "Rejected", "Withdrawn"], key="add_app_overall")
            common_stages = ["Saved", "Applied", "Online Assessment", "Recruiter Call", "Technical Interview", "HR Interview", "Managerial Interview"]
            stage_choice = c8.selectbox("Current Stage", options=common_stages + ["Custom..."], key="add_app_stage")
            custom_stage = st.text_input("Enter Custom Stage Name", key="add_app_custom_stage") if stage_choice == "Custom..." else ""

            if st.form_submit_button("Save Application", key="add_app_submit"):
                if company and role:
                    final_stage = custom_stage if stage_choice == "Custom..." else stage_choice
                    if not final_stage:
                        st.error("Please specify a stage")
                    else:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        res_id = resume_options.get(selected_resume_name)
                        cursor.execute('''
                            INSERT INTO applications (user_id, company, role, location, job_type, application_date, job_url, salary, current_stage, overall_status, resume_id, notes, job_description)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (user_id, company, role, loc, jtype, date, url, salary, final_stage, overall_status, res_id, notes, jd_text))
                        app_id = cursor.lastrowid
                        cursor.execute("INSERT INTO application_history (application_id, stage, notes) VALUES (?, ?, ?)",
                                       (app_id, final_stage, "Application created"))
                        conn.commit()
                        conn.close()
                        st.success(f"Application to {company} added successfully!")
                        st.session_state.view_app_id = app_id
                        st.rerun()
                else:
                    st.error("Company and Role are required")

    st.markdown("---")

    # --- Filters ---
    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([3, 1, 1, 1, 1])
    search_q = f_col1.text_input("🔍 Search", placeholder="Company or Role...", key="app_search_q")
    filter_stage = f_col2.selectbox("Stage", ["All"] + ["Offer", "Rejected", "Applied", "Online Assessment"], key="app_filter_stage")
    filter_status = f_col3.selectbox("Status", ["All", "Active", "Offer", "Rejected", "Withdrawn"], key="app_filter_status")
    filter_type = f_col4.selectbox("Type", ["All", "Internship", "Full-time", "Part-time", "Other"], key="app_filter_type")
    sort_order = f_col5.selectbox("Sort", ["Newest First", "Oldest First", "Company Name"], key="app_sort")

    conn = get_db_connection()
    query = "SELECT * FROM applications WHERE user_id = ?"
    params = [user_id]
    if search_q:
        query += " AND (company LIKE ? OR role LIKE ?)"
        params.extend([f"%{search_q}%", f"%{search_q}%"])
    if filter_stage != "All":
        query += " AND current_stage = ?"
        params.append(filter_stage)
    if filter_status != "All":
        query += " AND overall_status = ?"
        params.append(filter_status)
    if filter_type != "All":
        query += " AND job_type = ?"
        params.append(filter_type)

    apps_df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if not apps_df.empty:
        if sort_order == "Newest First": apps_df = apps_df.sort_values('application_date', ascending=False)
        elif sort_order == "Oldest First": apps_df = apps_df.sort_values('application_date', ascending=True)
        elif sort_order == "Company Name": apps_df = apps_df.sort_values('company')

    for idx, row in apps_df.iterrows():
        with st.container():
            # Construct the full HTML card directly to avoid any potential issues with helper function return types
            full_card_html = f"""
                <div class="st-card" style="background-color: var(--bg-card) !important; padding: 1.5rem; border-radius: var(--radius-lg); border: 1px solid var(--border-color) !important; box-shadow: var(--shadow-sm); margin-bottom: 1rem; color: var(--text-main) !important;">
                    <div style="display: flex; justify-content: space-between; align-items: center; color: var(--text-main); width: 100%;">
                        <div style="display: flex; flex-direction: column; text-align: left;">
                            <div style="font-size: 1.1rem; font-weight: 700; color: var(--text-main);">{row['company']}</div>
                            <div style="font-size: 0.9rem; color: var(--text-muted);">{row['role']}</div>
                        </div>
                        <div style="text-align: right; display: flex; flex-direction: column; align-items: flex-end;">
                            {render_badge(row['current_stage'], row['current_stage'])}
                            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">📅 {row['application_date']}</div>
                        </div>
                    </div>
                </div>
            """
            st.markdown(full_card_html, unsafe_allow_html=True)

            if st.button(f"View Details", key=f"det_{row['application_id']}", use_container_width=False):
                st.session_state.view_app_id = row['application_id']
                st.rerun()
            st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)

    if 'view_app_id' in st.session_state:
        render_app_detail(st.session_state.view_app_id, user_id)

def render_app_detail(app_id, user_id):
    st.markdown("---")
    st.subheader(f"📄 Application Detail")

    conn = get_db_connection()
    app = conn.execute("SELECT * FROM applications WHERE application_id = ?", (app_id,)).fetchone()
    if not app:
        st.error("Application not found")
        conn.close()
        return

    resume_name = "None"
    ats_text = ""
    if app['resume_id']:
        res = conn.execute("SELECT resume_name, ats_text FROM resumes WHERE resume_id = ?", (app['resume_id'],)).fetchone()
        if res:
            resume_name = res['resume_name']
            ats_text = res['ats_text']

    # --- Metadata Grid ---
    url_link = f'<a href="{app["job_url"]}" target="_blank" style="color: var(--primary);">Open Job Posting</a>' if app['job_url'] else 'Not provided'

    # Use a simple div wrapper and direct st.markdown for the grid to avoid rendering issues
    grid_html = f"""
        <div style="background-color: var(--bg-card) !important; padding: 1.5rem; border-radius: var(--radius-lg); border: 1px solid var(--border-color) !important; margin-bottom: 1rem; color: var(--text-main) !important;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <div><strong style="color: var(--text-muted);">Company:</strong> {app['company']}</div>
                    <div><strong style="color: var(--text-muted);">Role:</strong> {app['role']}</div>
                    <div><strong style="color: var(--text-muted);">Location:</strong> {app['location']}</div>
                    <div><strong style="color: var(--text-muted);">URL:</strong> {url_link}</div>
                </div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <div><strong style="color: var(--text-muted);">Date:</strong> {app['application_date']}</div>
                    <div><strong style="color: var(--text-muted);">Type:</strong> {app['job_type']}</div>
                    <div><strong style="color: var(--text-muted);">Salary:</strong> {app['salary']}</div>
                    <div><strong style="color: var(--text-muted);">Overall Status:</strong> {app['overall_status']}</div>
                    <div><strong style="color: var(--text-muted);">Current Stage:</strong> {app['current_stage']}</div>
                    <div><strong style="color: var(--text-muted);">Resume Used:</strong> {resume_name}</div>
                </div>
            </div>
        </div>
    """
    st.markdown(grid_html, unsafe_allow_html=True)

    st.divider()
    col_act1, col_act2, col_act3 = st.columns(3)
    if col_act1.button("✏️ Edit Application", key=f"edit_app_btn_{app_id}"):
        st.session_state.edit_app_id = app_id
        st.rerun()
    if col_act2.button("🗑️ Delete Application", key=f"del_app_btn_{app_id}"):
        st.session_state.confirm_del_app = app_id
        st.rerun()
    if col_act3.button("🎙️ Add Interview", key=f"add_int_app_btn_{app_id}"):
        st.session_state.add_int_app_id = app_id
        st.rerun()

    if 'confirm_del_app' in st.session_state and st.session_state.confirm_del_app == app_id:
        st.warning(f"Are you sure you want to delete the application for {app['company']}?")
        if st.button("Yes, Delete", key=f"confirm_del_{app_id}"):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE application_id = ?", (app_id,))
            cursor.execute("DELETE FROM interviews WHERE application_id = ?", (app_id,))
            cursor.execute("DELETE FROM application_history WHERE application_id = ?", (app_id,))
            cursor.execute("DELETE FROM applications WHERE application_id = ?", (app_id,))
            conn.commit()
            conn.close()
            del st.session_state.confirm_del_app
            del st.session_state.view_app_id
            st.success("Application deleted.")
            st.rerun()
        if st.button("Cancel", key=f"cancel_del_{app_id}"):
            del st.session_state.confirm_del_app
            st.rerun()

    if 'edit_app_id' in st.session_state and st.session_state.edit_app_id == app_id:
        with st.form("edit_app_form"):
            st.write("Modify Application Details")
            c1, c2 = st.columns(2)
            e_company = c1.text_input("Company", value=app['company'], key=f"e_comp_{app_id}")
            e_role = c2.text_input("Role", value=app['role'], key=f"e_role_{app_id}")
            c3, c4 = st.columns(2)
            e_loc = c3.text_input("Location", value=app['location'], key=f"e_loc_{app_id}")
            e_type = c4.selectbox("Type", ["Internship", "Full-time", "Part-time", "Other"],
                                index=["Internship", "Full-time", "Part-time", "Other"].index(app['job_type']) if app['job_type'] in ["Internship", "Full-time", "Part-time", "Other"] else 0, key=f"e_type_{app_id}")
            c5, c6 = st.columns(2)
            e_date = c5.date_input("Date", value=datetime.strptime(app['application_date'], '%Y-%m-%d'), key=f"e_date_{app_id}")
            e_url = c6.text_input("URL", value=app['job_url'], key=f"e_url_{app_id}")
            e_salary = st.text_input("Salary", value=app['salary'], key=f"e_sal_{app_id}")

            resumes_df = pd.read_sql_query("SELECT resume_id, resume_name FROM resumes WHERE user_id = ?", conn, params=(user_id,))
            res_options = {r['resume_name']: r['resume_id'] for r in resumes_df.to_dict('records')}
            e_resume = st.selectbox("Resume", options=list(res_options.keys()),
                                  index=list(res_options.keys()).index(resume_name) if resume_name in res_options else 0, key=f"e_res_{app_id}")
            e_notes = st.text_area("Notes", value=app['notes'], key=f"e_notes_{app_id}")
            c7, c8 = st.columns(2)
            e_status = c7.selectbox("Overall Status", ["Active", "Offer", "Rejected", "Withdrawn"],
                                   index=["Active", "Offer", "Rejected", "Withdrawn"].index(app['overall_status']) if app['overall_status'] in ["Active", "Offer", "Rejected", "Withdrawn"] else 0, key=f"e_stat_{app_id}")
            common_stages = ["Saved", "Applied", "Online Assessment", "Recruiter Call", "Technical Interview", "HR Interview", "Managerial Interview"]
            e_stage_choice = c8.selectbox("Current Stage", options=common_stages + ["Custom..."],
                                        index=common_stages.index(app['current_stage']) if app['current_stage'] in common_stages else len(common_stages), key=f"e_stage_{app_id}")
            e_custom_stage = st.text_input("Custom Stage Name", value=app['current_stage'], key=f"e_cust_stage_{app_id}") if e_stage_choice == "Custom..." else ""

            if st.form_submit_button("Save Changes", key=f"save_edit_{app_id}"):
                final_stage = e_custom_stage if e_stage_choice == "Custom..." else e_stage_choice
                if final_stage:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE applications SET company=?, role=?, location=?, job_type=?, application_date=?, job_url=?, salary=?, resume_id=?, notes=?, overall_status=?, current_stage=?
                        WHERE application_id=?
                    ''', (e_company, e_role, e_loc, e_type, e_date, e_url, e_salary, res_options.get(e_resume), e_notes, e_status, final_stage, app_id))
                    if final_stage != app['current_stage']:
                        cursor.execute("INSERT INTO application_history (application_id, stage, notes) VALUES (?, ?, ?)", (app_id, final_stage, "Stage updated via edit"))
                    conn.commit()
                    conn.close()
                    st.success("Application updated!")
                    del st.session_state.edit_app_id
                    st.rerun()

    if 'add_int_app_id' in st.session_state and st.session_state.add_int_app_id == app_id:
        with st.form("add_int_app_form"):
            st.write("🎙️ Log Interview for this Application")
            i_round = st.text_input("Round (e.g. Technical 1)")
            i_date = st.date_input("Date", datetime.now())
            i_time = st.text_input("Time")
            i_mode = st.selectbox("Mode", ["Online", "Offline", "Hybrid"])
            i_result = st.text_input("Result")
            i_rating = st.slider("Rating", 1, 5, 3)
            i_topics = st.text_area("Topics (comma separated)")
            i_well = st.text_area("What went well?")
            i_imp = st.text_area("What to improve?")
            i_link = st.text_input("Meeting Link")

            if st.form_submit_button("Save Interview"):
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO interviews (application_id, round, date, time, mode, result, rating, topics, went_well, improvement, meeting_link)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (app_id, i_round, i_date, i_time, i_mode, i_result, i_rating, i_topics, i_well, i_imp, i_link))
                conn.commit()
                conn.close()
                st.success("Interview logged!")
                del st.session_state.add_int_app_id
                st.rerun()

    with st.expander("⏰ Add a Task for this Job", key=f"app_detail_task_expander_{app_id}"):
        with st.form(f"app_detail_task_form_{app_id}"):
            t_desc = st.text_input("Task Description")
            t_date = st.date_input("Deadline")
            if st.form_submit_button("Save Task"):
                cursor = conn.cursor()
                cursor.execute("INSERT INTO tasks (application_id, task_description, deadline) VALUES (?, ?, ?)", (app_id, t_desc, t_date))
                conn.commit()
                conn.close()
                st.success("Task added!")
                st.rerun()

    st.divider()
    st.write("⏳ **Application Timeline**")
    history = conn.execute("SELECT * FROM application_history WHERE application_id = ? ORDER BY changed_at ASC", (app_id,)).fetchall()
    for h in history:
        st.markdown(f"""
        <div style="display: flex; gap: 15px; margin-bottom: 10px; align-items: center;">
            <div style="font-size: 0.85rem; color: var(--text-muted); min-width: 100px;">{h['changed_at'][:10]}</div>
            <div style="flex-grow: 1; padding: 8px 12px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; box-shadow: var(--shadow-sm); color: var(--text-main);">
                <strong style="color: var(--text-main);">{h['stage']}</strong> {f'<span style="color: var(--text-muted); margin-left: 5px;">({h["notes"]})</span>' if h['notes'] else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.write("🎙️ **Linked Interviews**")
    interviews = conn.execute("SELECT * FROM interviews WHERE application_id = ?", (app_id,)).fetchall()
    if not interviews:
        st.info("No interviews logged for this application.")
    for intv in interviews:
        with st.expander(f"Round: {intv['round']} ({intv['date']}) - Rating: {intv['rating']}/5"):
            st.write(f"**Result:** {intv['result']}")
            st.write(f"**Mode:** {intv['mode']} at {intv['time']}")
            st.write(f"**Topics:** {intv['topics']}")
            st.write(f"**Went Well:** {intv['went_well']}")
            st.write(f"**Improvement:** {intv['improvement']}")
            st.write(f"**Link:** {intv['meeting_link']}")
            if st.button("Delete Interview", key=f"del_int_{intv['interview_id']}"):
                cursor = conn.cursor()
                cursor.execute("DELETE FROM interviews WHERE interview_id = ?", (intv['interview_id'],))
                conn.commit()
                conn.close()
                st.rerun()

    st.divider()
    st.write("⏰ **Application Tasks**")
    tasks = conn.execute("SELECT * FROM tasks WHERE application_id = ? ORDER BY deadline ASC", (app_id,)).fetchall()
    if not tasks:
        st.info("No tasks for this application.")
    for t in tasks:
        with st.container():
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 8px; color: var(--text-main);">
                <div>
                    <span style="font-size: 0.85rem; color: var(--text-muted); margin-right: 10px;">📅 {t['deadline']}</span>
                    <span style="font-weight: 500; color: var(--text-main);">{t['task_description']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            col_chk, col_del = st.columns([1, 1])
            with col_chk:
                if st.checkbox("Done", value=bool(t['completed']), key=f"chk_{t['task_id']}"):
                    cursor = conn.cursor()
                    cursor.execute("UPDATE tasks SET completed = ? WHERE task_id = ?", (1, t['task_id']))
                    conn.commit()
                    conn.close()
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_t_{t['task_id']}"):
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM tasks WHERE task_id = ?", (t['task_id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

    if st.button("Close Details", key="close_det_btn"):
        del st.session_state.view_app_id
        st.rerun()

    conn.close()

    conn.close()

def render_interviews(user_id):
    st.header("🎙️ Interview Tracker")
    with st.expander("➕ Log New Interview"):
        with st.form("add_intv_form"):
            conn = get_db_connection()
            apps = pd.read_sql_query("SELECT application_id, company FROM applications WHERE user_id = ?", conn, params=(user_id,))
            conn.close()
            app_options = {f"{a['company']} ({a['application_id']})": a['application_id'] for a in apps.to_dict('records')}
            selected_app = st.selectbox("Application", options=list(app_options.keys()), key="intv_app_select")
            round_name = st.text_input("Interview Round (e.g. Technical 1)", key="intv_round")
            date = st.date_input("Interview Date", datetime.now(), key="intv_date")
            time = st.text_input("Time", key="intv_time")
            mode = st.selectbox("Mode", ["Online", "Offline", "Hybrid"], key="intv_mode")
            result = st.text_input("Result/Outcome", key="intv_result")
            rating = st.slider("Personal Performance Rating", 1, 5, 3, key="intv_rating")
            topics = st.text_area("Topics Asked (comma separated)", key="intv_topics")
            well = st.text_area("What went well?", key="intv_well")
            imp = st.text_area("What needs improvement?", key="intv_imp")
            link = st.text_input("Meeting Link/Location", key="intv_link")
            if st.form_submit_button("Save Interview", key="intv_submit"):
                if selected_app and round_name:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO interviews (application_id, round, date, time, mode, result, rating, topics, went_well, improvement, meeting_link)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (app_options[selected_app], round_name, date, time, mode, result, rating, topics, well, imp, link))
                    conn.commit()
                    conn.close()
                    st.success("Interview logged!")
                    st.rerun()
                else:
                    st.error("Application and Round are required")

    st.divider()
    conn = get_db_connection()
    intvs_df = pd.read_sql_query('''
        SELECT i.*, a.company
        FROM interviews i
        JOIN applications a ON i.application_id = a.application_id
        WHERE a.user_id = ?
    ''', conn, params=(user_id,))
    conn.close()

    for idx, row in intvs_df.iterrows():
        with st.container():
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.markdown(f"**{row['company']}** — {row['round']}")
                st.markdown(f"📅 {row['date']} | Rating: {row['rating']}/5")
            with c2:
                st.markdown(f"Topics: {row['topics']}")
            with c3:
                if st.button("Delete", key=f"del_int_list_{row['interview_id']}"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM interviews WHERE interview_id = ?", (row['interview_id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()
            st.divider()

def render_resumes(user_id):
    st.header("📄 Resume Manager")

    with st.expander("➕ Upload New Resume"):
        with st.form("upload_resume_form"):
            res_name = st.text_input("Resume Name (e.g. SWE_v1)")
            uploaded_file = st.file_uploader(
                "Choose PDF or DOCX",
                type=["pdf", "docx"]
            )

            if st.form_submit_button(
                "Upload Resume",
                key="upload_res_submit"
            ):
                if res_name and uploaded_file:

                    if uploaded_file.type == "application/pdf":
                        pdf_bytes = uploaded_file.getvalue()
                        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
                        with st.expander("📄 Uploaded Resume Preview", expanded=True):
                            st.markdown(
                                f'<iframe src="data:application/pdf;base64,{pdf_base64}" '
                                'width="100%" height="700" type="application/pdf"></iframe>',
                                unsafe_allow_html=True
                            )

                    file_ext = uploaded_file.name.split('.')[-1].lower()

                    unique_filename = (
                        f"{user_id}_"
                        f"{datetime.now().strftime('%Y%m%d%H%M%S')}_"
                        f"{res_name.replace(' ', '_')}."
                        f"{file_ext}"
                    )

                    file_path = os.path.join(
                        RESUME_FOLDER,
                        unique_filename
                    )

                    # Save resume locally
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    # Save resume in database
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                        INSERT INTO resumes
                        (user_id, resume_name, file_path, file_type, upload_date)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        user_id,
                        res_name,
                        file_path,
                        file_ext,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ))

                    conn.commit()
                    conn.close()

                    st.success("Resume uploaded successfully!")

                    # Send the same uploaded resume to OpenCATS
                    with st.spinner("Sending resume to OpenCATS..."):
                        try:
                            result = send_resume_to_opencats(file_path)
                        except Exception:
                            result = {
                                "success": False,
                                "error": "OpenCATS is unavailable. The resume was saved locally, but parsing could not be completed."
                            }

                    if result["success"]:
                        st.success(
                            f"Resume successfully added to OpenCATS. "
                            f"Candidate ID: {result['candidate_id']}"
                        )

                        # Get ATS extracted text
                        ats_text = result.get("resume_text", "")

                        # Save ATS text permanently to this resume
                        conn = get_db_connection()
                        cursor = conn.cursor()

                        cursor.execute(
                            """
                            UPDATE resumes
                            SET ats_text = ?
                            WHERE user_id = ? AND file_path = ?
                            """,
                            (ats_text, user_id, file_path)
                        )

                        conn.commit()
                        conn.close()

                        # Show extracted text immediately
                        st.subheader("🔍 ATS Extracted Text")

                        if ats_text:
                            st.text_area(
                                "Text extracted by OpenCATS",
                                ats_text,
                                height=500
                            )
                        else:
                            st.warning(
                                "OpenCATS did not extract any text from this resume."
                            )

                    else:
                        st.error(
                            f"OpenCATS upload failed: {result['error']}"
                        )

                else:
                    st.error("Both name and file are required")

    st.divider()

    # Load saved resumes including permanent ATS text
    conn = get_db_connection()

    resumes_df = pd.read_sql_query('''
        SELECT
            resume_id,
            user_id,
            resume_name,
            file_path,
            file_type,
            upload_date,
            ats_text
        FROM resumes
        WHERE user_id = ?
    ''', conn, params=(user_id,))

    conn.close()

    if resumes_df.empty:
        st.info("No resumes uploaded yet.")

    else:
        for idx, row in resumes_df.iterrows():

            st.markdown("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            col_info, col_action = st.columns([3, 1])

            # Resume information
            with col_info:

                st.markdown(
                    f"**Resume:** {row['resume_name']}"
                )

                st.markdown(
                    f"**Uploaded:** "
                    f"{row['upload_date'][:10] if row['upload_date'] else 'Unknown'}"
                )

                st.markdown(
                    f"**Type:** "
                    f"{row['file_type'].upper() if row['file_type'] else 'Unknown'}"
                )

                # View permanently stored ATS text
                if row['ats_text']:

                    if st.button(
                        "🔍 View ATS Text",
                        key=f"view_ats_{row['resume_id']}"
                    ):
                        st.text_area(
                            "OpenCATS Extracted Text",
                            row['ats_text'],
                            height=500,
                            key=f"ats_text_display_{row['resume_id']}"
                        )

                else:
                    st.caption("No ATS text available")

            # Actions
            with col_action:

                # View PDF
                if row['file_type'] == 'pdf':

                    if os.path.exists(row['file_path']):

                        with open(row['file_path'], "rb") as f:

                            pdf_base64 = base64.b64encode(
                                f.read()
                            ).decode('utf-8')

                            pdf_display = (
                                f'<iframe '
                                f'src="data:application/pdf;base64,{pdf_base64}" '
                                f'width="700" '
                                f'height="1000" '
                                f'type="application/pdf">'
                                f'</iframe>'
                            )

                            if st.button(
                                "View Resume",
                                key=f"view_res_{row['resume_id']}"
                            ):
                                st.markdown(
                                    pdf_display,
                                    unsafe_allow_html=True
                                )

                    else:
                        st.error("File not found")

                # Download resume
                if os.path.exists(row['file_path']):

                    with open(row['file_path'], "rb") as f:

                        st.download_button(
                            "Download",
                            data=f,
                            file_name=(
                                row['resume_name']
                                + "."
                                + row['file_type']
                            ),
                            key=f"dl_res_{row['resume_id']}"
                        )

                else:
                    st.warning("File missing")

                # Delete resume
                if st.button(
                    "🗑️ Delete",
                    key=f"del_res_{row['resume_id']}"
                ):

                    if os.path.exists(row['file_path']):
                        os.remove(row['file_path'])

                    conn = get_db_connection()
                    cursor = conn.cursor()

                    cursor.execute(
                        "DELETE FROM resumes WHERE resume_id = ?",
                        (row['resume_id'],)
                    )

                    conn.commit()
                    conn.close()

                    st.rerun()

            st.markdown("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

def render_analytics(user_id):
    st.header("📊 Performance Analytics")
    conn = get_db_connection()
    intvs_df = pd.read_sql_query('''
        SELECT i.*, a.company
        FROM interviews i
        JOIN applications a ON i.application_id = a.application_id
        WHERE a.user_id = ?
    ''', conn, params=(user_id,))
    conn.close()

    if intvs_df.empty:
        st.info("No interview data to analyze. Log some interviews first!")
        return

    intvs_df['date'] = pd.to_datetime(intvs_df['date'])
    intvs_df['month'] = intvs_df['date'].dt.strftime('%Y-%m')
    st.subheader("📈 Interview Performance Over Time")
    perf_df = intvs_df.groupby('month')['rating'].mean().reset_index()
    perf_df.columns = ['Month', 'Avg Rating']
    fig_perf = px.line(perf_df, x='Month', y='Avg Rating', markers=True,
                      title="Average Performance Rating by Month",
                      labels={'Avg Rating': 'Rating (1-5)'})
    fig_perf.update_yaxes(range=[0, 5])
    st.plotly_chart(fig_perf, use_container_width=True, key="analytics_perf_line")
    st.subheader("📅 Interview Volume")
    vol_df = intvs_df.groupby('month').size().reset_index(name='Count')
    fig_vol = px.bar(vol_df, x='month', y='Count', title="Interviews per Month")
    st.plotly_chart(fig_vol, use_container_width=True, key="analytics_vol_bar")
    st.subheader("🧩 Topic Distribution & Weak Areas")
    all_topics = []
    for t_str in intvs_df['topics'].dropna():
        topics = [t.strip() for t in t_str.split(',')]
        all_topics.extend(topics)
    if all_topics:
        topic_counts = pd.Series(all_topics).value_counts().reset_index()
        topic_counts.columns = ['Topic', 'Count']
        c1, c2 = st.columns(2)
        with c1:
            st.write("Frequency of Topics")
            fig_topics = px.bar(topic_counts, x='Count', y='Topic', orientation='h',
                               color='Count', color_continuous_scale='Viridis')
            st.plotly_chart(fig_topics, use_container_width=True, key="analytics_topics_bar")
        with c2:
            st.write("⚠️ **Identified Weak Areas**")
            weak_topics = []
            for _, row in intvs_df.iterrows():
                if row['rating'] < 3:
                    t_list = [t.strip() for t in str(row['topics']).split(',')]
                    weak_topics.extend(t_list)
            weak_counts = pd.Series(weak_topics).value_counts().reset_index()
            weak_counts.columns = ['Topic', 'Count']
            if not weak_counts.empty:
                st.table(weak_counts)
            else:
                st.write("No weak areas identified yet! Keep it up.")
    else:
        st.write("No topic data available.")

# --- Google Calendar Integration ---
def sync_to_google_calendar(task_description, deadline, company):
    """
    Authenticates with Google and adds a task to the user's calendar.
    """
    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    creds = None

    # The file credentials.json stores the client and secrets
    if os.path.exists('credentials.json'):
        try:
            # Attempt to load existing credentials from a local file
            if os.path.exists('token.json'):
                from google.oauth2.credentials import Credentials
                creds = Credentials.from_authorized_user_file('token.json', SCOPES)

            # If there are no (valid) credentials available, let the user log in.
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    # For Streamlit, we use local server flow which opens a browser tab
                    creds = flow.run_local_server(port=0)

                # Save the credentials for the next run
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())

            service = build('calendar', 'v3', credentials=creds)

            # Prepare event details
            start_date = deadline.strftime('%Y-%m-%dT09:00:00Z')
            end_date = deadline.strftime('%Y-%m-%dT10:00:00Z')

            event = {
                'summary': f"Job Task: {company} - {task_description}",
                'description': f"Deadline for {company} application task: {task_description}",
                'start': {'dateTime': start_date, 'timeZone': 'UTC'},
                'end': {'dateTime': end_date, 'timeZone': 'UTC'},
            }

            event = service.events().insert(calendarId='primary', body=event).execute()
            return True, f"Event created: {event.get('htmlLink')}"
        except Exception as e:
            return False, str(e)
    else:
        return False, "credentials.json not found. Please set up Google Cloud Console."

def render_reminders(user_id):
    st.header("⏰ Deadlines & Reminders")

    with st.expander("➕ Add Reminder"):
        with st.form("add_task_form", clear_on_submit=True):
            conn = get_db_connection()
            apps_df = pd.read_sql_query("SELECT application_id, company FROM applications WHERE user_id = ?", conn, params=(user_id,))
            conn.close()

            if apps_df.empty:
                st.warning("Please add an application first before setting reminders.")
                return

            app_options = {f"{a['company']} ({a['application_id']})": a['application_id'] for a in apps_df.to_dict('records')}
            selected_app = st.selectbox("Application", options=list(app_options.keys()), key="remind_app_select")
            task_desc = st.text_input("Task / Deadline (e.g. OA Deadline)", key="remind_desc")
            deadline = st.date_input("Deadline Date", datetime.now(), key="remind_date")

            if st.form_submit_button("Save Reminder", key="remind_submit"):
                if selected_app and task_desc:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO tasks (application_id, task_description, deadline) VALUES (?, ?, ?)",
                                   (app_options[selected_app], task_desc, deadline))
                    conn.commit()
                    conn.close()
                    st.success("Reminder added!")
                    st.rerun()
                else:
                    st.error("Application and Task description are required")

    st.divider()

    conn = get_db_connection()
    tasks_df = pd.read_sql_query('''
        SELECT t.task_id, t.task_description, t.deadline, t.completed, a.company
        FROM tasks t
        JOIN applications a ON t.application_id = a.application_id
        WHERE a.user_id = ?
    ''', conn, params=(user_id,))
    conn.close()

    if tasks_df.empty:
        st.info("No reminders set.")
        return

    tasks_df = tasks_df.sort_values('deadline')

    for idx, row in tasks_df.iterrows():
        with st.container():
            c1, c2, c3 = st.columns([3, 2, 1])
            with c1:
                st.markdown(f"**{row['company']}**: {row['task_description']}")
            with c2:
                st.markdown(f"📅 {row['deadline']}")
            with c3:
                # Use unique keys based on task_id
                is_done = st.checkbox("Done", key=f"task_done_{row['task_id']}", value=bool(row['completed']))
                if is_done != bool(row['completed']):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE tasks SET completed = ? WHERE task_id = ?", (1 if is_done else 0, row['task_id']))
                    conn.commit()
                    conn.close()
                    st.rerun()

                if st.button("🗑️", key=f"task_del_{row['task_id']}"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM tasks WHERE task_id = ?", (row['task_id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()
            st.divider()

def render_settings(user_id):
    st.header("⚙️ Settings & Data Management")

    st.subheader("🗑️ Application Data")
    st.warning("⚠️ This will permanently delete your applications, interview records, tasks, and application history. This cannot be undone.")
    confirm_app_data = st.checkbox("I understand that this will permanently delete my application data")

    if st.button("Clear My Application Data", key="clear_app_data_btn", disabled=not confirm_app_data):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT application_id FROM applications WHERE user_id = ?", (user_id,))
        app_ids = [row['application_id'] for row in cursor.fetchall()]

        if app_ids:
            id_list = ",".join(map(str, app_ids))
            cursor.execute(f"DELETE FROM application_history WHERE application_id IN ({id_list})")
            cursor.execute(f"DELETE FROM interviews WHERE application_id IN ({id_list})")
            cursor.execute(f"DELETE FROM tasks WHERE application_id IN ({id_list})")
            cursor.execute("DELETE FROM applications WHERE user_id = ?", (user_id,))
            conn.commit()
            st.success("All application data cleared successfully.")
        else:
            st.info("No data found to clear.")
        conn.close()
        st.rerun()

    st.divider()
    st.subheader("📄 Resume Data")
    st.warning("⚠️ This will permanently delete all your uploaded resumes and their physical files.")
    confirm_res_data = st.checkbox("I understand that this will permanently delete my resumes")

    if st.button("Delete My Uploaded Resumes", key="clear_res_data_btn", disabled=not confirm_res_data):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT resume_id, file_path FROM resumes WHERE user_id = ?", (user_id,))
        resumes = cursor.fetchall()

        for res in resumes:
            if os.path.exists(res['file_path']):
                os.remove(res['file_path'])

        cursor.execute("DELETE FROM resumes WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        st.success("All resume data and files deleted successfully.")
        st.rerun()

    st.divider()
    st.subheader("🛠️ Developer Options")
    if st.button("Restore Demo Data", key="restore_demo_btn"):
        import seed_data
        seed_data.seed_data()
        st.success("Demo data restored successfully!")
        st.rerun()

    st.divider()
    st.subheader("👤 Account Management")
    st.warning("⚠️ Deleting your account is permanent. All your applications, resumes, and settings will be erased forever.")
    confirm_acc_del = st.checkbox("I understand and I want to delete my account permanently")

    if st.button("Delete My Account", key="delete_account_btn", disabled=not confirm_acc_del):
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all data associated with the user for cleanup
        cursor.execute("SELECT application_id FROM applications WHERE user_id = ?", (user_id,))
        app_ids = [row['application_id'] for row in cursor.fetchall()]

        cursor.execute("SELECT resume_id, file_path FROM resumes WHERE user_id = ?", (user_id,))
        resumes = cursor.fetchall()

        # 1. Delete physical resume files
        for res in resumes:
            if os.path.exists(res['file_path']):
                try:
                    os.remove(res['file_path'])
                except Exception as e:
                    st.error(f"Could not delete file {res['file_path']}: {e}")

        # 2. Delete application-related data (Cascading)
        if app_ids:
            id_list = ",".join(map(str, app_ids))
            cursor.execute(f"DELETE FROM application_history WHERE application_id IN ({id_list})")
            cursor.execute(f"DELETE FROM interviews WHERE application_id IN ({id_list})")
            cursor.execute(f"DELETE FROM tasks WHERE application_id IN ({id_list})")

        # 3. Delete user-specific records
        cursor.execute("DELETE FROM applications WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM resumes WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

        conn.commit()
        conn.close()

        # Clear session and redirect to login
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.success("Account deleted successfully. You have been logged out.")
        st.rerun()

def render_ai_analyzer(user_id):
    st.markdown("## 🤖 AI Resume Analyzer")
    st.markdown("Compare your ATS-parsed resume with a job description to identify relevant skills, terminology, and potential gaps.")

    st.divider()

    # Reuse the resume file and OpenCATS text saved by render_resumes().
    conn = get_db_connection()
    saved_resumes = conn.execute(
        """
        SELECT resume_id, resume_name, file_path, file_type, ats_text
        FROM resumes
        WHERE user_id = ?
        ORDER BY upload_date DESC, resume_id DESC
        """,
        (user_id,)
    ).fetchall()
    conn.close()

    resume_by_name = {
        f"{resume['resume_name']} ({resume['file_type'].upper() if resume['file_type'] else 'FILE'})": resume
        for resume in saved_resumes
    }
    selected_resume = None
    if resume_by_name:
        selected_name = st.selectbox(
            "Uploaded Resume",
            ["Paste manually"] + list(resume_by_name.keys()),
            key="analyzer_resume_selection"
        )
        if selected_name != "Paste manually":
            selected_resume = resume_by_name[selected_name]

            with st.expander("📄 Uploaded Resume Preview", expanded=True):
                if os.path.exists(selected_resume["file_path"]):
                    if selected_resume["file_type"] == "pdf":
                        with open(selected_resume["file_path"], "rb") as resume_file:
                            pdf_base64 = base64.b64encode(resume_file.read()).decode("utf-8")
                        st.markdown(
                            f'<iframe src="data:application/pdf;base64,{pdf_base64}" '
                            'width="100%" height="700" type="application/pdf"></iframe>',
                            unsafe_allow_html=True
                        )
                    else:
                        with open(selected_resume["file_path"], "rb") as resume_file:
                            resume_bytes = resume_file.read()
                        st.download_button(
                            "Download uploaded resume",
                            data=resume_bytes,
                            file_name=os.path.basename(selected_resume["file_path"]),
                            key=f"analyzer_download_resume_{selected_resume['resume_id']}"
                        )
                else:
                    st.warning("Uploaded resume file is not available.")

            with st.expander("🔍 OpenCATS Parsed Resume Text", expanded=True):
                if selected_resume["ats_text"]:
                    st.text_area(
                        "Text extracted by OpenCATS",
                        selected_resume["ats_text"],
                        height=400,
                        key=f"analyzer_ats_text_{selected_resume['resume_id']}"
                    )
                else:
                    st.info("No parsed resume text available.")

    col1, col2 = st.columns(2)

    with col1:
        parsed_resume = st.text_area(
            "ATS Parsed Resume",
            value=selected_resume["ats_text"] if selected_resume else "",
            placeholder="Paste the resume text extracted by the ATS/OpenCATS here...",
            height=400
        )

    with col2:
        job_description = st.text_area(
            "Job Description",
            placeholder="Paste the complete job description here...",
            height=400
        )

    st.markdown(" ") # Spacer

    if st.button("Analyze Resume", type="primary"):
        if not parsed_resume or not job_description:
            st.warning("Please provide both the ATS-parsed resume and the job description.")
        else:
            try:
                with st.spinner("AI is analyzing your resume... Please wait."):
                    # 1. Extract Requirements
                    requirements = extract_jd_requirements(job_description)

                    # 2. Get semantic analysis from existing analyzer
                    # PASS REQUIREMENTS TO FORCE LABEL CONSISTENCY
                    result = analyze_resume(parsed_resume, job_description, requirements=requirements)

                    # 3. Calculate Weighted Match Score
                    score, breakdown_data = calculate_match_score(requirements, result)

                    # 4. Generate Explainable Report
                    report = generate_explainable_report(requirements, result)


                st.success("Analysis Complete!")
                st.divider()

                # --- CANONICAL DATA OBJECT ---
                canonical_match_result = {
                    "final_report": report,
                    "ai_result": result,
                    "jd_requirements": requirements
                }

                st.success("Analysis Complete!")
                st.divider()

                # Show the existing pipeline inputs and outputs before the final score.
                with st.expander("📄 Resume Analysis / Parsed Resume Data", expanded=False):
                    st.text_area(
                        "OpenCATS Parsed Resume Text",
                        parsed_resume,
                        height=300,
                        key="analysis_parsed_resume_display"
                    )
                    resume_analysis = {}
                    if isinstance(result, dict):
                        for analysis_key in ("resume_analysis", "resume_data", "parsed_resume_data"):
                            if result.get(analysis_key):
                                resume_analysis = result[analysis_key]
                                break
                    if resume_analysis:
                        st.json(resume_analysis)

                with st.expander("📋 Job Description Analysis / Extracted Requirements", expanded=False):
                    if requirements:
                        st.dataframe(
                            [
                                {
                                    "Requirement": requirement.get("item", ""),
                                    "Category": requirement.get("category", "General"),
                                    "Importance": requirement.get("importance", "REQUIRED")
                                }
                                for requirement in requirements
                                if isinstance(requirement, dict)
                            ],
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.info("No job description requirements were extracted.")

                with st.expander("🔗 Requirement Matching", expanded=False):
                    matching_rows = []
                    for status, items in (
                        ("MATCHED", report.get("matched", [])),
                        ("PARTIALLY MATCHED", report.get("partially_matched", [])),
                        ("MISSING", report.get("missing", [])),
                    ):
                        for item in items:
                            if isinstance(item, dict):
                                matching_rows.append({
                                    "Status": status,
                                    "Requirement": item.get("item", ""),
                                    "Evidence": item.get("evidence", ""),
                                    "Reason": item.get("reason", "")
                                })
                    if matching_rows:
                        st.dataframe(matching_rows, use_container_width=True, hide_index=True)
                    else:
                        st.info("No requirement matching data available.")

                # --- PROMINENT MATCH SCORE ---
                st.markdown(f"""
                <div style="text-align: center; padding: 2rem; background-color: var(--bg-card); border: 2px solid var(--primary); border-radius: var(--radius-lg); margin-bottom: 2rem;">
                    <div style="color: var(--text-muted); font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem;">RESUME–JOB MATCH</div>
                    <div style="font-size: 4rem; font-weight: 800; color: var(--primary); margin-bottom: 0.5rem;">{score}%</div>
                    <div style="color: var(--text-main); font-size: 1.1rem; margin-bottom: 1rem;">Your resume has a {score}% match with this job description.</div>
                    <div style="font-size: 0.85rem; color: var(--text-muted); font-style: italic; max-width: 600px; margin: 0 auto;">
                        This score measures how closely the information in your resume matches the requirements identified in this job description. <br>
                        It is not a prediction of hiring probability.
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # --- MATCH SCORE BREAKDOWN ---
                st.markdown("#### 📊 Resume–JD Match Score Breakdown")
                b_col1, b_col2 = st.columns(2)

                with b_col1:
                    summary = breakdown_data.get("summary", {})
                    req = summary.get("Required", {"matched": 0, "total": 0})
                    pref = summary.get("Preferred", {"matched": 0, "total": 0})
                    st.markdown(f"**Required Skills:** {req['matched']:.1f} / {req['total']}")
                    st.markdown(f"**Preferred Skills:** {pref['matched']:.1f} / {pref['total']}")

                with b_col2:
                    cats = breakdown_data.get("categories", {})
                    for cat, perc in cats.items():
                        st.markdown(f"**{cat}:** {perc}%")

                st.markdown("---")
                st.subheader("🤖 AI Analysis Results")

                # Define a helper for safe item rendering
                def get_item_text(item):
                    if isinstance(item, str): return item
                    if isinstance(item, dict):
                        return item.get("item") or item.get("requirement") or item.get("text") or str(item)
                    return str(item)

                def get_valid_phrasing(items):
                    valid_items = []
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        current = item.get("current_phrase") or item.get("original")
                        suggested = (
                            item.get("suggested_phrase")
                            or item.get("suggested")
                            or item.get("replacement")
                        )
                        if isinstance(current, str) and isinstance(suggested, str):
                            current = current.strip()
                            suggested = suggested.strip()
                            if current and suggested:
                                valid_items.append((item, current, suggested))
                    return valid_items

                # Result sections configuration
                # format: (UI Title, Canonical Key, Data Source, Empty Message)
                sections = [
                    ("✅ MATCHED", "matched", "final_report", "No clearly represented skills found."),
                    ("⚠ PARTIALLY MATCHED", "partially_matched", "final_report", "No conceptual matches found."),
                    ("❌ MISSING", "missing", "final_report", "All requirements appear to be covered!"),
                    ("📌 Important Job Requirements", "jd_requirements", "canonical", "No specific requirements identified."),
                    ("🔎 Evidence Gaps", "evidence_gaps", "final_report", "No significant evidence gaps found."),
                    ("💡 Safe Improvement Suggestions", "evidence_gaps", "final_report", "No improvement suggestions at this time."),
                    ("🚀 Keyword Optimization", "keyword_optimization", "final_report", "No specific keywords identified for optimization.")
                ]

                for title, key, source, empty_msg in sections:
                    st.markdown(f"### {title}")

                    # Extract data from the correct source
                    if source == "canonical":
                        data = canonical_match_result.get(key)
                    else:
                        data_source = canonical_match_result.get(source, {})
                        data = data_source.get(key)

                    if data:
                        if key == "jd_requirements":
                            # Separate into Required and Preferred
                            required = [r.get("item", "") for r in data if r.get("importance") == "REQUIRED"]
                            preferred = [r.get("item", "") for r in data if r.get("importance") == "PREFERRED"]

                            if required:
                                st.markdown("**Required:**")
                                for req_item in required:
                                    st.markdown(f"- {req_item}")

                            if preferred:
                                st.markdown("**Preferred:**")
                                for pref_item in preferred:
                                    st.markdown(f"- {pref_item}")

                        elif key == "keyword_optimization":
                            # Handle Power Words (List of Strings or List of Dicts)
                            # The AI is now instructed to append truthfulness warnings, so these may be strings or dicts.
                            data_val = data if isinstance(data, dict) else {}
                            if isinstance(data, dict) and data.get("keyword"):
                                power_words = [data]
                            elif isinstance(data, dict):
                                power_words = data.get("missing_power_words", [])
                            else:
                                power_words = data

                            if power_words:
                                rendered_keywords = []
                                for word in power_words:
                                    if isinstance(word, dict):
                                        word_text = word.get("keyword")
                                        warning = word.get("warning") or word.get("reason") or "Add only if you genuinely have this experience."
                                    elif isinstance(word, str):
                                        word_text = word
                                        warning = "Add only if you genuinely have this experience."
                                    else:
                                        continue
                                    if not isinstance(word_text, str) or not word_text.strip():
                                        continue
                                    rendered_keywords.append((word_text.strip(), warning))

                                if rendered_keywords:
                                    st.markdown("**Missing Power Words:**")
                                for word_text, warning in rendered_keywords:
                                    st.markdown(f"""
                                    <div class="analysis-card">
                                        <div class="analysis-card-header">✨ {word_text}</div>
                                        <div style="color: var(--text-muted); font-size: 0.9rem;">{warning}</div>
                                    </div>
                                    """, unsafe_allow_html=True)

                            # Handle Phrasing Suggestions (List of Dicts)
                            if isinstance(data, dict):
                                phrasing = []
                                for suggestions_key in (
                                    "optimization_suggestions",
                                    "suggested_phrasing_changes",
                                    "suggested_phrasing",
                                ):
                                    suggestions = data.get(suggestions_key, [])
                                    if isinstance(suggestions, list):
                                        phrasing.extend(suggestions)
                                phrasing = get_valid_phrasing(phrasing)
                                if phrasing:
                                    st.markdown("**Suggested Phrasing:**")
                                    for sug, curr, sug_txt in phrasing:
                                        reason = sug.get("reasoning", "")
                                        st.markdown(f"""
                                        <div class="analysis-card">
                                            <div class="analysis-card-header">🔄 {curr} → {sug_txt}</div>
                                            <div style="color: var(--text-muted); font-size: 0.9rem;">{reason}</div>
                                        </div>
                                        """, unsafe_allow_html=True)

                        elif key == "evidence_gaps":
                            # This block handles BOTH "Evidence Gaps" and "Safe Improvement Suggestions"
                            # depending on which title is currently being rendered.
                            if title == "🔎 Evidence Gaps":
                                for gap in data:
                                    if isinstance(gap, dict):
                                        req_text = gap.get("requirement") or get_item_text(gap)
                                        gap_text = gap.get("gap", "No gap described")
                                        sug_text = gap.get("suggestion", "No suggestion provided")
                                    else:
                                        req_text = get_item_text(gap)
                                        gap_text = "No gap described"
                                        sug_text = "No suggestion provided"
                                    st.markdown(f"""
                                    <div class="analysis-card">
                                        <div class="analysis-card-header">⚠️ {req_text}</div>
                                        <div style="margin-bottom: 8px;"><strong>Gap:</strong> {gap_text}</div>
                                        <div style="color: var(--primary);"><strong>Suggestion:</strong> {sug_text}</div>
                                    </div>
                                    """, unsafe_allow_html=True)
                            else:
                                # Rendering for "💡 Safe Improvement Suggestions"
                                suggestions_found = False
                                for gap in data:
                                    suggestion = gap.get("suggestion") if isinstance(gap, dict) else None
                                    if suggestion:
                                        suggestions_found = True
                                        st.markdown(f"""
                                        <div class="analysis-card">
                                            <div class="analysis-card-header">💡 {suggestion}</div>
                                        </div>
                                        """, unsafe_allow_html=True)

                                if not suggestions_found:
                                    st.info(empty_msg)
                                    # Skip the final empty_msg display at the end of the loop
                                    continue

                        elif key == "optimization_suggestions":
                            # This key is no longer used in 'sections' but kept for safety
                            for sug, curr, sug_txt in get_valid_phrasing(data):
                                reason = sug.get("reasoning", "")

                                st.markdown(f"""
                                <div class="analysis-card">
                                    <div class="analysis-card-header">💡 {curr} → {sug_txt}</div>
                                    <div style="color: var(--text-muted); font-size: 0.9rem;">{reason}</div>
                                </div>
                                """, unsafe_allow_html=True)

                        else:
                            # Generic renderer for MATCHED, PARTIAL, MISSING
                            for item in data:
                                item_txt = get_item_text(item)
                                if key == "matched":
                                    evidence = item.get('evidence', 'Matched') if isinstance(item, dict) else 'Matched'
                                    content = f"**{item_txt}**: {evidence}"
                                elif key == "partially_matched":
                                    evidence = item.get('evidence', 'N/A') if isinstance(item, dict) else 'N/A'
                                    reason = item.get('reason', 'N/A') if isinstance(item, dict) else 'N/A'
                                    content = f"**{item_txt}**<br><small>Evidence: {evidence}<br>Reason: {reason}</small>"
                                elif key == "missing":
                                    reason = item.get('reason', 'No reason provided') if isinstance(item, dict) else 'No reason provided'
                                    content = f"**{item_txt}**: {reason}"
                                else:
                                    content = str(item)

                                st.markdown(f"""
                                <div class="analysis-card">
                                    <div>{content}</div>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info(empty_msg)
                    st.markdown(" ")

            except ConnectionError as e:
                st.error(str(e))
            except RuntimeError as e:
                st.error(str(e))
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

# --- entry point ---
if st.session_state.authenticated:
    main_app()
else:
    login_page()

if __name__ == "__main__":
    pass

def get_opencats_text(attachment_id):
    conn = mysql.connector.connect(
        host="localhost",
        port=3003,
        user="root",
        password="admin",
        database="opencats"
    )

    cursor = conn.cursor()
    cursor.execute(
        "SELECT text FROM attachment WHERE attachment_id = %s",
        (attachment_id,)
    )

    result = cursor.fetchone()

    cursor.close()
    conn.close()

    return result[0] if result and result[0] else ""