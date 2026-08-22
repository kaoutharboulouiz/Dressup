"""Authentification : hachage de mot de passe et jetons JWT."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException
from fastapi.security import HTTPBearer

from app.config import settings

# bcrypt tronque silencieusement au-dela de 72 OCTETS (pas caracteres).
# On tronque explicitement pour que le comportement soit visible ici.
LIMITE_BCRYPT = 72

securite = HTTPBearer(auto_error=False)


def hacher(mot_de_passe: str) -> str:
    octets = mot_de_passe.encode("utf-8")[:LIMITE_BCRYPT]
    return bcrypt.hashpw(octets, bcrypt.gensalt()).decode("utf-8")


def verifier(mot_de_passe: str, hash_stocke: str) -> bool:
    octets = mot_de_passe.encode("utf-8")[:LIMITE_BCRYPT]
    return bcrypt.checkpw(octets, hash_stocke.encode("utf-8"))


def creer_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.jwt_expire_heures
    )
    charge = {"sub": str(user_id), "exp": expire}
    return jwt.encode(charge, settings.jwt_secret, algorithm="HS256")


def lire_token(token: str) -> uuid.UUID:
    try:
        charge = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return uuid.UUID(charge["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "session expiree")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(401, "jeton invalide")