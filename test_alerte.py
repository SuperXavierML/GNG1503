"""
Tests unitaires de la logique d'alerte en deux temps.
 
Modules attendus dans le même dossier : pression.py, mesure.py, patient.py
Lancer avec :  python -m unittest -v test_alerte      (ou : pytest -v)
 
Flux simulé (comme le ferait l'interface) :
    1. patient.enregistreValeur(mesure)
         -> True  : l'UI affiche le message de repos et demande une mesure de vérification
         -> False : rien de plus à faire
    2. mesure.mesureDeVerification(...) puis patient.confirmationDeTension(mesure)
         -> True  : l'UI envoie l'alerte au médecin
         -> False : pas d'alerte
"""
import inspect
import unittest
 
from mesure import Mesure
from patient import (DELAI_PLANCHER, NB_ANORMALES_PLANCHER,
                     NB_SYMPTOMES_CRITIQUE, Patient)
from pression import Pression
 
NB_SYMPTOMES = 8          # nombre de symptômes dans Mesure
MAX_PAR_SYMPTOME = 5      # chaque symptôme vaut de 0 à 5
NORMALE = (115, 75, 70)   # (systolique, diastolique, pouls) sous tous les seuils
 
 
# --------------------------------------------------------------------------
# Outils de test
# --------------------------------------------------------------------------
def repartir(total):
    """Répartit une somme de symptômes (0 à 40) sur les 8 symptômes, max 5 chacun."""
    assert 0 <= total <= NB_SYMPTOMES * MAX_PAR_SYMPTOME
    valeurs = []
    for _ in range(NB_SYMPTOMES):
        v = min(MAX_PAR_SYMPTOME, total)
        valeurs.append(v)
        total -= v
    return valeurs
 
 
def mesure(systolique=115, diastolique=75, pouls=70, symptomes=0):
    """Crée une Mesure ; `symptomes` = somme des 8 valeurs (points = 0,5 x somme)."""
    return Mesure(systolique, diastolique, pouls, *repartir(symptomes))
 
 
def patient_standard():
    return Patient(0, "Standard", "S-1")      # seuils 140/90, 48 h
 
 
def patient_a_risque():
    return Patient(6, "A risque", "R-1")      # seuils 130/80, 24 h
 
 
PROFILS = (patient_standard, patient_a_risque)
 
# Somme de symptômes qui donne exactement le seuil critique (points = 4)
SOMME_CRITIQUE = int(2 * NB_SYMPTOMES_CRITIQUE)
 
 
def prend_une_mesure(methode):
    """True si notificationAlerte attend la mesure courante en paramètre."""
    return len(inspect.signature(methode).parameters) > 0
 
 
def alerte_active(patient, mesure_courante):
    """Appelle notificationAlerte avec ou sans la mesure, selon la signature du code testé."""
    if prend_une_mesure(patient.notificationAlerte):
        return patient.notificationAlerte(mesure_courante)
    return patient.notificationAlerte()
 
 
def deux_temps(patient, premiere, verification):
    """Simule l'UI. Retourne (message_de_repos, alerte_au_medecin)."""
    repos = patient.enregistreValeur(premiere)
    if not repos:
        return repos, alerte_active(patient, premiere)
    premiere.mesureDeVerification(*verification)
    return repos, patient.confirmationDeTension(premiere)
 
 
def echantillons(p):
    """Pressions (sys, dia) élevées et normales pour les seuils du patient p."""
    sys_hautes = (p.seuilSystolique, p.seuilSystolique + 1, p.seuilSystolique + 40)
    dia_hautes = (p.seuilDiastolique, p.seuilDiastolique + 1, p.seuilDiastolique + 25)
    sys_ok = (90, p.seuilSystolique - 1)
    dia_ok = (60, p.seuilDiastolique - 1)
    elevees = ([(s, d) for s in sys_hautes for d in dia_ok + dia_hautes]
               + [(s, d) for s in sys_ok for d in dia_hautes])
    normales = [(s, d) for s in sys_ok for d in dia_ok]
    return elevees, normales
 
 
def frequence_attendue(haute_tension, points):
    if haute_tension:
        return min(1, 0.5 + 0.05 * points)
    return min(1, max(0.5, 0.05 * points))
 
 
# --------------------------------------------------------------------------
# Pression et Mesure
# --------------------------------------------------------------------------
class TestPression(unittest.TestCase):
 
    def test_attributs_et_pression_differentielle(self):
        p = Pression(120, 80, 70)
        self.assertEqual((p.systolique, p.diastolique, p.pouls), (120, 80, 70))
        pulsee = getattr(p, "pulsee", None) or getattr(p, "pulsée")   # nom avec ou sans accent
        self.assertEqual(pulsee(), 40)
 
 
