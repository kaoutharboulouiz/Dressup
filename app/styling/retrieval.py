"""Recuperation de recettes d'inspiration pertinentes pour une piece ancre."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Garment, Recipe
from app.styling.scoring import ecart_teinte, est_neutre, hex_to_hsl


def _piece_compatible(piece: dict, garment: Garment) -> float:
    """Proximite entre une piece de recette et un vetement reel. 0-1."""
    if piece.get("slot") != garment.slot:
        return 0.0

    score = 0.5  # meme slot : base

    # Proximite de couleur
    hex_piece = piece.get("couleur_hex", "")
    if hex_piece:
        c1, c2 = hex_to_hsl(hex_piece), hex_to_hsl(garment.couleur_hex)
        if est_neutre(c1) and est_neutre(c2):
            score += 0.25
        elif not est_neutre(c1) and not est_neutre(c2):
            d = ecart_teinte(c1[0], c2[0])
            score += 0.25 * max(0.0, 1 - d / 90)

    # Proximite de formalite
    f = piece.get("formalite")
    if f is not None:
        score += 0.25 * max(0.0, 1 - abs(int(f) - garment.formalite) / 4)

    return round(score, 3)


def recettes_pour_ancres(
    s: Session,
    user_id,
    ancres: list[Garment],
    k: int = 10,
) -> list[tuple[Recipe, float]]:
    """Retourne les k recettes les plus pertinentes pour les pieces imposees.

    Une recette n'est retenue que si CHAQUE ancre y trouve une piece
    compatible : c'est le filtre dur.
    """
    recettes = s.scalars(
        select(Recipe).where(Recipe.user_id == user_id)
    ).all()

    resultats = []
    for r in recettes:
        scores_ancres = []
        for ancre in ancres:
            meilleur = max(
                (_piece_compatible(p, ancre) for p in r.pieces),
                default=0.0,
            )
            if meilleur == 0.0:
                break               # cette ancre n'a pas sa place ici
            scores_ancres.append(meilleur)
        else:
            # boucle terminee sans break : toutes les ancres sont placees
            moyenne = sum(scores_ancres) / len(scores_ancres)
            resultats.append((r, round(moyenne, 3)))

    resultats.sort(key=lambda t: t[1], reverse=True)
    return resultats[:k]