"""
风险类型定向法律依据检索规则。

目标：
1. 将风险类型与更贴近的法律主题词绑定，提升 LightRAG 检索 precision。
2. 尽量过滤目录、章节标题、明显无关的高频法条。
3. 仅作为检索层配置，不改变模块二的风险识别逻辑。
"""

from __future__ import annotations

from typing import Dict, List


DEFAULT_TOPICS = {
    "include_any": [],
    "prefer_any": [],
    "exclude_any": ["目录", "第八章", "第七章", "总则", "附则"],
    "fallback_keywords": [],
}


LEGAL_RETRIEVAL_RULES: Dict[str, Dict[str, List[str]]] = {
    "试用期风险": {
        "include_any": ["试用期", "劳动合同", "期限"],
        "prefer_any": ["试用期", "最长不得超过六个月", "劳动合同可以约定试用期"],
        "exclude_any": ["加班工资", "职业培训", "社会保险", "竞业限制"],
        "fallback_keywords": ["试用期", "试用期上限", "劳动合同期限"],
    },
    "试用期工资风险": {
        "include_any": ["试用期", "工资", "劳动报酬"],
        "prefer_any": ["试用期工资", "不得低于", "最低工资", "劳动报酬"],
        "exclude_any": ["加班工资", "竞业限制", "职业培训", "社会保险"],
        "fallback_keywords": ["试用期工资", "劳动报酬", "最低工资"],
    },
    "薪酬支付风险": {
        "include_any": ["工资", "劳动报酬", "支付"],
        "prefer_any": ["劳动报酬", "工资支付", "加班工资", "延长工作时间", "休息日", "法定节假日"],
        "exclude_any": ["试用期", "社会保险", "竞业限制", "职业培训"],
        "fallback_keywords": ["劳动报酬", "工资支付", "加班工资"],
    },
    "社保公积金风险": {
        "include_any": ["社会保险", "保险费", "缴纳"],
        "prefer_any": ["社会保险", "缴纳社会保险费", "依法参加社会保险"],
        "exclude_any": ["加班工资", "试用期", "竞业限制", "职业培训"],
        "fallback_keywords": ["社会保险", "保险费", "缴纳"],
    },
    "竞业限制风险": {
        "include_any": ["商业秘密", "竞业限制", "保密"],
        "prefer_any": ["商业秘密", "竞业限制", "保密", "知识产权"],
        "exclude_any": ["加班工资", "社会保险", "职业培训", "试用期"],
        "fallback_keywords": ["商业秘密", "竞业限制", "保密"],
    },
    "培训服务期风险": {
        "include_any": ["培训", "服务期", "协议"],
        "prefer_any": ["专项培训", "服务期", "职业培训", "培训费用", "违约金"],
        "exclude_any": ["加班工资", "试用期", "社会保险", "竞业限制", "第八章"],
        "fallback_keywords": ["培训", "服务期", "职业培训"],
    },
    "单方调岗调薪风险": {
        "include_any": ["岗位", "工资", "劳动合同"],
        "prefer_any": ["劳动报酬", "工作内容", "协商一致", "变更劳动合同", "工资待遇"],
        "exclude_any": ["加班工资", "社会保险", "职业培训"],
        "fallback_keywords": ["工作内容", "劳动报酬", "变更劳动合同"],
    },
}


def get_legal_retrieval_rule(risk_type: str) -> Dict[str, List[str]]:
    rule = LEGAL_RETRIEVAL_RULES.get(risk_type, {})
    merged = {key: list(value) for key, value in DEFAULT_TOPICS.items()}
    for key, value in rule.items():
        merged[key] = list(value)
    return merged
