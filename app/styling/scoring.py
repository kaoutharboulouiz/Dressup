"""Scoring d'harmonie entre vetements. Pur, deterministe, testable sans I/O."""

from __future__ import annotations

import colorsys

# Seuils colorimetriques
SAT_NEUTRE = 0.18       # en dessous : pas de teinte significative
LUM_SOMBRE = 0.18
LUM_CLAIRE = 0.85
SAT_VIVE = 0.70         # au dela : couleur qui "crie"


# Un ton clair ou sombre tolere plus de saturation avant d'etre "colore"
SAT_NEUTRE_EXTREME = 0.40
LUM_TRES_CLAIRE = 0.72
LUM_TRES_SOMBRE = 0.28

ECART_FORMALITE_MAX = 2

def est_neutre(hsl: tuple[float, float, float]) -> bool:
    """Noir, blanc, gris, mais aussi beige, taupe, marine tres fonce."""
    _, sat, lum = hsl

    if sat < SAT_NEUTRE:              # gris franc
        return True
    if lum < LUM_SOMBRE or lum > LUM_CLAIRE:   # quasi noir / quasi blanc
        return True
    # Beige, creme, taupe, marine profond : peu satures ET extremes en luminosite
    if sat < SAT_NEUTRE_EXTREME and (lum > LUM_TRES_CLAIRE or lum < LUM_TRES_SOMBRE):
        return True
    return False

def hex_to_hsl(hex_str: str) -> tuple[float, float, float]:
    """'#4c77af' -> (teinte 0-360, saturation 0-1, luminosite 0-1)."""
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return (0.0, 0.0, 0.5)          # gris moyen par defaut
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    teinte, lum, sat = colorsys.rgb_to_hls(r, g, b)
    return (teinte * 360, sat, lum)




def ecart_teinte(t1: float, t2: float) -> float:
    """Distance angulaire sur le cercle chromatique, 0-180."""
    d = abs(t1 - t2)
    return min(d, 360 - d)


def score_couleur(hex1: str, hex2: str) -> float:
    """Harmonie entre deux couleurs. 0 = discordant, 1 = parfait."""
    c1, c2 = hex_to_hsl(hex1), hex_to_hsl(hex2)

    n1, n2 = est_neutre(c1), est_neutre(c2)
    if n1 and n2:
        return 0.80                      # deux neutres : sobre, jamais faux
    if n1 or n2:
        return 0.90                      # un neutre ancre n'importe quelle couleur

    d = ecart_teinte(c1[0], c2[0])

    if d < 25:
        base = 0.85                      # camaieu, meme famille
    elif d < 45:
        base = 0.35                      # zone batarde : trop proche pour etre voulu
    elif d < 100:
        base = 0.60                      # analogue elargi
    elif d < 140:
        base = 0.75                      # triadique
    else:
        base = 0.80                      # complementaire

    if c1[1] > SAT_VIVE and c2[1] > SAT_VIVE:
        base *= 0.70                     # deux saturees se battent

    return round(base, 3)


def score_formalite(formalites: list[int]) -> float | None:
    """None = rejet (ecart trop grand). Sinon 0-1."""
    ecart = max(formalites) - min(formalites)
    if ecart > ECART_FORMALITE_MAX:
        return None
    return round(1 - ecart / 4, 3)


def score_tenue(pieces: list[dict]) -> dict:
    """pieces : [{'slot':..., 'couleur_hex':..., 'formalite':...}, ...]

    Retourne {'score': float|None, 'couleur': float, 'formalite': float|None}
    """
    f = score_formalite([p["formalite"] for p in pieces])
    if f is None:
        return {"score": None, "couleur": 0.0, "formalite": None,
                "rejet": "ecart de formalite trop grand"}

    # Moyenne sur toutes les paires possibles
    paires = [
        score_couleur(pieces[i]["couleur_hex"], pieces[j]["couleur_hex"])
        for i in range(len(pieces))
        for j in range(i + 1, len(pieces))
    ]
    c = round(sum(paires) / len(paires), 3) if paires else 1.0

    return {
        "score": round(0.65 * c + 0.35 * f, 3),
        "couleur": c,
        "formalite": f,
    }