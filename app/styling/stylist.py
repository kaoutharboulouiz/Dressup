"""LLM styliste : transpose le port et redige la justification.

N'est appele que sur le top 5-10, jamais sur la combinatoire complete.
"""

from __future__ import annotations

import json
import time

from app.config import settings
from app.vision import _parse, client

PROMPT = """Tu es styliste. On te donne une tenue construite a partir des vetements
reels d'une personne, inspiree d'une reference.

Ton travail : TRANSPOSER le port de la reference vers les vetements reels.

Le champ "port_reference" decrit comment la piece etait portee sur l'INSPIRATION,
avec d'AUTRES vetements. Il peut mentionner un vetement absent de la tenue reelle
(ex: "rentre dans le pantalon" alors que la personne porte une jupe).
Tu dois reecrire ce port pour qu'il ait du sens avec le vetement REEL.

Reponds uniquement par un objet JSON :

{
  "pieces": [
    {
      "slot": "...",
      "port": "comment porter CE vetement, formule pour cette tenue precise.
               Si aucune indication utile, mets null.",
      "transpose": true si tu as adapte depuis la reference, false si tu l'as
                   repris tel quel ou invente
    }
  ],
  "silhouette": "une phrase sur les volumes et proportions de CETTE tenue",
  "justification": "2 phrases expliquant pourquoi cette tenue fonctionne.
                    Appuie-toi sur la regle de l'inspiration, mais parle des
                    vetements reels. Ton naturel, pas de jargon marketing.",
  "occasion": "un contexte ou porter cette tenue, 3-5 mots"
}

REGLES :
- Ne mentionne JAMAIS un vetement absent de la tenue reelle.
- Si le port de reference ne se transpose pas, mets null plutot qu'inventer.
- La justification doit etre specifique a ces vetements, pas generique."""


def _payload(tenue: dict) -> str:
    return json.dumps({
        "inspiration": {
            "registre": tenue["recette"].registre,
            "regle_cle": tenue["recette"].regle_cle,
            "silhouette": tenue["recette"].silhouette,
        },
        "tenue_reelle": [
            {
                "slot": i["slot"],
                "vetement": i["garment"].categorie,
                "couleur": i["garment"].attributs.get("couleur_nom", ""),
                "matiere": i["garment"].attributs.get("matiere", ""),
                "coupe": i["garment"].attributs.get("coupe", ""),
                "port_reference": i.get("port"),
                "impose": i["is_anchor"],
            }
            for i in tenue["items"]
        ],
    }, ensure_ascii=False, indent=2)


def styliser(tenue: dict, tentatives: int = 3) -> dict:
    """Enrichit une tenue avec son styling_spec. Modifie et retourne la tenue."""
    for i in range(tentatives):
        try:
            resp = client.models.generate_content(
                model=settings.model_vision,
                contents=[PROMPT, _payload(tenue)],
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

    # Reinjecte le port transpose dans les items, par slot
    ports = {p["slot"]: p.get("port") for p in spec.get("pieces", [])}
    for item in tenue["items"]:
        item["port_transpose"] = ports.get(item["slot"])

    tenue["styling_spec"] = {
        "silhouette": spec.get("silhouette"),
        "justification": spec.get("justification"),
        "occasion": spec.get("occasion"),
        "ordre_superposition": [i["slot"] for i in tenue["items"]],
        "pieces": [
            {"slot": i["slot"], "port": i.get("port_transpose")}
            for i in tenue["items"]
        ],
    }
    return tenue


def styliser_lot(tenues: list[dict], n: int = 5) -> list[dict]:
    """Stylise les n premieres tenues. Les autres sont retournees telles quelles."""
    for t in tenues[:n]:
        try:
            styliser(t)
        except Exception as e:
            print(f"  styliser echoue : {str(e)[:80]}")
            t["styling_spec"] = None
    return tenues
def styliser_lot_intelligent(s, user_id, tenues: list[dict], n: int = 5) -> list[dict]:
    """Ne stylise que les tenues absentes de la base. Recupere le spec des autres."""
    from app.models import Outfit
    from app.rendering.service import outfit_key
    from sqlalchemy import select

    for t in tenues[:n]:
        ids = [i["garment"].id for i in t["items"]]
        cle = outfit_key(user_id, ids)
        connu = s.scalar(select(Outfit).where(Outfit.outfit_key == cle))

        if connu is not None and connu.styling_spec:
            t["styling_spec"] = connu.styling_spec
            ports = {p["slot"]: p.get("port")
                     for p in connu.styling_spec.get("pieces", [])}
            for item in t["items"]:
                item["port_transpose"] = ports.get(item["slot"])
            print("  (styling en cache)")
            continue

        try:
            styliser(t)
        except Exception as e:
            print(f"  styliser echoue : {str(e)[:80]}")
            t["styling_spec"] = None
    return tenues