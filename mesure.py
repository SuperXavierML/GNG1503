##AIA

from pression import Pression

class Mesure:

    def __init__(self, systolique, diastolique, pouls, malDeTete, vertige,
                 visionFloue, essoufflement, saignementDeNez, fatigue,confusion, perteDeBalan):
        
        self.pression= [Pression(systolique, diastolique, pouls)]

        self.pointsInquietude = ((0.5)*(malDeTete + vertige + visionFloue
                                 + essoufflement + saignementDeNez + fatigue + confusion + perteDeBalan))

    def mesureDeVerification(self, systolique, diastolique, pouls):
        self.pression.append(Pression(systolique, diastolique, pouls))

##AIA : Partie assistée par Claude, Anthropic, 08/11/2026

##J'ai utilisé Claude afin de m'aider à corriger et à nettoyer mes tests. 
##J'ai également utilisé Claude pour créer des cas de test permettant de vérifier le fonctionnement de 
##l'application. Le résultat final demeure le reflet de ma logique et le fruit de mon travail.