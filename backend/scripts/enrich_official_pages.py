import html
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import Publication, ReviewStatus, Teacher  # noqa: E402


USER_AGENT = "TraCN local official-page enrichment/0.1"
MAX_PUBLICATIONS = 12
IMPORT_BATCH_DIR = ROOT.parent / "data" / "import_batches"

RESEARCH_HEADINGS = (
    "研究方向",
    "研究兴趣",
    "研究领域",
    "研究内容",
    "科研方向",
    "科研兴趣",
    "主要研究",
    "个人简介",
    "简介",
    "课题组简介",
    "research interests",
    "research areas",
    "research",
    "biography",
    "profile",
)

PUBLICATION_HEADINGS = (
    "publications",
    "selected publications",
    "representative publications",
    "recent publications",
    "发表论文",
    "代表论文",
    "代表性论文",
    "主要论文",
    "论文发表",
    "学术论文",
    "论著",
)

STOP_HEADINGS = (
    "联系方式",
    "contact",
    "招生",
    "teaching",
    "教学",
    "education",
    "工作经历",
    "experience",
    "奖励",
    "honors",
    "基金",
    "项目",
    "grants",
    "projects",
    "成员",
    "团队",
    "news",
)

NAVIGATION_TERMS = (
    "主任致辞",
    "历史沿革",
    "现任领导",
    "历任领导",
    "组织架构",
    "人才招聘",
    "学生风采",
    "联系我们",
    "院长寄语",
    "治理架构",
    "院系导航",
    "学术活动",
    "课程",
    "师资队伍",
    "search menu",
    "highlights research centers",
    "alumni council",
)

