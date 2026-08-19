"""API FastAPI. Routes fines : toute la logique vit dans les modules metier."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.rendering.service import quota_restant, rendre, sauver_tenue
from app.styling.retrieval import recettes_pour_ancres
from app.models import Avatar, Garment, Outfit, Render, User, Variant
from app.styling.matching import grouper_par_outfit, proposer_tenues
from app.styling.stylist import styliser

app = FastAPI(title="Dressup")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def get_user(s: Session, handle: str = "kaouthar") -> User:
    u = s.scalar(select(User).where(User.handle == handle))
    if u is None:
        raise HTTPException(404, "utilisateur introuvable")
    return u


# ---------- Schemas ----------

class GarmentOut(BaseModel):
    id: uuid.UUID
    slot: str
    categorie: str
    couleur_hex: str
    formalite: int


class ProposeIn(BaseModel):
    ancre_ids: list[uuid.UUID]
    n: int = 5


class ItemOut(BaseModel):
    garment_id: uuid.UUID
    slot: str
    categorie: str
    couleur_hex: str
    port: str | None
    is_anchor: bool


class VariantOut(BaseModel):
    id: uuid.UUID
    titre: str
    justification_port: str | None
    silhouette: str | None
    source: str
    ports: dict
    render_id: uuid.UUID | None
    render_status: str | None


class OutfitOut(BaseModel):
    id: uuid.UUID
    score: float
    harmonie: float
    couverture: float
    justification_tenue: str | None
    items: list[ItemOut]
    variants: list[VariantOut]

def _serialiser(s: Session, outfit: Outfit) -> OutfitOut:
    variants = []
    for v in sorted(outfit.variants, key=lambda x: x.ordre):
        dernier = s.scalar(
            select(Render)
            .where(Render.variant_id == v.id)
            .order_by(Render.created_at.desc())
        )
        variants.append(VariantOut(
            id=v.id,
            titre=v.titre,
            justification_port=v.justification_port,
            silhouette=v.silhouette,
            source=v.source,
            ports=v.ports,
            render_id=dernier.id if dernier else None,
            render_status=dernier.status if dernier else None,
        ))

    return OutfitOut(
        id=outfit.id,
        score=outfit.score,
        harmonie=outfit.harmonie,
        couverture=outfit.couverture,
        justification_tenue=outfit.justification_tenue,
        items=[
            ItemOut(
                garment_id=it.garment_id,
                slot=it.slot,
                categorie=it.garment.categorie,
                couleur_hex=it.garment.couleur_hex,
                port=it.port,
                is_anchor=it.is_anchor,
            )
            for it in sorted(outfit.items, key=lambda x: x.ordre)
        ],
        variants=variants,
    )
# ---------- Routes ----------

@app.get("/garments", response_model=list[GarmentOut])
def lister_garments(s: Session = Depends(get_db)):
    user = get_user(s)
    return s.scalars(
        select(Garment)
        .where(Garment.user_id == user.id)
        .order_by(Garment.slot, Garment.categorie)
    ).all()


@app.get("/quota")
def lire_quota(s: Session = Depends(get_db)):
    user = get_user(s)
    return {"restant": quota_restant(s, user.id)}


@app.post("/outfits/propose", response_model=list[OutfitOut])
def proposer(body: ProposeIn, s: Session = Depends(get_db)):
    user = get_user(s)

    ancres = s.scalars(
        select(Garment).where(
            Garment.user_id == user.id, Garment.id.in_(body.ancre_ids)
        )
    ).all()
    if not ancres:
        raise HTTPException(400, "aucune piece ancre valide")

    recettes = recettes_pour_ancres(s, user.id, list(ancres), k=20)
    tenues = proposer_tenues(s, user.id, list(ancres), recettes)
    if not tenues:
        return []

    tenues = grouper_par_outfit(tenues)[: body.n]

    sortie = []
    for t in tenues:
        styliser(t, t.get("recettes"))
        outfit, _ = sauver_tenue(s, user.id, t)
        s.commit()
        s.refresh(outfit)
        sortie.append(_serialiser(s, outfit))
    return sortie


def _travail_rendu(variant_id: uuid.UUID, user_id: uuid.UUID):
    s = SessionLocal()
    try:
        variant = s.get(Variant, variant_id)
        rendre(s, user_id, variant)
        s.commit()
    except Exception as e:
        s.rollback()
        print(f"rendu {variant_id} echoue : {e}")
    finally:
        s.close()


@app.post("/variants/{variant_id}/render")
def lancer_rendu(
    variant_id: uuid.UUID,
    taches: BackgroundTasks,
    s: Session = Depends(get_db),
):
    user = get_user(s)
    variant = s.get(Variant, variant_id)
    if variant is None or variant.outfit.user_id != user.id:
        raise HTTPException(404, "variante introuvable")

    if quota_restant(s, user.id) <= 0:
        raise HTTPException(429, "quota journalier atteint")

    taches.add_task(_travail_rendu, variant_id, user.id)
    return {"status": "pending"}


@app.get("/variants/{variant_id}/render")
def statut_rendu(variant_id: uuid.UUID, s: Session = Depends(get_db)):
    r = s.scalar(
        select(Render)
        .where(Render.variant_id == variant_id)
        .order_by(Render.created_at.desc())
    )
    if r is None:
        return {"status": "absent"}
    return {"id": r.id, "status": r.status, "erreur": r.erreur}


@app.get("/renders/{render_id}/image")
def image_rendu(render_id: uuid.UUID, s: Session = Depends(get_db)):
    r = s.get(Render, render_id)
    if r is None or r.status != "ok" or not r.image_path:
        raise HTTPException(404, "image indisponible")
    return FileResponse(r.image_path, media_type="image/png")


@app.get("/garments/{garment_id}/image")
def image_garment(garment_id: uuid.UUID, s: Session = Depends(get_db)):
    g = s.get(Garment, garment_id)
    if g is None or not Path(g.image_path).exists():
        raise HTTPException(404, "image introuvable")
    return FileResponse(g.image_path)


@app.get("/feed", response_model=list[OutfitOut])
def feed(limite: int = 30, s: Session = Depends(get_db)):
    user = get_user(s)
    outfits = s.scalars(
        select(Outfit)
        .where(Outfit.user_id == user.id)
        .order_by(Outfit.created_at.desc())
        .limit(limite)
    ).all()
    return [_serialiser(s, o) for o in outfits]