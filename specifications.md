# Specifications

## Timer

- Measurement frequency should never drop to 5 minutes before going back up. The minimum delay is 5 minutes, but all values (except Grade 3) should be based on the equations.

## Confirmation

- Any grade change must be confirmed with a new pressure reading, whether the grade goes up or down. For example, Grade 1 to 3 and Grade 2 to 0 must both be confirmed, since the grade has changed.
- Even on the first reading, the patient is presumed to be stable (Grade 0). If the first reading is not normal (not Grade 0), it should produce an alert.
- A confirmation measurement should be requested immediately after any reading whose grade differs from the previous one.
- Confirmation readings are not optional: they are mandatory whenever the conditions are met. When a confirmation is needed, display a pop-up that forces the user to complete it.

## Alerts and Alarms

- Replace the Grade 1 critical symptom value of 5 with 8 (more symptom points are required to trigger an alarm).
- The patient's grade must be visible to the doctor, displayed beside the patient's name. It must use the same meaning and color code as on the patient's UI welcome page.
- An alarm notification should pop up on the doctor's home page. Alarms are prioritized according to the time remaining before the next reading and the grade. The grade, the patient's name and the patient's information must all be visible in the alert notification.

## Other

- When filling out a measurement form, the default value should be 0, not "Select an option".
- When creating a new patient profile, the doctor should be able to set their own critical value for the patient, overriding the value calculated by the program.
- When creating a new patient profile, the questionnaire must be completed **before** the profile is created. After creation, the patient's code should be accessible, and no option should let the doctor fill in the patient's information after leaving their account.
- The diastolic line in the graph should be green, not black.
- The periods shown on the graph should be 1 week, 2 weeks and 30 days. The 1 month and 6 months options should be removed.
