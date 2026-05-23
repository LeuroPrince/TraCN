import csv
import io
import json
import os
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import Settings, get_settings
from .database import get_db
from .fetcher import fetch_page_preview
from .llm import LlmConfigurationError, classify_teacher_directions, extract_profile_summary, rank_teachers_with_llm, test_llm
from .llm import runtime_from_db, runtime_from_settings
from .models import (
    ApplicationProfile,
    LlmProviderConfig,
    ResearchDirection,
    ReviewStatus,
    SourceEvidence,
    Teacher,
    TeacherDirectionMatch,
)
from .schemas import (
    DirectionCategoryRead,
    LlmConfigRead,
    LlmConfigCreate,
    LlmTestRead,
    MatchProfileResponse,
    ResearchDirectionRead,
    ResearchDirectionUpdate,
    ReclassifyTeachersResponse,
    TeacherCreate,
    TeacherDetail,
    TeacherMatchResult,
    TeacherReclassifyResult,
    TeacherStatusUpdate,
    TeacherSummary,
)
from .scoring import sort_teachers, summarize_teacher_score, teacher_to_detail, teacher_to_summary


router = APIRouter(prefix="/api")


def teacher_options():
    return (
        selectinload(Teacher.direction_matches).selectinload(TeacherDirectionMatch.direction),
        selectinload(Teacher.publications),
        selectinload(Teacher.grants),
        selectinload(Teacher.sources),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/directions", response_model=list[ResearchDirectionRead])
def list_directions(db: Annotated[Session, Depends(get_db)]) -> list[ResearchDirection]:
    return db.scalars(select(ResearchDirection).order_by(ResearchDirection.sort_order)).all()


@router.patch("/directions/{direction_id}", response_model=ResearchDirectionRead)
def update_direction(
    direction_id: int,
    payload: ResearchDirectionUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ResearchDirection:
    direction = db.get(ResearchDirection, direction_id)
    if not direction:
        raise HTTPException(status_code=404, detail="Direction not found")
    direction.weight = payload.weight
    db.commit()
    db.refresh(direction)
    return direction


@router.get("/teachers", response_model=list[TeacherSummary])
def list_teachers(
    db: Annotated[Session, Depends(get_db)],
    status: str = "approved",
    q: Optional[str] = None,
    direction: Optional[str] = None,
) -> list[TeacherSummary]:
    stmt = select(Teacher).options(*teacher_options()).where(Teacher.status == status)
    teachers = db.scalars(stmt).unique().all()
    if q:
        needle = q.lower()
        teachers = [
            teacher
            for teacher in teachers
            if needle in teacher.name.lower()
            or needle in teacher.institution.lower()
            or needle in (teacher.department or "").lower()
            or needle in teacher.bio.lower()
        ]
    if direction:
        teachers = [
            teacher
            for teacher in teachers
            if any(match.direction.key == direction for match in teacher.direction_matches)
        ]
    return [teacher_to_summary(teacher) for teacher in sort_teachers(teachers)]


@router.get("/direction-categories", response_model=list[DirectionCategoryRead])
def list_direction_categories(db: Annotated[Session, Depends(get_db)]) -> list[DirectionCategoryRead]:
    directions = db.scalars(select(ResearchDirection).order_by(ResearchDirection.sort_order)).all()
    grouped: dict[str, list[Teacher]] = {direction.key: [] for direction in directions}
    teachers = db.scalars(
        select(Teacher).options(*teacher_options()).where(Teacher.status == ReviewStatus.approved.value)
    ).unique().all()

    for teacher in teachers:
        score = summarize_teacher_score(teacher)
        if score.primary_direction_key and score.primary_direction_key in grouped:
            grouped[score.primary_direction_key].append(teacher)

    ordered_directions = sorted(directions, key=lambda item: (-item.weight, item.sort_order, item.name))
    return [
        DirectionCategoryRead(
            direction=direction,
            teachers=[teacher_to_summary(teacher) for teacher in sort_teachers(grouped[direction.key])],
        )
        for direction in ordered_directions
    ]


@router.post("/teachers/reclassify", response_model=ReclassifyTeachersResponse)
async def reclassify_teachers(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReclassifyTeachersResponse:
    try:
        runtime = get_active_runtime(db, settings)
    except LlmConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    directions = db.scalars(select(ResearchDirection).order_by(ResearchDirection.sort_order)).all()
    direction_payload = [
        {
            "key": direction.key,
            "name": direction.name,
            "weight": direction.weight,
            "description": direction.description,
        }
        for direction in directions
    ]
    valid_keys = {direction.key for direction in directions}
    teachers = db.scalars(
        select(Teacher).options(*teacher_options()).where(Teacher.status == ReviewStatus.approved.value)
    ).unique().all()
    results: list[TeacherReclassifyResult] = []

    for teacher in teachers:
        payload = teacher_for_llm(teacher)
        payload["sources"] = [
            {"source_type": source.source_type, "field_name": source.field_name, "quote": source.quote}
            for source in teacher.sources[:5]
        ]
        try:
            classified = await classify_teacher_directions(runtime, payload, direction_payload)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"AI classification failed for {teacher.name}: {exc}") from exc
        direction_keys = [
            key
            for key in classified.get("direction_keys", [])
            if isinstance(key, str) and key in valid_keys
        ]
        evidence_sentence = str(classified.get("evidence_sentence") or teacher.bio[:300] or "AI 未返回明确证据句。")
        teacher.direction_matches.clear()
        db.flush()
        add_direction_matches(db, teacher, direction_keys, evidence_sentence)
        results.append(
            TeacherReclassifyResult(
                teacher_id=teacher.id,
                teacher_name=teacher.name,
                direction_keys=direction_keys,
                evidence_sentence=evidence_sentence,
            )
        )
    db.commit()
    return ReclassifyTeachersResponse(updated=len(results), results=results)


@router.get("/teachers/{teacher_id}", response_model=TeacherDetail)
def get_teacher(teacher_id: int, db: Annotated[Session, Depends(get_db)]) -> TeacherDetail:
    stmt = select(Teacher).options(*teacher_options()).where(Teacher.id == teacher_id)
    teacher = db.scalars(stmt).unique().one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return teacher_to_detail(teacher)


@router.post("/teachers", response_model=TeacherDetail)
def create_teacher(payload: TeacherCreate, db: Annotated[Session, Depends(get_db)]) -> TeacherDetail:
    teacher = Teacher(
        name=payload.name,
        institution=payload.institution,
        department=payload.department,
        city=payload.city,
        latitude=payload.latitude,
        title=payload.title,
        avatar_url=payload.avatar_url,
        homepage_url=payload.homepage_url,
        lab_url=payload.lab_url,
        email=payload.email,
        phone=payload.phone,
        bio=payload.bio,
        status=ReviewStatus.pending.value,
    )
    db.add(teacher)
    db.flush()
    add_direction_matches(db, teacher, payload.direction_keys, payload.evidence_sentence)
    if payload.source_url:
        db.add(
            SourceEvidence(
                teacher_id=teacher.id,
                source_url=str(payload.source_url),
                source_type=payload.source_type,
                field_name="candidate",
                quote=payload.evidence_sentence or payload.bio[:500],
                trust_level=3 if payload.source_type == "official" else 2,
            )
        )
    db.commit()
    return get_teacher(teacher.id, db)


@router.patch("/teachers/{teacher_id}/status", response_model=TeacherDetail)
def update_teacher_status(
    teacher_id: int,
    payload: TeacherStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> TeacherDetail:
    teacher = db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    teacher.status = payload.status
    db.commit()
    return get_teacher(teacher.id, db)


@router.post("/ingest/csv", response_model=dict)
async def import_teacher_csv(
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> dict[str, int]:
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    imported = 0
    for row in reader:
        name = (row.get("name") or "").strip()
        institution = (row.get("institution") or "").strip()
        if not name or not institution:
            continue
        teacher = Teacher(
            name=name,
            institution=institution,
            department=(row.get("department") or "").strip() or None,
            city=(row.get("city") or "").strip() or None,
            latitude=parse_float(row.get("latitude")),
            title=(row.get("title") or "").strip() or None,
            avatar_url=(row.get("avatar_url") or "").strip() or None,
            homepage_url=(row.get("homepage_url") or "").strip() or None,
            lab_url=(row.get("lab_url") or "").strip() or None,
            email=(row.get("email") or "").strip() or None,
            phone=(row.get("phone") or "").strip() or None,
            bio=(row.get("bio") or "").strip(),
            status=ReviewStatus.pending.value,
        )
        db.add(teacher)
        db.flush()
        direction_keys = split_keys(row.get("direction_keys") or "")
        add_direction_matches(db, teacher, direction_keys, (row.get("evidence_sentence") or "").strip())
        source_url = (row.get("source_url") or "").strip()
        if source_url:
            db.add(
                SourceEvidence(
                    teacher_id=teacher.id,
                    source_url=source_url,
                    source_type=(row.get("source_type") or "official").strip(),
                    field_name="csv_import",
                    quote=(row.get("evidence_sentence") or row.get("bio") or "").strip()[:800],
                    trust_level=3,
                )
            )
        imported += 1
    db.commit()
    return {"imported": imported}


@router.post("/ingest/url-preview")
async def url_preview(source_url: Annotated[str, Form(...)]) -> dict[str, str]:
    try:
        return await fetch_page_preview(source_url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Fetch failed: {exc}") from exc


@router.get("/llm/config", response_model=LlmConfigRead)
def get_llm_config(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmConfigRead:
    active = db.scalars(select(LlmProviderConfig).where(LlmProviderConfig.is_active == True)).first()
    if active:
        return llm_config_to_read(active)
    return LlmConfigRead(
        id="env",
        name="Default .env",
        provider=settings.llm_provider,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key_env_name=settings.llm_api_key_env_name,
        has_api_key=bool(os.getenv(settings.llm_api_key_env_name)),
        is_active=True,
        is_env=True,
    )


@router.get("/llm/configs", response_model=list[LlmConfigRead])
def list_llm_configs(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[LlmConfigRead]:
    configs = db.scalars(select(LlmProviderConfig).order_by(LlmProviderConfig.created_at.desc())).all()
    has_active_custom = any(config.is_active for config in configs)
    env_config = LlmConfigRead(
        id="env",
        name="Default .env",
        provider=settings.llm_provider,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key_env_name=settings.llm_api_key_env_name,
        has_api_key=bool(os.getenv(settings.llm_api_key_env_name)),
        is_active=not has_active_custom,
        is_env=True,
    )
    return [env_config, *[llm_config_to_read(config) for config in configs]]


@router.post("/llm/configs", response_model=LlmConfigRead)
def create_llm_config(
    payload: LlmConfigCreate,
    db: Annotated[Session, Depends(get_db)],
) -> LlmConfigRead:
    config = LlmProviderConfig(
        name=payload.name,
        provider=payload.provider,
        model=payload.model,
        base_url=payload.base_url.rstrip("/"),
        api_key=payload.api_key,
        is_active=False,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return llm_config_to_read(config)


@router.patch("/llm/configs/{config_id}/select", response_model=LlmConfigRead)
def select_llm_config(
    config_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmConfigRead:
    for config in db.scalars(select(LlmProviderConfig)).all():
        config.is_active = False
    if config_id == "env":
        db.commit()
        return LlmConfigRead(
            id="env",
            name="Default .env",
            provider=settings.llm_provider,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            api_key_env_name=settings.llm_api_key_env_name,
            has_api_key=bool(os.getenv(settings.llm_api_key_env_name)),
            is_active=True,
            is_env=True,
        )
    config = db.get(LlmProviderConfig, int(config_id)) if config_id.isdigit() else None
    if not config:
        raise HTTPException(status_code=404, detail="Model config not found")
    config.is_active = True
    db.commit()
    db.refresh(config)
    return llm_config_to_read(config)


@router.post("/llm/config/test", response_model=LlmTestRead)
async def test_llm_config(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmTestRead:
    try:
        message = await test_llm(get_active_runtime(db, settings))
    except LlmConfigurationError as exc:
        return LlmTestRead(ok=False, message=str(exc))
    except Exception as exc:
        return LlmTestRead(ok=False, message=f"LLM request failed: {exc}")
    return LlmTestRead(ok=True, message=message.strip())


@router.post("/llm/configs/{config_id}/test", response_model=LlmTestRead)
async def test_named_llm_config(
    config_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmTestRead:
    try:
        if config_id == "env":
            runtime = runtime_from_settings(settings)
        else:
            config = db.get(LlmProviderConfig, int(config_id)) if config_id.isdigit() else None
            if not config:
                raise HTTPException(status_code=404, detail="Model config not found")
            runtime = runtime_from_db(config)
        message = await test_llm(runtime)
    except LlmConfigurationError as exc:
        return LlmTestRead(ok=False, message=str(exc))
    except Exception as exc:
        return LlmTestRead(ok=False, message=f"LLM request failed: {exc}")
    return LlmTestRead(ok=True, message=message.strip())


@router.post("/match/profile", response_model=MatchProfileResponse)
async def match_profile(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
) -> MatchProfileResponse:
    raw_text = (await file.read()).decode("utf-8", errors="ignore").strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Uploaded file is empty or not readable as text.")
    profile = ApplicationProfile(filename=file.filename, raw_text=raw_text)
    db.add(profile)
    db.commit()
    db.refresh(profile)

    teachers = db.scalars(
        select(Teacher).options(*teacher_options()).where(Teacher.status == ReviewStatus.approved.value)
    ).unique().all()
    sorted_candidates = sort_teachers(teachers)[:40]

    try:
        runtime = get_active_runtime(db, settings)
        profile.extracted_summary = await extract_profile_summary(runtime, raw_text)
        llm_candidates = [teacher_for_llm(teacher) for teacher in sorted_candidates]
        ai_rankings = await rank_teachers_with_llm(runtime, profile.extracted_summary, llm_candidates)
    except LlmConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        profile.extracted_summary = fallback_profile_summary(raw_text)
        ai_rankings = []
    db.commit()

    ai_by_id = {
        int(item.get("teacher_id")): item
        for item in ai_rankings
        if str(item.get("teacher_id", "")).isdigit()
    }
    results: list[TeacherMatchResult] = []
    for teacher in sorted_candidates:
        score = summarize_teacher_score(teacher).match_score
        ai_item = ai_by_id.get(teacher.id, {})
        ai_score = float(ai_item.get("ai_score", 0) or 0)
        reason = str(ai_item.get("reason") or "按方向权重、研究简介与来源证据进行基础匹配。")
        results.append(
            TeacherMatchResult(
                teacher=teacher_to_summary(teacher),
                total_score=round(score + ai_score, 2),
                direction_score=score,
                ai_score=round(ai_score, 2),
                reason=reason,
            )
        )
    results.sort(key=lambda item: (-item.total_score, item.teacher.institution, item.teacher.name))
    return MatchProfileResponse(
        profile_id=profile.id,
        extracted_summary=profile.extracted_summary or "",
        results=results[:10],
    )


def add_direction_matches(db: Session, teacher: Teacher, direction_keys: list[str], evidence_sentence: str) -> None:
    if not direction_keys:
        return
    directions = db.scalars(select(ResearchDirection).where(ResearchDirection.key.in_(direction_keys))).all()
    for direction in directions:
        override = None
        if direction.key == "brain_inspired_intelligence" and contains_bio_intelligence(evidence_sentence):
            override = 3.5
        if direction.key == "neuroimaging" and contains_mechanism_or_theory(evidence_sentence):
            override = 3.0
        db.add(
            TeacherDirectionMatch(
                teacher_id=teacher.id,
                direction_id=direction.id,
                evidence_sentence=evidence_sentence or teacher.bio[:300] or "待补充来源证据句。",
                weight_override=override,
            )
        )


def teacher_for_llm(teacher: Teacher) -> dict:
    score = summarize_teacher_score(teacher)
    return {
        "teacher_id": teacher.id,
        "name": teacher.name,
        "institution": teacher.institution,
        "title": teacher.title,
        "bio": teacher.bio[:1200],
        "directions": [item.model_dump() for item in score.directions],
        "evidence": score.evidence_sentence,
    }


def fallback_profile_summary(raw_text: str) -> str:
    return "未能调用外部模型，已保留原始文本用于后续匹配。文本预览：" + raw_text[:500]


def split_keys(value: str) -> list[str]:
    return [part.strip() for part in value.replace(";", ",").replace("，", ",").split(",") if part.strip()]


def parse_float(value: Optional[str]) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def contains_bio_intelligence(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ["生物智能", "biological intelligence", "认知机制", "智能机制"])


def contains_mechanism_or_theory(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ["机制", "理论", "建模", "mechanism", "theory", "model"])


def llm_config_to_read(config: LlmProviderConfig) -> LlmConfigRead:
    return LlmConfigRead(
        id=config.id,
        name=config.name,
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        api_key_env_name="stored locally",
        has_api_key=bool(config.api_key),
        is_active=config.is_active,
        is_env=False,
    )


def get_active_runtime(db: Session, settings: Settings):
    active = db.scalars(select(LlmProviderConfig).where(LlmProviderConfig.is_active == True)).first()
    if active:
        return runtime_from_db(active)
    return runtime_from_settings(settings)
