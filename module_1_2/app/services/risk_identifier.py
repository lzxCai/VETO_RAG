"""
第二模块：核心风险条款识别与初步分级

输入：第一模块输出的结构化条款（至少包含 clause_id / clause_type / section_title / title / text）
输出：每条条款对应的风险识别结果（支持多风险命中）
"""

from typing import Any, Dict, List, Optional, Tuple
import re

from app.config.risk_rules import RISK_RULES


NO_RISK_LABEL = "无明显风险"


def normalize_text(text: Optional[str]) -> str:
    """标准化文本，便于关键词匹配。"""
    if not text:
        return ""
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", "", text)
    return text.strip()


def deduplicate_keep_order(items: List[str]) -> List[str]:
    """按出现顺序去重。"""
    seen = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def hit_keywords(text: str, keywords: List[str]) -> List[str]:
    """返回命中的关键词列表。"""
    hits: List[str] = []
    for keyword in keywords:
        if keyword and normalize_text(keyword) in text:
            hits.append(keyword)
    return deduplicate_keep_order(hits)


def check_combinations(text: str, combinations: List[List[str]]) -> bool:
    """
    任意组合命中：
    - combinations 中每个元素是一个关键词组合，组合内需全部命中
    - 只要任意一个组合满足即返回 True
    """
    if not combinations:
        return True
    for combo in combinations:
        if combo and all(normalize_text(token) in text for token in combo):
            return True
    return False


def clause_type_related(clause_type: str, related_clause_types: List[str]) -> bool:
    """
    clause_type 关联判断：
    - 允许包含匹配，增强兼容性
    - 注意：仅作为加分项，不可单独触发风险
    """
    if not clause_type:
        return False
    normalized_clause_type = normalize_text(clause_type)
    for related in related_clause_types:
        normalized_related = normalize_text(related)
        if normalized_related and normalized_related in normalized_clause_type:
            return True
    return False


def hit_keyword_groups(
    combined_text: str, keyword_groups: Dict[str, List[str]]
) -> Tuple[Dict[str, List[str]], bool]:
    """
    命中分组关键词。
    返回：
    - group_hits: {group_name: [hit_keywords]}
    - all_groups_hit: 所有组是否都至少命中 1 个
    """
    group_hits: Dict[str, List[str]] = {}
    all_groups_hit = True

    for group_name, group_keywords in keyword_groups.items():
        hits = hit_keywords(combined_text, group_keywords)
        group_hits[group_name] = hits
        if not hits:
            all_groups_hit = False

    return group_hits, all_groups_hit


def compute_confidence_score(
    clause_related: bool,
    keyword_hits: List[str],
    strong_keyword_hits: List[str],
    required_groups_ok: bool,
) -> int:
    """
    置信分（精度优先）：
    - strong: 高权重
    - keyword: 次高
    - clause_type_related: 仅加分，不可单独触发
    - required_groups_ok: 对结构性规则（如培训服务期）加分
    """
    score = 0
    score += len(strong_keyword_hits) * 6
    score += len(keyword_hits) * 2
    if clause_related:
        score += 1
    if required_groups_ok:
        score += 1
    return score


def evaluate_preliminary_level(
    clause_related: bool,
    keyword_hits: List[str],
    strong_keyword_hits: List[str],
    strategy: Dict[str, Any],
    confidence_score: int,
) -> str:
    """根据命中证据评估初步风险等级。"""
    # clause_type_related 不能单独触发：至少要有关键词命中
    if not keyword_hits and not strong_keyword_hits:
        return NO_RISK_LABEL

    if strategy.get("high_if_strong_keyword_hit", True) and strong_keyword_hits:
        return "高"

    medium_threshold = int(strategy.get("medium_if_keyword_hits_ge", 3))
    low_threshold = int(strategy.get("low_if_keyword_hits_ge", 2))

    # 精度优先：中风险要求更强证据
    if len(keyword_hits) >= medium_threshold or confidence_score >= 6:
        return "中"

    # 低风险也要求至少 2 个关键词，或“条款相关 + 至少 1 个关键词”
    if len(keyword_hits) >= low_threshold:
        return "低"
    if clause_related and len(keyword_hits) >= 1:
        return "低"

    return NO_RISK_LABEL


