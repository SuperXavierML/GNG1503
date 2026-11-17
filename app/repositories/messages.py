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
