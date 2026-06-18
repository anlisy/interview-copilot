from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import List, Optional


class QType(str, Enum):
    RESUME_PROJECT = "项目追问"
    RESUME_INTERNSHIP = "实习追问"
    JAVA_BASIC = "Java八股"
    AI_BASIC = "AI应用八股"
    CODING = "编程题"
    BEHAVIOR = "行为问题"


@dataclass
class Score:
    accuracy: int = 0       # 准确性 1-5
    completeness: int = 0   # 完整性 1-5
    depth: int = 0          # 技术深度 1-5
    clarity: int = 0        # 表达清晰度 1-5
    total: float = 0.0      # 总分
    comment: str = ""       # 评语+改进建议


@dataclass
class QARecord:
    order: int
    q_type: str
    question: str
    user_answer: str = ""
    score: Optional[Score] = None


@dataclass
class InterviewConfig:
    total_questions: int = 8
    type_ratio: dict = field(default_factory=lambda: {
        "RESUME_PROJECT": 30,
        "RESUME_INTERNSHIP": 15,
        "JAVA_BASIC": 20,
        "AI_BASIC": 20,
        "CODING": 10,
        "BEHAVIOR": 5,
    })
    max_followup: int = 0   # L1=0 不追问，L2 再开


@dataclass
class InterviewSession:
    session_id: str
    company: str
    position: str
    resume_name: str
    resume_content: str
    jd_content: str
    config: InterviewConfig = field(default_factory=InterviewConfig)
    qa_list: List[QARecord] = field(default_factory=list)
    status: str = "进行中"
    overall_score: float = 0.0
    review_report: str = ""
    created_at: Optional[str] = None
    finished_at: Optional[str] = None

    @property
    def title(self) -> str:
        return f"{self.company}-{self.position}-{self.resume_name}"
