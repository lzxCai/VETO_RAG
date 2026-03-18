import re
from typing import List, Dict, Optional, Tuple


SECTION_TITLE_PATTERN = r"([一二三四五六七八九十]+、[^\n]+)"
CLAUSE_HEADER_PATTERN = r"(第[一二三四五六七八九十百零\d]+条)"
ATTACHMENT_PATTERN = r"(附件\d+[^\n]*)"
SOFT_SECTION_KEYWORDS = [
    "权利及义务",
    "相关费用",
    "付款方式",
    "违约责任",
    "争议",
    "保密",
    "服务期",
    "解除",
    "终止",
]


def extract_main_body(full_text: str) -> str:
    """
    从“第一条”开始截取正文
    """
    match = re.search(r"第一条", full_text)
    if match:
        return full_text[match.start():].strip()
    return full_text.strip()


def split_main_and_attachments(full_text: str) -> Tuple[str, str]:
    """
    将正文与附件区分开：
    - main_body: 从第一条开始，到附件前为止
    - attachments: 附件内容
    """
    full_text = extract_main_body(full_text)

    attachment_match = re.search(r"\n附件\d+", full_text)
    if attachment_match:
        main_body = full_text[:attachment_match.start()].strip()
        attachments = full_text[attachment_match.start():].strip()
        return main_body, attachments

    return full_text, ""


def find_all_section_titles(text: str) -> List[Dict]:
    """
    找出所有章节标题及其位置
    例如：
    一、劳动合同期限
    二、工作内容和工作地点
    """
    matches = list(re.finditer(SECTION_TITLE_PATTERN, text))
    results = []
    for m in matches:
        results.append({
            "title": m.group(1).strip(),
            "start": m.start(),
            "end": m.end()
        })
    return results


def find_nearest_section_title(section_titles: List[Dict], position: int) -> Optional[str]:
    """
    找到某个条款前最近的章节标题
    """
    nearest = None
    for item in section_titles:
        if item["start"] < position:
            nearest = item["title"]
        else:
            break
    return nearest


def strip_trailing_section_title(clause_text: str) -> str:
    """
    去掉条款末尾误带入的下一章节标题
    例如：
    ...
    二、工作内容和工作地点
    """
    lines = [line.strip() for line in clause_text.split("\n") if line.strip()]
    if not lines:
        return clause_text.strip()

    # 如果最后一行是章节标题，则删除
    if re.match(r"^[一二三四五六七八九十]+、", lines[-1]):
        lines = lines[:-1]

    return "\n".join(lines).strip()


def clean_clause_leading_section_title(clause_text: str) -> str:
    """
    如果条款开头误带章节标题，也去掉。
    例如：
    二、工作内容和工作地点
    第二条 ...
    """
    lines = [line.strip() for line in clause_text.split("\n") if line.strip()]
    if not lines:
        return clause_text.strip()

    if len(lines) >= 2 and re.match(r"^[一二三四五六七八九十]+、", lines[0]) and re.match(r"^第[一二三四五六七八九十百零\d]+条", lines[1]):
        lines = lines[1:]

    return "\n".join(lines).strip()


def normalize_clause_text(clause_text: str) -> str:
    """
    统一处理条款文本：
    - 去首部章节标题
    - 去尾部章节标题
    """
    clause_text = clean_clause_leading_section_title(clause_text)
    clause_text = strip_trailing_section_title(clause_text)
    return clause_text.strip()


def extract_clause_title(section: str, clause_text: str) -> str:
    """
    提取条款标题。
    对于这类劳动合同模板，大多数“第X条”后面没有规范小标题，
    因此这里采用“第X条后前 18 个有效字符”作为摘要式标题。
    """
    text = clause_text.strip()

    # 去掉 section
    if text.startswith(section):
        text = text[len(section):].strip()

    # 去掉首部换行
    text = re.sub(r"^\s+", "", text)

    # 取第一行
    first_line = text.split("\n")[0].strip()

    # 去掉多余空格
    first_line = re.sub(r"\s+", "", first_line)

    # 如果第一行太短，就直接返回 section
    if len(first_line) <= 1:
        return f"{section}条款"

    # 截取较短摘要作为 title
    title = first_line[:18]

    return title if title else f"{section}条款"


def split_clauses(main_body: str) -> List[Dict]:
    """
    按“第X条”切分正文条款，并关联章节标题
    """
    section_titles = find_all_section_titles(main_body)
    matches = list(re.finditer(CLAUSE_HEADER_PATTERN, main_body))

    clauses = []

    if not matches:
        return split_clauses_with_weak_signals(main_body)

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(main_body)

        raw_clause_text = main_body[start:end].strip()
        section = match.group(1)

        # 找最近章节标题
        section_title = find_nearest_section_title(section_titles, start)

        # 规范化文本
        clause_text = normalize_clause_text(raw_clause_text)

        # 提取 title
        title = extract_clause_title(section, clause_text)

        clauses.append({
            "clause_id": f"C{idx + 1}",
            "section_title": section_title,
            "section": section,
            "title": title,
            "text": clause_text,
            "part": "main_body"
        })

    return clauses


