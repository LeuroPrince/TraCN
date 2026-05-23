import json
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import ResearchDirection, ReviewStatus, SourceEvidence, Teacher, TeacherDirectionMatch  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_teachers.py <batch.json>")
    path = Path(sys.argv[1])
    payload = json.loads(path.read_text(encoding="utf-8"))

    with SessionLocal() as db:
        directions = {row.key: row for row in db.scalars(select(ResearchDirection)).all()}
        imported = 0
        updated = 0
        skipped = 0

        for item in payload:
            teacher = db.scalars(
                select(Teacher).where(Teacher.name == item["name"], Teacher.institution == item["institution"])
            ).one_or_none()
            if teacher:
                updated += 1
            else:
                teacher = Teacher(name=item["name"], institution=item["institution"])
                db.add(teacher)
                db.flush()
                imported += 1

            for key in [
                "avatar_url",
                "department",
                "city",
                "latitude",
                "title",
                "homepage_url",
                "lab_url",
                "email",
                "phone",
                "bio",
            ]:
                if key in item:
                    setattr(teacher, key, item[key])
            teacher.status = item.get("status", ReviewStatus.approved.value)

            teacher.direction_matches.clear()
            db.flush()
            evidence_sentence = item.get("evidence_sentence") or item.get("bio") or "待补充来源证据句。"
            for direction_key in item.get("direction_keys", []):
                direction = directions.get(direction_key)
                if not direction:
                    continue
                override = None
                lowered = evidence_sentence.lower()
                if direction.key == "brain_inspired_intelligence" and any(
                    term in lowered for term in ["生物智能", "biological intelligence", "认知机制", "智能机制"]
                ):
                    override = 3.5
                if direction.key == "neuroimaging" and any(
                    term in lowered for term in ["机制", "理论", "建模", "mechanism", "theory", "model"]
                ):
                    override = 3.0
                db.add(
                    TeacherDirectionMatch(
                        teacher_id=teacher.id,
                        direction_id=direction.id,
                        evidence_sentence=evidence_sentence,
                        weight_override=override,
                    )
                )

            source_url = item.get("source_url") or item.get("homepage_url")
            if source_url and not any(source.source_url == source_url for source in teacher.sources):
                db.add(
                    SourceEvidence(
                        teacher_id=teacher.id,
                        source_url=source_url,
                        source_type=item.get("source_type", "official"),
                        field_name="national_import",
                        quote=evidence_sentence,
                        trust_level=3,
                    )
                )
            skipped += int(not item.get("direction_keys"))

        db.commit()
        print(json.dumps({"imported": imported, "updated": updated, "without_directions": skipped}, ensure_ascii=False))


if __name__ == "__main__":
    main()
