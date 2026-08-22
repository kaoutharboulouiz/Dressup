"""Synchronise les boards Pinterest vers des recettes.

L'image du pin n'est jamais stockee : on ne conserve que la recette derivee.
"""

from __future__ import annotations
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from app.db import session
from app.models import Recipe, User
from app.pinterest import lister_boards, lister_pins, url_image
from app.vision import embed, extraire_recette

MOTS_CLES = ("style", "outfit", "mode", "look", "tenue", "fashion", "inspo")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--board", help="nom exact d'un board precis")
    ap.add_argument("--limite", type=int, default=15, help="pins max par board")
    ap.add_argument("--lister", action="store_true", help="liste les boards et sort")
    args = ap.parse_args()

    with session() as s:
        user = s.scalar(select(User).where(User.handle == args.user))
        if user is None:
            print(f"Utilisateur {args.user} introuvable.")
            return 2

        token = user.pinterest_token
        if not token:
            print("Aucun token en base.")
            return 2

        boards = lister_boards(token)
        print(f"{len(boards)} boards trouves.\n")

        if args.lister:
            for b in boards:
                print(f"  {b['name']}  ({b.get('pin_count', '?')} pins)")
            return 0

        if args.board:
            cibles = [b for b in boards if b["name"].lower() == args.board.lower()]
        else:
            cibles = [b for b in boards
                      if any(m in b["name"].lower() for m in MOTS_CLES)]

        if not cibles:
            print("Aucun board retenu. Utilise --lister pour voir les noms.")
            return 2

        connus = set(s.scalars(
            select(Recipe.source_ref).where(Recipe.user_id == user.id)
        ))

        ok = ignores = rejets = echecs = 0

        for board in cibles:
            print(f"=== {board['name']} ===")
            for pin in lister_pins(token, board["id"], args.limite):
                ref = f"pinterest:{pin['id']}"
                if ref in connus:
                    ignores += 1
                    continue

                img = url_image(pin)
                if not img:
                    continue

                try:
                    donnees = httpx.get(img, timeout=30).content
                    r = extraire_recette(donnees)
                except Exception as e:
                    print(f"  echec : {str(e)[:70]}")
                    echecs += 1
                    continue

                if not r.get("pieces"):
                    rejets += 1
                    continue

                texte = (f"{r.get('registre', '')}. {r.get('silhouette', '')}. "
                         f"{r.get('description', '')}")

                s.add(Recipe(
                    user_id=user.id,
                    source="pinterest",
                    source_ref=ref,
                    pieces=r["pieces"],
                    registre=r.get("registre"),
                    silhouette=r.get("silhouette"),
                    regle_cle=r.get("regle_cle"),
                    description=texte,
                    embedding=embed(texte),
                ))
                slots = " + ".join(p["slot"] for p in r["pieces"])
                print(f"  {r.get('registre', '?'):22} [{slots}]")
                ok += 1

        user.pinterest_last_sync = datetime.now(timezone.utc)

    print(f"\n{ok} recettes, {ignores} connues, {rejets} rejetees, {echecs} echecs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())