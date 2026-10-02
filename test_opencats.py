import requests
import re

OPENCATS_URL = "http://localhost:4000"

USERNAME = "admin"
PASSWORD = "admin"

RESUME_PATH = r"D:\Job Application Tracker\resumes\9_20260924141933_Aarush.pdf"

session = requests.Session()

# 1. Login

login_url = f"{OPENCATS_URL}/index.php?m=login&a=attemptLogin"

login_response = session.post(
    login_url,
    data={
        "username": USERNAME,
        "password": PASSWORD
    },
    allow_redirects=False
)

print("Login status:", login_response.status_code)

if login_response.status_code != 302:
    print("Login failed")
    exit()

print("Login successful")


# 2. Open candidate-add page to get CSRF token

candidate_url = f"{OPENCATS_URL}/index.php?m=candidates&a=add"

page_response = session.get(candidate_url)

print("Candidate page status:", page_response.status_code)

match = re.search(
    r'name=["\']csrfToken["\'][^>]*value=["\']([^"\']*)["\']',
    page_response.text
)

if not match:
    print("CSRF token not found")
    exit()

csrf_token = match.group(1)

print("CSRF token found")


# 3. Upload resume to OpenCATS parser

data = {
    "postback": "postback",
    "csrfToken": csrf_token,
    "loadDocument": "true",
    "parseDocument": "true",
    "firstName": "Aarush",
    "lastName": "Naskar"
}

with open(RESUME_PATH, "rb") as resume:
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

print("Parser response:", response.status_code)

if "Invalid request." in response.text:
    print("OpenCATS rejected the request.")
    exit()

print("Resume accepted by OpenCATS")


# Extract parsed fields

def get_field(name):
    pattern = rf'name=["\']{re.escape(name)}["\'][^>]*value=["\']([^"\']*)["\']'
    match = re.search(pattern, response.text)

    if match:
        return match.group(1)

    return ""


first_name = get_field("firstName")
last_name = get_field("lastName")
email = get_field("email1")
document_temp_file = get_field("documentTempFile")

text_match = re.search(
    r'<textarea[^>]*name=["\']documentText["\'][^>]*>(.*?)</textarea>',
    response.text,
    re.DOTALL
)

document_text = text_match.group(1).strip() if text_match else ""

print("First name:", first_name)
print("Last name:", last_name)
print("Email:", email)
print("Temporary file:", document_temp_file)
print("Resume text length:", len(document_text))


# Submit Candidate

final_data = {
    "postback": "postback",
    "csrfToken": csrf_token,
    "firstName": first_name or "Aarush",
    "lastName": last_name or "Naskar",
    "email1": email,
    "documentText": document_text,
    "documentTempFile": document_temp_file
}

final_response = session.post(
    candidate_url,
    data=final_data,
    allow_redirects=False
)

print("Final response:", final_response.status_code)
print("Redirect:", final_response.headers.get("Location"))


# Check result

if final_response.status_code == 302:

    location = final_response.headers.get("Location", "")

    if "candidateID=" in location:
        print()
        print("SUCCESS: Candidate created in OpenCATS.")
        print("Candidate URL:", location)

    else:
        print()
        print("OpenCATS redirected, but candidate ID was not found.")

else:

    print()
    print("Candidate creation failed.")

    with open("candidate_error.html", "w", encoding="utf-8") as f:
        f.write(final_response.text)

    print("Saved candidate_error.html")