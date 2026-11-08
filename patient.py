## AIA

NB_SYMPTOMES_CRITIQUE = 4
NB_ANORMALES_PLANCHER = 4 
DELAI_PLANCHER = 5 * 60 * 60

class Patient:

    def __init__(self, facteurRisque, nom, identifiant):
        self.nom=nom
        self.identifiant=identifiant
        self.compteurAnormal = 0
        self.compteurNormal = 3
        self.hautTension=False
 
        if facteurRisque >= 6:
            self.seuilDiastolique = 80
            self.seuilSystolique = 130
            self.nbSecondes = 24 * 60 * 60
        else:
            self.seuilDiastolique = 90
            self.seuilSystolique = 140
            self.nbSecondes = 48 * 60 * 60

        self.delai=self.nbSecondes

    def verificationDeTension(self, derniereMesure, i ):
        p = derniereMesure.pression[i]
        self.hautTension = (p.diastolique >= self.seuilDiastolique
                            or p.systolique >= self.seuilSystolique)
        return self.hautTension

    def confirmationDeTension(self, derniereMesure):

        points = derniereMesure.pointsInquietude

        danger = self.verificationDeTension(derniereMesure, -1 ) or (points >= NB_SYMPTOMES_CRITIQUE)
       
        if (danger):
            self.compteurNormal = 0
            self.compteurAnormal += 1
        else:
            self.compteurNormal += 1
            self.compteurAnormal = max(0, self.compteurAnormal - 1)  

        return self.notificationAlerte(derniereMesure)

    def enregistreValeur(self, derniereMesure):

        validation=False
        points = derniereMesure.pointsInquietude
        symptomesGraves = points >= NB_SYMPTOMES_CRITIQUE
        frequence = 0
        

        if (self.verificationDeTension(derniereMesure,0) or (symptomesGraves)):
            self.compteurAnormal += 1
            self.compteurNormal = 0
            if (self.hautTension):
                frequence = min(1, 0.5 + 0.05 * points)
            else:
                frequence = min(1, max(0.5, 0.05 * points))
        else:
            self.compteurNormal += 1
            if (self.compteurNormal >= 3):
                self.compteurAnormal = 0
 
        self.delai = self.nbSecondes * (1 - frequence)

        if self.compteurAnormal == 1:
            validation=True

        if ((self.compteurAnormal >= NB_ANORMALES_PLANCHER) and (self.delai < DELAI_PLANCHER)):
            self.delai = DELAI_PLANCHER   

        return validation
    
    def notificationAlerte(self, derniereMesure):
        danger = self.hautTension or derniereMesure.pointsInquietude >= NB_SYMPTOMES_CRITIQUE
        return danger and self.compteurAnormal >= 2
    
    def messageRassurent(self, derniereMesure):
        points = derniereMesure.pointsInquietude
        danger = ((self.hautTension) or (points >= NB_SYMPTOMES_CRITIQUE))

        if((danger) and (self.compteurAnormal >= 2)):
            return True
        return False

##AIA : Partie assistée par Claude, Anthropic, 08/11/2026

##J'ai utilisé Claude afin de m'aider à corriger et à nettoyer mes tests. 
##J'ai également utilisé Claude pour créer des cas de test permettant de vérifier le fonctionnement de 
##l'application. Le résultat final demeure le reflet de ma logique et le fruit de mon travail.