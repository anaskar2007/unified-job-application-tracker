import json
from ai.jd_matcher import extract_jd_requirements, calculate_match_score, generate_explainable_report
from ai.jd_resume_analyzer import analyze_resume

# Test Case: Google SE III Infrastructure
test_resume = """
Experience:
- 3 years as Software Engineer at TechCorp.
- Developed distributed systems using C++, Python, and Go.
- Optimized network throughput by 20% using custom TCP/IP protocols.
- Experience with Kubernetes, Docker, and AWS (EC2, S3).
- Built high-availability services handling 1M+ RPS.
Education:
- BS in Computer Science, Stanford University.
Skills:
- C++, Python, Go, Distributed Systems, Networking, Kubernetes, Docker, AWS, Linux.
"""

test_jd = """
Role: Software Engineer III, Infrastructure
Requirements:
- BS or MS in Computer Science or related field (Required)
- 2+ years of professional software development experience (Required)
- Proficiency in C++ or Java (Required)
- Experience with Distributed Systems or Large-scale Infrastructure (Required)
- Knowledge of Networking/TCP/IP (Required)
- Experience with Kubernetes and Docker (Preferred)
- Experience with Cloud Platforms (AWS/GCP/Azure) (Preferred)
- Master's Degree in CS (Preferred)
"""

def run_verification():
    print("--- Starting Verification: Google SE III Infrastructure ---")
    
    # 1. Extract Requirements
    print("\n[1/4] Extracting JD Requirements...")
    requirements = extract_jd_requirements(test_jd)
    print(f"Extracted {len(requirements)} requirements.")
    for i, req in enumerate(requirements):
        print(f"  {i+1}. {req['item']} ({req['importance']})")
    
    # 2. Analyze Resume
    print("\n[2/4] Analyzing Resume...")
    ai_analysis = analyze_resume(test_resume, test_jd, requirements=requirements)
    
    # 3. Calculate Score
    print("\n[3/4] Calculating Weighted Score...")
    score, breakdown = calculate_match_score(requirements, ai_analysis)
    print(f"Calculated Match Score: {score}%")
    
    # 4. Generate Report
    print("\n[4/4] Generating Explainable Report...")
    report = generate_explainable_report(requirements, ai_analysis)
    
    # Validation
    print("\n--- Final Validation Results ---")
    
    # Check Score (Expected approx 90%+)
    if score >= 90:
        print("Score is in expected range (>= 90%).")
    else:
        print(f"Score {score}% is lower than expected.")
        
    # Check Matched (Expected: BS, 2+ years, C++, Distributed Systems, Networking)
    matched_items = [m['item'].lower() for m in report['matched']]
    essential_matches = ['bs', 'experience', 'c++', 'distributed systems', 'networking']
    match_count = 0
    for e in essential_matches:
        if any(e in m for m in matched_items):
            match_count += 1
    print(f"Essential matches found: {match_count}/{len(essential_matches)}")
    
    # Check Missing (Expected: Master's Degree)
    missing_items = [m['item'].lower() for m in report['missing']]
    if any('master' in m for m in missing_items):
        print("Master's degree correctly identified as missing.")
    else:
        print("Master's degree NOT identified as missing.")

    print("\nFull Report Summary:")
    print(f"Matched: {len(report['matched'])}")
    print(f"Partially Matched: {len(report['partially_matched'])}")
    print(f"Missing: {len(report['missing'])}")

if __name__ == "__main__":
    run_verification()
