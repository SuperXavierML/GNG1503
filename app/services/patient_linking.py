from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from werkzeug.security import generate_password_hash


INVITE_LIFETIME = timedelta(days=7)


def _utc_timestamp(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _code_hash(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def issue_access_code(database, doctor_id, patient_id):
    patient = database.execute(
        """
        SELECT id FROM patient_profiles
        WHERE id = ? AND doctor_id = ? AND profile_status = 'ready'
          AND patient_user_id IS NULL
          AND risk_score IS NOT NULL
          AND systolic_threshold IS NOT NULL
          AND diastolic_threshold IS NOT NULL
        """,
        (patient_id, doctor_id),
    ).fetchone()
    if patient is None:
        return None

    code = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    expires_at = now + INVITE_LIFETIME
    database.execute(
        """
        UPDATE patient_invites
        SET expires_at = ?
        WHERE patient_profile_id = ? AND consumed_at IS NULL
        """,
        (_utc_timestamp(now), patient_id),
    )
    database.execute(
        """
        INSERT INTO patient_invites
            (patient_profile_id, issued_by, code_hash, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (patient_id, doctor_id, _code_hash(code), _utc_timestamp(expires_at)),
    )
    database.commit()
    return code


def redeem_access_code(database, code, email, password):
    normalized_code = code.strip()
    if not normalized_code:
        return False

    now = _utc_timestamp(datetime.now(timezone.utc))
    database.execute("BEGIN IMMEDIATE")
    invite = database.execute(
        """
        SELECT i.id, i.patient_profile_id
        FROM patient_invites AS i
        JOIN patient_profiles AS p ON p.id = i.patient_profile_id
        WHERE i.code_hash = ? AND i.consumed_at IS NULL
          AND i.expires_at > ? AND p.profile_status = 'ready'
          AND p.patient_user_id IS NULL
        """,
        (_code_hash(normalized_code), now),
    ).fetchone()
    if invite is None:
        database.rollback()
        return False

    user_result = database.execute(
        """
        INSERT INTO users (email, password_hash, role)
        VALUES (?, ?, 'patient')
        """,
        (email, generate_password_hash(password)),
    )
    patient_user_id = user_result.lastrowid
    updated = database.execute(
        """
        UPDATE patient_profiles
        SET patient_user_id = ?, profile_status = 'linked',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND patient_user_id IS NULL AND profile_status = 'ready'
        """,
        (patient_user_id, invite["patient_profile_id"]),
    )
    if updated.rowcount != 1:
        database.rollback()
        return False

    database.execute(
        "UPDATE patient_invites SET consumed_at = ? WHERE id = ?",
        (now, invite["id"]),
    )
    database.commit()
    return True
