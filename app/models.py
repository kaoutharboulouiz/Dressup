from __future__ import annotations
import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from app.config import settings

SLOTS = ("haut", "bas", "robe", "chaussures", "veste", "accessoire")

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    handle: Mapped[str] = mapped_column(String(64), unique=True)
    prenom: Mapped[str | None] = mapped_column(String(80))
    taille_cm: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    garments: Mapped[list["Garment"]] = relationship(back_populates="user")

class Garment(Base):
    __tablename__ = "garments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    image_path: Mapped[str] = mapped_column(Text)
    cutout_path: Mapped[str | None] = mapped_column(Text)
    slot: Mapped[str] = mapped_column(String(16), index=True)
    categorie: Mapped[str] = mapped_column(String(40))
    couleur_hex: Mapped[str] = mapped_column(String(7))
    formalite: Mapped[int] = mapped_column(Integer)
    attributs: Mapped[dict] = mapped_column(JSONB, default=dict)
    description: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embed_dim))
    render_quality: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship(back_populates="garments")

class Recipe(Base):
    __tablename__ = "recipes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(20))
    source_ref: Mapped[str | None] = mapped_column(String(200))
    pieces: Mapped[list] = mapped_column(JSONB)
    registre: Mapped[str | None] = mapped_column(String(60))
    silhouette: Mapped[str | None] = mapped_column(Text)
    regle_cle: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embed_dim))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())