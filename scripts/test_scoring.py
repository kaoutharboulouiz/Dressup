import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.styling.scoring import hex_to_hsl, est_neutre, score_couleur, score_tenue

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