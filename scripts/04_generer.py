import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from sqlalchemy import select

from app.db import session
from app.models import Garment, User
from app.rendering.service import quota_restant, rendre, sauver_tenue
from app.styling.matching import proposer_tenues
from app.styling.retrieval import recettes_pour_ancres
from app.styling.stylist import styliser_lot_intelligent

ap = argparse.ArgumentParser()
ap.add_argument("--user", required=True)
ap.add_argument("--ancre", help="mot-cle dans la categorie du vetement impose")
ap.add_argument("--slot", default="bas")
ap.add_argument("--n", type=int, default=3, help="tenues a styliser")
ap.add_argument("--rendre", type=int, default=0, help="combien generer en image")
args = ap.parse_args()

with session() as s:
    user = s.scalar(select(User).where(User.handle == args.user))

    q = select(Garment).where(Garment.user_id == user.id, Garment.slot == args.slot)
    if args.ancre:
        q = q.where(Garment.categorie.ilike(f"%{args.ancre}%"))
    ancre = s.scalar(q.limit(1))

    if ancre is None:
        print("Aucune piece ancre trouvee.")
        raise SystemExit(1)

    print(f"ANCRE : {ancre.categorie} ({ancre.couleur_hex})")
    print(f"Quota restant : {quota_restant(s, user.id)}\n")

    recettes = recettes_pour_ancres(s, user.id, [ancre], k=20)
    tenues = proposer_tenues(s, user.id, [ancre], recettes)
    tenues = styliser_lot_intelligent(s, user.id, tenues, n=args.n)

    for i, t in enumerate(tenues[:args.n], 1):
        outfit, cree = sauver_tenue(s, user.id, t)
        spec = t.get("styling_spec") or {}
        marqueur = "" if cree else "  (deja en base)"

        print(f"--- Tenue {i}  score {t['score']:.2f}{marqueur} ---")
        for item in t["items"]:
            g = item["garment"]
            marque = "*" if item["is_anchor"] else " "
            port = item.get("port_transpose") or ""
            print(f"  {marque} {g.slot:11} {g.categorie:26} {port[:50]}")
        if spec.get("justification"):
            print(f"    {spec['justification']}")

        if i <= args.rendre:
            print("  generation...")
            try:
                r = rendre(s, user.id, outfit)
                print(f"  -> {r.status}  {r.image_path or r.erreur}")
            except RuntimeError as e:
                print(f"  -> {e}")
        print()