def rule_preconditions_pass(
    rule: Dict[str, Any],
    combined_text: str,
    keyword_hits: List[str],
    strong_keyword_hits: List[str],
    group_hits: Dict[str, List[str]],
) -> Tuple[bool, Dict[str, Any]]:
    """
    校验规则前置条件（可选）：
    - require_strong_keyword: 必须命中强关键词
    - require_keyword_groups_all: 指定分组都必须命中
    - required_any_keywords: 至少命中 1 个关键语义词
    - required_combinations_any: 至少命中 1 个关键词组合
    - blocked_phrases: 命中排除语境时默认过滤（可被 strong 覆盖）
    """
    require_strong_keyword = bool(rule.get("require_strong_keyword", False))
    required_groups = rule.get("require_keyword_groups_all", [])
    required_any_keywords = rule.get("required_any_keywords", [])
    required_combinations_any = rule.get("required_combinations_any", [])
    blocked_phrases = rule.get("blocked_phrases", [])
    blocked_context_max_keyword_hits_to_filter = int(
        rule.get("blocked_context_max_keyword_hits_to_filter", 2)
    )
    allow_strong_override_on_blocked = bool(
        rule.get("allow_strong_override_on_blocked", True)
    )

    required_any_keywords_hits = hit_keywords(combined_text, required_any_keywords)
    required_any_keywords_ok = (
        True if not required_any_keywords else bool(required_any_keywords_hits)
    )
    required_combinations_ok = check_combinations(combined_text, required_combinations_any)
    blocked_phrase_hits = hit_keywords(combined_text, blocked_phrases)

    blocked_context_ok = True
    if blocked_phrase_hits:
        weak_signal = len(keyword_hits) <= blocked_context_max_keyword_hits_to_filter
        if weak_signal and not (allow_strong_override_on_blocked and strong_keyword_hits):
            blocked_context_ok = False

    checks = {
        "require_strong_keyword": require_strong_keyword,
        "strong_keyword_ok": (not require_strong_keyword) or bool(strong_keyword_hits),
        "required_groups": required_groups,
        "required_groups_ok": True,
        "required_any_keywords": required_any_keywords,
        "required_any_keywords_hits": required_any_keywords_hits,
        "required_any_keywords_ok": required_any_keywords_ok,
        "required_combinations_any": required_combinations_any,
        "required_combinations_ok": required_combinations_ok,
        "blocked_phrase_hits": blocked_phrase_hits,
        "blocked_context_ok": blocked_context_ok,
    }

    if required_groups:
        checks["required_groups_ok"] = all(bool(group_hits.get(g, [])) for g in required_groups)

    passed = (
        checks["strong_keyword_ok"]
        and checks["required_groups_ok"]
        and required_any_keywords_ok
        and required_combinations_ok
        and blocked_context_ok
    )

    # 再次收紧：至少要有关键词命中
    if not keyword_hits and not strong_keyword_hits:
        passed = False

    return passed, checks


def is_key_risk_record(item: Dict[str, Any]) -> bool:
    """
    key_risk_clauses 收紧规则（满足其一）：
    1) risk_level_preliminary 为中或高
    2) 命中 strong keyword
    3) 命中 required_combinations
    4) clause_type 高度相关且 keyword_hit_count >= 2
    """
    if item.get("risk_type") == NO_RISK_LABEL:
        return False

    level = item.get("risk_level_preliminary", NO_RISK_LABEL)
    hits = item.get("rule_hits", {})
    checks = hits.get("precondition_checks", {})

    if level in {"中", "高"}:
        return True
    if hits.get("strong_keyword_hit_count", 0) > 0:
        return True
    if checks.get("required_combinations_any") and checks.get("required_combinations_ok"):
        return True
    if hits.get("clause_type_related") and hits.get("keyword_hit_count", 0) >= 2:
        return True

    return False


