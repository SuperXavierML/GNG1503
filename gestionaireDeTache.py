DELAI_CONFIRMATION = 5 * 60


class GestionnaireDeTache:
    """Orchestre nouvelle mesure -> (confirmation) -> alarme.

    Une mesure compte UNE fois dans les compteurs du patient :
    - sans changement de grade : sa première lecture est validée tout de suite;
    - avec changement de grade : la première lecture est mise en attente
      (compteurs intacts) et c'est la lecture de confirmation qui est validée.
    """

    def __init__(self, patient):
        self.patient = patient
        self.grades = []
        self.alarmes = []          # (dateHeure, grade, motif)
        self.dernierGrade = None   # dernier grade VALIDÉ
        self.mesureEnAttente = None
        self._alerteImmediateEnvoyee = False

    @property
    def confirmationRequise(self):
        return self.mesureEnAttente is not None

    @property
    def delaiProchaineSaisie(self):
        """Secondes avant la prochaine saisie (5 min si confirmation)."""
        if self.confirmationRequise:
            return DELAI_CONFIRMATION
        return self.patient.delai

    def nouvelleMesure(self, mesure):
        """Reçoit une mesure complète (vitaux + symptômes).

        Retourne (grade_de_la_lecture, alarme, confirmation_requise).
        """
        if self.confirmationRequise:
            raise RuntimeError("Une confirmation est en attente.")

        grade = self.patient.calculerGrade(mesure, 0)
        alarme = False

        # Grade 3 : alerte tout de suite, sans attendre confirmation ni compteurs.
        if grade >= 3:
            self._declencher(mesure, grade, "grade 3")
            alarme = True
            self._alerteImmediateEnvoyee = True
        else:
            self._alerteImmediateEnvoyee = False

        if self.dernierGrade is not None and grade != self.dernierGrade:
            # changement de grade (vitaux OU symptômes) : confirmation
            self.mesureEnAttente = mesure
            return grade, alarme, True

        grade_valide = self.patient.enregistreValeur(mesure, 0)
        self._valider(mesure, grade_valide)
        if not alarme and self.patient.alarmeDeclenchee(grade_valide):
            self._declencher(mesure, grade_valide, "3 mesures anormales")
            alarme = True
        return grade_valide, alarme, False

    def confirmerMesure(self, systolique, diastolique, pouls):
        """Ajoute la lecture de confirmation à la mesure en attente.

        Seuls les signes vitaux sont fournis; les symptômes restent ceux de
        la mesure d'origine. Retourne (grade, alarme).
        """
        if not self.confirmationRequise:
            raise RuntimeError("Aucune confirmation n'est attendue.")

        mesure = self.mesureEnAttente
        mesure.mesureDeVerification(systolique, diastolique, pouls)
        grade = self.patient.enregistreValeur(mesure, 1)
        self._valider(mesure, grade)
        self.mesureEnAttente = None

        alarme = False
        if grade >= 3:
            # déjà alerté pour cette mesure ? on n'alerte pas deux fois
            if not self._alerteImmediateEnvoyee:
                self._declencher(mesure, grade, "grade 3")
            alarme = True
        elif self.patient.alarmeDeclenchee(grade):
            self._declencher(mesure, grade, "3 mesures anormales")
            alarme = True
        self._alerteImmediateEnvoyee = False
        return grade, alarme

    def _valider(self, mesure, grade):
        self.grades.append(grade)
        self.dernierGrade = grade

    def _declencher(self, mesure, grade, motif):
        self.alarmes.append((mesure.dateHeure, grade, motif))
