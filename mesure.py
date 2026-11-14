from datetime import datetime
from pression import Pression


class Mesure:
    """Une mesure = symptômes + tableau de lectures.

    pression[0] : première lecture
    pression[1] : lecture de confirmation (si elle a lieu)
    """

    def __init__(self, systolique, diastolique, pouls, malDeTete, vertige,
                 visionFloue, essoufflement, saignementDeNez, fatigue,
                 confusion, perteDeBalan, dateHeure=None):
        intensites = (
            malDeTete,
            vertige,
            visionFloue,
            essoufflement,
            saignementDeNez,
            fatigue,
            confusion,
            perteDeBalan,
        )
        if any(
            type(intensite) is not int or not 0 <= intensite <= 5
            for intensite in intensites
        ):
            raise ValueError(
                "Chaque intensité de symptôme doit être un entier de 0 à 5."
            )

        self.dateHeure = dateHeure if dateHeure is not None else datetime.now()

        self.pression = [Pression(systolique, diastolique, pouls)]
        self.symptomes = {
            "malDeTete": malDeTete,
            "vertige": vertige,
            "visionFloue": visionFloue,
            "essoufflement": essoufflement,
            "saignementDeNez": saignementDeNez,
            "fatigue": fatigue,
            "confusion": confusion,
            "perteDeBalan": perteDeBalan,
        }
        self.pointsInquietude = 0.5 * sum(self.symptomes.values())

    def mesureDeVerification(self, systolique, diastolique, pouls):
        """Ajoute la lecture de confirmation (une seule par mesure)."""
        if len(self.pression) >= 2:
            raise ValueError("Cette mesure a déjà une confirmation.")
        self.pression.append(Pression(systolique, diastolique, pouls))
