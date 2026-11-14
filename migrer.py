"""Applique les fichiers .sql de supabase/migrations/ dans l'ordre alphabétique.

Chaque fichier n'est appliqué qu'une fois (suivi dans la table schema_migrations).

Usage :
    pip install "psycopg[binary]"
    export DATABASE_URL="postgresql://postgres:MOT_DE_PASSE@db.xxxx.supabase.co:5432/postgres"
    python migrer.py

(La chaîne de connexion se trouve dans Supabase > Project Settings > Database.)
"""
import os
import sys
from pathlib import Path

import psycopg

DOSSIER = Path("supabase/migrations")


def migrer():
    fichiers = sorted(DOSSIER.glob("*.sql"))
    if not fichiers:
        print(f"Aucun fichier .sql dans {DOSSIER}/")
        return

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(
            """
            create table if not exists schema_migrations (
                nom text primary key,
                appliquee_le timestamptz not null default now()
            )
            """
        )
        deja = {ligne[0] for ligne in conn.execute("select nom from schema_migrations")}

        for fichier in fichiers:
            if fichier.name in deja:
                continue
            print(f"Application de {fichier.name}...")
            with conn.transaction():  # tout ou rien pour chaque fichier
                conn.execute(fichier.read_text(encoding="utf-8"))
                conn.execute(
                    "insert into schema_migrations (nom) values (%s)", (fichier.name,)
                )
            print("  OK")


if __name__ == "__main__":
    try:
        migrer()
    except KeyError:
        sys.exit("Variable d'environnement DATABASE_URL manquante.")