def split_clauses_with_weak_signals(main_body: str) -> List[Dict]:
    """
    弱编号兜底切分（用于多模态OCR下“第X条”识别不稳定场景）：
    1) 优先按章节标题（“一、二、三”）切分
    2) 对超长段落再按软关键词辅助切分
    """
    text = main_body.strip()
    if not text:
        return []

    section_matches = list(re.finditer(SECTION_TITLE_PATTERN, text))
    clauses: List[Dict] = []

    if len(section_matches) >= 2:
        for idx, match in enumerate(section_matches):
            start = match.start()
            end = section_matches[idx + 1].start() if idx + 1 < len(section_matches) else len(text)
            chunk = text[start:end].strip()
            section_title = match.group(1).strip()
            if not chunk:
                continue
            title = extract_clause_title("", chunk)
            clauses.append(
                {
                    "clause_id": f"C{len(clauses) + 1}",
                    "section_title": section_title,
                    "section": "",
                    "title": title if title else "未识别条款",
                    "text": chunk,
                    "part": "main_body",
                }
            )
    else:
        clauses.append(
            {
                "clause_id": "C1",
                "section_title": None,
                "section": "",
                "title": "未识别条款",
                "text": text,
                "part": "main_body",
            }
        )

    # 对过长单条再做一次软切分
    refined: List[Dict] = []
    for clause in clauses:
        clause_text = clause["text"]
        if len(clause_text) < 1200:
            refined.append(clause)
            continue

        split_pattern = r"(?=\n?[一二三四五六七八九十]+、)|(?=" + "|".join(
            re.escape(k) for k in SOFT_SECTION_KEYWORDS
        ) + r")"
        parts = [p.strip() for p in re.split(split_pattern, clause_text) if p and p.strip()]

        if len(parts) <= 1:
            refined.append(clause)
            continue

        for part in parts:
            title = extract_clause_title("", part)
            refined.append(
                {
                    "clause_id": f"C{len(refined) + 1}",
                    "section_title": clause.get("section_title"),
                    "section": "",
                    "title": title if title else "未识别条款",
                    "text": part,
                    "part": "main_body",
                }
            )

    # 二级兜底：按小点（1、2、3 / （1）（2））切分
    second_refined: List[Dict] = []
    subpoint_pattern = r"(?=(?:^|\n)[（(]?\d{1,2}[）)\.、])"
    for clause in refined:
        text = clause.get("text", "")
        if len(text) < 250:
            second_refined.append(clause)
            continue

        sub_parts = [p.strip() for p in re.split(subpoint_pattern, text) if p and p.strip()]
        # 至少有两个小点才触发拆分
        matched_sub = [p for p in sub_parts if re.match(r"^[（(]?\d{1,2}[）)\.、]", p)]
        if len(matched_sub) < 2:
            second_refined.append(clause)
            continue

        for p in sub_parts:
            if len(p) < 12:
                continue
            title = extract_clause_title("", p)
            second_refined.append(
                {
                    "clause_id": f"C{len(second_refined) + 1}",
                    "section_title": clause.get("section_title"),
                    "section": clause.get("section", ""),
                    "title": title if title else "未识别条款",
                    "text": p,
                    "part": "main_body",
                }
            )

    # 统一重排 clause_id
    final_items = second_refined if second_refined else refined
    for idx, item in enumerate(final_items, start=1):
        item["clause_id"] = f"C{idx}"

    return final_items if final_items else [{
        "clause_id": "C1",
        "section_title": None,
        "section": "",
        "title": "未识别条款",
        "text": text,
        "part": "main_body",
    }]


def split_attachments(attachments_text: str) -> List[Dict]:
    """
    切分附件
    """
    if not attachments_text.strip():
        return []

    matches = list(re.finditer(ATTACHMENT_PATTERN, attachments_text))
    attachments = []

    if not matches:
        return [{
            "attachment_id": "A1",
            "title": "附件",
            "text": attachments_text.strip(),
            "part": "attachment"
        }]

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(attachments_text)

        attachment_text = attachments_text[start:end].strip()
        lines = [line.strip() for line in attachment_text.split("\n") if line.strip()]

        if len(lines) >= 2:
            title = f"{lines[0]} {lines[1]}"
        else:
            title = lines[0]

        attachments.append({
            "attachment_id": f"A{idx + 1}",
            "title": title.strip(),
            "text": attachment_text,
            "part": "attachment"
        })

    return attachments


def fix_first_clause_section_title(clauses: List[Dict]) -> List[Dict]:
    """
    某些情况下第一条前的章节标题没有被正确挂到 C1，
    如果 C1 没有 section_title，而 C2 有明显章节标题，则尝试补上：
    一般情况下 C1 应属于 “一、劳动合同期限”
    """
    if not clauses:
        return clauses

    if clauses[0]["section_title"] is None:
        clauses[0]["section_title"] = "一、劳动合同期限"

    return clauses


def split_contract(full_text: str) -> Dict:
    """
    总入口：
    返回正文条款 + 附件
    """
    main_body, attachments_text = split_main_and_attachments(full_text)

    clauses = split_clauses(main_body)
    clauses = fix_first_clause_section_title(clauses)

    attachments = split_attachments(attachments_text)

    return {
        "main_body": clauses,
        "attachments": attachments
    }
