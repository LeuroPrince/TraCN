from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ResearchDirectionRead(BaseModel):
    id: int
    key: str
    name: str
    weight: float
    description: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class ResearchDirectionUpdate(BaseModel):
    weight: float = Field(ge=0, le=5)


class DirectionMatchRead(BaseModel):
    id: int
    direction_id: int
    direction_key: str
    direction_name: str
    effective_weight: float
    evidence_sentence: str


class PublicationRead(BaseModel):
    id: int
    title: str
    year: Optional[int] = None
    authors: Optional[str] = None
    venue: Optional[str] = None
    source_url: Optional[str] = None
    doi_url: Optional[str] = None
    scholar_url: Optional[str] = None
    is_official_source: bool

    model_config = ConfigDict(from_attributes=True)


class GrantRead(BaseModel):
    id: int
    name: str
    year: Optional[int] = None
    funder: Optional[str] = None
    source_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SourceEvidenceRead(BaseModel):
    id: int
    source_url: str
    source_type: str
    field_name: Optional[str] = None
    quote: Optional[str] = None
    trust_level: int

    model_config = ConfigDict(from_attributes=True)


class TeacherCreate(BaseModel):
    name: str
    institution: str
    department: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    title: Optional[str] = None
    avatar_url: Optional[str] = None
    homepage_url: Optional[str] = None
    lab_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    bio: str = ""
    direction_keys: list[str] = []
    evidence_sentence: str = ""
    source_url: Optional[HttpUrl] = None
    source_type: str = "official"


class TeacherStatusUpdate(BaseModel):
    status: str = Field(pattern="^(pending|approved|rejected)$")


class DirectionMatchPayload(BaseModel):
    direction_key: str
    evidence_sentence: str
    weight_override: Optional[float] = Field(default=None, ge=0, le=5)


class TeacherSummary(BaseModel):
    id: int
    name: str
    avatar_url: Optional[str] = None
    institution: str
    department: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    title: Optional[str] = None
    homepage_url: Optional[str] = None
    lab_url: Optional[str] = None
    email: Optional[str] = None
    status: str
    bio: str
    match_score: float
    primary_direction_key: Optional[str] = None
    primary_direction_name: Optional[str] = None
    evidence_sentence: Optional[str] = None
    directions: list[DirectionMatchRead]


class TeacherDetail(TeacherSummary):
    phone: Optional[str] = None
    publications: list[PublicationRead]
    grants: list[GrantRead]
    sources: list[SourceEvidenceRead]


class DirectionCategoryRead(BaseModel):
    direction: ResearchDirectionRead
    teachers: list[TeacherSummary]


class LlmConfigRead(BaseModel):
    id: Optional[int | str] = None
    name: str = "Default"
    provider: str
    model: str
    base_url: str
    api_key_env_name: str
    has_api_key: bool
    is_active: bool = True
    is_env: bool = True


class LlmConfigCreate(BaseModel):
    name: str
    provider: str = "openai-compatible"
    model: str
    base_url: str
    api_key: str


class LlmTestRead(BaseModel):
    ok: bool
    message: str


class TeacherMatchResult(BaseModel):
    teacher: TeacherSummary
    total_score: float
    direction_score: float
    ai_score: float
    reason: str


class TeacherReclassifyResult(BaseModel):
    teacher_id: int
    teacher_name: str
    direction_keys: list[str]
    evidence_sentence: str


class ReclassifyTeachersResponse(BaseModel):
    updated: int
    results: list[TeacherReclassifyResult]


class MatchProfileResponse(BaseModel):
    profile_id: int
    extracted_summary: str
    results: list[TeacherMatchResult]
