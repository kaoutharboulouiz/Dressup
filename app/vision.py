from __future__ import annotations
import json
from pathlib import Path
from google import genai
from google.genai import types
from app.config import settings

client = genai.Client(api_key=settings.gemini_api_key)

PROMPT_GARMENT = """Tu analyses la photo d'UN seul vetement.
Reponds uniquement par un objet JSON, sans texte autour :

{
  "slot": "haut | bas | robe | chaussures | veste | accessoire",
  "categorie": "nom precis en francais, ex. chemise oxford, jean droit",
  "couleur_hex": "#RRGGBB de la couleur dominante du tissu",
  "couleur_nom": "nom courant, ex. bleu indigo, blanc casse",
  "formalite": 1,
  "motif": "uni | raye | carreaux | imprime | fleuri | autre",
  "matiere": "matiere apparente, ex. denim, popeline, maille",
  "coupe": "ex. droite, oversize, ajustee",
  "saison": ["printemps", "ete", "automne", "hiver"],
  "description": "2 phrases decrivant le vetement comme un styliste"
}

Regles :
- formalite : 1=sport, 2=casual, 3=quotidien, 4=smart casual, 5=ceremonie
- couleur_hex doit refleter le tissu, pas le fond
- description sera utilisee pour recherche semantique : sois concrete"""


def _parse(txt: str) -> dict:
    txt = txt.strip()
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(txt)


def _image_part(path: Path) -> types.Part:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)


import time

def extraire_garment(path: Path, tentatives: int = 3) -> dict:
    for i in range(tentatives):
        try:
            resp = client.models.generate_content(
                model=settings.model_vision,
                contents=[_image_part(path), PROMPT_GARMENT],
                config={"response_mime_type": "application/json"},
            )
            return _parse(resp.text)
        except Exception as e:
            if "503" in str(e) and i < tentatives - 1:
                print(f"   503 - attente {15 * (i+1)}s avant retry...")
                time.sleep(15 * (i + 1))
            else:
                raise


def embed(texte: str) -> list[float]:
    resp = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=texte,
    )
    return list(resp.embeddings[0].values)