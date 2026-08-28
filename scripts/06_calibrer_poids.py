"""Recalibre poids_visuel par comparaison relative sur toute la garde-robe.

Noter chaque piece isolement fait converger le modele vers la mediane.
En lui montrant l'ensemble, il compare au lieu de deviner une echelle.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.config import settings
from app.db import session
from app.models import Garment, User
from app.vision import _parse, client

PROMPT = """Voici la garde-robe complete d'une personne. Classe chaque piece selon
son POIDS VISUEL : combien elle capte le regard dans une tenue.

Tu dois COMPARER les pieces entre elles, pas les noter dans l'absolu.

Attribue les notes en respectant cette repartition, quelle que soit la
garde-robe :
  environ 15% en 1  (les plus effacees : basiques unis, pieces de fond)
  environ 30% en 2
  environ 30% en 3
  environ 20% en 4
  environ  5% en 5  (les plus spectaculaires de CETTE garde-robe)

Meme si toutes les pieces se ressemblent, tu dois etaler les notes : il y a
forcement des plus discretes et des plus fortes.

Ce qui augmente le poids visuel : sequins, brillance, volants, drape
spectaculaire, imprime fort, couleur eclatante, structure sculpturale,
asymetrie marquee, dos nu.
Ce qui le diminue : uni, coupe classique, teinte neutre, matiere mate.

Reponds uniquement par un objet JSON, sans aucun texte autour :
{"notes": {"0": 3, "1": 5, "2": 1, ...}}
Une entree par piece, la cle etant son champ "n". Rien d'autre."""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    args = ap.parse_args()

    with session() as s:
        user = s.scalar(select(User).where(User.handle == args.user))
        garments = s.scalars(
            select(Garment).where(Garment.user_id == user.id)
        ).all()

        inventaire = [
            {
                "n": n,
                "categorie": g.categorie,
                "couleur": g.attributs.get("couleur_nom", ""),
                "motif": g.attributs.get("motif", ""),
                "matiere": g.attributs.get("matiere", ""),
                "coupe": g.attributs.get("coupe", ""),
                "description": g.description[:180],
            }
            for n, g in enumerate(garments)
        ]

        print(f"{len(inventaire)} pieces envoyees pour calibrage...")

        resp = client.models.generate_content(
            model=settings.model_vision,
            contents=[PROMPT, json.dumps(inventaire, ensure_ascii=False)],
            config={"response_mime_type": "application/json",
                    "max_output_tokens": 8192},
        )
        notes = _parse(resp.text).get("notes", {})

        maj = 0
        for n, g in enumerate(garments):
            note = notes.get(str(n)) or notes.get(n)
            if note is None:
                continue
            attrs = dict(g.attributs)
            attrs["poids_visuel"] = int(note)
            g.attributs = attrs
            maj += 1


    print(f"{maj} pieces recalibrees.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())