class TestMesure(unittest.TestCase):
 
    def test_points_sans_symptome(self):
        self.assertEqual(mesure(symptomes=0).pointsInquietude, 0)
 
    def test_points_maximum(self):
        m = Mesure(115, 75, 70, *([MAX_PAR_SYMPTOME] * NB_SYMPTOMES))
        self.assertEqual(m.pointsInquietude, 20)
 
    def test_chaque_symptome_compte_pour_un_demi_point_par_niveau(self):
        for i in range(NB_SYMPTOMES):
            for niveau in range(0, MAX_PAR_SYMPTOME + 1):
                with self.subTest(symptome=i, niveau=niveau):
                    valeurs = [0] * NB_SYMPTOMES
                    valeurs[i] = niveau
                    m = Mesure(115, 75, 70, *valeurs)
                    self.assertAlmostEqual(m.pointsInquietude, 0.5 * niveau)
 
    def test_tous_les_symptomes_sont_additionnes(self):
        m = Mesure(115, 75, 70, 1, 2, 3, 4, 5, 0, 1, 2)
        self.assertAlmostEqual(m.pointsInquietude, 0.5 * 18)
 
    def test_mesure_de_verification_ajoutee_a_la_suite(self):
        m = mesure(150, 95, 80)
        m.mesureDeVerification(118, 76, 66)
        self.assertEqual(len(m.pression), 2)
        self.assertEqual(m.pression[0].systolique, 150)
        self.assertEqual(m.pression[-1].systolique, 118)
        self.assertEqual(m.pression[-1].pouls, 66)
 
 
# --------------------------------------------------------------------------
# Seuils de tension
# --------------------------------------------------------------------------
class TestSeuils(unittest.TestCase):
 
    def test_seuils_selon_facteur_de_risque(self):
        for facteur, sys_, dia, secondes in [(0, 140, 90, 48 * 3600), (5, 140, 90, 48 * 3600),
                                             (6, 130, 80, 24 * 3600), (10, 130, 80, 24 * 3600)]:
            with self.subTest(facteur=facteur):
                p = Patient(facteur, "x", "1")
                self.assertEqual((p.seuilSystolique, p.seuilDiastolique, p.nbSecondes),
                                 (sys_, dia, secondes))
                self.assertEqual(p.delai, secondes)
 
    def test_limites_inclusives(self):
        for fabrique in PROFILS:
            p = fabrique()
            S, D = p.seuilSystolique, p.seuilDiastolique
            cas = [((S, D - 1), True), ((S - 1, D), True), ((S, D), True),
                   ((S - 1, D - 1), False), ((S + 20, D - 20), True)]
            for (s, d), attendu in cas:
                with self.subTest(profil=p.nom, s=s, d=d):
                    self.assertEqual(p.verificationDeTension(mesure(s, d), 0), attendu)
                    self.assertEqual(p.hautTension, attendu)
 
    def test_tension_a_risque_se_declenche_plus_tot(self):
        m = mesure(135, 85)
        self.assertFalse(patient_standard().verificationDeTension(m, 0))
        self.assertTrue(patient_a_risque().verificationDeTension(m, 0))
 
 