RESEARCH_CUES = (
    "研究",
    "方向",
    "兴趣",
    "机制",
    "建模",
    "神经",
    "脑",
    "计算",
    "research",
    "interest",
    "focus",
    "computational",
    "neural",
    "brain",
    "model",
)


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
        if tag in {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "section"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return html.unescape("".join(self.parts))


def normalize_lines(text: str) -> list[str]:
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    raw_lines = [line.strip(" \t-·•") for line in text.split("\n")]
    lines: list[str] = []
    for line in raw_lines:
        line = re.sub(r"\s+", " ", line).strip()
        if line and line not in lines[-3:]:
            lines.append(line)
    return lines


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    contexts = [ssl.create_default_context(), ssl._create_unverified_context()]
    last_error: Exception | None = None
    for context in contexts:
        try:
            with urllib.request.urlopen(request, timeout=18, context=context) as response:
                body = response.read()
                encoding = response.headers.get_content_charset() or "utf-8"
                markup = body.decode(encoding, errors="ignore")
                parser = TextExtractor()
                parser.feed(markup)
                return parser.text()
        except Exception as exc:  # pragma: no cover - network variability
            last_error = exc
    raise RuntimeError(str(last_error))


def is_heading(line: str) -> bool:
    compact = line.strip().lower().strip(":：")
    if len(compact) > 60:
        return False
    return any(token == compact or token in compact for token in (*RESEARCH_HEADINGS, *PUBLICATION_HEADINGS, *STOP_HEADINGS))


def collect_after_heading(lines: list[str], headings: Iterable[str], *, max_chars: int) -> str:
    lower_headings = tuple(item.lower() for item in headings)
    start_index = -1
    for index, line in enumerate(lines):
        lowered = line.lower().strip(":：")
        if any(heading == lowered or heading in lowered for heading in lower_headings):
            start_index = index + 1
            break
    if start_index == -1:
        return ""

    collected: list[str] = []
    for line in lines[start_index:]:
        lowered = line.lower().strip(":：")
        if collected and is_heading(line) and any(stop in lowered for stop in (*STOP_HEADINGS, *PUBLICATION_HEADINGS)):
            break
        if len(line) <= 2:
            continue
        collected.append(line)
        if len(" ".join(collected)) >= max_chars:
            break
    return clean_section(" ".join(collected), max_chars=max_chars)


def clean_section(text: str, *, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text).strip(" ;；")
    text = re.sub(r"(上一页|下一页|打印|关闭|分享|版权所有).*", "", text)
    return text[:max_chars].strip()


def is_noisy_text(text: str) -> bool:
    lowered = text.lower()
    navigation_hits = sum(1 for term in NAVIGATION_TERMS if term in lowered)
    if navigation_hits >= 2:
        return True
    if len(text) > 220 and navigation_hits >= 1 and not any(cue in lowered for cue in ("研究方向", "research interest")):
        return True
    if re.match(r"^\d+\.\s+[A-Z][A-Za-z .,'*-]+\(?(19|20)\d{2}", text):
        return True
    return False


def is_good_research_text(text: str) -> bool:
    lowered = text.lower()
    if len(text) < 40 or is_noisy_text(text):
        return False
    return any(cue in lowered for cue in RESEARCH_CUES)


def looks_like_publication(line: str) -> bool:
    lowered = line.lower()
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", line))
    has_journal_signal = any(
        token in lowered
        for token in (
            "nature",
            "science",
            "cell",
            "neuron",
            "pnas",
            "elife",
            "cerebral cortex",
            "journal",
            "frontiers",
            "neural",
            "brain",
            "neuroscience",
            "neuroimage",
            "proceedings",
            "ieee",
            "bioinformatics",
        )
    )
    has_title_shape = len(line) >= 35 and ("," in line or "." in line or "：" in line or ":" in line)
    biography_signal = any(
        token in lowered
        for token in (
            "学士",
            "硕士",
            "博士",
            "b. eng",
            "m. eng",
            "phd",
            "postdoc",
            "principle investigator",
            "principal investigator",
            "visiting scholar",
            "he received",
            "she received",
            "currently a professor",
            "made original contributions",
            "authored or co-authored",
            "优秀毕业生",
            "杂志编委",
            "期刊 contributing editor",
        )
    )
    return has_year and has_journal_signal and has_title_shape and not biography_signal


def extract_publications(lines: list[str]) -> list[dict[str, str | int | None]]:
    section = collect_after_heading(lines, PUBLICATION_HEADINGS, max_chars=7000)
    candidate_lines = normalize_lines(section) if section else []
    if not candidate_lines:
        candidate_lines = [line for line in lines if looks_like_publication(line)]

    publications: list[dict[str, str | int | None]] = []
    seen: set[str] = set()
    for line in candidate_lines:
        if not looks_like_publication(line):
            continue
        title = clean_section(line, max_chars=900)
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        year_match = re.search(r"\b(19|20)\d{2}\b", title)
        publications.append(
            {
                "title": title,
                "year": int(year_match.group(0)) if year_match else None,
            }
        )
        if len(publications) >= MAX_PUBLICATIONS:
            break
    return publications


def source_url_for_teacher(teacher: Teacher) -> str:
    return teacher.homepage_url or teacher.lab_url or (teacher.sources[0].source_url if teacher.sources else "")


def fallback_bios_from_batches() -> dict[tuple[str, str], str]:
    fallbacks: dict[tuple[str, str], str] = {}
    if not IMPORT_BATCH_DIR.exists():
        return fallbacks
    for path in IMPORT_BATCH_DIR.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload:
            bio = item.get("bio") or item.get("evidence_sentence") or ""
            if bio:
                fallbacks[(item["name"], item["institution"])] = bio
    return fallbacks


def fallback_bio_for_teacher(teacher: Teacher, batch_bios: dict[tuple[str, str], str]) -> str:
    batch_bio = batch_bios.get((teacher.name, teacher.institution), "")
    if batch_bio:
        return batch_bio
    for source in teacher.sources:
        if source.quote:
            return source.quote
    return teacher.bio or ""


def main() -> None:
    updated_bio = 0
    added_publications = 0
    removed_publications = 0
    repaired_bio = 0
    failed: list[dict[str, str]] = []
    batch_bios = fallback_bios_from_batches()

    with SessionLocal() as db:
        teachers = db.scalars(
            select(Teacher).where(Teacher.status == ReviewStatus.approved.value).order_by(Teacher.id)
        ).all()
        for teacher in teachers:
            if teacher.bio and is_noisy_text(teacher.bio):
                teacher.bio = fallback_bio_for_teacher(teacher, batch_bios)
                repaired_bio += 1

            for publication in list(teacher.publications):
                if publication.is_official_source and not looks_like_publication(publication.title):
                    db.delete(publication)
                    removed_publications += 1
            db.flush()

            url = source_url_for_teacher(teacher)
            if not url:
                failed.append({"name": teacher.name, "reason": "no official URL"})
                continue
            try:
                lines = normalize_lines(fetch_text(url))
                research_text = collect_after_heading(lines, RESEARCH_HEADINGS, max_chars=1600)
                if is_good_research_text(research_text) and len(research_text) > max(80, len(teacher.bio or "") + 20):
                    teacher.bio = research_text
                    updated_bio += 1

                existing_titles = {publication.title.casefold() for publication in teacher.publications}
                for item in extract_publications(lines):
                    title = str(item["title"])
                    if title.casefold() in existing_titles:
                        continue
                    db.add(
                        Publication(
                            teacher_id=teacher.id,
                            title=title,
                            year=item["year"],
                            source_url=url,
                            is_official_source=True,
                        )
                    )
                    existing_titles.add(title.casefold())
                    added_publications += 1
                db.commit()
            except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
                failed.append({"name": teacher.name, "reason": str(exc)[:180]})
                db.rollback()
            time.sleep(0.25)

    print(
        json.dumps(
            {
                "updated_bio": updated_bio,
                "repaired_bio": repaired_bio,
                "added_publications": added_publications,
                "removed_publications": removed_publications,
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
