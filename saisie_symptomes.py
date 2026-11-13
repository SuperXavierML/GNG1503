import math
import tkinter as tk
from tkinter import ttk, messagebox

from gestionnaire_tache import GestionnaireDeTache
from mesure import Mesure
from patient import Patient


SYMPTOMES = [
    "Maux de tête",
    "Vertiges",
    "Vision floue",
    "Saignement du nez",
    "Essoufflement",
    "Faiblesse musculaire",
    "Confusion",
    "Perte d'équilibre",
]
INTENSITES = range(6)  # 0 à 5

# Nom affiché -> paramètre de Mesure
PARAMETRES_SYMPTOMES = {
    "Maux de tête": "malDeTete",
    "Vertiges": "vertige",
    "Vision floue": "visionFloue",
    "Essoufflement": "essoufflement",
    "Saignement du nez": "saignementDeNez",
    "Faiblesse musculaire": "fatigue",
    "Confusion": "confusion",
    "Perte d'équilibre": "perteDeBalan",
}

BLEU = "#2F5D9E"
GRIS = "#9AA5B1"
ROUGE = "#C62828"


def dessiner_icone(canevas, nom, actif):
    canevas.delete("all")
    trait = BLEU if actif else GRIS
    alerte = ROUGE if actif else GRIS

    if nom == "Maux de tête":
        canevas.create_oval(9, 12, 35, 42, outline=trait, width=2)
        canevas.create_oval(17, 25, 20, 28, fill=trait, outline=trait)
        canevas.create_oval(25, 25, 28, 28, fill=trait, outline=trait)
        canevas.create_line(18, 35, 26, 35, fill=trait, width=2)
        canevas.create_line(31, 3, 26, 11, 33, 11, 28, 19, fill=alerte, width=2)

    elif nom == "Vertiges":
        points = []
        for i in range(60):
            angle = i / 59 * 4 * math.pi
            rayon = 2 + 19 * i / 59
            points += [23 + rayon * math.cos(angle), 23 + rayon * math.sin(angle)]
        canevas.create_line(*points, smooth=True, fill=trait, width=2)

    elif nom == "Vision floue":
        canevas.create_polygon(
            3, 23, 14, 11, 32, 11, 43, 23, 32, 35, 14, 35,
            smooth=True, fill="", outline=trait, width=2, dash=(4, 3),
        )
        canevas.create_oval(16, 16, 30, 30, fill=trait, outline=trait)

    elif nom == "Saignement du nez":
        canevas.create_line(
            16, 4, 14, 24, 8, 32, 13, 38, 24, 38,
            smooth=True, fill=trait, width=2,
        )
        canevas.create_oval(14, 31, 19, 35, outline=trait, width=2)
        canevas.create_polygon(
            32, 22, 36, 29, 36, 34, 32, 38, 28, 34, 28, 29,
            smooth=True, fill=alerte, outline=alerte,
        )

    elif nom == "Essoufflement":
        canevas.create_line(23, 5, 23, 22, fill=trait, width=2)
        canevas.create_polygon(
            21, 14, 12, 16, 6, 30, 8, 41, 18, 41, 21, 30,
            smooth=True, fill="", outline=trait, width=2,
        )
        canevas.create_polygon(
            25, 14, 34, 16, 40, 30, 38, 41, 28, 41, 25, 30,
            smooth=True, fill="", outline=trait, width=2,
        )

    elif nom == "Faiblesse musculaire":
        canevas.create_line(14, 15, 32, 15, fill=trait, width=3)
        canevas.create_rectangle(8, 8, 14, 22, outline=trait, width=2)
        canevas.create_rectangle(32, 8, 38, 22, outline=trait, width=2)
        canevas.create_line(23, 26, 23, 42, arrow=tk.LAST, fill=alerte, width=3)

    elif nom == "Confusion":
        canevas.create_oval(7, 5, 39, 41, outline=trait, width=2)
        canevas.create_text(
            23, 23, text="?", font=("Helvetica", 22, "bold"), fill=alerte
        )

    elif nom == "Perte d'équilibre":
        canevas.create_line(4, 42, 42, 42, fill=trait, width=2)
        canevas.create_oval(26, 4, 34, 12, outline=trait, width=2)
        canevas.create_line(29, 12, 21, 30, fill=trait, width=2)
        canevas.create_line(21, 30, 13, 42, fill=trait, width=2)
        canevas.create_line(21, 30, 27, 42, fill=trait, width=2)
        canevas.create_line(26, 18, 37, 16, fill=trait, width=2)
        canevas.create_line(26, 18, 16, 14, fill=trait, width=2)
        canevas.create_line(4, 16, 10, 16, fill=alerte, width=2)
        canevas.create_line(2, 25, 9, 25, fill=alerte, width=2)


