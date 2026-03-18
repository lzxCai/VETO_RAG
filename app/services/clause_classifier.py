import re
from typing import Dict, List, Optional


# -----------------------------
# 1. 条款类型定义
# -----------------------------
CLAUSE_TYPES = [
    "合同期限",
    "工作内容和工作地点",
    "工作时间和休息休假",
    "劳动报酬",
    "社会保险和福利待遇",
    "职业培训和劳动保护",
    "劳动合同变更/解除/终止",
    "保密义务/竞业限制",
    "培训服务期",
    "劳动争议处理",
    "其他约定",
    "其他"
]


# -----------------------------
# 2. section_title 映射规则
# 优先级最高
# -----------------------------
SECTION_TITLE_MAPPING = {
    "一、劳动合同期限": "合同期限",
    "二、工作内容和工作地点": "工作内容和工作地点",
    "三、工作时间和休息休假": "工作时间和休息休假",
    "四、劳动报酬": "劳动报酬",
    "五、社会保险和福利待遇": "社会保险和福利待遇",
    "六、职业培训和劳动保护": "职业培训和劳动保护",
    "七、劳动合同的变更、解除、终止": "劳动合同变更/解除/终止",
    "八、双方约定事项": "其他约定",
    "九、劳动争议处理": "劳动争议处理",
    "十、其他": "其他"
}


# -----------------------------
# 3. section 编号映射（模板型合同兜底）
# 针对你当前的人社部模板非常有效
# -----------------------------
SECTION_NUMBER_MAPPING = {
    "第一条": "合同期限",
    "第二条": "工作内容和工作地点",
    "第三条": "工作时间和休息休假",
    "第四条": "工作时间和休息休假",
    "第五条": "工作时间和休息休假",
    "第六条": "劳动报酬",
    "第七条": "劳动报酬",
    "第八条": "劳动报酬",
    "第九条": "社会保险和福利待遇",
    "第十条": "社会保险和福利待遇",
    "第十一条": "社会保险和福利待遇",
    "第十二条": "职业培训和劳动保护",
    "第十三条": "职业培训和劳动保护",
    "第十四条": "职业培训和劳动保护",
    "第十五条": "劳动合同变更/解除/终止",
    "第十六条": "劳动合同变更/解除/终止",
    "第十七条": "劳动合同变更/解除/终止",
    "第十八条": "劳动合同变更/解除/终止",
    "第十九条": "保密义务/竞业限制",
    "第二十条": "培训服务期",
    "第二十一条": "其他约定",
    "第二十二条": "劳动争议处理",
    "第二十三条": "其他",
    "第二十四条": "其他",
    "第二十五条": "其他",
}


# -----------------------------
# 4. 关键词规则
# 如果 section_title 不准或者未来换合同模板时，
# 可以靠关键词兜底
# -----------------------------
KEYWORD_RULES = {
    "合同期限": [
        "劳动合同期限", "固定期限", "无固定期限",
        "完成一定工作任务", "用工之日起", "合同期限"
    ],
    "工作内容和工作地点": [
        "工作岗位", "岗位职责", "工作地点", "工作内容"
    ],
    "工作时间和休息休假": [
        "工时制度", "标准工时", "综合计算工时",
        "不定时工作制", "加班", "补休",
        "休息休假", "法定节假日", "带薪年休假", "婚丧假", "产假"
    ],
    "劳动报酬": [
        "劳动报酬", "工资", "薪酬", "绩效工资",
        "计件工资", "月工资", "试用期期间的工资",
        "代扣代缴", "工资待遇"
    ],
    "社会保险和福利待遇": [
        "社会保险", "社保", "福利待遇", "工伤",
        "职业病", "患病", "非因工负伤", "社会保险费"
    ],
    "职业培训和劳动保护": [
        "培训", "职业技能", "劳动保护", "劳动安全",
        "卫生", "安全操作规程", "职业健康检查",
        "女职工", "未成年工", "职业危害"
    ],
    "劳动合同变更/解除/终止": [
        "变更劳动合同", "解除", "终止", "工作交接",
        "经济补偿", "档案", "社会保险关系转移"
    ],
    "保密义务/竞业限制": [
        "商业秘密", "保密", "竞业限制",
        "知识产权相关", "保守商业秘密协议", "竞业限制协议"
    ],
    "培训服务期": [
        "服务期", "专业技术培训", "签订协议", "明确双方权利义务"
    ],
    "劳动争议处理": [
        "劳动争议", "协商", "调解", "仲裁", "人民法院", "提起诉讼"
    ],
    "其他约定": [
        "双方约定的其它事项", "双方约定事项", "其它事项"
    ],
}


