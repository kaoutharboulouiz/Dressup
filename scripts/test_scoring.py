import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.styling.scoring import hex_to_hsl, est_neutre, score_couleur, score_tenue
from app.styling.scoring import malus_focal, malus_superposition


CAS = [
    ("#000000", "#FFFFFF", "noir + blanc"),
    ("#2B3A5C", "#E8E2D5", "bleu marine + beige"),
    ("#4C77AF", "#3F6BA0", "deux bleus tres proches"),
    ("#4C77AF", "#6B5FA0", "bleu + violet (zone batarde)"),
    ("#FF0000", "#00FF00", "rouge vif + vert vif"),
    ("#8B4513", "#4F6B5C", "terre + vert sourd"),
]

print("=== Paires de couleurs ===")
for h1, h2, label in CAS:
    print(f"{score_couleur(h1, h2):.2f}  {label}")

print("\n=== Detection des neutres ===")
for h in ("#000000", "#FFFFFF", "#808080", "#E8E2D5", "#D4C5A9",
          "#8B7D6B", "#1C2841", "#FF0000", "#4C77AF"):
    hsl = hex_to_hsl(h)
    print(f"{h}  H={hsl[0]:6.1f} S={hsl[1]:.2f} L={hsl[2]:.2f}  "
          f"{'NEUTRE' if est_neutre(hsl) else 'coloree'}")

print("\n=== Tenues completes ===")
tenues = {
    "casual coherent": [
        {"slot": "haut", "couleur_hex": "#E8E2D5", "formalite": 3},
        {"slot": "bas", "couleur_hex": "#4C77AF", "formalite": 3},
        {"slot": "chaussures", "couleur_hex": "#3A3A3A", "formalite": 3},
    ],
    "ecart de formalite": [
        {"slot": "haut", "couleur_hex": "#FFFFFF", "formalite": 5},
        {"slot": "bas", "couleur_hex": "#4C77AF", "formalite": 1},
        {"slot": "chaussures", "couleur_hex": "#000000", "formalite": 5},
    ],
    "trois couleurs vives": [
        {"slot": "haut", "couleur_hex": "#FF0000", "formalite": 3},
        {"slot": "bas", "couleur_hex": "#00FF00", "formalite": 3},
        {"slot": "chaussures", "couleur_hex": "#0000FF", "formalite": 3},
    ],
}
for nom, pieces in tenues.items():
    r = score_tenue(pieces)
    print(f"{nom:24} {r}")


print("\n=== Malus focal ===")
cas_focal = {
    "un seul statement": [{"poids_visuel": 5}, {"poids_visuel": 2}, {"poids_visuel": 2}],
    "deux statements": [{"poids_visuel": 5}, {"poids_visuel": 4}, {"poids_visuel": 2}],
    "trois statements": [{"poids_visuel": 4}, {"poids_visuel": 4}, {"poids_visuel": 5}],
    "tout neutre": [{"poids_visuel": 2}, {"poids_visuel": 1}, {"poids_visuel": 3}],
    "valeurs en chaine": [{"poids_visuel": "5"}, {"poids_visuel": "4"}],
}
for nom, p in cas_focal.items():
    print(f"{nom:22} {malus_focal(p):.2f}")

print("\n=== Malus superposition ===")
cas_sup = {
    "hierarchie correcte": [
        {"slot": "haut", "motif": "uni", "longueur": "courte", "texture": "lisse"},
        {"slot": "haut", "motif": "imprime", "longueur": "longue", "texture": "fluide"},
    ],
    "deux motifs, meme longueur": [
        {"slot": "haut", "motif": "fleuri", "longueur": "standard", "texture": "fluide"},
        {"slot": "haut", "motif": "raye", "longueur": "standard", "texture": "fluide"},
    ],
    "pas de superposition": [
        {"slot": "haut", "motif": "fleuri", "longueur": "courte", "texture": "fluide"},
        {"slot": "bas", "motif": "raye", "longueur": "longue", "texture": "structuree"},
    ],
}
for nom, p in cas_sup.items():
    print(f"{nom:28} {malus_superposition(p):.2f}")