# ----------------------------------------------------------------------
# "CARTES déroulantes"
# ----------------------------------------------------------------------
class CarteSymptome:
    def __init__(self, parent, nom):
        self.nom = nom

        self.coche = tk.BooleanVar(value=False)
        self.intensite = tk.StringVar(value="")

        self.cadre = ttk.Frame(parent, padding=8, relief="solid", borderwidth=1)
        self.cadre.pack(fill="x", pady=4)

        entete = ttk.Frame(self.cadre)
        entete.pack(fill="x")
        self.icone = tk.Canvas(
            entete,
            width=46,
            height=46,
            highlightthickness=0,
            bg=ttk.Style().lookup("TFrame", "background") or "white",
        )
        self.icone.pack(side="left")
        dessiner_icone(self.icone, nom, False)

        ttk.Checkbutton(
            entete,
            text=nom,
            variable=self.coche,
            command=self.afficher_details,
            style="Gros.TCheckbutton",
        ).pack(side="left", padx=10)

        self.details = ttk.Frame(self.cadre)
        ttk.Label(self.details, text="Intensité (0 à 5)").pack(anchor="w")
        ligne = ttk.Frame(self.details)
        ligne.pack(anchor="w", pady=(0, 4))
        for choix in INTENSITES:
            ttk.Radiobutton(
                ligne, text=str(choix), value=str(choix), variable=self.intensite
            ).pack(side="left", padx=(0, 12))

    def afficher_details(self):
        """Montre ou cache l'intensité selon la case cochée."""
        dessiner_icone(self.icone, self.nom, self.coche.get())
        if self.coche.get():
            self.details.pack(fill="x", pady=(6, 0))
        else:
            self.details.pack_forget()
            self.intensite.set("")

    def reinitialiser(self):
        """Remet cette carte à zéro (après l'enregistrement)."""
        self.coche.set(False)
        self.afficher_details()

    def valeur_intensite(self):
        """Intensité indiquée par le patient (0 à 5), ou 0 si non cochée."""
        if not self.coche.get():
            return 0
        return int(self.intensite.get())


