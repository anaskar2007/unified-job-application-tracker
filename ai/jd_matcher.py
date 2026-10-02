import json
import requests
from ai.jd_resume_analyzer import analyze_resume

# --- Configuration ---
MODEL_NAME = "gemma4:31b-cloud"
OLLAMA_URL = "http://localhost:11434/api/chat"

def normalize_term(text):
    """
    Basic normalization to improve matching consistency.
    """
    if not text:
        return ""
    # Lowercase, strip whitespace, and remove common filler words
    text = text.lower().strip()
    fillers = ["knowledge of ", "experience with ", "proficiency in ", "skilled in "]
    for filler in fillers:
        text = text.replace(filler, "")
    return text.strip()

def is_semantic_match(req_item, rep_item):
    """
    Checks if two terms are semantically similar.
    Handles 'OR' logic in requirements (e.g., 'C++ or Java').
    """
    # Handle OR conditions in the requirement
    if " or " in req_item.lower():
        options = [opt.strip() for opt in req_item.lower().split(" or ")]
        for option in options:
            if is_semantic_match(option, rep_item):
                return True
        return False

    req = normalize_term(req_item)
    rep = normalize_term(rep_item)

    if not req or not rep:
        return False

    # Exact match
    if req == rep:
        return True

    # Containment match (e.g., "Python" in "Python 3")
    if req in rep or rep in req:
        return True

    return False

def get_requirement_assessments(requirements, ai_analysis):
    """Return one validated status per JD requirement, preserving exact JD labels."""
    if not isinstance(ai_analysis, dict):
        return {}
    if 'semantic_match_analysis' in ai_analysis:
        ai_analysis = ai_analysis['semantic_match_analysis']

    assessments = ai_analysis.get('requirement_assessments', [])
    status_by_item = {}
    if isinstance(assessments, list):
        for assessment in assessments:
            if not isinstance(assessment, dict):
                continue
            item = assessment.get('item')
            status = assessment.get('status')
            if item and status in {'MATCHED', 'PARTIALLY_MATCHED', 'MISSING'}:
                status_by_item[normalize_term(item)] = assessment

    # Backward compatibility for older model responses and existing saved results.
    for key, status in (
        ('represented', 'MATCHED'),
        ('possibly_represented', 'PARTIALLY_MATCHED'),
        ('not_found', 'MISSING'),
    ):
        values = ai_analysis.get(key, [])
        if not isinstance(values, list):
            continue
        for value in values:
            item = value.get('item', '') if isinstance(value, dict) else value
            if item:
                normalized_item = normalize_term(item)
                entry = value.copy() if isinstance(value, dict) else {'item': item}
                entry['status'] = status
                status_by_item.setdefault(normalized_item, entry)

    return {
        normalize_term(req['item']): status_by_item[normalize_term(req['item'])]
        for req in requirements
        if isinstance(req, dict) and req.get('item')
        and normalize_term(req['item']) in status_by_item
    }

def _supporting_analysis(ai_analysis):
    """Preserve supporting analyzer fields across the canonical report boundary."""
    if not isinstance(ai_analysis, dict):
        return [], {}

    source = ai_analysis.get('semantic_match_analysis', ai_analysis)
    evidence_gaps = source.get('evidence_gaps', ai_analysis.get('evidence_gaps', []))
    if not isinstance(evidence_gaps, list):
        evidence_gaps = []

    keyword_optimization = source.get('keyword_optimization')
    if keyword_optimization is None:
        keyword_optimization = ai_analysis.get('keyword_optimization')
    if keyword_optimization is None:
        keyword_optimization = {}
        for key in (
            'missing_power_words',
            'optimization_suggestions',
            'suggested_phrasing_changes',
            'suggested_phrasing',
        ):
            if key in source:
                keyword_optimization[key] = source[key]
            elif key in ai_analysis:
                keyword_optimization[key] = ai_analysis[key]
    elif not isinstance(keyword_optimization, (dict, list)):
        keyword_optimization = {}

    return evidence_gaps, keyword_optimization

def extract_jd_requirements(job_description):
    """
    Uses AI to extract a structured list of requirements from a JD,
    categorizing them as Required or Preferred.
    """
    system_prompt = """
    You are a technical recruitment expert. Extract a structured list of requirements from the provided Job Description.

    ### CATEGORIES TO IDENTIFY:
    - Programming Languages
    - Frameworks & Libraries
    - Databases
    - Cloud Technologies
    - DevOps & Tools
    - Machine Learning / AI
    - Core CS Concepts
    - Education & Experience
    - Soft Skills

    ### RULES:
    1. Distinguish between 'REQUIRED' (must-have) and 'PREFERRED' (nice-to-have).
    2. Be precise. Use industry-standard names (e.g., "C++" instead of "Proficiency in C++").
    3. Handle "OR" conditions by grouping them into a single item (e.g., "C++ or Java", "AWS or GCP or Azure"). This is critical for accurate scoring.
    4. Do not extract generic phrases like "ability to work in a team".
    5. Return ONLY a valid JSON object.

    ### OUTPUT SCHEMA:
    {
      "requirements": [
        {
          "item": "Skill Name",
          "category": "Category Name",
          "importance": "REQUIRED" | "PREFERRED"
        }
      ]
    }
    """

    user_prompt = f"JOB DESCRIPTION:\n{job_description}"

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "seed": 42, "top_p": 0}
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        response_text = response.json().get("message", {}).get("content", "")

        # Clean markdown wrappers if present
        if "```json" in response_text:
            import re
            match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if match: response_text = match.group(1)

        return json.loads(response_text).get("requirements", [])
    except Exception as e:
        print(f"Error extracting JD requirements: {e}")
        return []