def build_no_risk_record(source: Dict[str, Any]) -> Dict[str, Any]:
    """构建统一的“无明显风险”结果，兼容正文/附件。"""
    clause_id = source.get("clause_id") or source.get("attachment_id", "")
    clause_type = source.get("clause_type") or source.get("attachment_type", "")
    return {
        "clause_id": clause_id,
        "clause_type": clause_type,
        "risk_type": NO_RISK_LABEL,
        "risk_level_preliminary": NO_RISK_LABEL,
        "trigger_phrases": [],
        "rule_hits": {
            "clause_type_related": False,
            "keyword_hits": [],
            "strong_keyword_hits": [],
            "keyword_hit_count": 0,
            "strong_keyword_hit_count": 0,
            "group_hits": {},
            "precondition_checks": {
                "require_strong_keyword": False,
                "strong_keyword_ok": False,
                "required_groups": [],
                "required_groups_ok": False,
                "required_any_keywords": [],
                "required_any_keywords_hits": [],
                "required_any_keywords_ok": False,
                "required_combinations_any": [],
                "required_combinations_ok": False,
                "blocked_phrase_hits": [],
                "blocked_context_ok": False,
            },
        },
        "needs_attention": False,
    }


def select_top_clause_risks(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    同一条 clause 的去噪逻辑：
    - 优先保留高/中风险
    - 最多保留 2 条
    - 若只有低风险，最多保留 1 条
    """
    if not candidates:
        return []

    level_rank = {"高": 3, "中": 2, "低": 1, NO_RISK_LABEL: 0}

    sorted_items = sorted(
        candidates,
        key=lambda x: (
            level_rank.get(x.get("risk_level_preliminary", NO_RISK_LABEL), 0),
            x.get("confidence_score", 0),
            x.get("rule_hits", {}).get("strong_keyword_hit_count", 0),
            x.get("rule_hits", {}).get("keyword_hit_count", 0),
        ),
        reverse=True,
    )

    high_or_medium = [i for i in sorted_items if i.get("risk_level_preliminary") in {"高", "中"}]
    if high_or_medium:
        return high_or_medium[:2]

    low_only = [i for i in sorted_items if i.get("risk_level_preliminary") == "低"]
    if low_only:
        return low_only[:1]

    return []


def identify_risks_for_clause(clause: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    单条条款风险识别（可多标签）。

    返回结构（每个风险一条）：
    {
      clause_id,
      clause_type,
      risk_type,
      risk_level_preliminary,
      trigger_phrases,
      rule_hits,
      needs_attention
    }
    """
    clause_id = clause.get("clause_id", "")
    clause_type = clause.get("clause_type", "")
    section_title = clause.get("section_title", "") or ""
    section = clause.get("section", "") or ""
    title = clause.get("title", "") or ""
    text = clause.get("text", "") or ""

    combined_text = normalize_text(" ".join([section_title, section, title, text]))

    candidates: List[Dict[str, Any]] = []

    for rule in RISK_RULES:
        risk_type = rule["risk_type"]
        keywords = rule.get("keywords", [])
        strong_keywords = rule.get("strong_keywords", [])
        related_clause_types = rule.get("related_clause_types", [])
        strategy = rule.get("preliminary_level_strategy", {})
        keyword_groups = rule.get("keyword_groups", {})

        clause_related = clause_type_related(clause_type, related_clause_types)
        keyword_hits = hit_keywords(combined_text, keywords)
        strong_keyword_hits = hit_keywords(combined_text, strong_keywords)
        group_hits, all_groups_hit = hit_keyword_groups(combined_text, keyword_groups) if keyword_groups else ({}, True)

        precondition_passed, precondition_checks = rule_preconditions_pass(
            rule=rule,
            combined_text=combined_text,
            keyword_hits=keyword_hits,
            strong_keyword_hits=strong_keyword_hits,
            group_hits=group_hits,
        )
        if not precondition_passed:
            continue

        confidence_score = compute_confidence_score(
            clause_related=clause_related,
            keyword_hits=keyword_hits,
            strong_keyword_hits=strong_keyword_hits,
            required_groups_ok=all_groups_hit,
        )
        level = evaluate_preliminary_level(
            clause_related=clause_related,
            keyword_hits=keyword_hits,
            strong_keyword_hits=strong_keyword_hits,
            strategy=strategy,
            confidence_score=confidence_score,
        )
        if level == NO_RISK_LABEL:
            continue

        trigger_phrases = deduplicate_keep_order(strong_keyword_hits + keyword_hits)
        trigger_phrases = trigger_phrases[:8]

        rule_hits = {
            "clause_type_related": clause_related,
            "keyword_hits": keyword_hits,
            "strong_keyword_hits": strong_keyword_hits,
            "keyword_hit_count": len(keyword_hits),
            "strong_keyword_hit_count": len(strong_keyword_hits),
            "group_hits": group_hits,
            "precondition_checks": precondition_checks,
        }

        candidates.append(
            {
                "clause_id": clause_id,
                "clause_type": clause_type,
                "risk_type": risk_type,
                "risk_level_preliminary": level,
                "trigger_phrases": trigger_phrases,
                "rule_hits": rule_hits,
                "needs_attention": level in {"高", "中"},
                "confidence_score": confidence_score,  # 去噪排序用，最终返回前会移除
            }
        )

    selected = select_top_clause_risks(candidates)
    for item in selected:
        item.pop("confidence_score", None)

    if selected:
        return selected

    return [build_no_risk_record(clause)]


def identify_risks_for_clauses(clauses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    批量识别（扁平结果）：
    - 一条 clause 可对应多条风险记录（去噪后最多 1~2 条）
    - 无风险条款会有一条“无明显风险”记录
    """
    results: List[Dict[str, Any]] = []
    for clause in clauses:
        results.extend(identify_risks_for_clause(clause))
    return results


def identify_risks_for_attachments(attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    附件识别：
    - 保留输出结构
    - 每个附件优先保留高价值风险；若无有效风险，保留一条“无明显风险”
    """
    results: List[Dict[str, Any]] = []
    for attachment in attachments:
        normalized_attachment = attachment.copy()
        if not normalized_attachment.get("clause_id"):
            normalized_attachment["clause_id"] = attachment.get("attachment_id", "")
        if not normalized_attachment.get("clause_type"):
            normalized_attachment["clause_type"] = attachment.get(
                "attachment_type", "附件"
            )

        att_risks = identify_risks_for_clause(normalized_attachment)
        high_value_risks = [item for item in att_risks if is_key_risk_record(item)]

        if high_value_risks:
            results.extend(high_value_risks[:2])
        else:
            results.append(build_no_risk_record(normalized_attachment))

    return results


def summarize_risk_results(flat_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """生成简要汇总，便于上层模块消费。"""
    summary = {
        "total_records": len(flat_results),
        "attention_records": 0,
        "high_risk_records": 0,
        "risk_type_counts": {},
    }

    for item in flat_results:
        risk_type = item.get("risk_type", NO_RISK_LABEL)
        level = item.get("risk_level_preliminary", NO_RISK_LABEL)
        needs_attention = bool(item.get("needs_attention", False))

        summary["risk_type_counts"][risk_type] = summary["risk_type_counts"].get(risk_type, 0) + 1

        if needs_attention:
            summary["attention_records"] += 1
        if level == "高":
            summary["high_risk_records"] += 1

    return summary


def identify_contract_risks(classified_contract: Dict[str, Any]) -> Dict[str, Any]:
    """
    合同级入口函数。

    输入（第一模块输出）：
    {
      "main_body": [...],
      "attachments": [...]
    }

    输出（第二模块 V1）：
    {
      "main_body_risks": [...],
      "attachment_risks": [...],
      "key_risk_clauses": [...],
      "summary": {...}
    }
    """
    main_body = classified_contract.get("main_body", [])
    attachments = classified_contract.get("attachments", [])

    main_body_risks = identify_risks_for_clauses(main_body)
    attachment_risks = identify_risks_for_attachments(attachments)

    all_risks = main_body_risks + attachment_risks

    key_risk_clauses = [
        item
        for item in all_risks
        if is_key_risk_record(item)
    ]

    summary = summarize_risk_results(all_risks)
    summary["key_risk_clause_count"] = len(key_risk_clauses)

    return {
        "main_body_risks": main_body_risks,
        "attachment_risks": attachment_risks,
        "key_risk_clauses": key_risk_clauses,
        "summary": summary,
    }
