import unittest

from app.services.risk_assessment import (
    calculate_risk_result,
    parse_risk_answers,
    parse_threshold_overrides,
)


def answers(**overrides):
    result = {
        "age_years": 40,
        "height_cm": 160.0,
        "weight_kg": 60.0,
        "alcohol_standard_drinks_per_week": 0.0,
        "current_smoker": False,
        "pregnant": "not_applicable",
        "cardiovascular_disease": False,
        "stroke_tia_history": False,
        "premature_family_history": False,
        "chronic_kidney_disease": False,
        "diabetes_type": "none",
    }
    result.update(overrides)
    return result


class RiskAssessmentTests(unittest.TestCase):
    def test_thresholds_follow_risk_factor_and_combination_rules(self):
        cases = (
            (answers(), (140, 90)),
            (answers(age_years=60), (135, 85)),
            (answers(cardiovascular_disease=True), (130, 80)),
            (
                answers(
                    age_years=60,
                    alcohol_standard_drinks_per_week=3,
                    current_smoker=True,
                ),
                (130, 80),
            ),
            (
                answers(
                    cardiovascular_disease=True,
                    age_years=60,
                    current_smoker=True,
                ),
                (125, 75),
            ),
            (
                answers(
                    cardiovascular_disease=True,
                    chronic_kidney_disease=True,
                ),
                (125, 75),
            ),
        )
        for questionnaire, expected in cases:
            with self.subTest(questionnaire=questionnaire):
                result = calculate_risk_result(questionnaire)
                self.assertEqual(
                    (
                        result["systolic_threshold"],
                        result["diastolic_threshold"],
                    ),
                    expected,
                )

    def test_bmi_categories_are_exclusive_at_thresholds(self):
        overweight = calculate_risk_result(
            answers(weight_kg=64.0)
        )
        obesity = calculate_risk_result(
            answers(weight_kg=76.8)
        )
        self.assertEqual(overweight["moderate_factor_count"], 1)
        self.assertEqual(overweight["high_factor_count"], 0)
        self.assertEqual(obesity["moderate_factor_count"], 0)
        self.assertEqual(obesity["high_factor_count"], 1)
        self.assertEqual(obesity["systolic_threshold"], 130)

    def test_questionnaire_rejects_missing_invalid_and_non_finite_values(self):
        with self.assertRaises(ValueError):
            parse_risk_answers({})

        invalid = {
            "age_years": "40",
            "height_cm": "160",
            "weight_kg": "60",
            "alcohol_standard_drinks_per_week": "nan",
            "current_smoker": "no",
            "pregnant": "not_applicable",
            "cardiovascular_disease": "no",
            "stroke_tia_history": "no",
            "premature_family_history": "no",
            "chronic_kidney_disease": "no",
            "diabetes_type": "none",
        }
        with self.assertRaises(ValueError):
            parse_risk_answers(invalid)

    def test_threshold_override_requires_a_positive_ordered_pair(self):
        self.assertIsNone(parse_threshold_overrides({}))
        self.assertEqual(
            parse_threshold_overrides(
                {
                    "systolic_threshold_override": "150",
                    "diastolic_threshold_override": "95",
                }
            ),
            (150, 95),
        )
        for form in (
            {"systolic_threshold_override": "150"},
            {
                "systolic_threshold_override": "90",
                "diastolic_threshold_override": "100",
            },
            {
                "systolic_threshold_override": "not a number",
                "diastolic_threshold_override": "80",
            },
        ):
            with self.subTest(form=form):
                with self.assertRaises(ValueError):
                    parse_threshold_overrides(form)


if __name__ == "__main__":
    unittest.main()
