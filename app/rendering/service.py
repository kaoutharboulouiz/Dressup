"""Persistance des tenues et generation des rendus, avec cache et quota."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.genai import types
from sqlalchemy import func as sqlfunc
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Avatar, Outfit, OutfitItem, Render
from app.vision import client

ORDRE = ["bas", "robe", "haut", "veste", "chaussures", "accessoire"]


def render_key(avatar_id, garment_ids: list, provider: str) -> str:
    """Cle de deduplication. Change si l'avatar, les vetements ou le modele change."""
    brut = f"{avatar_id}|{'|'.join(sorted(str(g) for g in garment_ids))}|{provider}"
    return hashlib.sha256(brut.encode()).hexdigest()


def outfit_key(user_id, garment_ids: list) -> str:
    """Empreinte d'un ensemble de vetements. Independante de l'ordre."""
    brut = f"{user_id}|{'|'.join(sorted(str(g) for g in garment_ids))}"
    return hashlib.sha256(brut.encode()).hexdigest()


def sauver_tenue(s: Session, user_id, tenue: dict) -> tuple[Outfit, bool]:
    """Persiste une tenue. Retourne (outfit, cree) — cree=False si deja en base."""
    ids = [i["garment"].id for i in tenue["items"]]
    cle = outfit_key(user_id, ids)

    existant = s.scalar(select(Outfit).where(Outfit.outfit_key == cle))
    if existant is not None:
        return existant, False

    spec = tenue.get("styling_spec") or {}
    outfit = Outfit(
        user_id=user_id,
        outfit_key=cle,
        recipe_id=tenue["recette"].id,
        score=tenue["score"],
        couverture=tenue["couverture"],
        harmonie=tenue["harmonie"],
        justification=spec.get("justification"),
        occasion=spec.get("occasion"),
        styling_spec=spec,
    )
    s.add(outfit)
    s.flush()

    for item in tenue["items"]:
        s.add(OutfitItem(
            outfit_id=outfit.id,
            garment_id=item["garment"].id,
            slot=item["slot"],
            port=item.get("port_transpose") or item.get("port"),
            is_anchor=item["is_anchor"],
            ordre=item["ordre"],
        ))
    return outfit, True


def quota_restant(s: Session, user_id) -> int:
    """Nombre de rendus encore autorises aujourd'hui."""
    depuis = datetime.now(timezone.utc) - timedelta(days=1)
    faits = s.scalar(
        select(sqlfunc.count(Render.id))
        .join(Outfit, Render.outfit_id == Outfit.id)
        .where(Outfit.user_id == user_id,
               Render.created_at >= depuis,
               Render.status == "ok")
    ) or 0
    return max(0, settings.max_renders_par_jour - faits)


def _part(path: Path) -> types.Part:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)


def _prompt(items: list[OutfitItem]) -> str:
    lignes = [
        "Image 1 - PERSONNE : preserve exactement le visage, la morphologie, "
        "la pose et le fond. Retire tous les vetements visibles avant "
        "d'habiller avec les pieces listees ci-dessous."
    ]
    for i, item in enumerate(items, start=2):
        lignes.append(
            f"Image {i} - {item.slot.upper()} : reproduis fidelement ce vetement. "
            f"Couleur, motif, matiere, coupe et longueur identiques a la reference."
        )

    lignes += [
        "",
        f"Habille la personne de l'image 1 avec ces {len(items)} pieces.",
        "Superposition, du plus pres du corps au plus exterieur : "
        + ", ".join(i.slot for i in items) + ".",
    ]

    ports = [f"{i.slot} {i.port}" for i in items if i.port]
    if ports:
        lignes.append("Port : " + " ; ".join(ports) + ".")

    lignes += [
        "",
        "Photographie en pied, eclairage neutre et uniforme, fond identique "
        "a l'image 1.",
        "N'ajoute AUCUN vetement ni accessoire qui ne soit pas liste ci-dessus.",
    ]
    return "\n".join(lignes)


def rendre(s: Session, user_id, outfit: Outfit, forcer: bool = False) -> Render:
    """Genere l'image d'une tenue. Retourne le rendu existant si deja en cache."""
    avatar = s.scalar(
        select(Avatar).where(Avatar.user_id == user_id, Avatar.is_active.is_(True))
    )
    if avatar is None:
        raise RuntimeError("Aucun avatar actif. Ajoute-en un d'abord.")

    items = sorted(outfit.items, key=lambda i: ORDRE.index(i.slot))
    cle = render_key(avatar.id, [i.garment_id for i in items], settings.model_image)

    if not forcer:
        existant = s.scalar(select(Render).where(Render.render_key == cle))
        if existant is not None and existant.status == "ok":
            print(f"  cache : {existant.image_path}")
            return existant

    if quota_restant(s, user_id) <= 0:
        raise RuntimeError(
            f"Quota journalier atteint ({settings.max_renders_par_jour})."
        )

    render = Render(
        outfit_id=outfit.id,
        avatar_id=avatar.id,
        render_key=cle,
        provider=settings.model_image,
        status="pending",
    )
    s.add(render)
    s.flush()

    contenus = [_part(Path(avatar.image_path))]
    for item in items:
        contenus.append(_part(Path(item.garment.image_path)))
    contenus.append(_prompt(items))

    try:
        resp = client.models.generate_content(
            model=settings.model_image, contents=contenus
        )
    except Exception as e:
        render.status = "erreur"
        render.erreur = str(e)[:500]
        return render

    settings.dir_renders.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")

    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and part.inline_data.data:
            chemin = settings.dir_renders / f"{horodatage}-{str(outfit.id)[:8]}.png"
            chemin.write_bytes(part.inline_data.data)
            render.image_path = str(chemin)
            render.status = "ok"
            return render

    render.status = "erreur"
    render.erreur = "aucune image renvoyee"
    return render