def normalize_text(text: Optional[str]) -> str:
    """
    标准化文本，便于匹配
    """
    if not text:
        return ""
    text = re.sub(r"\s+", "", text)
    return text.strip()


def keyword_score(text: str, keywords: List[str]) -> int:
    """
    简单关键词计分
    """
    score = 0
    for kw in keywords:
        if kw in text:
            score += 1
    return score


def classify_by_section_title(section_title: Optional[str]) -> Optional[str]:
    """
    按章节标题分类，优先级最高
    """
    if not section_title:
        return None

    section_title = section_title.strip()
    return SECTION_TITLE_MAPPING.get(section_title)


def classify_by_section(section: Optional[str]) -> Optional[str]:
    """
    按第X条编号分类，适合当前模板兜底
    """
    if not section:
        return None

    section = section.strip()
    return SECTION_NUMBER_MAPPING.get(section)


def classify_by_keywords(title: str, text: str) -> Optional[str]:
    """
    按关键词分类
    """
    combined = normalize_text(f"{title} {text}")

    best_type = None
    best_score = 0

    for clause_type, keywords in KEYWORD_RULES.items():
        score = keyword_score(combined, keywords)
        if score > best_score:
            best_score = score
            best_type = clause_type

    # 至少命中 1 个关键词才返回
    if best_score > 0:
        return best_type

    return None


def classify_clause(clause: Dict) -> str:
    """
    单条条款分类逻辑

    优先级：
    1. section_title
    2. section（第X条编号）
    3. keywords
    4. 其他
    """
    section_title = clause.get("section_title")
    section = clause.get("section")
    title = clause.get("title", "")
    text = clause.get("text", "")

    # 1. section_title 优先
    result = classify_by_section_title(section_title)
    if result:
        # 对“八、双方约定事项”做细分修正
        if result == "其他约定":
            combined = normalize_text(f"{title} {text}")
            if "竞业限制" in combined or "商业秘密" in combined:
                return "保密义务/竞业限制"
            if "培训" in combined or "服务期" in combined:
                return "培训服务期"
        return result

    # 2. section 编号兜底
    result = classify_by_section(section)
    if result:
        return result

    # 3. 关键词兜底
    result = classify_by_keywords(title, text)
    if result:
        return result

    # 4. 默认
    return "其他"


def classify_clauses(clauses: List[Dict]) -> List[Dict]:
    """
    批量分类
    返回带 clause_type 的条款列表
    """
    results = []

    for clause in clauses:
        clause_type = classify_clause(clause)

        new_clause = clause.copy()
        new_clause["clause_type"] = clause_type
        results.append(new_clause)

    return results


def classify_attachments(attachments: List[Dict]) -> List[Dict]:
    """
    附件分类
    """
    results = []

    for att in attachments:
        title = normalize_text(att.get("title", ""))
        text = normalize_text(att.get("text", ""))

        attachment_type = "附件"

        if "续订劳动合同" in title or "续订劳动合同" in text:
            attachment_type = "续订劳动合同附件"
        elif "变更劳动合同" in title or "变更劳动合同" in text:
            attachment_type = "变更劳动合同附件"

        new_att = att.copy()
        new_att["attachment_type"] = attachment_type
        results.append(new_att)

    return results


def classify_contract_parts(split_result: Dict) -> Dict:
    """
    对 split_contract 的结果整体分类
    输入：
    {
        "main_body": [...],
        "attachments": [...]
    }

    输出：
    {
        "main_body": [...带 clause_type],
        "attachments": [...带 attachment_type]
    }
    """
    main_body = split_result.get("main_body", [])
    attachments = split_result.get("attachments", [])

    return {
        "main_body": classify_clauses(main_body),
        "attachments": classify_attachments(attachments)
    }