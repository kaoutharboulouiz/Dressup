"""Client Pinterest v5, lecture seule.

Perimetre : l'API ne donne acces qu'aux contenus du compte authentifie.
Il n'existe pas de recherche sur le catalogue global.
"""

from __future__ import annotations

import httpx


API = "https://api.pinterest.com/v5"
def _get(token: str, chemin: str, params: dict | None = None) -> dict:
    r = httpx.get(
        f"{API}{chemin}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"[{r.status_code}] {r.text[:400]}")
    r.raise_for_status()
    return r.json()


def lister_boards(token: str) -> list[dict]:
    boards, bookmark = [], None
    while True:
        params = {"page_size": 25}
        if bookmark:
            params["bookmark"] = bookmark
        data = _get(token, "/boards", params)
        boards.extend(data.get("items", []))
        bookmark = data.get("bookmark")
        if not bookmark:
            return boards


def lister_pins(token: str, board_id: str, limite: int = 50) -> list[dict]:
    pins, bookmark = [], None
    while len(pins) < limite:
        params = {"page_size": 25}
        if bookmark:
            params["bookmark"] = bookmark
        data = _get(token, f"/boards/{board_id}/pins", params)
        pins.extend(data.get("items", []))
        bookmark = data.get("bookmark")
        if not bookmark:
            break
    return pins[:limite]


def url_image(pin: dict) -> str | None:
    """Extrait l'URL de l'image la plus grande disponible."""
    images = (pin.get("media") or {}).get("images") or {}
    for taille in ("1200x", "600x", "400x300", "150x150"):
        if taille in images:
            return images[taille].get("url")
    return None