from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.db import session
from app.models import Recipe, User
from app.vision import embed, extraire_recette

EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path("data/inspirations"))
    ap.add_argument("--user", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    photos = sorted(p for p in args.dir.iterdir() if p.suffix.lower() in EXTS)
    if not photos:
        print(f"Aucune image dans {args.dir}")
        return 2

    ok = ignores = rejets = echecs = 0

    with session() as s:
        user = s.scalar(select(User).where(User.handle == args.user))
        if user is None:
            print(f"Utilisateur {args.user} introuvable. Lance d'abord l'etape 1.")
            return 2

        connus = set()
        if not args.force:
            connus = set(s.scalars(
                select(Recipe.source_ref).where(Recipe.user_id == user.id)
            ))

        for photo in photos:
            rel = str(photo)
            if rel in connus:
                ignores += 1
                continue

            print(f"-> {photo.name}")
            try:
                r = extraire_recette(photo)
            except Exception as e:
                print(f"   echec VLM : {e}")
                echecs += 1
                continue

            if not r.get("pieces"):
                print("   pas une tenue - rejete")
                rejets += 1
                continue

            texte = (f"{r.get('registre', '')}. {r.get('silhouette', '')}. "
                     f"{r.get('description', '')}")

            s.add(Recipe(
                user_id=user.id,
                source="local",
                source_ref=rel,
                pieces=r["pieces"],
                registre=r.get("registre"),
                silhouette=r.get("silhouette"),
                regle_cle=r.get("regle_cle"),
                description=texte,
                embedding=embed(texte),
            ))
            slots = " + ".join(p["slot"] for p in r["pieces"])
            print(f"   {r.get('registre', '?'):20} [{slots}]")
            print(f"   regle : {r.get('regle_cle', '')[:75]}")
            ok += 1

    print(f"\n{ok} recettes, {ignores} connues, {rejets} rejetees, {echecs} echecs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())