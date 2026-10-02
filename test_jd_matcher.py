import unittest
import json
from ai.jd_matcher import calculate_match_score, generate_explainable_report

class TestJDMatcher(unittest.TestCase):
    def setUp(self):
        # Mocked JD requirements
        self.requirements = [
            {"item": "Python", "category": "Language", "importance": "REQUIRED"},
            {"item": "PyTorch", "category": "Framework", "importance": "REQUIRED"},
            {"item": "Docker", "category": "Tools", "importance": "PREFERRED"},
            {"item": "AWS", "category": "Cloud", "importance": "PREFERRED"},
            {"item": "Algorithms", "category": "CS Core", "importance": "REQUIRED"},
        ]

    def test_weighted_scoring_full_match(self):
        # All requirements represented
        ai_analysis = {
            "represented": [
                {"item": "Python", "evidence": "Used Python for X"},
                {"item": "PyTorch", "evidence": "Implemented Y in PyTorch"},
                {"item": "Docker", "evidence": "Deployed with Docker"},
                {"item": "AWS", "evidence": "Used AWS S3"},
                {"item": "Algorithms", "evidence": "Expert in Algorithms"},
            ],
            "possibly_represented": [],
            "not_found": []
        }
        score, breakdown = calculate_match_score(self.requirements, ai_analysis)
        self.assertEqual(score, 100)
        self.assertEqual(breakdown["categories"]["Language"], 100.0)

    def test_weighted_scoring_partial_match(self):
        # Match: Python(R), Algorithms(R), Docker(P)
        # Miss: PyTorch(R), AWS(P)
        # Potential Weight: 1+1+0.5+0.5+1 = 4.0
        # Earned Weight: 1+1+0.5 = 2.5
        # Score: 2.5 / 4.0 * 100 = 62.5 -> round to 63
        ai_analysis = {
            "represented": [
                {"item": "Python", "evidence": "..."},
                {"item": "Algorithms", "evidence": "..."},
                {"item": "Docker", "evidence": "..."},
            ],
            "possibly_represented": [],
            "not_found": [
                {"item": "PyTorch", "reason": "..."},
                {"item": "AWS", "reason": "..."},
            ]
        }
        score, breakdown = calculate_match_score(self.requirements, ai_analysis)
        self.assertEqual(score, 62)

    def test_weighted_scoring_possibly_represented(self):
        # Python(R) - Full, PyTorch(R) - Partial
        # Potential: 1+1 = 2.0
        # Earned: 1 + (1 * 0.5) = 1.5
        # Score: 1.5 / 2.0 = 75%
        reqs = [
            {"item": "Python", "category": "L", "importance": "REQUIRED"},
            {"item": "PyTorch", "category": "F", "importance": "REQUIRED"},
        ]
        ai_analysis = {
            "represented": [{"item": "Python", "evidence": "..."}],
            "possibly_represented": [{"item": "PyTorch", "evidence": "...", "reason": "..."}],
            "not_found": []
        }
        score, breakdown = calculate_match_score(reqs, ai_analysis)
        self.assertEqual(score, 75)

    def test_structured_assessments_drive_score_without_fuzzy_reclassification(self):
        ai_analysis = {
            "requirement_assessments": [
                {"item": "Python", "status": "MATCHED", "evidence": "Built services in Python."},
                {"item": "Algorithms", "status": "PARTIALLY_MATCHED", "evidence": "Used algorithmic techniques in a project."},
                {"item": "Docker", "status": "MISSING", "reason": "Not present in the resume."},
            ]
        }
        requirements = [
            {"item": "Python", "category": "Language", "importance": "REQUIRED"},
            {"item": "Algorithms", "category": "CS Core", "importance": "REQUIRED"},
            {"item": "Docker", "category": "Tools", "importance": "PREFERRED"},
        ]

        score, _ = calculate_match_score(requirements, ai_analysis)
        report = generate_explainable_report(requirements, ai_analysis)

        self.assertEqual(score, 60)
        self.assertEqual([item["item"] for item in report["matched"]], ["Python"])
        self.assertEqual([item["item"] for item in report["partially_matched"]], ["Algorithms"])
        self.assertEqual([item["item"] for item in report["missing"]], ["Docker"])

    def test_report_preserves_supporting_analysis_fields(self):
        ai_analysis = {
            "requirement_assessments": [
                {"item": "Python", "status": "MATCHED", "evidence": "Used Python."}
            ],
            "evidence_gaps": [
                {
                    "requirement": "Distributed systems",
                    "gap": "Only project-level evidence is present.",
                    "suggestion": "Add production scale only if you genuinely have it."
                }
            ],
            "missing_power_words": [
                {"keyword": "C++", "warning": "Add only if you genuinely have C++ experience."}
            ],
            "suggested_phrasing_changes": [
                {"current_phrase": "Built systems", "suggested_phrase": "Built distributed systems"}
            ]
        }
        requirements = [{"item": "Python", "category": "Language", "importance": "REQUIRED"}]

        report = generate_explainable_report(requirements, ai_analysis)

        self.assertEqual(len(report["evidence_gaps"]), 1)
        self.assertEqual(report["evidence_gaps"][0]["suggestion"], "Add production scale only if you genuinely have it.")
        self.assertEqual(report["keyword_optimization"]["missing_power_words"][0]["keyword"], "C++")
        self.assertIn("suggested_phrasing_changes", report["keyword_optimization"])

    def test_report_preserves_top_level_keywords_with_nested_semantic_analysis(self):
        ai_analysis = {
            "semantic_match_analysis": {
                "requirement_assessments": [
                    {"item": "Python", "status": "MATCHED", "evidence": "Used Python."}
                ]
            },
            "keyword_optimization": {
                "missing_power_words": [
                    {"keyword": "Scalability", "warning": "Add only if genuine."}
                ]
            }
        }
        requirements = [{"item": "Python", "category": "Language", "importance": "REQUIRED"}]

        report = generate_explainable_report(requirements, ai_analysis)

        self.assertEqual(
            report["keyword_optimization"]["missing_power_words"][0]["keyword"],
            "Scalability"
        )

    def test_explainable_report_generation(self):
        ai_analysis = {
            "represented": [{"item": "Python", "evidence": "Used Python"}],
            "possibly_represented": [{"item": "PyTorch", "evidence": "Used ML", "reason": "Terminology differs"}],
            "not_found": [
                {"item": "Docker", "reason": "Not mentioned"},
                {"item": "AWS", "reason": "Not mentioned"},
                {"item": "Algorithms", "reason": "Not mentioned"}
            ]
        }
        report = generate_explainable_report(self.requirements, ai_analysis)

        self.assertEqual(len(report["matched"]), 1)
        self.assertEqual(report["matched"][0]["item"], "Python")
        self.assertEqual(report["matched"][0]["importance"], "REQUIRED")

        self.assertEqual(len(report["partially_matched"]), 1)
        self.assertEqual(report["partially_matched"][0]["item"], "PyTorch")

        self.assertEqual(len(report["missing"]), 3)
        self.assertEqual(report["missing"][0]["item"], "Docker")

if __name__ == "__main__":
    unittest.main()
