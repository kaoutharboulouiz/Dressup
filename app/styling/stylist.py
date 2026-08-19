"""LLM styliste : produit N facons de porter une meme tenue.

N'est appele que sur le top 5, jamais sur la combinatoire complete.
"""

from __future__ import annotations

import json
import time

from app.config import settings
from app.vision import _parse, client

PROMPT = """Tu es styliste. On te donne une tenue construite avec les vetements reels
d'une personne, et des references de style dont elle s'inspire.

Tu produis DEUX choses :

1. Une justification de la TENUE : pourquoi ces pieces vont ensemble. Parle
   couleurs, matieres, formes, proportions. Ne parle PAS de la facon de les porter.

2. DEUX OU TROIS facons de la porter. Chaque facon doit etre justifiee par la
   FORME des vetements : un volume ample appelle une taille marquee, un haut
   court se porte autrement qu'un haut long, une matiere rigide ne se drape pas.
   Ne propose que des facons qui rendent VRAIMENT bien sur ces pieces precises.
   Si une seule facon fonctionne, n'en donne qu'une.

Le champ "port_reference" de chaque piece decrit comment elle etait portee sur
UNE inspiration, avec d'AUTRES vetements. C'est une source, pas une consigne :
transpose-la si elle marche ici, ignore-la sinon.

Reponds uniquement par un objet JSON :

{
  "justification_tenue": "2 phrases sur l'accord des pieces : couleurs, matieres,
                          formes. Concret, sans jargon marketing.",
  "variantes": [
    {
      "titre": "3 a 6 mots nommant la facon, ex. 'caraco rentre a l'avant'",
      "ports": {
        "0": "comment porter la piece d'index 0 dans CETTE facon, ou null",
        "1": "..."
      },
      "silhouette": "une phrase sur les volumes obtenus par cette facon",
      "justification_port": "2 phrases : pourquoi cette facon marche sur ces
                             formes precises. TERMINE par une suggestion
                             d'occasion, ex. 'Parfait pour un dejeuner en
                             terrasse.'",
      "source": "recette" si tu transposes un port_reference, "styliste" si
                tu proposes de toi-meme
    }
  ]
}


REGLES :
- Les cles de "ports" sont les index (en chaine) de la tenue reelle.
- Ne mentionne JAMAIS un vetement absent de la tenue reelle.
- Deux variantes doivent differer VISIBLEMENT, pas par une nuance de formulation.
- Chaque variante doit changer un AXE DIFFERENT : le rentre/sorti, l'ouverture
  d'une piece, la position de taille, le retroussement des manches, la
  superposition. Deux variantes qui jouent sur le meme axe sont un doublon,
  meme si les mots different.
- Si deux vetements partagent le meme slot (superposition), donne-leur des
  instructions differentes et coherentes entre elles.
- Le champ "port" sera lu par un generateur d'images. Decris donc ce qu'on VOIT,
  jamais le geste : quelle partie du vetement est visible, ou passe sa ligne,
  ce qui apparait dessous, ou s'arrete l'ourlet.
    MAUVAIS : "mi-rentre"
    BON     : "l'avant disparait sous la ceinture, l'arriere retombe sur les
               hanches"
    MAUVAIS : "veste boutonnee en bas"
    BON     : "seuls les deux boutons du bas sont fermes, les pans du haut
               s'ecartent et laissent voir le top en dessous"
  Le champ "titre", lui, reste court et lisible pour un humain.
  - Mets "port": null quand il n'y a rien de visuellement notable a dire sur une
  piece. Une paire de chaussures se porte aux pieds : ce n'est pas une
  instruction. N'ecris un port que s'il change ce qu'on voit."""


def _payload(tenue: dict, recettes: list) -> str:
    return json.dumps({
        "inspirations": [
            {
                "registre": r.registre,
                "regle_cle": r.regle_cle,
                "silhouette": r.silhouette,
            }
            for r in recettes
        ],
        "tenue_reelle": [
            {
                "index": n,
                "slot": i["slot"],
                "vetement": i["garment"].categorie,
                "couleur": i["garment"].attributs.get("couleur_nom", ""),
                "matiere": i["garment"].attributs.get("matiere", ""),
                "coupe": i["garment"].attributs.get("coupe", ""),
                "port_reference": i.get("port"),
                "impose": i["is_anchor"],
            }
            for n, i in enumerate(tenue["items"])
        ],
    }, ensure_ascii=False, indent=2)


def styliser(tenue: dict, recettes: list | None = None, tentatives: int = 3) -> dict:
    """Enrichit une tenue avec justification_tenue et variantes."""
    recettes = recettes or [tenue["recette"]]

    for i in range(tentatives):
        try:
            resp = client.models.generate_content(
                model=settings.model_vision,
                contents=[PROMPT, _payload(tenue, recettes)],
                config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": 4096,
                },
            )
            spec = _parse(resp.text)
            break
        except json.JSONDecodeError:
            if i < tentatives - 1:
                continue
            raise
        except Exception as e:
            if "503" in str(e) and i < tentatives - 1:
                time.sleep(15 * (i + 1))
            else:
                raise
    else:
        raise RuntimeError("styliser : echec apres retries")

    tenue["justification_tenue"] = spec.get("justification_tenue")
    tenue["variantes"] = [
        {
            "titre": v.get("titre", "sans titre")[:80],
            "ports": {int(k): val for k, val in (v.get("ports") or {}).items()},
            "silhouette": v.get("silhouette"),
            "justification_port": v.get("justification_port"),
            "source": v.get("source", "styliste"),
        }
        for v in spec.get("variantes", [])
    ]
    return tenue