# --------------------------------------------------------------------------
# Logique en deux temps
# --------------------------------------------------------------------------
class TestDeuxTemps(unittest.TestCase):
 
    def test_mesure_normale_aucun_message_ni_alerte(self):
        for fabrique in PROFILS:
            p = fabrique()
            m = mesure(*NORMALE)
            self.assertFalse(p.enregistreValeur(m))
            self.assertFalse(alerte_active(p, m))
            self.assertEqual(p.compteurAnormal, 0)
 
    def test_premier_depassement_demande_repos_sans_alerte(self):
        for fabrique in PROFILS:
            p = fabrique()
            s, d = p.seuilSystolique + 10, p.seuilDiastolique + 5
            m = mesure(s, d)
            self.assertTrue(p.enregistreValeur(m))                # message de repos
            self.assertFalse(alerte_active(p, m))                 # pas encore d'alerte
            self.assertEqual(p.compteurAnormal, 1)
 
    def test_double_depassement_declenche_alerte(self):
        for fabrique in PROFILS:
            p = fabrique()
            s, d = p.seuilSystolique + 10, p.seuilDiastolique + 5
            repos, alerte = deux_temps(p, mesure(s, d), (s, d, 80))
            self.assertTrue(repos)
            self.assertTrue(alerte)
 
    def test_depassement_isole_pas_d_alerte(self):
        for fabrique in PROFILS:
            p = fabrique()
            s, d = p.seuilSystolique + 10, p.seuilDiastolique + 5
            repos, alerte = deux_temps(p, mesure(s, d), NORMALE)
            self.assertTrue(repos)
            self.assertFalse(alerte)
            self.assertEqual(p.compteurAnormal, 0)
 
    def test_verification_elevee_apres_mesure_normale_pas_d_alerte(self):
        for fabrique in PROFILS:
            p = fabrique()
            p.enregistreValeur(mesure(*NORMALE))
            m = mesure(*NORMALE)
            m.mesureDeVerification(p.seuilSystolique + 10, p.seuilDiastolique + 5, 80)
            self.assertFalse(p.confirmationDeTension(m))
 
    def test_alerte_persiste_tant_que_les_mesures_restent_anormales(self):
        p = patient_standard()
        m1 = mesure(160, 100)
        deux_temps(p, m1, (160, 100, 80))
        self.assertTrue(alerte_active(p, m1))
        m2 = mesure(160, 100)
        p.enregistreValeur(m2)                      # 3e dépassement
        self.assertTrue(alerte_active(p, m2))
 
    def test_retour_a_la_normale_leve_l_alerte_apres_trois_mesures_normales(self):
        p = patient_standard()
        m1 = mesure(160, 100)
        deux_temps(p, m1, (160, 100, 80))
        self.assertTrue(alerte_active(p, m1))
        for _ in range(3):
            m = mesure(*NORMALE)
            p.enregistreValeur(m)
        self.assertFalse(alerte_active(p, m))
        self.assertEqual(p.compteurAnormal, 0)
 
    # ---- Critère de réussite : 100 % des doubles dépassements -> alerte -----
    def test_100_pourcent_alerte_sur_double_depassement_persistant(self):
        total = declenchees = 0
        echecs = []
        for fabrique in PROFILS:
            ref = fabrique()
            elevees, _ = echantillons(ref)
            for premiere in elevees:
                for verification in elevees:
                    for symptomes in (0, 3, SOMME_CRITIQUE, 20):
                        p = fabrique()
                        _, alerte = deux_temps(p, mesure(*premiere, 70, symptomes),
                                               verification + (70,))
                        total += 1
                        declenchees += bool(alerte)
                        if not alerte:
                            echecs.append((ref.nom, premiere, verification, symptomes))
        self.assertGreater(total, 0)
        self.assertEqual(declenchees, total, f"Alertes manquées : {echecs[:5]}")
 
    # ---- Critère de réussite : 0 % de fausse alerte sur mesure isolée -------
    def test_0_pourcent_fausse_alerte_sur_mesure_isolee(self):
        total = fausses = 0
        cas_fautifs = []
        for fabrique in PROFILS:
            ref = fabrique()
            elevees, normales = echantillons(ref)
            for premiere in elevees:
                for verification in normales:
                    for symptomes in (0, 2 * NB_SYMPTOMES_CRITIQUE - 1):   # < seuil critique
                        p = fabrique()
                        _, alerte = deux_temps(p, mesure(*premiere, 70, symptomes),
                                               verification + (70,))
                        total += 1
                        fausses += bool(alerte)
                        if alerte:
                            cas_fautifs.append((ref.nom, premiere, verification, symptomes))
        self.assertGreater(total, 0)
        self.assertEqual(fausses, 0, f"Fausses alertes : {cas_fautifs[:5]}")
 
    def test_mesures_isolees_repetees_ne_s_accumulent_pas(self):
        """Dépassement isolé, puis retour à la normale, 20 fois de suite : jamais d'alerte."""
        for fabrique in PROFILS:
            p = fabrique()
            s, d = p.seuilSystolique + 10, p.seuilDiastolique + 5
            for cycle in range(20):
                with self.subTest(profil=p.nom, cycle=cycle):
                    repos, alerte = deux_temps(p, mesure(s, d), NORMALE)
                    self.assertTrue(repos)       # le message de repos revient à chaque fois
                    self.assertFalse(alerte)
                    self.assertEqual(p.compteurAnormal, 0)
 
 
