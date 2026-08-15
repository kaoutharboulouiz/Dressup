import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from sqlalchemy import select

from app.db import session
from app.models import Garment, User

ap = argparse.ArgumentParser()
ap.add_argument("--user", required=True)
ap.add_argument("--tous", action="store_true", help="renoter meme ceux deja notes")
args = ap.parse_args()

VALIDES = {"b": "bon", "m": "moyen", "x": "mauvais", "": None}

with session() as s:
    user = s.scalar(select(User).where(User.handle == args.user))
    q = select(Garment).where(Garment.user_id == user.id)
    if not args.tous:
        q = q.where(Garment.render_quality.is_(None))
    garments = s.scalars(q.order_by(Garment.slot)).all()

    if not garments:
        print("Tout est deja note. Utilise --tous pour renoter.")
        raise SystemExit(0)

    print("b = bon, m = moyen, x = mauvais, Entree = passer, q = quitter\n")

    for g in garments:
        print(f"{g.slot:11} {g.categorie:28} {g.image_path}")
        rep = input("  qualite ? ").strip().lower()
        if rep == "q":
            break
        if rep in VALIDES:
            g.render_quality = VALIDES[rep]
            print(f"  -> {VALIDES[rep] or 'non note'}\n")
        else:
            print("  reponse ignoree\n")