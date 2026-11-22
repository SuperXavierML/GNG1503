# Blood Pressure Monitoring App: UI Change Requirements

## 1. Sources

| File | Role |
|---|---|
| `template.txt` | Visual base: palette, style, bottom navigation, patient and doctor screens |
| `reference.txt` | Functional React prototype: source of the history, analysis, statistics and CSV features |

> Where a requirement below conflicts with either file, this document takes priority.

---

## 2. Global changes (patient and doctor UI)

### 2.1 Navigation
- Move the navigation bar to the **bottom of the screen** instead of the top.

### 2.2 Visual style
- Apply the template's **color palette and style** to every **table** and every **button**.
- Format the comparison table in the Analysis section to match the other tables and charts.

### 2.3 Settings: display name
- Add a setting in **Settings** where the user chooses the **name displayed on their account**.

---

## 3. Patient UI

### 3.1 Home: health status
- Show the patient's health status as a **button-style badge**:

| Status | Grade | Color |
|---|---|---|
| Good | none | Green |
| High | Grade 1 | Yellow |
| Elevated | Grade 2 | Orange |
| Critical | Grade 3 | Red |

### 3.2 History log
- Purpose: a **log of all previous measurements**.
- Each measurement shows whether it was **valid or not**.
- The log and its **.csv** download are at the bottom of the Analysis page.
- The standalone History and CSV URLs redirect to Analysis.
- The log contains **no charts and no data comparison**. Those belong to the Analysis page.
- The patient bottom navigation does not include Measurement or History; measurement is
  initiated from the Home page.

### 3.3 Analysis page
This page holds all **charts and data comparison**.

- **Time-range buttons** above the charts to select the period shown.
- **Abnormal measurements** are marked with a **red triangle** on the charts (above the threshold).
- **Statistics**, computed **separately** for systolic pressure, diastolic pressure and pulse:
  - mean
  - standard deviation
  - standard deviation as a percentage (% of the mean)
  - variation of the mean, relative to its previous value
  - a **graphical representation** of each of these
- **Comparison table**: same table standards as the rest of the app (see 2.2).

### 3.4 Symptom selection
- Add an **adjective** next to each numeric value in the symptom selection (for example, an intensity scale with a descriptive word per number).
- Add an **icon** to each symptom so it is easier to identify. Icons must come from an **icon library**.

---

## 4. Doctor UI

### 4.1 Home: notification system
- Add a **notification system** to the doctor's home screen.
- As soon as one of the doctor's patients triggers an alert, it is **displayed on the home screen**.

**Sorting rules**
1. A higher-severity alert always ranks above a lower-severity one, **even if the lower-severity alert is older**.
2. Within the same severity, the alert with the **longest delay between its emission and its reading** ranks higher (the oldest unread alert comes first).

**Interaction**
- Tapping a notification takes the doctor **directly to that patient's analytics data**.

### 4.2 Doctor dashboard patient list
- Show the patient list and search bar below the alerts list on the doctor dashboard.
- Do not provide a separate Patients page or Patients bottom-navigation option.
- Redirect old `/doctor/patients` links to the dashboard patient-list section, preserving search.
- Show an unread-message dot next to patient names with incoming messages that the doctor has
  not read.
- Each doctor's patient detail page also provides an all-time historical readings table and CSV
  download, newest first.

### 4.3 Message notifications
- Show a red dot on the Messages bottom-navigation button when the signed-in user has unread
  incoming messages.
- Mark incoming messages read when the user opens the conversation.

---

## 5. Open points to confirm

These were ambiguous in the source text. The default shown is what the text most likely means.

| # | Question | Default assumed |
|---|---|---|
| 1 | Final list of bottom-bar tabs for each role | Patient: Home, Analysis, Messages, Settings. Doctor: Home, Messages, Settings |
| 2 | Thresholds for Grade 1, 2 and 3 | To be defined (suggest a clinical source) |
| 3 | "Valid or not" in the history | Measurement above or below the personal threshold |
| 4 | "Variation of the mean relative to its previous value" | Current period mean vs the previous period of the same length |
| 5 | Patient search behavior on the doctor dashboard | Standard search field with the device keyboard; no custom on-screen keyboard |
| 6 | Standard deviation formula | Population standard deviation |
| 7 | Icon library | Local files (not a CDN), so the PWA works offline |
| 8 | Alerts shared between patient and doctor | Requires shared storage or a backend; `template.txt` uses separate `localStorage` per page |
| 9 | Time-range options | 7, 14 and 30 days (as in `reference.txt`) |
| 10 | Language switch (FR/EN) | Keep, and translate all new strings |