# --------------------------------------------------------------------------
# Symptômes dans l'alerte
# --------------------------------------------------------------------------
class TestSymptomesDansAlerte(unittest.TestCase):
 
    def test_seuil_critique_exact_sur_toutes_les_sommes(self):
        """Avec une tension normale, le message de repos n'apparaît que si points >= 4."""
        for total in range(0, NB_SYMPTOMES * MAX_PAR_SYMPTOME + 1):
            with self.subTest(somme=total):
                p = patient_standard()
                m = mesure(*NORMALE, symptomes=total)
                self.assertEqual(p.enregistreValeur(m), 0.5 * total >= NB_SYMPTOMES_CRITIQUE)
 
    def test_symptomes_graves_seuls_declenchent_alerte_apres_double(self):
        for fabrique in PROFILS:
            p = fabrique()
            m = mesure(*NORMALE, symptomes=SOMME_CRITIQUE)
            self.assertTrue(p.enregistreValeur(m))
            m.mesureDeVerification(*NORMALE)
            self.assertTrue(p.confirmationDeTension(m))
 
    def test_symptomes_juste_sous_le_seuil_pas_d_alerte(self):
        for fabrique in PROFILS:
            p = fabrique()
            m = mesure(*NORMALE, symptomes=SOMME_CRITIQUE - 1)    # 3,5 points
            self.assertFalse(p.enregistreValeur(m))
            m.mesureDeVerification(*NORMALE)
            self.assertFalse(p.confirmationDeTension(m))
 
    def test_un_seul_symptome_au_maximum_ne_suffit_pas(self):
        for i in range(NB_SYMPTOMES):
            with self.subTest(symptome=i):
                valeurs = [0] * NB_SYMPTOMES
                valeurs[i] = MAX_PAR_SYMPTOME            # 2,5 points < 4
                p = patient_a_risque()
                m = Mesure(*NORMALE, *valeurs)
                self.assertFalse(p.enregistreValeur(m))
 
    def test_symptomes_graves_maintiennent_l_alerte_malgre_tension_de_verification_normale(self):
        """Tension élevée puis verification normale : les symptômes font la différence."""
        for fabrique in PROFILS:
            ref = fabrique()
            haute = (ref.seuilSystolique + 10, ref.seuilDiastolique + 5, 80)
 
            sans = fabrique()
            _, alerte_sans = deux_temps(sans, mesure(*haute[:2], 80, 0), NORMALE)
            avec = fabrique()
            _, alerte_avec = deux_temps(avec, mesure(*haute[:2], 80, SOMME_CRITIQUE), NORMALE)
 
            self.assertFalse(alerte_sans)
            self.assertTrue(alerte_avec)
 
    def test_symptomes_faibles_ne_declenchent_pas_a_eux_seuls_la_confirmation(self):
        p = patient_standard()
        m = mesure(160, 100, 80, symptomes=SOMME_CRITIQUE - 1)
        self.assertTrue(p.enregistreValeur(m))
        m.mesureDeVerification(*NORMALE)
        self.assertFalse(p.confirmationDeTension(m))
 
 
# --------------------------------------------------------------------------
# Symptômes dans le calcul de la fréquence (délai avant la prochaine mesure)
# --------------------------------------------------------------------------
class TestFrequence(unittest.TestCase):
 
    def test_mesure_normale_delai_inchange(self):
        for fabrique in PROFILS:
            p = fabrique()
            p.enregistreValeur(mesure(*NORMALE))
            self.assertEqual(p.delai, p.nbSecondes)
 
    def test_valeurs_de_reference_tension_elevee(self):
        # Patient standard : 48 h = 172 800 s
        p = patient_standard()
        p.enregistreValeur(mesure(150, 95))                       # 0 point  -> fréquence 0,5
        self.assertAlmostEqual(p.delai, 86400)
 
        p = patient_standard()
        p.enregistreValeur(mesure(150, 95, 70, symptomes=10))     # 5 points -> 0,75
        self.assertAlmostEqual(p.delai, 172800 * 0.25)
 
        p = patient_standard()
        p.enregistreValeur(mesure(150, 95, 70, symptomes=20))     # 10 points -> 1 (plafonné)
        self.assertAlmostEqual(p.delai, 0)
 
    def test_formule_tension_elevee_pour_toutes_les_sommes_de_symptomes(self):
        for fabrique in PROFILS:
            for total in range(0, NB_SYMPTOMES * MAX_PAR_SYMPTOME + 1):
                p = fabrique()
                m = mesure(p.seuilSystolique + 5, p.seuilDiastolique, 70, total)
                p.enregistreValeur(m)
                attendu = p.nbSecondes * (1 - frequence_attendue(True, 0.5 * total))
                with self.subTest(profil=p.nom, somme=total):
                    self.assertAlmostEqual(p.delai, attendu)
 
    def test_formule_symptomes_seuls_pour_les_sommes_graves(self):
        for fabrique in PROFILS:
            for total in range(SOMME_CRITIQUE, NB_SYMPTOMES * MAX_PAR_SYMPTOME + 1):
                p = fabrique()
                m = mesure(*NORMALE, symptomes=total)
                p.enregistreValeur(m)
                attendu = p.nbSecondes * (1 - frequence_attendue(False, 0.5 * total))
                with self.subTest(profil=p.nom, somme=total):
                    self.assertFalse(p.hautTension)
                    self.assertAlmostEqual(p.delai, attendu)
 
    def test_plus_de_symptomes_ne_rallonge_jamais_le_delai(self):
        for fabrique in PROFILS:
            for tension in ("haute", "normale"):
                precedent = None
                for total in range(SOMME_CRITIQUE if tension == "normale" else 0,
                                   NB_SYMPTOMES * MAX_PAR_SYMPTOME + 1):
                    p = fabrique()
                    base = (p.seuilSystolique + 5, p.seuilDiastolique) if tension == "haute" else NORMALE[:2]
                    p.enregistreValeur(mesure(*base, 70, total))
                    with self.subTest(profil=p.nom, tension=tension, somme=total):
                        self.assertGreaterEqual(p.delai, 0)
                        if precedent is not None:
                            self.assertLessEqual(p.delai, precedent + 1e-9)
                    precedent = p.delai
 
    def test_symptomes_raccourcissent_le_delai_a_tension_egale(self):
        p1, p2 = patient_standard(), patient_standard()
        p1.enregistreValeur(mesure(150, 95, 70, symptomes=0))
        p2.enregistreValeur(mesure(150, 95, 70, symptomes=12))
        self.assertLess(p2.delai, p1.delai)
 
    def test_retour_a_la_normale_remet_le_delai_de_base(self):
        p = patient_standard()
        p.enregistreValeur(mesure(160, 100, 70, symptomes=12))
        self.assertLess(p.delai, p.nbSecondes)
        p.enregistreValeur(mesure(*NORMALE))
        self.assertEqual(p.delai, p.nbSecondes)
 
    def test_plancher_applique_apres_assez_de_mesures_anormales(self):
        p = patient_a_risque()
        for _ in range(NB_ANORMALES_PLANCHER - 1):
            p.enregistreValeur(mesure(150, 95, 70, symptomes=40))   # fréquence 1 -> délai 0
        self.assertAlmostEqual(p.delai, 0)                          # pas encore de plancher
        p.enregistreValeur(mesure(150, 95, 70, symptomes=40))
        self.assertEqual(p.compteurAnormal, NB_ANORMALES_PLANCHER)
        self.assertEqual(p.delai, DELAI_PLANCHER)
 
    def test_plancher_ne_rallonge_pas_un_delai_deja_plus_long(self):
        p = patient_a_risque()
        for _ in range(NB_ANORMALES_PLANCHER):
            p.enregistreValeur(mesure(150, 95, 70, symptomes=0))    # fréquence 0,5 -> 12 h
        self.assertAlmostEqual(p.delai, p.nbSecondes * 0.5)
        self.assertGreater(p.delai, DELAI_PLANCHER)
 
 
