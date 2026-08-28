from __future__ import annotations
import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
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
    pinterest_token: Mapped[str | None] = mapped_column(Text)
    pinterest_last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email: Mapped[str | None] = mapped_column(String(160), unique=True)
    mot_de_passe_hash: Mapped[str | None] = mapped_column(String(128))

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

class Outfit(Base):
    __tablename__ = "outfits"
    __table_args__ = (UniqueConstraint("outfit_key", name="uq_outfit_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    outfit_key: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[float] = mapped_column(Float)
    couverture: Mapped[float] = mapped_column(Float)
    harmonie: Mapped[float] = mapped_column(Float)
    justification_tenue: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["OutfitItem"]] = relationship(back_populates="outfit")
    variants: Mapped[list["Variant"]] = relationship(back_populates="outfit")


class Variant(Base):
    __tablename__ = "variants"
    __table_args__ = (UniqueConstraint("variant_key", name="uq_variant_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outfit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outfits.id"))
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recipes.id"))
    variant_key: Mapped[str] = mapped_column(String(64), index=True)

    titre: Mapped[str] = mapped_column(String(80))
    ports: Mapped[dict] = mapped_column(JSONB, default=dict)
    justification_port: Mapped[str | None] = mapped_column(Text)
    silhouette: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(12), default="styliste")
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    outfit: Mapped[Outfit] = relationship(back_populates="variants")


class Render(Base):
    __tablename__ = "renders"
    __table_args__ = (UniqueConstraint("render_key", name="uq_render_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("variants.id"))
    avatar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("avatars.id"))
    render_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending")
    provider: Mapped[str] = mapped_column(String(60))
    image_path: Mapped[str | None] = mapped_column(Text)
    erreur: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    variant: Mapped["Variant"] = relationship()


class OutfitItem(Base):
    __tablename__ = "outfit_items"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outfit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outfits.id"))
    garment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("garments.id"))
    slot: Mapped[str] = mapped_column(String(16))
    port: Mapped[str | None] = mapped_column(Text)
    is_anchor: Mapped[bool] = mapped_column(default=False)
    ordre: Mapped[int] = mapped_column(Integer)
    outfit: Mapped[Outfit] = relationship(back_populates="items")
    garment: Mapped[Garment] = relationship()




class Avatar(Base):
    __tablename__ = "avatars"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    image_path: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())