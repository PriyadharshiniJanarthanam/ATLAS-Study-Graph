import unittest


class TestReviewCrew(unittest.TestCase):

    def test_stage2_file_exists(self):
        import os
        self.assertTrue(os.path.exists("stage2/crew.py"))


if __name__ == "__main__":
    unittest.main()

    import json

report = crew.run_cycle(6, 2)

with open("stage2/report.json", "w") as f:
    json.dump(report.summary, f, indent=2)

print("report.json created successfully")