# --------------------------------------------------------------------------
# messageRassurent(derniereMesure) : seulement si une mesure inquiétante est
# confirmée, puis lors des mesures inquiétantes suivantes, jamais si la mesure
# est normale (même si compteurAnormal n'est pas encore revenu à 0)
# --------------------------------------------------------------------------
def tension_elevee(p):
    return p.seuilSystolique + 10, p.seuilDiastolique + 5
 
 
class TestMessageRassurent(unittest.TestCase):
 
    def test_mesure_normale_seule_pas_de_message(self):
        for fabrique in PROFILS:
            p = fabrique()
            m = mesure(*NORMALE)
            p.enregistreValeur(m)
            self.assertFalse(p.messageRassurent(m))
 
    def test_premier_depassement_non_confirme_pas_de_message(self):
        for fabrique in PROFILS:
            p = fabrique()
            m = mesure(*tension_elevee(p))
            self.assertTrue(p.enregistreValeur(m))
            self.assertFalse(p.messageRassurent(m))
 
    def test_depassement_isole_pas_de_message(self):
        for fabrique in PROFILS:
            p = fabrique()
            m = mesure(*tension_elevee(p))
            deux_temps(p, m, NORMALE)
            self.assertFalse(p.messageRassurent(m))
 
    def test_depassement_confirme_message_envoye(self):
        for fabrique in PROFILS:
            p = fabrique()
            s, d = tension_elevee(p)
            m = mesure(s, d)
            deux_temps(p, m, (s, d, 80))
            self.assertTrue(p.messageRassurent(m))
 
    def test_mesure_inquietante_suivante_apres_confirmation_message_envoye(self):
        for fabrique in PROFILS:
            p = fabrique()
            s, d = tension_elevee(p)
            deux_temps(p, mesure(s, d), (s, d, 80))
            suivante = mesure(s, d)
            p.enregistreValeur(suivante)
            self.assertTrue(p.messageRassurent(suivante))
 
    def test_mesure_normale_apres_alerte_pas_de_message_meme_si_compteur_non_nul(self):
        for fabrique in PROFILS:
            p = fabrique()
            s, d = tension_elevee(p)
            deux_temps(p, mesure(s, d), (s, d, 80))
            for i in range(2):                         # 1re et 2e mesures normales
                normale = mesure(*NORMALE)
                p.enregistreValeur(normale)
                with self.subTest(profil=p.nom, mesure_normale=i + 1):
                    self.assertGreaterEqual(p.compteurAnormal, 2)   # compteur pas encore à 0
                    self.assertFalse(p.messageRassurent(normale))
            normale = mesure(*NORMALE)                 # 3e : le compteur est remis à 0
            p.enregistreValeur(normale)
            self.assertEqual(p.compteurAnormal, 0)
            self.assertFalse(p.messageRassurent(normale))
 
    def test_mesure_normale_apres_alerte_ne_declenche_ni_message_ni_alerte(self):
        """Après une alerte, une mesure normale (compteur anormal pas encore à 0) ne relance rien."""
        p = patient_standard()
        deux_temps(p, mesure(160, 100), (160, 100, 80))
        normale = mesure(*NORMALE)
        p.enregistreValeur(normale)
        self.assertGreaterEqual(p.compteurAnormal, 2)
        self.assertFalse(p.messageRassurent(normale))
        if not prend_une_mesure(p.notificationAlerte):
            self.skipTest("notificationAlerte() sans paramètre : reste vraie tant que compteurAnormal >= 2")
        self.assertFalse(alerte_active(p, normale))
 
    def test_symptomes_graves_confirmes_message_envoye(self):
        for fabrique in PROFILS:
            p = fabrique()
            m = mesure(*NORMALE, symptomes=SOMME_CRITIQUE)
            deux_temps(p, m, NORMALE)
            self.assertTrue(p.messageRassurent(m))
 
    def test_symptomes_suivants_apres_confirmation_message_envoye(self):
        p = patient_standard()
        deux_temps(p, mesure(160, 100), (160, 100, 80))
        suivante = mesure(*NORMALE, symptomes=SOMME_CRITIQUE)
        p.enregistreValeur(suivante)
        self.assertTrue(p.messageRassurent(suivante))
 
    def test_symptomes_sous_le_seuil_apres_alerte_pas_de_message(self):
        p = patient_standard()
        deux_temps(p, mesure(160, 100), (160, 100, 80))
        suivante = mesure(*NORMALE, symptomes=SOMME_CRITIQUE - 1)
        p.enregistreValeur(suivante)
        self.assertFalse(p.messageRassurent(suivante))
 
    def test_balayage_message_si_et_seulement_si_inquietant_confirme(self):
        """Message = True pour tout double dépassement ; False pour toute mesure isolée."""
        erreurs = []
        for fabrique in PROFILS:
            ref = fabrique()
            elevees, normales = echantillons(ref)
            for premiere in elevees:
                for verification in elevees + normales:
                    p = fabrique()
                    m = mesure(*premiere, 70, 0)
                    deux_temps(p, m, verification + (70,))
                    attendu = verification in elevees
                    if p.messageRassurent(m) != attendu:
                        erreurs.append((ref.nom, premiere, verification, attendu))
        self.assertEqual(erreurs, [], f"Écarts : {erreurs[:5]}")
 
    def test_balayage_apres_alerte_message_selon_la_nouvelle_mesure(self):
        erreurs = []
        for fabrique in PROFILS:
            ref = fabrique()
            elevees, normales = echantillons(ref)
            s, d = tension_elevee(ref)
            for nouvelle in elevees + normales:
                p = fabrique()
                deux_temps(p, mesure(s, d), (s, d, 80))     # alerte confirmée
                m = mesure(*nouvelle, 70, 0)
                p.enregistreValeur(m)
                attendu = nouvelle in elevees
                if p.messageRassurent(m) != attendu:
                    erreurs.append((ref.nom, nouvelle, attendu))
        self.assertEqual(erreurs, [], f"Écarts : {erreurs[:5]}")
 
 
