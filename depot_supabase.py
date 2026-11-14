import os

from supabase import create_client


class DepotSupabase:
    """Persistance des mesures dans Supabase."""

    def __init__(self, url=None, cle=None):
        self.client = create_client(
            url or os.environ["SUPABASE_URL"],
            cle or os.environ["SUPABASE_KEY"],
        )

    def enregistrerMesure(self, mesure, patientId):
        """Enregistre une mesure COMPLÈTE en un seul appel (transaction côté base).

        À appeler quand la mesure est terminée :
        - sans changement de grade : mesure.pression contient 1 lecture;
        - avec changement de grade : après la confirmation, 2 lectures.
        Retourne l'id de la mesure.
        """
        s = mesure.symptomes
        reponse = self.client.rpc(
            "enregistrer_mesure",
            {
                "p_patient_id": patientId,
                "p_date_heure": mesure.dateHeure.isoformat(),
                "p_symptomes": {
                    "mal_de_tete": s["malDeTete"],
                    "vertige": s["vertige"],
                    "vision_floue": s["visionFloue"],
                    "essoufflement": s["essoufflement"],
                    "saignement_de_nez": s["saignementDeNez"],
                    "fatigue": s["fatigue"],
                    "confusion": s["confusion"],
                    "perte_de_balan": s["perteDeBalan"],
                },
                "p_points_inquietude": mesure.pointsInquietude,
                "p_lectures": [
                    {
                        "ordre": i,
                        "systolique": p.systolique,
                        "diastolique": p.diastolique,
                        "pouls": p.pouls,
                    }
                    for i, p in enumerate(mesure.pression)
                ],
            },
        ).execute()
        return reponse.data
