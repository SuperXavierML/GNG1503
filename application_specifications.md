# Mobile Application Specifications: Hypertension Monitoring

## 1. General & Technical Requirements
1. **Mobile Formatting:** The layout and formatting must be fully responsive and usable on a mobile phone screen.
2. **Profile Creation Logic (Doctor and Patient):**
   1. The doctor has a password, creates an account for the patient (entering the answers to questions used to calculate the patient's risk factor), and sends them a unique access code that links their accounts.
   2. When the patient opens the application for the first time, they must enter their unique code to link their account with their doctor's account.
3. **Authentication UI:** Account creation and login interfaces for both doctors and patients.
4. **Local Database:** A local SQLite-style database for data storage.
5. **Language Settings:** The application must include a language setting supporting both French and English.

---

## 2. Risk Factors & Initial Thresholds
Classification of patients' critical thresholds and initial delays between blood pressure measurements based on the answers entered by the doctor during patient account creation:
1. **No risk factors:** $140/90\text{ mmHg}$.
2. **Maximum risk factor:** $125/75\text{ mmHg}$.
3. **Intermediate values:** Any entered values between these extremes are adjusted appropriately for patients with lower risk factors.
4. **Initial Delay:** Every user has an initial measurement delay of **24 hours**, regardless of their risk factors.

---

## 3. Data Entry & Measurement Logic
1. **Patient Data Entry UI:** Interface allowing the patient to enter their symptoms, symptom intensity (from $0$ to $5$), and their blood pressure measurements (systolic, diastolic, and pulse).
2. **Tracked Symptoms:** The following symptoms are tracked and are considered critical when their total value exceeds $5$:
   ```json
   {
     "headache": "malDeTete",
     "dizziness": "vertige",
     "blurredVision": "visionFloue",
     "shortnessOfBreath": "essoufflement",
     "nosebleed": "saignementDeNez",
     "fatigue": "fatigue",
     "confusion": "confusion",
     "lossOfBalance": "perteDeBalan"
   }
   ```
3. **Delay Calculation & Hypertension Grade Determination:** During calculation, the following values are verified:
   1. **Pulse pressure:** Must be between $20$ and $60\text{ mmHg}$.
   2. **Blood pressure:** Systolic and diastolic pressures must be below the patient's critical threshold.
   3. **Symptom score:** The sum of symptom intensity values must be below the critical value ($5$).
   4. **Doctor Alerts:** If there are two consecutive concerning values and a confirmation of these (or two confirmations in certain cases), an alert is sent to the doctor.
   5. **Resetting Delay:** After three normal readings, the delay returns to its initial value ($24\text{ hours}$), even if the patient has symptoms, provided those symptoms remain below the tolerated critical value.
   6. **Immediate Verification:** An immediate verification measurement is triggered if the hypertension grade changes compared to the previous reading. This verification only includes measurable vital signs (no re-entry of symptoms).
   7. **Standard Measurement:** During a regular measurement session, both blood pressure readings and symptoms are recorded.
   8. **Delay Calculation Formula:** The delay is calculated using the following logic, where `points` is determined by the equation $\text{pointsInquietude} = 0.5 \times \sum(\text{symptomes.values()})$, with `symptomes.values()` representing the sum of intensities associated with each symptom:
      ```python
      elif grade == 2:
          self.delai = self.nbSecondes * (1 - min(1, 0.7 + 0.05 * points))
      else:
          self.delai = self.nbSecondes * (1 - min(1, 0.5 + 0.05 * points))
      ```

---

## 4. Hypertension Grading System
Use of a grading system to classify hypertension ($1, 2, 3$). Grades 2 and 3 have fixed ranges, while Grade 1 varies between the patient's specific critical threshold and the minimum value of Grade 2. **If Grade 3 is reached, the delay between two measurements is strictly 5 minutes, regardless of any other values.**

* **Grade 1 (Mild):** Systolic pressure between $140$ and $159\text{ mmHg}$ and/or diastolic between $90$ and $99\text{ mmHg}$ *(lower bound adjusts to patient's critical threshold)*.
* **Grade 2 (Moderate):** Systolic pressure between $160$ and $179\text{ mmHg}$ and/or diastolic between $100$ and $109\text{ mmHg}$.
* **Grade 3 (Severe):** Systolic pressure $\ge 180\text{ mmHg}$ and/or diastolic $\ge 110\text{ mmHg}$.

---

## 5. Data Visualization & Archives UI
1. **Symptoms Graph:** Representation of symptoms (duration and intensity) using a modular chart. All symptoms can be displayed on the same graph, and the user can toggle visibility via a checklist. Lines must be discontinuous (broken) if a symptom was not observed over a period of time.
2. **Blood Pressure Graph:** Representation of pulse pressure, systolic pressure, diastolic pressure, and the patient's limit/threshold value on a second graph.
3. **Pulse Graph:** A third graph representing heart rate (pulse).
4. **Min/Max Values:** Minimum and maximum values for each measurement must be displayed and available.
5. **Timeframe Selector:** All data must be displayed over a variable timeframe chosen by the user (**1 week, 2 weeks, 1 month, 6 months**).

---

## 6. Communication & User Interfaces (UI)

### Messaging
* **Text Messaging UI:** A text-style messaging interface allowing direct communication between the patient and their doctor.

### Doctor Interface (UI)
* **Navigation Menu:** Home (new patient alerts), Messages, Archives, and Settings.
* **Patient History** Within the patient archives/history, the doctor can view graphical data 
* **Notes:** Leave time based note on the patient's record so they can be shown in the patient archives/history.
* **Period Comparison:** The doctor must be able to compare two different measurements from two different time periods.

### Patient Interface (UI)
* **Navigation Menu:** Home, History, Messages, and Settings.
* **Home Screen:**
  * A countdown timer indicating the remaining delay before the next required measurement (based on the calculated delay).
  * Tailored advice and instructions in case of hypertension (e.g., *"Stay calm"*, *"Call your doctor"*).
## 7.Branding and visuals
* **Name:** The name for this app is "Solutions SPHM" in both language
   * SPHM stands for "Systemes de prevention d'hypertension mobile"
* **Style**: In Parameters (or Settings), there must be a light and dark mode that patients and doctors can use to customize their personal interface.