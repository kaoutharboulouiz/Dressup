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
from app.models import Avatar, Outfit, OutfitItem, Render, Variant
from app.vision import client

ORDRE = ["bas", "robe", "haut", "veste", "chaussures", "accessoire"]


def outfit_key(user_id, garment_ids: list) -> str:
    """Empreinte d'un ensemble de vetements. Independante de l'ordre."""
    brut = f"{user_id}|{'|'.join(sorted(str(g) for g in garment_ids))}"
    return hashlib.sha256(brut.encode()).hexdigest()


def variant_key(outfit_id, ports: dict) -> str:
    """Forme canonique des instructions de port, hachee."""
    canonique = "|".join(f"{k}:{ports[k]}" for k in sorted(ports) if ports[k])
    return hashlib.sha256(f"{outfit_id}|{canonique}".encode()).hexdigest()


def render_key(avatar_id, variant_id, provider: str) -> str:
    """La variante couvre deja vetements ET port."""
    brut = f"{avatar_id}|{variant_id}|{provider}"
    return hashlib.sha256(brut.encode()).hexdigest()


def sauver_tenue(s: Session, user_id, tenue: dict) -> tuple[Outfit, bool]:
    """Persiste une tenue et ses variantes. Retourne (outfit, cree)."""
    ids = [i["garment"].id for i in tenue["items"]]
    cle = outfit_key(user_id, ids)

    outfit = s.scalar(select(Outfit).where(Outfit.outfit_key == cle))
    cree = outfit is None

    if cree:
        outfit = Outfit(
            user_id=user_id,
            outfit_key=cle,
            score=tenue["score"],
            couverture=tenue["couverture"],
            harmonie=tenue["harmonie"],
            justification_tenue=tenue.get("justification_tenue"),
        )
        s.add(outfit)
        s.flush()

        for item in tenue["items"]:
            s.add(OutfitItem(
                outfit_id=outfit.id,
                garment_id=item["garment"].id,
                slot=item["slot"],
                port=item.get("port"),
                is_anchor=item["is_anchor"],
                ordre=item["ordre"],
            ))

    recettes = tenue.get("recettes") or [tenue["recette"]]
    recipe_id = recettes[0].id if recettes else None
    existantes = {v.variant_key for v in outfit.variants}

    for n, v in enumerate(tenue.get("variantes", [])):
        vk = variant_key(outfit.id, v["ports"])
        if vk in existantes:
            continue
        existantes.add(vk)
        s.add(Variant(
            outfit_id=outfit.id,
            recipe_id=recipe_id,
            variant_key=vk,
            titre=v["titre"],
            ports=v["ports"],
            justification_port=v.get("justification_port"),
            silhouette=v.get("silhouette"),
            source=v.get("source", "styliste"),
            ordre=n,
        ))

    s.flush()
    return outfit, cree


def quota_restant(s: Session, user_id) -> int:
    """Nombre de rendus encore autorises aujourd'hui."""
    depuis = datetime.now(timezone.utc) - timedelta(days=1)
    faits = s.scalar(
        select(sqlfunc.count(Render.id))
        .join(Variant, Render.variant_id == Variant.id)
        .join(Outfit, Variant.outfit_id == Outfit.id)
        .where(Outfit.user_id == user_id,
               Render.created_at >= depuis,
               Render.status == "ok")
    ) or 0
    return max(0, settings.max_renders_par_jour - faits)


def _part(path: Path) -> types.Part:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)


def _prompt(items: list, ports: dict) -> str:
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

    instructions = [
        f"{item.slot} {ports[str(n)] if str(n) in ports else ports.get(n)}"
        for n, item in enumerate(items)
        if ports.get(n) or ports.get(str(n))
    ]
    if instructions:
        lignes.append("Port : " + " ; ".join(instructions) + ".")

    lignes += [
        "",
        "Photographie en pied, eclairage neutre et uniforme, fond identique "
        "a l'image 1.",
        "N'ajoute AUCUN vetement ni accessoire qui ne soit pas liste ci-dessus.",
    ]
    return "\n".join(lignes)


def rendre(s: Session, user_id, variant: Variant, forcer: bool = False) -> Render:
    """Genere l'image d'une variante. Retourne le rendu en cache si existant."""
    avatar = s.scalar(
        select(Avatar).where(Avatar.user_id == user_id, Avatar.is_active.is_(True))
    )
    if avatar is None:
        raise RuntimeError("Aucun avatar actif.")

    cle = render_key(avatar.id, variant.id, settings.model_image)

    if not forcer:
        existant = s.scalar(select(Render).where(Render.render_key == cle))
        if existant is not None and existant.status == "ok":
            return existant

    if quota_restant(s, user_id) <= 0:
        raise RuntimeError(f"Quota atteint ({settings.max_renders_par_jour}).")

    render = Render(
        variant_id=variant.id,
        avatar_id=avatar.id,
        render_key=cle,
        provider=settings.model_image,
        status="pending",
    )
    s.add(render)
    s.flush()

    items = sorted(variant.outfit.items, key=lambda i: ORDRE.index(i.slot))

    contenus = [_part(Path(avatar.image_path))]
    for item in items:
        contenus.append(_part(Path(item.garment.image_path)))
    contenus.append(_prompt(items, variant.ports))

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
            chemin = settings.dir_renders / f"{horodatage}-{str(variant.id)[:8]}.png"
            chemin.write_bytes(part.inline_data.data)
            render.image_path = str(chemin)
            render.status = "ok"
            return render

    render.status = "erreur"
    render.erreur = "aucune image renvoyee"
    return render