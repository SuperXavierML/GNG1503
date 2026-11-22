def list_messages(database, patient_id):
    return database.execute(
        """
        SELECT m.id, m.sender_user_id, m.body, m.sent_at,
               COALESCE(
                   NULLIF(u.display_name, ''),
                   substr(u.email, 1, instr(u.email, '@') - 1)
               ) AS sender_name,
               u.role AS sender_role
        FROM messages AS m
        JOIN users AS u ON u.id = m.sender_user_id
        WHERE m.patient_profile_id = ?
        ORDER BY m.sent_at, m.id
        """,
        (patient_id,),
    ).fetchall()


def create_message(database, patient_id, sender_id, body):
    result = database.execute(
        """
        INSERT INTO messages (patient_profile_id, sender_user_id, body)
        VALUES (?, ?, ?)
        """,
        (patient_id, sender_id, body),
    )
    database.commit()
    return result.lastrowid


def has_unread_messages(database, user_id, role):
    if role == "doctor":
        query = """
            SELECT EXISTS(
                SELECT 1
                FROM messages AS m
                JOIN patient_profiles AS p ON p.id = m.patient_profile_id
                WHERE p.doctor_id = ? AND m.sender_user_id != ?
                  AND m.read_at IS NULL
            )
        """
    elif role == "patient":
        query = """
            SELECT EXISTS(
                SELECT 1
                FROM messages AS m
                JOIN patient_profiles AS p ON p.id = m.patient_profile_id
                WHERE p.patient_user_id = ? AND m.sender_user_id != ?
                  AND m.read_at IS NULL
            )
        """
    else:
        raise ValueError(f"Unsupported messaging role: {role}")
    return bool(database.execute(query, (user_id, user_id)).fetchone()[0])


def mark_messages_read(database, patient_id, recipient_id):
    database.execute(
        """
        UPDATE messages
        SET read_at = CURRENT_TIMESTAMP
        WHERE patient_profile_id = ? AND sender_user_id != ? AND read_at IS NULL
        """,
        (patient_id, recipient_id),
    )
    database.commit()
