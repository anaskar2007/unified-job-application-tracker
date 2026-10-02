import json
import requests
from datetime import date

# --- Configuration ---
MODEL_NAME = "gemma4:31b-cloud"
OLLAMA_URL = "http://localhost:11434/api/chat"

def analyze_resume(parsed_resume, job_description, requirements=None):
    """
    Analyzes the semantic match between a parsed resume and a job description using Ollama (gemma4:31b-cloud).
    If requirements are provided, the AI is forced to use those specific terms for consistency.
    """

    # --- System Prompt ---
    system_prompt = """
You are an expert technical recruiter and resume analyzer. Your task is to semantically compare an ATS-parsed resume against a job description.

### CRITICAL RULES:
1. **NO HALLUCINATIONS**: Never invent experience. Never assume the candidate has a skill if it's not in the resume.
2. **EVIDENCE-BASED CLASSIFICATION**: Assess each supplied JD requirement individually using only evidence explicitly present in the resume.
    - MATCHED: explicit and sufficient evidence satisfies the requirement.
    - PARTIALLY_MATCHED: genuinely related evidence exists, but it does not fully satisfy the requirement.
    - MISSING: no meaningful evidence exists. Do not use PARTIALLY_MATCHED for vague conceptual similarity or isolated keyword overlap.
    - Do not infer years of experience, scale, production use, education, or proficiency that the resume does not state.
    - Do not downgrade explicit sufficient evidence or upgrade weak evidence.
3. **SEMANTIC MATCHING**: Recognize related technologies only when the resume evidence is meaningful for the specific requirement.
   - Example: "Built backend APIs using Flask" is a semantic match for "RESTful web services".
4. **DISTINGUISH EVIDENCE**:
   - 'Represented': Clearly present.
   - 'Possibly Represented': Conceptually present but terminology differs or evidence is thin.
   - 'Not Found': No reasonable evidence.
5. **DETAILED & ACTIONABLE SUGGESTIONS (TRUTHFUL ONLY)**:
   - Every suggestion MUST be conditional on actual experience.
   - NEVER tell a candidate to "Add [Skill]" or "Use [Metric]" blindly.
   - CORRECT: "If you genuinely have experience with [Skill], consider adding it. Do not add it if you do not have it."
   - CORRECT: "If you have measured the system's throughput or latency, replace vague claims with the actual measured metric. Do not invent or estimate metrics."
   - INCORRECT: "Add C++ to your resume." / "Use metrics like 'handled 10k requests/sec'."
6. **PREFERRED VS REQUIRED**:
   - Check the provided requirements list. If a skill is marked 'PREFERRED', do NOT describe it as a "hard requirement", "critical gap", or "mandatory".
   - Instead, use: "[Skill] is listed as a preferred qualification. If you have relevant experience, consider adding it."
7. **COMPREHENSIVE ANALYSIS**: Be exhaustive. Identify every single technical skill, soft skill, and tool mentioned in the Job Description. Do not summarize or skip items.
8. **EVIDENCE-AWARE KEYWORD OPTIMIZATION**:
   - When identifying missing power words or keywords, do NOT recommend adding them solely for ATS matching.
   - For every suggested keyword, append a truthfulness warning.
   - Example: "TCP/IP — consider adding only if you have actually worked with TCP/IP."
   - Example: "Kernel — do not add unless you have actual kernel-level experience."
9. **STRICT JSON OUTPUT**: Return ONLY a valid JSON object. No preamble, no conversational text.
10. **NO SCORE**: Do not calculate or return an overall match percentage. The application calculates that deterministically.
11. **PRESERVE SUPPORTING ANALYSIS**: Return supporting analysis when applicable. Keep these fields in the JSON response:
     - 'evidence_gaps': a list of objects with 'requirement', 'gap', and truthful 'suggestion'.
     - 'keyword_optimization': preserve structured keyword objects or legacy fields such as 'missing_power_words',
         'optimization_suggestions', 'suggested_phrasing_changes', or 'suggested_phrasing'.
12. **DATE-AWARE EXPERIENCE**: When evaluating a requirement with a duration such as "2 years of experience":
    - Use explicit employment dates in the resume and calculate through {date.today().strftime('%B %Y')} when an entry says Present.
    - "July 2024 - Present" therefore represents more than two years as of September 2026.
    - Count full-time industry employment as professional experience. Keep internships clearly distinguished.
    - Do not count university coursework or academic projects as professional employment.
    - Do not invent missing dates. If dates are ambiguous, state the uncertainty instead of estimating a duration.
"""
    # If we have pre-extracted requirements, we force the AI to use those labels.
    if requirements:
        req_list = ", ".join([r['item'] for r in requirements])
        system_prompt += f"""
13. **REQUIREMENT CONSISTENCY**: You are provided with a list of target requirements: [{req_list}].
    Return exactly one object in 'requirement_assessments' for every target requirement, using the exact item name.
    Each object must contain 'item', 'status', and 'evidence'. 'status' must be exactly one of
    'MATCHED', 'PARTIALLY_MATCHED', or 'MISSING'. Include a concise 'reason' for PARTIALLY_MATCHED or MISSING.
    Keep the requirement's REQUIRED/PREFERRED importance in mind, but do not change the status based on importance.
"""

    # --- User Prompt ---
    user_prompt = f"""
### ATS PARSED RESUME:
{parsed_resume}

### JOB DESCRIPTION:
{job_description}

Perform the analysis and return the JSON result.
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "seed": 42,
            "top_p": 0
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()

        response_data = response.json()
        response_text = response_data.get("message", {}).get("content", "")

        if not response_text:
            raise ValueError("Ollama returned an empty response.")

        # Handle occasional markdown wrappers
        if "```json" in response_text:
            import re
            match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if match:
                response_text = match.group(1)
        elif "```" in response_text:
            import re
            match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
            if match:
                response_text = match.group(1)

        return json.loads(response_text)

    except requests.exceptions.ConnectionError:
        raise RuntimeError("Could not connect to Ollama. Please ensure Ollama is running locally (http://localhost:11434).")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Ollama API returned an HTTP error: {e}")
    except json.JSONDecodeError:
        raise ValueError("The AI returned an invalid JSON response. Please try again.")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred with the Ollama API: {e}")
