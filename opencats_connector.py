import requests
import re

OPENCATS_URL = "http://localhost:4000"
USERNAME = "admin"
PASSWORD = "admin"


def send_resume_to_opencats(resume_path):

    session = requests.Session()

    # Login
    login_response = session.post(
        f"{OPENCATS_URL}/index.php?m=login&a=attemptLogin",
        data={
            "username": USERNAME,
            "password": PASSWORD
        },
        allow_redirects=False
    )

    if login_response.status_code != 302:
        return {
            "success": False,
            "error": "OpenCATS login failed"
        }

    # Get candidate page
    candidate_url = f"{OPENCATS_URL}/index.php?m=candidates&a=add"
    page_response = session.get(candidate_url)

    match = re.search(
        r'name=["\']csrfToken["\'][^>]*value=["\']([^"\']+)',
        page_response.text
    )

    if not match:
        return {
            "success": False,
            "error": "OpenCATS CSRF token not found"
        }

    csrf_token = match.group(1)

    # Upload and parse resume
    data = {
        "postback": "postback",
        "csrfToken": csrf_token,
        "loadDocument": "true",
        "parseDocument": "true",
        "firstName": "Candidate",
        "lastName": "Resume"
    }

    with open(resume_path, "rb") as resume:
        files = {
            "documentFile": (
                "resume.pdf",
                resume,
                "application/pdf"
            )
        }

        response = session.post(
            candidate_url,
            data=data,
            files=files
        )

    if "Invalid request." in response.text:
        return {
            "success": False,
            "error": "OpenCATS rejected the resume"
        }

    # Extract fields
    def get_field(name):
        pattern = rf'name=["\']{name}["\'][^>]*value=["\']([^"\']*)'
        match = re.search(pattern, response.text)

        if match:
            return match.group(1)

        return ""

    first_name = get_field("firstName")
    last_name = get_field("lastName")
    email = get_field("email1")
    document_temp_file = get_field("documentTempFile")

    # Extract parsed resume text
    text_match = re.search(
        r'<textarea[^>]*name=["\']documentText["\'][^>]*>(.*?)</textarea>',
        response.text,
        re.DOTALL
    )

    document_text = (
        text_match.group(1).strip()
        if text_match
        else ""
    )

    # Create candidate
    final_data = {
        "postback": "postback",
        "csrfToken": csrf_token,
        "firstName": first_name or "Candidate",
        "lastName": last_name or "Resume",
        "email1": email,
        "documentText": document_text,
        "documentTempFile": document_temp_file
    }

    final_response = session.post(
        candidate_url,
        data=final_data,
        allow_redirects=False
    )

    location = final_response.headers.get("Location", "")

    if final_response.status_code == 302 and "candidateID=" in location:

        candidate_id = location.split("candidateID=")[-1]

        return {
            "success": True,
            "candidate_id": candidate_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "resume_text": document_text,
            "url": location
        }

    return {
        "success": False,
        "error": "OpenCATS candidate creation failed"
    }