# --------------------------------------------------------------------------
# messageRassurent(derniereMesure)
# Vrai seulement si la mesure courante est inquiétante ET déjà confirmée
# (compteurAnormal >= 2). Jamais sur une mesure normale, même si
# compteurAnormal n'est pas encore revenu à 0.
# --------------------------------------------------------------------------
class TestMessageRassurent(unittest.TestCase):
 
    def _patient_en_alerte(self, fabrique):
        p = fabrique()
        s, d = p.seuilSystolique + 10, p.seuilDiastolique + 5
        _, alerte = deux_temps(p, mesure(s, d), (s, d, 80))
        self.assertTrue(alerte)
        return p
 
    def test_pas_de_message_au_premier_depassement(self):
        for fabrique in PROFILS:
            p = fabrique()
            m = mesure(p.seuilSystolique + 10, p.seuilDiastolique + 5)
            self.assertTrue(p.enregistreValeur(m))
            self.assertFalse(p.messageRassurent(m))
 
    def test_pas_de_message_sur_depassement_isole(self):
        for fabrique in PROFILS:
            p = fabrique()
            s, d = p.seuilSystolique + 10, p.seuilDiastolique + 5
            m = mesure(s, d)
            p.enregistreValeur(m)
            m.mesureDeVerification(*NORMALE)
            p.confirmationDeTension(m)
            self.assertFalse(p.messageRassurent(m))
 
    def test_message_quand_le_depassement_est_confirme(self):
        for fabrique in PROFILS:
            p = fabrique()
            s, d = p.seuilSystolique + 10, p.seuilDiastolique + 5
            m = mesure(s, d)
            p.enregistreValeur(m)
            m.mesureDeVerification(s, d, 80)
            self.assertTrue(p.confirmationDeTension(m))
            self.assertTrue(p.messageRassurent(m))
 
    def test_message_sur_mesure_inquietante_suivant_une_alerte(self):
        for fabrique in PROFILS:
            p = self._patient_en_alerte(fabrique)
            m = mesure(p.seuilSystolique + 5, p.seuilDiastolique + 2)
            p.enregistreValeur(m)
            self.assertTrue(p.messageRassurent(m))
 
    def test_pas_de_message_sur_mesure_normale_meme_si_compteur_anormal_non_nul(self):
        for fabrique in PROFILS:
            p = self._patient_en_alerte(fabrique)
            m = mesure(*NORMALE)
            p.enregistreValeur(m)
            self.assertGreaterEqual(p.compteurAnormal, 2)     # pas encore remis à 0
            self.assertFalse(p.messageRassurent(m))
 
    def test_symptomes_graves_apres_alerte_declenchent_le_message(self):
        for fabrique in PROFILS:
            p = self._patient_en_alerte(fabrique)
            m = mesure(*NORMALE, symptomes=SOMME_CRITIQUE)
            p.enregistreValeur(m)
            self.assertTrue(p.messageRassurent(m))
 
    def test_symptomes_sous_le_seuil_apres_alerte_pas_de_message(self):
        for fabrique in PROFILS:
            p = self._patient_en_alerte(fabrique)
            m = mesure(*NORMALE, symptomes=SOMME_CRITIQUE - 1)
            p.enregistreValeur(m)
            self.assertFalse(p.messageRassurent(m))
 
    def test_alternance_inquietant_normal_apres_alerte(self):
        """Le message suit la mesure courante, pas l'historique."""
        for fabrique in PROFILS:
            p = self._patient_en_alerte(fabrique)
            attendus = [True, False, True, False]
            for attendu in attendus:
                if attendu:
                    m = mesure(p.seuilSystolique + 5, p.seuilDiastolique + 2)
                else:
                    m = mesure(*NORMALE)
                p.enregistreValeur(m)
                with self.subTest(profil=p.nom, attendu=attendu):
                    self.assertEqual(p.messageRassurent(m), attendu)
 
    def test_balayage_apres_alerte(self):
        total = 0
        for fabrique in PROFILS:
            ref = fabrique()
            elevees, normales = echantillons(ref)
            for (s, d), attendu in [(x, True) for x in elevees] + [(x, False) for x in normales]:
                p = self._patient_en_alerte(fabrique)
                m = mesure(s, d)
                p.enregistreValeur(m)
                total += 1
                with self.subTest(profil=ref.nom, s=s, d=d):
                    self.assertEqual(p.messageRassurent(m), attendu)
        self.assertGreater(total, 0)
 
 
