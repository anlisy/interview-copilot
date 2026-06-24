"""面试状态机：定义一场面试的生命周期状态与合法流转"""
from enum import Enum


class InterviewState(str, Enum):
    INIT = "初始化"           # 刚创建，未出题
    GENERATING = "出题中"     # 面试官 Agent 工作
    ASKING = "提问中"         # 等用户回答
    SCORING = "评分中"        # 评分 Agent 工作
    REVIEWING = "复盘中"      # 复盘 Agent 工作
    FINISHED = "已完成"


# 合法状态流转表（Supervisor 据此校验，防止乱跳）
TRANSITIONS = {
    InterviewState.INIT:       [InterviewState.GENERATING],
    InterviewState.GENERATING: [InterviewState.ASKING],
    InterviewState.ASKING:     [InterviewState.SCORING],
    InterviewState.SCORING:    [InterviewState.ASKING, InterviewState.REVIEWING],
    InterviewState.REVIEWING:  [InterviewState.FINISHED],
    InterviewState.FINISHED:   [],
}


def can_transit(src: InterviewState, dst: InterviewState) -> bool:
    return dst in TRANSITIONS.get(src, [])
