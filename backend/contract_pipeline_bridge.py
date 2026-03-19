"""
将项目内 RAG 合同审查流水线（report_context）转换为前端卷宗解构页所需的数据结构。

前端约定字段见 `VETO web/legalhero/veto.final(3).html` 中 `renderAnalysis`（与交付 PDF 板块对齐）：
- 报告头：reportTitle、reportSubtitle、contractSource、generatedAtCn
- coverInfo：封面信息（报告名称、审查对象、审查范围、风险分布等）
- executiveSummary：摘要正文
- riskOverviewRows：风险总览表（条款编号、所属章节、风险类型、风险等级、法律依据状态）
- clauses：逐条风险分析（条款内容 / 法律依据 / 风险说明 / 修改建议 等）
- conclusionBody、signingSuggestions、disclaimer：结论与说明
- 另保留 overview、summary、status 供仪表盘与兼容使用
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

# 保证可从 backend 包内导入时找到项目根下的 app/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


RISK_SEVERITY: Dict[str, str] = {
    "竞业限制风险": "critical",
    "社保公积金风险": "critical",
    "培训服务期风险": "critical",
    "薪酬支付风险": "warning",
    "试用期风险": "warning",
    "试用期工资风险": "warning",
    "单方调岗调薪风险": "warning",
    "无明显风险": "safe",
}

# 与交付版 PDF 中「修改建议」风格一致的类型化提示（无 LLM 时的结构化占位）
REVISION_BY_RISK_TYPE: Dict[str, str] = {
    "试用期风险": "明确试用期起算点与期限上限符合《劳动合同法》第十九条，并写明试用期工资不低于转正工资80%及当地最低工资标准。",
    "试用期工资风险": "写明试用期工资数额或计发规则，并确保不低于转正工资80%与当地最低工资标准（《劳动合同法》第二十条）。",
    "薪酬支付风险": "补充正常工作时间工资标准、加班工资计算基数与支付规则，并与《劳动法》第四十四条等强制性规定对齐。",
    "单方调岗调薪风险": "调岗调薪应限定合法事由并保留协商与书面变更程序，避免概括授权用人单位单方决定。",
    "社保公积金风险": "将社会保险与住房公积金（如当地强制）一并纳入书面约定，明确缴费义务与代扣代缴安排。",
    "竞业限制风险": "若约定竞业限制，应明确范围、期限（不超过二年）、地域及经济补偿标准，必要时另行签订专项协议。",
    "培训服务期风险": "对专项培训费用、服务期年限及违约金上限作出明确约定，并确保违约金不超过实际培训费用（建议引用《劳动合同法》第二十二条并由律师复核）。",
    "未分类": "建议与用人单位协商修订表述，并在签署前由专业律师复核。",
}

RISK_EXPLAIN_PREFIX: Dict[str, str] = {
    "试用期风险": "试用期条款易在期限上限、起算日与工资底线方面产生争议。",
    "试用期工资风险": "试用期工资低于法定底线或约定不明时，易引发工资差额与违法解除争议。",
    "薪酬支付风险": "工资结构、加班费基数与调整机制表述不清时，易引发劳动报酬争议。",
    "单方调岗调薪风险": "概括授权单方调整岗位或薪酬时，劳动者对劳动条件变动的预期与救济空间可能被压缩。",
    "社保公积金风险": "参保义务与公积金缴存若未完整覆盖，可能产生补缴与行政处罚风险。",
    "竞业限制风险": "竞业限制如缺少补偿与范围要素，可能导致条款效力争议。",
    "培训服务期风险": "服务期与违约金未与培训费用挂钩时，可能被认定无效或难以执行。",
}


def _strip_md(text: str, max_len: int = 900) -> str:
    if not text:
        return ""
    t = re.sub(r"^#+\s*", "", str(text), flags=re.MULTILINE)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > max_len:
        return t[: max_len - 1] + "…"
    return t


def _snippet(text: str, max_len: int = 800) -> str:
    if not text:
        return "（无正文片段）"
    t = str(text).strip()
    if len(t) > max_len:
        return t[: max_len - 1] + "…"
    return t


def _notes_join(notes: Any) -> str:
    if not notes:
        return ""
    return ",".join(str(n).lower() for n in notes)


def _legal_basis_status(item: Dict[str, Any]) -> str:
    bases = item.get("legal_basis_results") or []
    notes = item.get("retrieval_notes") or []
    note_s = _notes_join(notes)
    if not bases:
        return "法律依据待补充/建议人工复核"
    rt = str(item.get("risk_type") or "")
    clause_text = str(item.get("clause_text") or "")
    if "exact_match" in note_s:
        if rt == "试用期风险" and any(k in clause_text for k in ("工资", "计发", "元", "薪酬")):
            return "已提供（不充分）"
        return "已提供"
    return "已提供（不完全匹配）"


def _risk_level_display(item: Dict[str, Any], sev: str, legal_status: str) -> str:
    rt = str(item.get("risk_type") or "")
    if legal_status.startswith("法律依据待补充"):
        return "高"
    if rt == "社保公积金风险":
        return "低"
    if rt == "试用期风险":
        if "不充分" in legal_status:
            return "高"
        return "中"
    if rt == "薪酬支付风险":
        if "不完全匹配" in legal_status:
            return "低"
        return "中"
    if sev == "critical":
        return "高"
    return "中"


def _format_legal_basis_block(item: Dict[str, Any]) -> str:
    lines: List[str] = []
    for basis in (item.get("legal_basis_results") or [])[:4]:
        kb = basis.get("kb_name") or ""
        title = basis.get("title") or ""
        content = _strip_md(basis.get("content") or "", 400)
        lines.append(f"[{kb}] {title}：“{content}”" if content else f"[{kb}] {title}")
    if not lines:
        return "法律依据待补充/建议人工复核"
    return "\n".join(lines)


def _risk_explanation_text(item: Dict[str, Any], legal_status: str) -> str:
    rt = str(item.get("risk_type") or "未分类")
    prefix = RISK_EXPLAIN_PREFIX.get(rt, "该条款在劳动合规审查中存在需要关注的要点。")
    if legal_status.startswith("法律依据待补充"):
        return prefix + "系统未检索到可直接对应的法条片段，风险判断证据不足，必须由人工补充法律依据后再签署。"
    if "不充分" in legal_status:
        return prefix + "已引用条文可能无法单独覆盖本条款的核心争议点（例如仅涉及试用期长度而未覆盖试用期工资底线），结论不确定性较高。"
    if "不完全匹配" in legal_status:
        return prefix + "检索到的条文与条款表述之间可能存在适用边界差异，建议结合履约场景进一步论证。"
    return prefix + "已检索到相关法律依据，请结合合同上下文判断是否足以消除合规隐患。"


def _revision_for_item(item: Dict[str, Any]) -> str:
    rt = str(item.get("risk_type") or "未分类")
    return REVISION_BY_RISK_TYPE.get(rt, REVISION_BY_RISK_TYPE["未分类"])


def _legal_analysis(item: Dict[str, Any]) -> str:
    """兼容旧前端：合并展示。"""
    basis_block = _format_legal_basis_block(item)
    notes = item.get("retrieval_notes") or []
    tail = ""
    if notes:
        tail = "\n\n检索说明：" + ", ".join(str(n) for n in notes)
    return basis_block + tail


def _distribution_sentence(counts: Dict[str, Any]) -> str:
    parts: List[str] = []
    for k, v in counts.items():
        if k == "无明显风险" or not v:
            continue
        parts.append(f"{k}（{v}项）")
    return "、".join(parts) if parts else "—"


def _executive_summary_text(
    n_risk: int,
    counts: Dict[str, Any],
    missing_basis: int,
    weak_basis: int,
) -> str:
    dist = _distribution_sentence(counts)
    p1 = (
        f"本报告对目标劳动合同文本进行了结构化风险筛查，识别出{n_risk}项存在合规隐患的条款，"
        f"主要风险类型分布为：{dist}。"
    )
    p2 = "其中，多数条款可匹配到知识库中的法律依据片段用于辅助判断；"
    if missing_basis:
        p2 += f"另有{missing_basis}项暂无法检索到直接条文支撑，需人工复核。"
    else:
        p2 += "暂未发现完全无法检索依据的条款。"
    if weak_basis:
        p2 += f"另有约{weak_basis}项所引用条文与争议焦点匹配不够充分，建议谨慎解读。"
    p3 = "整体来看，合同在劳动权利义务的关键节点上可能存在模糊或缺口表述，建议在签约前完成针对性修订并与专业律师确认。"
    return p1 + p2 + p3


def _conclusion_and_suggestions(
    rows: List[Dict[str, str]],
) -> tuple[str, List[str]]:
    high = [r["clauseId"] for r in rows if r.get("riskLevel") == "高"]
    pending = [
        r["clauseId"]
        for r in rows
        if str(r.get("legalBasisStatus", "")).startswith("法律依据待补充")
    ]
    focus = sorted(set(high + pending), key=lambda x: (len(x), x))
    body = (
        "本合同整体框架可能符合劳动合同的基本形式要求，但在试用期、薪酬、社保公积金、竞业限制及培训服务期等节点上，"
        "仍可能出现约定不明或与强制性规范脱节的问题。"
    )
    if focus:
        body += f"其中，条款{ '、'.join(focus) }需要优先处理。"
    suggestions = [
        "暂缓签署或签署前完成高风险条款的实质性修订；",
        "对法律依据不足或匹配不充分的条款，补充引用更贴切条文或取得律师书面意见；",
        "就薪酬结构、加班管理、社保公积金、竞业限制补偿、培训费用与服务期违约金等，必要时以附件或专项协议固化；",
        "最终文本建议由劳动法律师做全量复核后再定稿。",
    ]
    return body, suggestions


def _clause_overview_headline(item: Dict[str, Any], rt: str, section: str) -> str:
    """
    逐条风险卡片副标题：一句话概括「争议焦点 / 风险要点」（对齐交付 PDF 风格），
    不使用条款拆分器生成的「条文前 18 字」式 clause_title。
    """
    explicit = str(item.get("risk_overview") or item.get("clause_summary") or "").strip()
    if explicit:
        return explicit[:80]

    ct = str(item.get("clause_text") or "")
    triggers = [str(x) for x in (item.get("trigger_phrases") or []) if x]
    trig_s = " ".join(triggers)

    def _has(*keys: str) -> bool:
        return any(k in ct for k in keys)

    if rt == "试用期风险":
        if _has("延长试用", "延长试用期", "可延长") or "延长" in trig_s:
            return "试用期延长或变更约定存在合规风险"
        if _has("六个月以上", "6个月以上", "七个月", "八个月", "九个月", "十个月", "十二个月") or "六个月以上" in trig_s:
            return "试用期期限可能超出法定上限"
        if _has("工资", "薪酬", "薪资", "计发", "元/月", "元／月") or "工资" in trig_s:
            return "试用期工资或计发标准不明确"
        if _has("录用条件", "不符合录用条件", "转正"):
            return "录用条件或转正标准约定不利于劳动者举证"
        return "试用期起算、期限或适用条件约定不充分"

    if rt == "试用期工资风险":
        return "试用期工资标准或法定底线保障不足"

    if rt == "薪酬支付风险":
        if _has("加班", "加班费", "加点"):
            return "加班工资计发基数或支付规则不明确"
        if _has("拖欠", "延迟支付", "克扣"):
            return "工资支付时间或足额支付存在不利约定"
        if _has("调整", "调薪", "降薪", "待遇调整"):
            return "工资待遇调整机制可能损害协商一致原则"
        if _has("绩效", "提成", "奖金") and _has("工资", "薪酬"):
            return "浮动薪酬或绩效规则不透明、计算依据不足"
        return "劳动报酬标准、结构或支付方式约定不充分"

    if rt == "社保公积金风险":
        if _has("公积金", "住房公积金"):
            return "住房公积金缴存义务表述缺失或不明确"
        if _has("商业保险", "意外险") and not _has("社会保险", "五险", "养老保险"):
            return "以商业保险替代社会保险的风险表述需警惕"
        return "社会保险参保义务或缴费约定不充分"

    if rt == "竞业限制风险":
        if not _has("补偿", "经济补偿", "竞业限制补偿"):
            return "竞业限制经济补偿未约定或标准不明"
        if not _has("二年", "两年", "2年", "二十四个月"):
            return "竞业限制范围、期限或地域约定需重点审视"
        return "竞业限制权利义务对等性及补偿安排不充分"

    if rt == "培训服务期风险":
        if _has("违约金", "违约赔偿"):
            return "服务期违约金与培训费用挂钩关系不清晰"
        return "专项培训费用及服务期约定不充分"

    if rt == "单方调岗调薪风险":
        return "单方调岗调薪条件与程序约定存在不利条款"

    sec = (section or "").strip()
    if sec and len(sec) <= 20:
        return f"{sec}项下存在需关注的合规表述"
    if sec:
        return f"{sec[:18]}…项下存在需关注的合规表述"
    return f"{rt.replace('风险', '')}相关约定需审慎审查" if rt != "未分类" else "该条款存在需人工复核的事项"


def build_frontend_contract_analysis(
    report_context: Dict[str, Any],
    *,
    filename: str = "",
) -> Dict[str, Any]:
    summary_info = report_context.get("summary") or {}
    risk_items: List[Dict[str, Any]] = list(report_context.get("risk_items") or [])
    counts = summary_info.get("risk_type_counts") or {}
    contract_source = str(report_context.get("contract_source") or filename or "")

    stem = Path(filename).stem if filename else "合同文件"
    main_body_n = int(summary_info.get("main_body_clause_count") or 0)
    att_n = int(summary_info.get("attachment_count") or 0)
    key_n = int(summary_info.get("key_risk_clause_count") or len(risk_items))

    risk_overview_rows: List[Dict[str, str]] = []
    clauses: List[Dict[str, str]] = []

    for item in risk_items:
        rt = str(item.get("risk_type") or "未分类")
        severity = RISK_SEVERITY.get(rt, "warning")
        cid = str(item.get("clause_id") or f"C{len(clauses) + 1}")
        section = str(item.get("section_title") or "").strip().rstrip("#").strip()
        overview = _clause_overview_headline(item, rt, section)
        display_title = f"{rt}｜{overview}" if overview and overview != rt else rt
        if section:
            display_title = f"{display_title}（{section}）"[:200]

        legal_status = _legal_basis_status(item)
        risk_level = _risk_level_display(item, severity, legal_status)
        risk_overview_rows.append(
            {
                "clauseId": cid,
                "section": section or "—",
                "riskType": rt,
                "riskLevel": risk_level,
                "legalBasisStatus": legal_status,
            }
        )

        analysis_headline = overview[:100] if overview else rt
        legal_block = _format_legal_basis_block(item)
        explain = _risk_explanation_text(item, legal_status)
        revision = _revision_for_item(item)

        clauses.append(
            {
                "id": cid,
                "severity": severity,
                "title": display_title,
                "analysisHeadline": analysis_headline,
                "originalSnippet": _snippet(item.get("clause_text") or ""),
                "legalBasisText": legal_block,
                "riskExplanationText": explain,
                "revisionSuggestionText": revision,
                "aiAnalysis": _legal_analysis(item),
                "riskType": rt,
                "sectionTitle": section,
            }
        )

    critical_n = sum(1 for c in clauses if c["severity"] == "critical")
    warning_n = sum(1 for c in clauses if c["severity"] == "warning")
    missing_basis = sum(1 for r in risk_overview_rows if r["legalBasisStatus"].startswith("法律依据待补充"))
    weak_basis = sum(
        1 for r in risk_overview_rows if ("不充分" in r["legalBasisStatus"] or "不完全匹配" in r["legalBasisStatus"])
    )

    if critical_n > 0:
        status = "critical"
        level_text = "高危"
    elif warning_n > 0 or len(clauses) > 0:
        status = "warning"
        level_text = "警示" if len(clauses) <= 3 else "中危"
    else:
        status = "safe"
        level_text = "低危"

    fatal_traps = len(clauses)
    dist_sentence = _distribution_sentence(counts)
    scope_line = (
        f"主文条款共{main_body_n}条，"
        + ("无附件" if att_n == 0 else f"附件共{att_n}份")
    )

    parse_meta = report_context.get("parse_meta") or {}
    parser_used = parse_meta.get("parser_used")

    tz_cn = timezone(timedelta(hours=8))
    now = datetime.now(tz_cn)
    generated = now.strftime("%Y-%m-%d %H:%M:%S")
    generated_cn = now.strftime("%Y年%m月%d日")

    exec_summary = _executive_summary_text(len(risk_items), counts, missing_basis, weak_basis)
    conclusion_body, signing_suggestions = _conclusion_and_suggestions(risk_overview_rows)

    summary_parts = [
        f"卷宗《{filename or '未命名'}》已由后端合同审查流水线完成解析与法律依据检索。",
        scope_line + "。",
        f"关键风险条款 {key_n} 条。",
    ]
    if dist_sentence and dist_sentence != "—":
        summary_parts.append("风险类型分布：" + dist_sentence + "。")
    if parser_used:
        summary_parts.append(f"解析通道：{parser_used}。")
    engine_summary = "".join(summary_parts)

    disclaimer = "本报告不构成正式法律意见，具体签约决策应结合专业律师意见作出。"

    return {
        "status": status,
        "overview": {
            "levelText": level_text,
            "fatalTrapsCount": fatal_traps,
            "missingGuaranteesCount": missing_basis,
        },
        "reportTitle": "劳动合同风险审查报告",
        "reportSubtitle": "——基于模块化合规筛查的专项分析",
        "contractSource": contract_source,
        "generatedAt": generated,
        "generatedAtCn": generated_cn,
        "coverInfo": {
            "reportName": "劳动合同风险审查报告",
            "reviewTarget": f"《劳动合同》（来源文件编号：{stem}）",
            "scopeLine": scope_line,
            "keyRiskCount": key_n,
            "riskDistributionLine": dist_sentence if dist_sentence != "—" else "—",
        },
        "executiveSummary": exec_summary,
        "riskOverviewRows": risk_overview_rows,
        "conclusionBody": conclusion_body,
        "signingSuggestions": signing_suggestions,
        "disclaimer": disclaimer,
        "summary": engine_summary,
        "clauses": clauses,
        "sourceFilename": filename,
        "parseMeta": {
            "parser_used": parse_meta.get("parser_used"),
            "quality_flag": parse_meta.get("quality_flag"),
        },
    }


def run_contract_analysis_sync(
    file_path: str,
    *,
    parser: str = "auto",
    filename: str = "",
) -> Dict[str, Any]:
    """同步执行：解析 + 风险 + 检索 -> 前端数据结构（供线程池调用）。"""
    from app.services.risk_report_pipeline import generate_report_context_for_contract

    report_context = generate_report_context_for_contract(
        contract_source=file_path,
        parser=parser,
        fallback_to_legacy=True,
        enable_image_preprocess=False,
        top_k_per_kb=3,
    )
    return build_frontend_contract_analysis(report_context, filename=filename or Path(file_path).name)