# --------------------------------------------------------------------------
# État interne : compteurs et drapeau hautTension
# --------------------------------------------------------------------------
class TestCompteurs(unittest.TestCase):
 
    def test_etat_initial(self):
        for fabrique in PROFILS:
            p = fabrique()
            self.assertEqual(p.compteurAnormal, 0)
            self.assertEqual(p.compteurNormal, 3)
            self.assertFalse(p.hautTension)
            self.assertEqual(p.delai, p.nbSecondes)
            self.assertFalse(alerte_active(p, mesure(*NORMALE)))
 
    def test_mesure_anormale_incremente_anormal_et_remet_normal_a_zero(self):
        p = patient_standard()
        p.enregistreValeur(mesure(160, 100))
        self.assertEqual((p.compteurAnormal, p.compteurNormal), (1, 0))
        p.enregistreValeur(mesure(160, 100))
        self.assertEqual((p.compteurAnormal, p.compteurNormal), (2, 0))
 
    def test_compteur_anormal_remis_a_zero_seulement_apres_trois_mesures_normales(self):
        p = patient_standard()
        p.enregistreValeur(mesure(160, 100))
        p.enregistreValeur(mesure(160, 100))                      # anormal = 2
        for attendu_normal, attendu_anormal in [(1, 2), (2, 2), (3, 0)]:
            p.enregistreValeur(mesure(*NORMALE))
            self.assertEqual((p.compteurNormal, p.compteurAnormal),
                             (attendu_normal, attendu_anormal))
 
    def test_validation_vraie_seulement_quand_compteur_anormal_vaut_un(self):
        p = patient_standard()
        self.assertTrue(p.enregistreValeur(mesure(160, 100)))      # compteur = 1
        self.assertFalse(p.enregistreValeur(mesure(160, 100)))     # compteur = 2
        self.assertFalse(p.enregistreValeur(mesure(160, 100)))     # compteur = 3
 
    def test_confirmation_normale_decremente_sans_descendre_sous_zero(self):
        p = patient_standard()
        m = mesure(*NORMALE)
        m.mesureDeVerification(*NORMALE)
        for _ in range(3):
            self.assertFalse(p.confirmationDeTension(m))
            self.assertEqual(p.compteurAnormal, 0)
 
    def test_confirmation_anormale_remet_compteur_normal_a_zero(self):
        p = patient_standard()
        m = mesure(160, 100)
        p.enregistreValeur(m)
        m.mesureDeVerification(160, 100, 80)
        p.confirmationDeTension(m)
        self.assertEqual((p.compteurAnormal, p.compteurNormal), (2, 0))
 
    def test_confirmation_normale_incremente_compteur_normal(self):
        p = patient_standard()
        m = mesure(160, 100)
        p.enregistreValeur(m)                                      # normal = 0
        m.mesureDeVerification(*NORMALE)
        p.confirmationDeTension(m)
        self.assertEqual((p.compteurAnormal, p.compteurNormal), (0, 1))
 
    def test_haute_tension_reflete_la_derniere_pression_evaluee(self):
        p = patient_standard()
        m = mesure(160, 100)
        p.enregistreValeur(m)
        self.assertTrue(p.hautTension)
        m.mesureDeVerification(*NORMALE)
        p.confirmationDeTension(m)
        self.assertFalse(p.hautTension)
 
    def test_verification_de_tension_indice_premier_et_dernier(self):
        p = patient_standard()
        m = mesure(160, 100)
        m.mesureDeVerification(*NORMALE)
        self.assertTrue(p.verificationDeTension(m, 0))
        self.assertFalse(p.verificationDeTension(m, -1))
 
    def test_retours_de_type_booleen(self):
        p = patient_standard()
        m = mesure(160, 100)
        self.assertIsInstance(p.enregistreValeur(m), bool)
        m.mesureDeVerification(160, 100, 80)
        self.assertIsInstance(p.confirmationDeTension(m), bool)
        self.assertIsInstance(alerte_active(p, m), bool)
        self.assertIsInstance(p.messageRassurent(m), bool)
 
 
