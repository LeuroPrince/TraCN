from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ResearchDirection


DEFAULT_DIRECTIONS = [
    (
        "network_dynamics_modeling",
        "神经网络动力学与建模",
        4.0,
        "神经系统动力学、计算建模、网络机制、全脑或局部神经网络模型。",
    ),
    (
        "neural_representation",
        "神经信息表征",
        3.5,
        "感觉、认知、行为相关的神经编码、信息表征与表征学习。",
    ),
    (
        "brain_inspired_intelligence",
        "类脑智能",
        3.0,
        "类脑计算、神经启发智能；若明确解释生物智能机制，可在匹配证据中加权为 3.5。",
    ),
    (
        "neuroimaging",
        "神经成像",
        2.0,
        "光学成像、fMRI、电生理等；若涉及机制或理论建模，可在匹配证据中加权为 3。",
    ),
    (
        "ai_for_neuroscience",
        "AI for neuroscience",
        3.5,
        "使用机器学习、大模型或统计 AI 方法分析、建模或解释神经科学数据。",
    ),
]


def seed_default_directions(db: Session) -> None:
    existing = {row.key for row in db.scalars(select(ResearchDirection)).all()}
    for order, (key, name, weight, description) in enumerate(DEFAULT_DIRECTIONS):
        if key in existing:
            continue
        db.add(
            ResearchDirection(
                key=key,
                name=name,
                weight=weight,
                description=description,
                sort_order=order,
            )
        )
    db.commit()
