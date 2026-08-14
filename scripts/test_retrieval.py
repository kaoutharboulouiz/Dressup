import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from sqlalchemy import select

from app.db import session
from app.models import Garment, User
from app.styling.retrieval import recettes_pour_ancres

ap = argparse.ArgumentParser()
ap.add_argument("--user", required=True)
ap.add_argument("--slot", default="bas", help="slot de la piece ancre")
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

    for recette, score in recettes_pour_ancres(s, user.id, [ancre], k=5):
        slots = " + ".join(p["slot"] for p in recette.pieces)
        print(f"{score:.2f}  {recette.registre or '?':24} [{slots}]")
        print(f"      {(recette.regle_cle or '')[:90]}")