# --------------------------------------------------------------------------
# Scénario de bout en bout
# --------------------------------------------------------------------------
class TestScenarioComplet(unittest.TestCase):
 
    def test_cycle_complet_alerte_puis_retour_a_la_normale(self):
        p = patient_standard()
 
        # 1. Mesure normale : rien
        m = mesure(*NORMALE)
        self.assertFalse(p.enregistreValeur(m))
        self.assertFalse(alerte_active(p, m))
 
        # 2. Premier dépassement : message de repos, pas d'alerte
        m = mesure(160, 100)
        self.assertTrue(p.enregistreValeur(m))
        self.assertFalse(alerte_active(p, m))
        self.assertFalse(p.messageRassurent(m))
 
        # 3. Vérification toujours élevée : alerte au médecin
        m.mesureDeVerification(160, 100, 80)
        self.assertTrue(p.confirmationDeTension(m))
 
        # 4. Nouvelle mesure inquiétante : message rassurant
        m = mesure(155, 95)
        p.enregistreValeur(m)
        self.assertTrue(p.messageRassurent(m))
 
        # 5. Trois mesures normales : alerte levée
        for _ in range(3):
            m = mesure(*NORMALE)
            p.enregistreValeur(m)
            self.assertFalse(p.messageRassurent(m))
        self.assertFalse(alerte_active(p, m))
 
        # 6. Le cycle recommence normalement
        m = mesure(160, 100)
        self.assertTrue(p.enregistreValeur(m))
        self.assertFalse(alerte_active(p, m))
 
    def test_scenario_symptomes_sans_hypertension(self):
        p = patient_a_risque()
        m = mesure(*NORMALE, symptomes=SOMME_CRITIQUE)
        self.assertTrue(p.enregistreValeur(m))                     # repos demandé
        m.mesureDeVerification(*NORMALE)
        self.assertTrue(p.confirmationDeTension(m))                # alerte (symptômes persistants)
        self.assertTrue(p.messageRassurent(m))
 
 
if __name__ == "__main__":
    unittest.main(verbosity=2)
 
