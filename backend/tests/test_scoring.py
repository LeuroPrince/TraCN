from app.models import ResearchDirection, Teacher, TeacherDirectionMatch
from app.scoring import sort_teachers, sort_teachers_by_institution, summarize_teacher_score


def make_teacher(
    name: str,
    latitude: float,
    matches: list[tuple[ResearchDirection, str]],
    institution: str | None = None,
) -> Teacher:
    teacher = Teacher(name=name, institution=institution or f"{name} University", latitude=latitude, status="approved")
    teacher.direction_matches = [
        TeacherDirectionMatch(id=index + 1, direction=direction, evidence_sentence=evidence)
        for index, (direction, evidence) in enumerate(matches)
    ]
    return teacher


def test_score_accumulates_multiple_direction_weights() -> None:
    dynamics = ResearchDirection(id=1, key="network_dynamics_modeling", name="动力学", weight=4)
    ai = ResearchDirection(id=2, key="ai_for_neuroscience", name="AI for neuroscience", weight=3.5)
    teacher = make_teacher("A", 39.9, [(dynamics, "动力学建模"), (ai, "AI 分析神经数据")])

    score = summarize_teacher_score(teacher)

    assert score.match_score == 7.5
    assert score.primary_direction_key == "network_dynamics_modeling"


def test_primary_category_uses_highest_weight_direction() -> None:
    imaging = ResearchDirection(id=1, key="neuroimaging", name="神经成像", weight=2)
    brain = ResearchDirection(id=2, key="brain_inspired_intelligence", name="类脑智能", weight=3.5)
    teacher = make_teacher("B", 31.2, [(imaging, "成像"), (brain, "解释生物智能机制")])

    score = summarize_teacher_score(teacher)

    assert score.primary_direction_key == "brain_inspired_intelligence"


def test_sort_uses_score_then_north_to_south() -> None:
    direction = ResearchDirection(id=1, key="network_dynamics_modeling", name="动力学", weight=4)
    north = make_teacher("North", 40.0, [(direction, "建模")])
    south = make_teacher("South", 30.0, [(direction, "建模")])

    assert [teacher.name for teacher in sort_teachers([south, north])] == ["North", "South"]


def test_category_sort_groups_by_institution_before_score() -> None:
    high = ResearchDirection(id=1, key="network_dynamics_modeling", name="Modeling", weight=4)
    low = ResearchDirection(id=2, key="neural_representation", name="Representation", weight=3)
    zeta = make_teacher("Zeta One", 31.0, [(high, "modeling"), (low, "representation")], "Zeta University")
    alpha_b = make_teacher("Beta", 39.0, [(low, "representation")], "Alpha University")
    alpha_a = make_teacher("Alpha", 39.0, [(low, "representation")], "Alpha University")

    sorted_teachers = sort_teachers_by_institution([zeta, alpha_b, alpha_a])

    assert [teacher.name for teacher in sorted_teachers] == ["Alpha", "Beta", "Zeta One"]
