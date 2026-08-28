from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.config import settings
from app.db import session
from app.models import SLOTS, Garment, User
from app.vision import embed, extraire_garment

EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def get_or_create_user(s, handle: str) -> User:
    u = s.scalar(select(User).where(User.handle == handle))
    if u is None:
        u = User(handle=handle)
        s.add(u)
        s.flush()
        print(f"Utilisateur cree : {handle}")
    return u


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=settings.dir_wardrobe)
    ap.add_argument("--user", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    photos = sorted(p for p in args.dir.iterdir() if p.suffix.lower() in EXTS)
    if not photos:
        print(f"Aucune photo dans {args.dir}")
        return 2

    ok = ignores = echecs = 0

    with session() as s:
        user = get_or_create_user(s, args.user)

        connus = set()
        if not args.force:
            connus = set(s.scalars(
                select(Garment.image_path).where(Garment.user_id == user.id)
            ))

        for photo in photos:
            rel = str(photo)
            if rel in connus:
                ignores += 1
                continue

            print(f"-> {photo.name}")
            try:
                fiche = extraire_garment(photo)
            except Exception as e:
                print(f"   echec VLM : {e}")
                echecs += 1
                continue

            if fiche.get("slot") not in SLOTS:
                print(f"   slot invalide ({fiche.get('slot')}) - ignore")
                echecs += 1
                continue

            description = (
                f"{fiche['categorie']}, {fiche.get('couleur_nom', '')}, "
                f"{fiche.get('matiere', '')}, coupe {fiche.get('coupe', '')}. "
                f"{fiche.get('description', '')}"
            )

            s.add(Garment(
                user_id=user.id,
                image_path=rel,
                slot=fiche["slot"],
                categorie=fiche["categorie"],
                couleur_hex=fiche.get("couleur_hex", "#808080"),
                formalite=int(fiche.get("formalite", 3)),
                attributs={k: v for k, v in fiche.items()
                           if k not in {"slot", "categorie", "couleur_hex",
                                        "formalite", "description"}},
                description=description,
                embedding=embed(description),
            ))
            print(f"   {fiche['slot']:12} {fiche['categorie']:25} formalite {fiche.get('formalite')}")
            ok += 1

    print(f"\n{ok} ingeres, {ignores} deja connus, {echecs} echecs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())