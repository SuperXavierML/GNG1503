NB_SYMPTOMES_CRITIQUE = 5
DELAI_PLANCHER = 5 * 60
NB_ANORMALES_ALARME = 3
NB_NORMALES_RETOUR = 3


class Patient:

    def __init__(self, facteurRisque, nom, identifiant):
        self.nom = nom
        self.identifiant = identifiant
        self.compteurAnormal = 0
        self.compteurNormal = NB_NORMALES_RETOUR

        if facteurRisque >= 6:
            self.seuilDiastolique = 80
            self.seuilSystolique = 130
            self.nbSecondes = 24 * 60 * 60
        else:
            self.seuilDiastolique = 90
            self.seuilSystolique = 140
            self.nbSecondes = 48 * 60 * 60

        self.delai = self.nbSecondes

    def calculerGrade(self, mesure, index=-1):
        """Grade de la lecture ``index`` (0 = première, 1 = confirmation).

        Fonction pure : ne modifie aucun compteur. Les symptômes sont ceux
        de la mesure, y compris pour la lecture de confirmation.
        """
        p = mesure.pression[index]
        points = mesure.pointsInquietude

        if p.diastolique >= 110 or p.systolique >= 180:
            return 3
        if p.diastolique >= 100 or p.systolique >= 160:
            return 2
        pulsee_anormale = p.pulsee() > 60 or p.pulsee() < 20
        if (p.diastolique >= self.seuilDiastolique
                or p.systolique >= self.seuilSystolique
                or pulsee_anormale
                or points >= NB_SYMPTOMES_CRITIQUE):
            return 1
        return 0

    def enregistreValeur(self, mesure, index=-1):
        """Valide la lecture ``index`` : met à jour compteurs et délai.

        À appeler UNE seule fois par mesure (sur la lecture retenue).
        """
        grade = self.calculerGrade(mesure, index)
        points = mesure.pointsInquietude

        if grade >= 1:
            self.compteurNormal = 0
            self.compteurAnormal += 1
            if grade == 3:
                self.delai = DELAI_PLANCHER
            elif grade == 2:
                self.delai = self.nbSecondes * (1 - min(1, 0.7 + 0.05 * points))
            else:
                self.delai = self.nbSecondes * (1 - min(1, 0.5 + 0.05 * points))
        else:
            self.compteurNormal += 1
            self.compteurAnormal = max(0, self.compteurAnormal - 1)
            if self.compteurNormal >= NB_NORMALES_RETOUR:
                self.delai = self.nbSecondes
            else:
                # on garde le délai court jusqu'à 3 valeurs normales
                self.delai = min(
                    self.delai, self.nbSecondes * (1 - min(1, 0.05 * points))
                )

        self.delai = max(self.delai, DELAI_PLANCHER)
        return grade

    def alarmeDeclenchee(self, grade):
        """Grade 3 : alerte immédiate. Sinon : 3 mesures anormales."""
        if grade >= 3:
            return True
        return grade >= 1 and self.compteurAnormal >= NB_ANORMALES_ALARME
