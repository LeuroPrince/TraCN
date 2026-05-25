from dataclasses import dataclass
from typing import Optional

from .models import ResearchDirection, Teacher
from .schemas import DirectionMatchRead, TeacherDetail, TeacherSummary

SUPPLEMENTAL_DIRECTION_KEY = "neuroscience_supplement"


@dataclass(frozen=True)
class TeacherScore:
    match_score: float
    primary_direction_key: Optional[str]
    primary_direction_name: Optional[str]
    evidence_sentence: Optional[str]
    directions: list[DirectionMatchRead]


def summarize_teacher_score(teacher: Teacher) -> TeacherScore:
    directions: list[DirectionMatchRead] = []
    scored_directions: list[DirectionMatchRead] = []
    for match in teacher.direction_matches:
        direction: ResearchDirection = match.direction
        effective_weight = match.weight_override if match.weight_override is not None else direction.weight
        direction_read = DirectionMatchRead(
            id=match.id,
            direction_id=direction.id,
            direction_key=direction.key,
            direction_name=direction.name,
            effective_weight=effective_weight,
            evidence_sentence=match.evidence_sentence,
        )
        directions.append(direction_read)
        if direction.key != SUPPLEMENTAL_DIRECTION_KEY:
            scored_directions.append(direction_read)

    directions.sort(key=lambda item: (-item.effective_weight, item.direction_name))
    scored_directions.sort(key=lambda item: (-item.effective_weight, item.direction_name))
    match_score = round(sum(item.effective_weight for item in scored_directions), 2)
    primary = scored_directions[0] if scored_directions else None
    return TeacherScore(
        match_score=match_score,
        primary_direction_key=primary.direction_key if primary else None,
        primary_direction_name=primary.direction_name if primary else None,
        evidence_sentence=primary.evidence_sentence if primary else None,
        directions=directions,
    )


def teacher_to_summary(teacher: Teacher) -> TeacherSummary:
    score = summarize_teacher_score(teacher)
    return TeacherSummary(
        id=teacher.id,
        name=teacher.name,
        avatar_url=teacher.avatar_url,
        institution=teacher.institution,
        department=teacher.department,
        city=teacher.city,
        latitude=teacher.latitude,
        title=teacher.title,
        homepage_url=teacher.homepage_url,
        lab_url=teacher.lab_url,
        email=teacher.email,
        status=teacher.status,
        bio=teacher.bio,
        match_score=score.match_score,
        primary_direction_key=score.primary_direction_key,
        primary_direction_name=score.primary_direction_name,
        evidence_sentence=score.evidence_sentence,
        directions=score.directions,
    )


def teacher_to_detail(teacher: Teacher) -> TeacherDetail:
    summary = teacher_to_summary(teacher)
    return TeacherDetail(
        **summary.model_dump(),
        phone=teacher.phone,
        publications=teacher.publications,
        grants=teacher.grants,
        sources=teacher.sources,
    )


def sort_teachers(teachers: list[Teacher]) -> list[Teacher]:
    return sorted(
        teachers,
        key=lambda teacher: (
            -summarize_teacher_score(teacher).match_score,
            -(teacher.latitude if teacher.latitude is not None else -999),
            teacher.institution,
            teacher.name,
        ),
    )


def sort_teachers_by_institution(teachers: list[Teacher]) -> list[Teacher]:
    return sorted(
        teachers,
        key=lambda teacher: (
            teacher.institution.casefold(),
            teacher.name.casefold(),
        ),
    )
