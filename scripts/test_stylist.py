import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from sqlalchemy import select

from app.db import session
from app.models import Garment, User
from app.styling.matching import proposer_tenues
from app.styling.retrieval import recettes_pour_ancres
from app.styling.stylist import styliser_lot

ap = argparse.ArgumentParser()
ap.add_argument("--user", required=True)
ap.add_argument("--slot", default="bas")
ap.add_argument("--n", type=int, default=3)
args = ap.parse_args()

with session() as s:
    user = s.scalar(select(User).where(User.handle == args.user))
    ancre = s.scalar(
        select(Garment)
        .where(Garment.user_id == user.id, Garment.slot == args.slot)
        .limit(1)
    )

    print(f"ANCRE : {ancre.categorie} ({ancre.couleur_hex})\n")

    recettes = recettes_pour_ancres(s, user.id, [ancre], k=20)
    tenues = proposer_tenues(s, user.id, [ancre], recettes)
    tenues = styliser_lot(tenues, n=args.n)

    for i, t in enumerate(tenues[:args.n], 1):
        spec = t.get("styling_spec")
        print(f"--- Tenue {i}  score {t['score']:.2f} ---")
        for item in t["items"]:
            g = item["garment"]
            marque = "*" if item["is_anchor"] else " "
            print(f"  {marque} {g.slot:11} {g.categorie:28} {g.couleur_hex}")
            if item.get("port"):
                print(f"        ref     : {item['port'][:75]}")
            if item.get("port_transpose"):
                print(f"        transpose: {item['port_transpose'][:75]}")
        if spec:
            print(f"\n    silhouette : {spec['silhouette']}")
            print(f"    pourquoi   : {spec['justification']}")
            print(f"    occasion   : {spec['occasion']}")
        print()