# ----------------------------------------------------------------------
# APPLICATION : page 1 = signes vitaux, page 2 = symptômes
#   nouvelle mesure : page 1 -> page 2 -> enregistrer
#   confirmation    : page 1 seulement
# ----------------------------------------------------------------------
class Application:
    def __init__(self, fenetre, gestionnaire):
        self.fenetre = fenetre
        self.gestionnaire = gestionnaire
        self.mode = "nouvelle"   # "nouvelle" ou "confirmation"
        self.page = "vitaux"     # "vitaux" ou "symptomes"

        self.champ_systolique = tk.StringVar()
        self.champ_diastolique = tk.StringVar()
        self.champ_pouls = tk.StringVar()
        self.titre = tk.StringVar()

        ttk.Label(
            fenetre, textvariable=self.titre, font=("Helvetica", 20, "bold")
        ).pack(anchor="w", padx=16, pady=(16, 8))

        barre_boutons = ttk.Frame(fenetre)
        barre_boutons.pack(side="bottom", fill="x", padx=16, pady=12)
        self.bouton_retour = ttk.Button(
            barre_boutons, text="Précédent", command=self.retour
        )
        self.bouton_principal = ttk.Button(
            barre_boutons, text="Suivant", command=self.avancer
        )
        self.bouton_principal.pack(side="right", ipady=8, padx=(8, 0))

        corps = ttk.Frame(fenetre)
        corps.pack(fill="both", expand=True, padx=(16, 0))
        self.page_vitaux = self._construire_page_vitaux(corps)
        self.page_symptomes = self._construire_page_symptomes(corps)

        self.afficher()

    # ---------------- construction des pages ----------------
    def _construire_page_vitaux(self, parent):
        page = ttk.Frame(parent)
        self.message_vitaux = tk.StringVar()
        ttk.Label(
            page, textvariable=self.message_vitaux, wraplength=420
        ).pack(anchor="w", pady=(0, 12))

        for etiquette, variable in (
            ("Systolique (mmHg)", self.champ_systolique),
            ("Diastolique (mmHg)", self.champ_diastolique),
            ("Pouls (bpm)", self.champ_pouls),
        ):
            ttk.Label(page, text=etiquette).pack(anchor="w", pady=(8, 2))
            ttk.Entry(
                page, textvariable=variable, width=12, font=("Helvetica", 16)
            ).pack(anchor="w")
        return page

    def _construire_page_symptomes(self, parent):
        page = ttk.Frame(parent)
        canevas = tk.Canvas(
            page,
            highlightthickness=0,
            yscrollincrement=20,
            bg=ttk.Style().lookup("TFrame", "background") or "white",
        )
        barre = ttk.Scrollbar(page, orient="vertical", command=canevas.yview)
        canevas.configure(yscrollcommand=barre.set)
        barre.pack(side="right", fill="y")
        canevas.pack(side="left", fill="both", expand=True)

        contenu = ttk.Frame(canevas)
        fenetre_contenu = canevas.create_window((0, 0), window=contenu, anchor="nw")
        contenu.bind(
            "<Configure>",
            lambda _: canevas.configure(scrollregion=canevas.bbox("all")),
        )
        canevas.bind(
            "<Configure>",
            lambda evenement: canevas.itemconfig(
                fenetre_contenu, width=evenement.width
            ),
        )

        def defiler_molette(evenement):
            canevas.yview_scroll(-1 if evenement.delta > 0 else 1, "units")

        def defiler_trackpad(evenement):
            try:
                deltas = canevas.tk.splitlist(
                    canevas.tk.call("tk::PreciseScrollDeltas", evenement.delta)
                )
                dy = int(deltas[1])
            except (tk.TclError, IndexError, ValueError):
                return
            hauteur = max(contenu.winfo_height(), 1)
            canevas.yview_moveto(max(0, canevas.yview()[0] - dy / hauteur))

        canevas.bind_all("<MouseWheel>", defiler_molette)
        try:
            canevas.bind_all("<TouchpadScroll>", defiler_trackpad)
        except tk.TclError:
            pass
        self.fenetre.bind_all("<Down>", lambda _: canevas.yview_scroll(1, "units"))
        self.fenetre.bind_all("<Up>", lambda _: canevas.yview_scroll(-1, "units"))

        self.cartes = [CarteSymptome(contenu, nom) for nom in SYMPTOMES]
        return page

    # ---------------- affichage ----------------
    def afficher(self):
        """Montre la page voulue et adapte titre et boutons."""
        self.page_vitaux.pack_forget()
        self.page_symptomes.pack_forget()
        self.bouton_retour.pack_forget()

        if self.page == "vitaux":
            self.page_vitaux.pack(fill="both", expand=True)
            if self.mode == "confirmation":
                self.titre.set("Mesure de confirmation")
                self.message_vitaux.set(
                    "Un changement a été détecté. Reprenez la pression et le "
                    "pouls (les symptômes déjà saisis sont conservés)."
                )
                self.bouton_principal.config(text="Enregistrer la confirmation")
            else:
                self.titre.set("Signes vitaux")
                self.message_vitaux.set("")
                self.bouton_principal.config(text="Suivant")
        else:
            self.page_symptomes.pack(fill="both", expand=True)
            self.titre.set("Comment vous sentez-vous ?")
            self.bouton_retour.pack(side="left", ipady=8)
            self.bouton_principal.config(text="Enregistrer")

    def avancer(self):
        if self.page == "vitaux":
            if self.lire_vitaux() is None:
                return
            if self.mode == "confirmation":
                self.enregistrer_confirmation()
            else:
                self.page = "symptomes"
                self.afficher()
        else:
            self.enregistrer_nouvelle_mesure()

    def retour(self):
        self.page = "vitaux"
        self.afficher()

    # ---------------- lecture / validation ----------------
    def lire_vitaux(self):
        try:
            systolique, diastolique, pouls = (
                int(variable.get())
                for variable in (
                    self.champ_systolique,
                    self.champ_diastolique,
                    self.champ_pouls,
                )
            )
        except ValueError:
            messagebox.showwarning(
                "Valeurs invalides",
                "Veuillez saisir des nombres entiers pour les signes vitaux.",
            )
            return None

        if min(systolique, diastolique, pouls) <= 0 or systolique <= diastolique:
            messagebox.showwarning(
                "Valeurs invalides",
                "Les signes vitaux doivent être positifs, et la systolique "
                "doit être supérieure à la diastolique.",
            )
            return None
        return systolique, diastolique, pouls

    def vider_vitaux(self):
        for variable in (
            self.champ_systolique,
            self.champ_diastolique,
            self.champ_pouls,
        ):
            variable.set("")

    # ---------------- enregistrements ----------------
    def enregistrer_nouvelle_mesure(self):
        choisis = [c for c in self.cartes if c.coche.get()]
        incomplets = [c.nom for c in choisis if not c.intensite.get()]
        if incomplets:
            messagebox.showwarning(
                "Informations manquantes",
                "Veuillez choisir l'intensité pour :\n- " + "\n- ".join(incomplets),
            )
            return

        vitaux = self.lire_vitaux()
        if vitaux is None:
            self.page = "vitaux"
            self.afficher()
            return

        intensites = {
            PARAMETRES_SYMPTOMES[carte.nom]: carte.valeur_intensite()
            for carte in self.cartes
        }
        mesure = Mesure(*vitaux, **intensites)

        grade, alarme, confirmation = self.gestionnaire.nouvelleMesure(mesure)

        if alarme:
            self.afficher_alerte(grade)
        if choisis:
            resume = "\n".join(f"- {c.nom} : {c.valeur_intensite()}/5" for c in choisis)
        else:
            resume = "Aucun symptôme"
        moment = mesure.dateHeure.strftime("%Y-%m-%d %H:%M")
        texte = f"Mesure enregistrée le {moment} (grade {grade}) :\n\n{resume}"

        for carte in self.cartes:
            carte.reinitialiser()
        self.vider_vitaux()

        if confirmation:
            texte += (
                "\n\nLe grade a changé : une mesure de confirmation est "
                "nécessaire (dans environ 5 minutes)."
            )
            messagebox.showinfo("Confirmation requise", texte)
            self.mode = "confirmation"
        else:
            messagebox.showinfo("Enregistré", texte)
            self.mode = "nouvelle"
        self.page = "vitaux"
        self.afficher()

    def enregistrer_confirmation(self):
        vitaux = self.lire_vitaux()
        if vitaux is None:
            return
        grade, alarme = self.gestionnaire.confirmerMesure(*vitaux)
        if alarme:
            self.afficher_alerte(grade)
        messagebox.showinfo(
            "Confirmation enregistrée", f"Mesure confirmée (grade {grade})."
        )
        self.vider_vitaux()
        self.mode = "nouvelle"
        self.page = "vitaux"
        self.afficher()

    def afficher_alerte(self, grade):
        if grade >= 3:
            message = "Grade 3 : contactez immédiatement un professionnel de santé."
        else:
            message = "Plusieurs mesures anormales : contactez un professionnel de santé."
        messagebox.showwarning("ALERTE", message)


if __name__ == "__main__":
    fenetre = tk.Tk()
    fenetre.title("Saisie des mesures")
    fenetre.geometry("480x780")

    style = ttk.Style()
    style.configure("Gros.TCheckbutton", font=("Helvetica", 16, "bold"))
    style.configure("TRadiobutton", font=("Helvetica", 13))
    style.configure("TLabel", font=("Helvetica", 13))

    patient = Patient(facteurRisque=6, nom="Patient", identifiant=1)
    Application(fenetre, GestionnaireDeTache(patient))
    fenetre.mainloop()
