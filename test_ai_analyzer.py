import os
import json
from ai.jd_resume_analyzer import analyze_resume

# Test Data
test_resume = """
Python, C++, Docker, SQL.
Built backend APIs using Flask.
"""

test_jd = """
Looking for a Software Engineer with Python,
Docker, AWS, REST APIs and Kubernetes.
Experience with cloud deployment and microservices.
"""

def run_test():
    print("--- Running Ollama AI Resume Analyzer Test (gemma4:31b-cloud) ---")
    print(f"Resume:\n{test_resume}")
    print(f"\nJD:\n{test_jd}\n")

    try:
        result = analyze_resume(test_resume, test_jd)
        print("--- AI Result ---")
        print(json.dumps(result, indent=2))

        # Verifications
        represented = [item['item'].lower() for item in result.get('represented', [])]
        possibly = [item['item'].lower() for item in result.get('possibly_represented', [])]

        aws_found = 'aws' in represented
        k8s_found = 'kubernetes' in represented
        rest_possibly = any('rest' in item for item in possibly)

        print("\n--- Verifications ---")
        print(f"AWS incorrectly claimed as present: {aws_found}")
        print(f"Kubernetes incorrectly claimed as present: {k8s_found}")
        print(f"REST APIs recognized as Possibly Represented (via Flask): {rest_possibly}")

        if not aws_found and not k8s_found and (rest_possibly or any('rest' in item for item in represented)):
            print("\n[PASS] TEST PASSED: Semantic matching works and hallucination is prevented.")
        else:
            print("\n[FAIL] TEST FAILED: AI did not meet the semantic/anti-hallucination requirements.")

    except Exception as e:
        print(f"\n[ERROR]: {e}")

if __name__ == "__main__":
    run_test()
