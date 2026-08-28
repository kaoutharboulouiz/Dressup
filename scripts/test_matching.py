import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from sqlalchemy import select

from app.db import session
from app.models import Garment, User
from app.styling.matching import proposer_tenues
from app.styling.retrieval import recettes_pour_ancres

ap = argparse.ArgumentParser()
ap.add_argument("--user", required=True)
ap.add_argument("--slot", default="bas")
ap.add_argument("--n", type=int, default=5)
args = ap.parse_args()

with session() as s:
    user = s.scalar(select(User).where(User.handle == args.user))

    ancre = s.scalar(
        select(Garment)
        .where(Garment.user_id == user.id, Garment.slot == args.slot)
        .limit(1)
    )
    if ancre is None:
        print(f"Aucun vetement en slot '{args.slot}'.")
        raise SystemExit(1)

    print(f"ANCRE : {ancre.categorie} ({ancre.couleur_hex}, "
          f"formalite {ancre.formalite})\n")

    recettes = recettes_pour_ancres(s, user.id, [ancre], k=20)
    tenues = proposer_tenues(s, user.id, [ancre], recettes)

    if not tenues:
        print("Aucune tenue viable. Seuil trop haut, ou garde-robe trop petite.")
        raise SystemExit(0)

    for i, t in enumerate(tenues[:args.n], 1):
        print(f"--- Tenue {i}  score {t['score']:.2f}  "
              f"(harmonie {t['harmonie']:.2f}, couverture {t['couverture']:.0%}) ---")
        print(f"    inspiration : {t['recette'].registre}")
        for item in t["items"]:
            g = item["garment"]
            marque = "*" if item["is_anchor"] else " "
            port = f"  [{item['port']}]" if item.get("port") else ""
            print(f"  {marque} {g.slot:11} {g.categorie:28} {g.couleur_hex}{port}")
        if t["manquants"]:
            print(f"    non pourvus : {', '.join(t['manquants'])}")
        print()
        