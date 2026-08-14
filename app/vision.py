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
                config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": 2048,
                },
            )
            return _parse(resp.text)
        except json.JSONDecodeError:
            if i < tentatives - 1:
                print("   JSON invalide - nouvelle tentative...")
                continue
            raise
        except Exception as e:
            if "503" in str(e) and i < tentatives - 1:
                print(f"   503 - attente {15 * (i+1)}s...")
                time.sleep(15 * (i + 1))
            else:
                raise


def embed(texte: str) -> list[float]:
    resp = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=texte,
    )
    return list(resp.embeddings[0].values)

PROMPT_RECIPE = """Tu analyses une photo d'inspiration mode pour en extraire la RECETTE
de la tenue, afin de la reproduire avec d'AUTRES vetements.

Si l'image ne montre pas une tenue portee (deco, nourriture, paysage, gros plan
d'un seul objet), reponds exactement : {"pieces": []}

Sinon, reponds uniquement par un objet JSON :

{
  "pieces": [
    {
      "slot": "haut | bas | robe | chaussures | veste | accessoire",
      "categorie": "nom precis",
      "couleur_nom": "...",
      "couleur_hex": "#RRGGBB",
      "coupe": "...",
      "matiere": "...",
      "formalite": 3,
      "port": "COMMENT la piece est portee : rentree, sortie, retroussee,
               ouverte, nouee, taille haute. Champ le plus important."
    }
  ],
  "ordre_superposition": ["slots du plus pres du corps au plus exterieur"],
  "registre": "ex. casual chic, streetwear, minimaliste, workwear",
  "silhouette": "une phrase sur les volumes et les proportions",
  "regle_cle": "...",
  "description": "2 phrases resumant la tenue, pour recherche semantique"
}

REGLE CRITIQUE pour regle_cle : formule un principe de style TRANSPOSABLE a
d'autres vetements, pas une description de ceux-ci.
  MAUVAIS : "la chemise blanche va bien avec le jean bleu"
  BON     : "un tuck partiel marque la taille sous un volume oversize"
  BON     : "deux neutres proches se distinguent par le contraste de matieres"
"""


def extraire_recette(path: Path, tentatives: int = 3) -> dict:
    for i in range(tentatives):
        try:
            resp = client.models.generate_content(
                model=settings.model_vision,
                contents=[_image_part(path), PROMPT_RECIPE],
                config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": 4096,
                },
            )
            return _parse(resp.text)
        except json.JSONDecodeError:
            if i < tentatives - 1:
                print("   JSON tronque - nouvelle tentative...")
                continue
            raise
        except Exception as e:
            if "503" in str(e) and i < tentatives - 1:
                print(f"   503 - attente {15 * (i+1)}s...")
                time.sleep(15 * (i + 1))
            else:
                raise