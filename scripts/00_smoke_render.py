from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google import genai
from google.genai import types

from app.config import settings

ORDRE = ["bas", "robe", "haut", "veste", "chaussures", "accessoire"]

client = genai.Client(api_key=settings.gemini_api_key)


def construire_prompt(garments, port):
    lignes = [
        "Image 1 - PERSONNE : preserve exactement le visage, la morphologie, "
        "la pose et le fond. Ne modifie rien de cette personne."
    ]
    for i, (_, slot) in enumerate(garments, start=2):
        lignes.append(
            f"Image {i} - {slot.upper()} : reproduis fidelement ce vetement. "
            f"Couleur, motif, matiere, coupe et longueur identiques a la reference."
        )
    slots = [s for _, s in garments]
    lignes += [
        "",
        f"Habille la personne de l'image 1 avec ces {len(garments)} piece(s).",
        "Superposition, du plus pres du corps au plus exterieur : "
        + ", ".join(sorted(slots, key=ORDRE.index))
        + ".",
        "",
        "Photographie en pied, eclairage neutre et uniforme, fond identique a l'image 1.",
        "N'ajoute AUCUN vetement ni accessoire qui ne soit pas liste ci-dessus.",
    ]
    return "\n".join(lignes)


def part(path):
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--avatar", type=Path, required=True)
    ap.add_argument("--garment", action="append", required=True)
    ap.add_argument("--draft", action="store_true")
    args = ap.parse_args()

    garments = []
    for g in args.garment:
        chemin, _, slot = g.rpartition(":")
        if slot not in ORDRE:
            print(f"Slot inconnu : {slot}. Attendu : {ORDRE}")
            return 2
        garments.append((Path(chemin), slot))

    for p in [args.avatar] + [c for c, _ in garments]:
        if not p.exists():
            print(f"Introuvable : {p}")
            return 2

    garments.sort(key=lambda t: ORDRE.index(t[1]))
    prompt = construire_prompt(garments, port={})

    print("--- Prompt envoye ---")
    print(prompt)
    print("---------------------")

    modele = settings.model_image_draft if args.draft else settings.model_image
    contents = [part(args.avatar)] + [part(c) for c, _ in garments] + [prompt]

    try:
        resp = client.models.generate_content(model=modele, contents=contents)
    except Exception as e:
        print(f"ECHEC ({modele}) : {e}")
        return 1

    settings.dir_renders.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    trouve = False

    for i, p in enumerate(resp.candidates[0].content.parts):
        if getattr(p, "inline_data", None) and p.inline_data.data:
            sortie = settings.dir_renders / f"smoke-{horodatage}-{i}.png"
            sortie.write_bytes(p.inline_data.data)
            print(f"Rendu ecrit : {sortie}")
            trouve = True
        elif getattr(p, "text", None):
            print(f"Reponse texte : {p.text}")

    if not trouve:
        print("Aucune image renvoyee.")
        return 1

    print("Regarde le rendu : tu reconnais tes vetements ?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())