def calculate_match_score(requirements, ai_analysis):
    """
    Calculates a weighted match score based on the AI's semantic analysis.

    Weights:
    - Required Match: 1.0
    - Preferred Match: 0.5
    - Partial Match: 0.5 * Weight
    """
    if not requirements:
        return 0, {}

    # Ensure ai_analysis is a dictionary
    if not isinstance(ai_analysis, dict):
        return 0, {}

    # Support nested structure: {"semantic_match_analysis": {...}}
    if 'semantic_match_analysis' in ai_analysis:
        ai_analysis = ai_analysis['semantic_match_analysis']

    assessments = get_requirement_assessments(requirements, ai_analysis)

    total_potential_weight = 0
    earned_weight = 0

    # Breakdown for transparency
    breakdown = {
        "Required": {"matched": 0, "total": 0},
        "Preferred": {"matched": 0, "total": 0},
        "Categories": {} # Category-specific stats
    }

    for req in requirements:
        # Handle cases where req might not be a dictionary
        if not isinstance(req, dict) or 'item' not in req:
            continue

        item_name = req['item']
        category = req.get('category', 'General')
        importance = req.get('importance', 'REQUIRED')

        weight = 1.0 if importance == "REQUIRED" else 0.5
        total_potential_weight += weight

        # Track totals for transparency
        if importance == "REQUIRED":
            breakdown["Required"]["total"] += 1
        else:
            breakdown["Preferred"]["total"] += 1

        assessment = assessments.get(normalize_term(item_name), {})
        status = assessment.get('status')
        match_value = 0
        if status == 'MATCHED':
            match_value = weight
            if importance == "REQUIRED":
                breakdown["Required"]["matched"] += 1
            else:
                breakdown["Preferred"]["matched"] += 1
        elif status == 'PARTIALLY_MATCHED':
            match_value = weight * 0.5
            if importance == "REQUIRED":
                breakdown["Required"]["matched"] += 0.5
            else:
                breakdown["Preferred"]["matched"] += 0.5

        earned_weight += match_value

        # Category breakdown
        if category not in breakdown["Categories"]:
            breakdown["Categories"][category] = {"earned": 0, "total": 0}
        breakdown["Categories"][category]["earned"] += match_value
        breakdown["Categories"][category]["total"] += weight

    final_score = (earned_weight / total_potential_weight * 100) if total_potential_weight > 0 else 0

    # Convert category breakdown to percentages
    category_percentages = {}
    for cat, values in breakdown["Categories"].items():
        category_percentages[cat] = round((values["earned"] / values["total"] * 100), 1) if values["total"] > 0 else 0

    return int(round(final_score)), {
        "summary": breakdown,
        "categories": category_percentages
    }

def generate_explainable_report(requirements, ai_analysis):
    """
    Transforms raw AI output into the explainable report format.
    """
    if not isinstance(ai_analysis, dict):
        return {
            "matched": [],
            "partially_matched": [],
            "missing": [],
            "keyword_coverage": {"found": [], "missing": [], "weak": []}
        }

    original_ai_analysis = ai_analysis

    # Support nested structure: {"semantic_match_analysis": {...}}
    if 'semantic_match_analysis' in ai_analysis:
        ai_analysis = ai_analysis['semantic_match_analysis']

    report = {
        "matched": [],
        "partially_matched": [],
        "missing": [],
        "evidence_gaps": [],
        "keyword_optimization": {},
        "keyword_coverage": {
            "found": [],
            "missing": [],
            "weak": []
        }
    }

    report["evidence_gaps"], report["keyword_optimization"] = _supporting_analysis(original_ai_analysis)

    # Create a map of all requirements for easy lookup
    req_map = {}
    for req in requirements:
        if isinstance(req, dict) and 'item' in req:
            req_map[req['item'].lower()] = req

    assessments = get_requirement_assessments(requirements, ai_analysis)

    # Instead of iterating over AI output, we iterate over the JD requirements
    # This ensures every requirement is accounted for in Matched, Partial, or Missing.
    for req in requirements:
        if not isinstance(req, dict) or 'item' not in req: continue

        item_name = req['item']
        norm_item = normalize_term(item_name)

        assessment = assessments.get(norm_item, {})
        status = assessment.get('status')

        if status == 'MATCHED':
            evidence = assessment.get('evidence', 'Matched')

            report["matched"].append({
                "item": item_name,
                "evidence": evidence,
                "importance": req.get('importance', 'N/A')
            })
            report["keyword_coverage"]["found"].append(item_name)

        elif status == 'PARTIALLY_MATCHED':
            evidence = assessment.get('evidence', 'Partial match found')
            reason = assessment.get('reason', 'Related evidence does not fully satisfy the requirement.')

            report["partially_matched"].append({
                "item": item_name,
                "evidence": evidence,
                "reason": reason,
                "importance": req.get('importance', 'N/A')
            })
            report["keyword_coverage"]["weak"].append(item_name)

        else:
            # Not in represented or possibly_represented -> Missing
            # Try to find specific reason from AI's not_found list
            reason = assessment.get('reason', "No evidence found in resume")

            report["missing"].append({
                "item": item_name,
                "reason": reason,
                "importance": req.get('importance', 'N/A')
            })
            report["keyword_coverage"]["missing"].append(item_name)

    return report
