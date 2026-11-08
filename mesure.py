from pression import Pression

class Mesure:

    def __init__(self, systolique, diastolique, pouls, malDeTete, vertige,
                 visionFloue, essoufflement, saignementDeNez, fatigue,confusion, perteDeBalan):
        
        self.pression= [Pression(systolique, diastolique, pouls)]

        self.pointsInquietude = ((0.5)*(malDeTete + vertige + visionFloue
                                 + essoufflement + saignementDeNez + fatigue + confusion + perteDeBalan))

    def mesureDeVerification(self, systolique, diastolique, pouls):
        self.pression.append(Pression(systolique, diastolique, pouls))
