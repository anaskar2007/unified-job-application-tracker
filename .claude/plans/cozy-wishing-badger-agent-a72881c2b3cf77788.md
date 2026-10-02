# Implementation Plan: Resume + Job Description Intelligence System

## 1. Overview
Extend the Job Application Tracker from a basic resume storage and AI analysis tool into an explainable intelligence system. The goal is to provide transparent, weighted scoring of resumes against job descriptions (JDs) using parsed ATS text, while integrating these insights directly into the application tracking workflow.

## 2. Database Schema Changes
To support JD storage, analysis tracking, and resume versioning, the following changes are required:

### New Tables
- `job_descriptions`:
    - `jd_id` (INTEGER PRIMARY KEY AUTOINCREMENT)
    - `application_id` (INTEGER, FOREIGN KEY -> `applications`)
    - `jd_text` (TEXT)
    - `created_at` (DATETIME)
- `match_analyses`:
    - `analysis_id` (INTEGER PRIMARY KEY AUTOINCREMENT)
    - `application_id` (INTEGER, FOREIGN KEY -> `applications`)
    - `resume_id` (INTEGER, FOREIGN KEY -> `resumes`)
    - `match_score` (REAL)
    - `analysis_json` (TEXT) - Stores the full structured report from AI.
    - `created_at` (DATETIME)

### Table Modifications
- `applications`:
    - Add `match_score` (REAL) to store the latest analysis score for quick filtering.
- `resumes`:
    - (Optional) Add `version_number` (INTEGER) if formal versioning is needed, though `resume_name` and `upload_date` currently serve as implicit versions.

## 3. Backend Logic Implementation

### New Module: `ai/jd_matcher.py`
This module will handle the intelligence logic, extending `ai/jd_resume_analyzer.py`.

**Key Functions:**
- `extract_requirements(jd_text)`:
    - Use LLM to extract a structured list of requirements.
    - Schema: `{"requirements": [{"item": "Python", "category": "Language", "importance": "Required/Preferred"}]}`.
- `calculate_weighted_score(analysis_result, requirements)`:
    - Algorithm: 
        - `Required` matches: High weight (e.g., 1.0)
        - `Preferred` matches: Medium weight (e.g., 0.5)
        - `Partially Matched`: Partial weight (e.g., 0.3 - 0.6)
        - `Missing`: 0
    - Result: $\frac{\sum(\text{weights of matched})}{\sum(\text{all weights})} \times 100$
- `generate_explainable_report(analysis_result)`:
    - Map `analyze_resume` output to the required categories:
        - **MATCHED**: `represented` items + evidence.
        - **PARTIALLY MATCHED**: `possibly_represented` items + reason.
        - **MISSING**: `not_found` items + importance explanation.

### Integration with `analyze_resume`
- The existing `analyze_resume` function in `ai/jd_resume_analyzer.py` already returns structured JSON. We will wrap this call in `jd_matcher.py` to add the scoring and requirement extraction layers.

## 4. UI Integration

### "JD Intelligence" Flow (New/Modified Page)
Replace or extend the `render_ai_analyzer` function in `app.py`:

1. **Input Phase**:
    - Select a stored Resume (dropdown from `resumes` table).
    - Paste JD text.
    - Associate with an existing Application or create a new one.
2. **Processing Phase**:
    - Call `extract_requirements` $\rightarrow$ `analyze_resume` $\rightarrow$ `calculate_weighted_score`.
3. **Reporting Phase (Visuals)**:
    - **Score Gauge**: Large KPI card showing the overall match percentage.
    - **Breakdown Grid**: Use `ui_components.py` cards to show:
        - **Matched (Green)**: List with evidence.
        - **Partially Matched (Yellow)**: List with reasons.
        - **Missing (Red)**: List with "Why it matters".
    - **ATS Validation**: A text area showing the `ats_text` from the selected resume, allowing the user to verify what the AI is seeing.
    - **Actionable Advice**: Display the `suggestions` and `keyword_optimization` from the AI.

## 5. Application Flow
1. **Resume Selection**: User chooses a resume version.
2. **JD Input**: User pastes the JD for a specific role.
3. **Analysis**: System runs the intelligence pipeline.
4. **Review**: User examines the explainable report and ATS extraction.
5. **Save/Apply**: User saves the JD and match score to the `applications` record.

## 6. Verification Plan
- **Test Case 1: Requirement Extraction**: Verify that a JD with "Required: Java, Preferred: AWS" correctly identifies categories and importance.
- **Test Case 2: Scoring Accuracy**: Ensure a resume with all "Required" but no "Preferred" skills scores higher than one with "Preferred" but missing "Required".
- **Test Case 3: ATS Text Integrity**: Confirm that `analyze_resume` is strictly using the `ats_text` field and not the original PDF.
- **Test Case 4: End-to-End Save**: Upload Resume $\rightarrow$ Run Intelligence $\rightarrow$ Save to Application $\rightarrow$ Verify score appears in Dashboard.

## 7. Critical Files
- `database.py`: Schema updates.
- `ai/jd_matcher.py`: New logic for scoring and extraction.
- `ai/jd_resume_analyzer.py`: (Read-only) Core analysis engine.
- `app.py`: UI implementation of the intelligence flow.
- `ui_components.py`: Styling for the reports.
