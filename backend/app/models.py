from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ResearchDirection(Base):
    __tablename__ = "research_directions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    weight: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(default=0)

    matches: Mapped[list["TeacherDirectionMatch"]] = relationship(back_populates="direction")


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    institution: Mapped[str] = mapped_column(String(200), index=True)
    department: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    homepage_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    lab_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default=ReviewStatus.pending.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    direction_matches: Mapped[list["TeacherDirectionMatch"]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan"
    )
    publications: Mapped[list["Publication"]] = relationship(back_populates="teacher", cascade="all, delete-orphan")
    grants: Mapped[list["Grant"]] = relationship(back_populates="teacher", cascade="all, delete-orphan")
    sources: Mapped[list["SourceEvidence"]] = relationship(back_populates="teacher", cascade="all, delete-orphan")


class TeacherDirectionMatch(Base):
    __tablename__ = "teacher_direction_matches"
    __table_args__ = (UniqueConstraint("teacher_id", "direction_id", name="uq_teacher_direction"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    direction_id: Mapped[int] = mapped_column(ForeignKey("research_directions.id"))
    evidence_sentence: Mapped[str] = mapped_column(Text)
    weight_override: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    teacher: Mapped[Teacher] = relationship(back_populates="direction_matches")
    direction: Mapped[ResearchDirection] = relationship(back_populates="matches")


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    title: Mapped[str] = mapped_column(Text)
    year: Mapped[Optional[int]] = mapped_column(nullable=True)
    authors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    venue: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    doi_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    scholar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_official_source: Mapped[bool] = mapped_column(Boolean, default=False)

    teacher: Mapped[Teacher] = relationship(back_populates="publications")


class Grant(Base):
    __tablename__ = "grants"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    name: Mapped[str] = mapped_column(Text)
    year: Mapped[Optional[int]] = mapped_column(nullable=True)
    funder: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    teacher: Mapped[Teacher] = relationship(back_populates="grants")


class SourceEvidence(Base):
    __tablename__ = "source_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    source_url: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(80), default="official")
    field_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trust_level: Mapped[int] = mapped_column(default=3)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    teacher: Mapped[Teacher] = relationship(back_populates="sources")


class ApplicationProfile(Base):
    __tablename__ = "application_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    extracted_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LlmProviderConfig(Base):
    __tablename__ = "llm_provider_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(80), default="openai-compatible")
    model: Mapped[str] = mapped_column(String(160))
    base_url: Mapped[str] = mapped_column(String(500))
    api_key: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
