import unittest
from organization_audit import validate_organization_issue, organization_audit_prompt


class OrganizationAuditTests(unittest.TestCase):
    def setUp(self):
        self.essay = (
            "Students may rely on AI. Many universities are adopting technology. "
            "AI sometimes gives inaccurate information."
        )
        self.issue = {
            "dimension": "Organization", "type": "Improvement",
            "category": "Paragraph coherence",
            "original": "Many universities are adopting technology.",
            "replacement": "Move this statement to the introduction or explain its connection to AI risks.",
            "explanation": "The paragraph focuses on risks, but this sentence switches to adoption."
        }

    def test_valid_grounded_issue(self):
        self.assertEqual(validate_organization_issue(self.essay, self.issue), self.issue)

    def test_reject_moving_existing_opening_to_essay_start(self):
        essay = (
            "AI tools is becoming common in university classrooms. "
            "Students use them to study.\\n\\n"
            "However, AI sometimes makes mistakes."
        )
        issue = dict(
            self.issue,
            original="AI tools is becoming common in university classrooms.",
            replacement="Move this sentence to the beginning of the essay.",
        )
        self.assertIsNone(validate_organization_issue(essay, issue))

    def test_allow_genuine_mid_paragraph_relocation(self):
        self.assertEqual(
            validate_organization_issue(self.essay, self.issue),
            self.issue,
        )

    def test_null_issue(self):
        self.assertIsNone(validate_organization_issue(self.essay, None))

    def test_reject_unquoted_evidence(self):
        bad = dict(self.issue, original="A sentence not in the essay.")
        self.assertIsNone(validate_organization_issue(self.essay, bad))

    def test_reject_content_disguised_as_organization(self):
        bad = dict(self.issue, dimension="Content")
        self.assertIsNone(validate_organization_issue(self.essay, bad))

    def test_prompt_requires_no_forced_merges(self):
        self.assertIn("Do not recommend merging", organization_audit_prompt())


if __name__ == "__main__":
    unittest.main()
