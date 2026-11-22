import unittest

from app.services.monitoring import classify_grade


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.patient = {
            "systolic_threshold": 140,
            "diastolic_threshold": 90,
        }

    def test_grade_boundaries_use_patient_threshold_and_fixed_ranges(self):
        self.assertEqual(classify_grade(139, 89, self.patient), 0)
        self.assertEqual(classify_grade(140, 80, self.patient), 1)
        self.assertEqual(classify_grade(159, 99, self.patient), 1)
        self.assertEqual(classify_grade(160, 80, self.patient), 2)
        self.assertEqual(classify_grade(179, 109, self.patient), 2)
        self.assertEqual(classify_grade(180, 80, self.patient), 3)

    def test_pulse_pressure_and_symptom_score_affect_grade(self):
        self.assertEqual(classify_grade(120, 59, self.patient), 1)
        self.assertEqual(classify_grade(120, 80, self.patient, 5), 0)
        self.assertEqual(classify_grade(120, 80, self.patient, 8), 0)
        self.assertEqual(classify_grade(120, 80, self.patient, 9), 1)


if __name__ == "__main__":
    unittest.main()
