import json
import math
from decimal import Decimal


INITIAL_DELAY_SECONDS = 24 * 60 * 60
QUESTIONNAIRE_VERSION = "sphm-risk-v1"


def parse_risk_answers(form):
    answers = {}
    try:
        age_years = int(form.get("age_years", ""))
        height_cm = float(form.get("height_cm", ""))
        weight_kg = float(form.get("weight_kg", ""))
        alcohol_per_week = float(
            form.get("alcohol_standard_drinks_per_week", "")
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Numeric risk answers are invalid.") from error

    if (
        age_years < 0
        or not math.isfinite(height_cm)
        or height_cm <= 0
        or not math.isfinite(weight_kg)
        or weight_kg <= 0
        or not math.isfinite(alcohol_per_week)
        or alcohol_per_week < 0
    ):
        raise ValueError("Numeric risk answers are outside valid values.")

    answers.update(
        {
            "age_years": age_years,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "alcohol_standard_drinks_per_week": alcohol_per_week,
        }
    )
    for key in (
        "current_smoker",
        "cardiovascular_disease",
        "stroke_tia_history",
        "premature_family_history",
        "chronic_kidney_disease",
    ):
        value = form.get(key)
        if value not in ("yes", "no"):
            raise ValueError("Every yes/no risk question must be answered.")
        answers[key] = value == "yes"

    pregnant = form.get("pregnant")
    if pregnant not in ("yes", "no", "not_applicable"):
        raise ValueError("Pregnancy status must be answered.")
    answers["pregnant"] = pregnant

    diabetes_type = form.get("diabetes_type")
    if diabetes_type not in ("none", "type_1", "type_2"):
        raise ValueError("Diabetes status must be answered.")
    answers["diabetes_type"] = diabetes_type
    return answers


def calculate_risk_result(answers):
    bmi_value = Decimal(str(answers["weight_kg"])) / (
        Decimal(str(answers["height_cm"])) / Decimal(100)
    ) ** 2
    bmi = float(bmi_value)
    moderate = sum(
        (
            answers["age_years"] >= 60,
            Decimal(25) <= bmi_value < Decimal(30),
            answers["alcohol_standard_drinks_per_week"] > 2,
            answers["current_smoker"],
            answers["pregnant"] == "yes",
        )
    )
    high = sum(
        (
            bmi_value >= Decimal(30),
            answers["cardiovascular_disease"],
            answers["stroke_tia_history"],
            answers["premature_family_history"],
            answers["chronic_kidney_disease"],
            answers["diabetes_type"] in ("type_1", "type_2"),
        )
    )

    if high >= 2 or (high >= 1 and moderate >= 2):
        systolic, diastolic = 125, 75
    elif high >= 1 or moderate >= 3:
        systolic, diastolic = 130, 80
    elif moderate >= 1:
        systolic, diastolic = 135, 85
    else:
        systolic, diastolic = 140, 90

    result_answers = dict(answers)
    result_answers["bmi"] = bmi
    result_answers["moderate_factor_count"] = moderate
    result_answers["high_factor_count"] = high
    return {
        "answers": result_answers,
        "risk_score": moderate + high,
        "moderate_factor_count": moderate,
        "high_factor_count": high,
        "systolic_threshold": systolic,
        "diastolic_threshold": diastolic,
        "initial_delay_seconds": INITIAL_DELAY_SECONDS,
    }


def parse_threshold_overrides(form):
    systolic_value = form.get("systolic_threshold_override", "").strip()
    diastolic_value = form.get("diastolic_threshold_override", "").strip()
    if not systolic_value and not diastolic_value:
        return None
    if not systolic_value or not diastolic_value:
        raise ValueError("Both pressure thresholds must be provided together.")
    try:
        systolic = int(systolic_value)
        diastolic = int(diastolic_value)
    except (TypeError, ValueError) as error:
        raise ValueError("Pressure thresholds must be whole numbers.") from error
    if systolic <= diastolic or diastolic <= 0:
        raise ValueError("Pressure thresholds must be positive and ordered.")
    return systolic, diastolic


def _serialize_answers(answers):
    if not isinstance(answers, dict) or not answers:
        raise ValueError("At least one questionnaire answer is required.")
    serialized_answers = []
    for question_key, answer in answers.items():
        if not isinstance(question_key, str) or not question_key.strip():
            raise ValueError("Question keys must be non-empty strings.")
        try:
            answer_value = json.dumps(answer, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError("Question answers must be JSON serializable.") from error
        serialized_answers.append((question_key.strip(), answer_value))
    return serialized_answers


def create_patient_profile(
    database, doctor_id, display_name, risk_result, threshold_override=None
):
    display_name = display_name.strip() if isinstance(display_name, str) else ""
    if not display_name or len(display_name) > 100:
        raise ValueError("A patient name of 1 to 100 characters is required.")
    if not isinstance(risk_result, dict):
        raise ValueError("The calculated risk result is invalid.")

    answers = risk_result.get("answers")
    serialized_answers = _serialize_answers(answers)
    risk_score = risk_result.get("risk_score")
    calculated_systolic = risk_result.get("systolic_threshold")
    calculated_diastolic = risk_result.get("diastolic_threshold")
    if (
        type(risk_score) not in (int, float)
        or not math.isfinite(risk_score)
        or type(calculated_systolic) is not int
        or type(calculated_diastolic) is not int
        or not 125 <= calculated_systolic <= 140
        or not 75 <= calculated_diastolic <= 90
    ):
        raise ValueError("The calculated risk result is invalid.")

    if threshold_override is None:
        systolic_threshold = calculated_systolic
        diastolic_threshold = calculated_diastolic
    else:
        systolic_threshold, diastolic_threshold = threshold_override
        if (
            type(systolic_threshold) is not int
            or type(diastolic_threshold) is not int
            or systolic_threshold <= diastolic_threshold
            or diastolic_threshold <= 0
        ):
            raise ValueError("The pressure threshold override is invalid.")

    with database:
        database.execute("BEGIN IMMEDIATE")
        patient = database.execute(
            """
            INSERT INTO patient_profiles
                (doctor_id, display_name, profile_status, risk_score,
                 systolic_threshold, diastolic_threshold, initial_delay_seconds)
            VALUES (?, ?, 'ready', ?, ?, ?, ?)
            """,
            (
                doctor_id,
                display_name,
                risk_score,
                systolic_threshold,
                diastolic_threshold,
                INITIAL_DELAY_SECONDS,
            ),
        )
        patient_id = patient.lastrowid
        assessment = database.execute(
            """
            INSERT INTO risk_assessments
                (patient_profile_id, questionnaire_version, risk_score,
                 systolic_threshold, diastolic_threshold)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                QUESTIONNAIRE_VERSION,
                risk_score,
                systolic_threshold,
                diastolic_threshold,
            ),
        )
        database.executemany(
            """
            INSERT INTO risk_answers (assessment_id, question_key, answer_value)
            VALUES (?, ?, ?)
            """,
            [
                (assessment.lastrowid, question_key, answer_value)
                for question_key, answer_value in serialized_answers
            ],
        )
    return patient_id


def save_risk_assessment(
    database,
    doctor_id,
    patient_id,
    questionnaire_version,
    answers,
    risk_score,
    systolic_threshold,
    diastolic_threshold,
):
    if not isinstance(questionnaire_version, str) or not questionnaire_version.strip():
        raise ValueError("A questionnaire version is required.")
    if not isinstance(answers, dict) or not answers:
        raise ValueError("At least one questionnaire answer is required.")
    if (
        type(risk_score) not in (int, float)
        or not math.isfinite(risk_score)
        or type(systolic_threshold) is not int
        or type(diastolic_threshold) is not int
        or not 125 <= systolic_threshold <= 140
        or not 75 <= diastolic_threshold <= 90
    ):
        raise ValueError("The calculated risk result is invalid.")

    serialized_answers = _serialize_answers(answers)

    owned_profile = database.execute(
        "SELECT id FROM patient_profiles WHERE id = ? AND doctor_id = ?",
        (patient_id, doctor_id),
    ).fetchone()
    if owned_profile is None:
        raise LookupError("Patient profile not found.")

    with database:
        assessment = database.execute(
            """
            INSERT INTO risk_assessments
                (patient_profile_id, questionnaire_version, risk_score,
                 systolic_threshold, diastolic_threshold)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                questionnaire_version.strip(),
                risk_score,
                systolic_threshold,
                diastolic_threshold,
            ),
        )
        for question_key, answer_value in serialized_answers:
            database.execute(
                """
                INSERT INTO risk_answers (assessment_id, question_key, answer_value)
                VALUES (?, ?, ?)
                """,
                (assessment.lastrowid, question_key, answer_value),
            )
        database.execute(
            """
            UPDATE patient_profiles
            SET profile_status = CASE
                    WHEN patient_user_id IS NULL THEN 'ready'
                    ELSE 'linked'
                END,
                risk_score = ?,
                systolic_threshold = ?, diastolic_threshold = ?,
                initial_delay_seconds = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND doctor_id = ?
            """,
            (
                risk_score,
                systolic_threshold,
                diastolic_threshold,
                INITIAL_DELAY_SECONDS,
                patient_id,
                doctor_id,
            ),
        )
    return assessment.lastrowid
