"""Affectation : mapper les pieces d'une recette sur la garde-robe reelle."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Garment, Recipe
from app.styling.retrieval import _piece_compatible
from app.styling.scoring import score_tenue

# En dessous : on prefere laisser le slot vide plutot qu'affecter une approximation
SEUIL_AFFECTATION = 0.62
# En dessous : la tenue n'est pas proposee, meme si c'est la meilleure disponible
SEUIL_TENUE = 0.55

# Slots dont l'absence ne degrade pas la tenue
SLOTS_OPTIONNELS = {"accessoire", "veste"}

# Ordre de superposition, du plus pres du corps au plus exterieur
ORDRE = ["bas", "robe", "haut", "veste", "chaussures", "accessoire"]


def affecter(
    recette: Recipe,
    garde_robe: list[Garment],
    ancres: list[Garment],
) -> dict | None:
    """Construit une tenue reelle a partir d'une recette.

    Retourne None si la tenue obtenue n'est pas viable.
    """
    utilises = {a.id for a in ancres}
    plan: list[tuple[Garment, dict, bool]] = []
    for a in ancres:
            piece_ref = max(
                (p for p in recette.pieces if p.get("slot") == a.slot),
                key=lambda p: _piece_compatible(p, a),
                default={},
            )
            plan.append((a, piece_ref, True))
    slots_ancres = {a.slot for a in ancres}
    manquants: list[str] = []

    for piece in recette.pieces:
        slot = piece.get("slot")
        if slot in slots_ancres:
            continue                      # deja tenu par une ancre

        candidats = [
            g for g in garde_robe
            if g.slot == slot and g.id not in utilises
        ]
        if not candidats:
            manquants.append(slot)
            continue

        meilleur = max(candidats, key=lambda g: _piece_compatible(piece, g))
        if _piece_compatible(piece, meilleur) < SEUIL_AFFECTATION:
            manquants.append(slot)
            continue

        plan.append((meilleur, piece, False))
        utilises.add(meilleur.id)
    
    if not _superposition_valide(plan):
        return None
    if not _viable(plan):
        return None

    # Couverture calculee sur les seuls slots obligatoires
    obligatoires = [
        p.get("slot") for p in recette.pieces
        if p.get("slot") not in SLOTS_OPTIONNELS
    ]
    manquants_obl = [s for s in manquants if s not in SLOTS_OPTIONNELS]
    couverture = (
        1 - len(manquants_obl) / len(obligatoires) if obligatoires else 1.0
    )

    pieces_scoring = [
        {
            "slot": g.slot,
            "couleur_hex": g.couleur_hex,
            "formalite": g.formalite,
            "motif": g.attributs.get("motif", "uni"),
            "longueur": g.attributs.get("longueur"),
            "texture": g.attributs.get("texture"),
            "poids_visuel": g.attributs.get("poids_visuel", 3),
        }
        for g, _, _ in plan
    ]
    harmonie = score_tenue(pieces_scoring)
    if harmonie["score"] is None:
        return None                       # rejet dur sur la formalite

    plan.sort(key=lambda t: ORDRE.index(t[0].slot))

    return {
        "recette": recette,
        "items": [
            {
                "garment": g,
                "slot": g.slot,
                "port": piece.get("port"),
                "is_anchor": ancre,
                "ordre": i,
            }
            for i, (g, piece, ancre) in enumerate(plan)
        ],
        "couverture": round(couverture, 3),
        "harmonie": harmonie["score"],
        "score": round(0.6 * harmonie["score"] + 0.4 * couverture, 3),
        "manquants": manquants,
    }


def _viable(plan) -> bool:
    """Une tenue doit habiller le corps ET les pieds."""
    slots = {g.slot for g, _, _ in plan}
    if "chaussures" not in slots:
        return False
    if "robe" in slots:
        return True
    return "haut" in slots and "bas" in slots


def proposer_tenues(
    s: Session,
    user_id,
    ancres: list[Garment],
    recettes_scorees: list[tuple[Recipe, float]],
) -> list[dict]:
    """Applique l'affectation a chaque recette candidate, trie par score."""
    garde_robe = s.scalars(
        select(Garment).where(
            Garment.user_id == user_id,
            (Garment.render_quality.is_(None)) | (Garment.render_quality != "mauvais"),
        )
    ).all()

    tenues = []
    for recette, pertinence in recettes_scorees:
        t = affecter(recette, garde_robe, ancres)
        if t is None:
            continue
        t["pertinence"] = pertinence
        tenues.append(t)

    tenues.sort(key=lambda t: t["score"], reverse=True)
    # Penalite de repetition : chaque reapparition d'un vetement degrade le score
    vus: dict = {}
    for t in tenues:
        malus = 0.0
        for item in t["items"]:
            if item["is_anchor"]:
                continue
            gid = item["garment"].id
            malus += 0.05 * vus.get(gid, 0)
            vus[gid] = vus.get(gid, 0) + 1
        t["score"] = round(max(0.0, t["score"] - malus), 3)
    tenues = [t for t in tenues if t["harmonie"] >= SEUIL_TENUE]
    tenues.sort(key=lambda t: t["score"], reverse=True)
    return tenues

def grouper_par_outfit(tenues: list[dict]) -> list[dict]:
    """Fusionne les tenues qui utilisent le meme ensemble de vetements.

    Retourne une tenue par ensemble distinct, avec toutes les recettes
    convergentes dans la cle 'recettes'.
    """
    groupes: dict[frozenset, dict] = {}

    for t in tenues:
        cle = frozenset(i["garment"].id for i in t["items"])
        if cle in groupes:
            groupes[cle]["recettes"].append(t["recette"])
        else:
            t["recettes"] = [t["recette"]]
            groupes[cle] = t

    return list(groupes.values())
def _superposition_valide(plan) -> bool:
    """Deux pieces d'un meme slot : l'une doit aller dessus, l'autre dessous."""
    par_slot: dict[str, list] = {}
    for g, _, _ in plan:
        par_slot.setdefault(g.slot, []).append(g)

    for slot, couches in par_slot.items():
        if slot in ("chaussures", "accessoire") or len(couches) < 2:
            continue
        if len(couches) > 2:
            return False              # trois couches : jamais
        caps = {g.attributs.get("superposable", "seul") for g in couches}
        if caps != {"dessus", "dessous"}:
            return False

    return True