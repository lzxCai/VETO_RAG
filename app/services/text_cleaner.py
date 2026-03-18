import re
from typing import List, Dict


def normalize_whitespace(text: str) -> str:
    """
    统一空白字符
    """
    if not text:
        return ""

    text = text.replace("\u3000", " ")
    text = text.replace("\xa0", " ")
    text = text.replace("\t", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def remove_page_number_lines(lines: List[str]) -> List[str]:
    """
    删除明显的页码行，例如单独一行的:
    1
    2
    9
    """
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r"\d{1,3}", stripped):
            continue
        cleaned.append(line)
    return cleaned


def merge_short_lines(lines: List[str]) -> List[str]:
    """
    合并明显的单字/短词断行。
    例如：
    签
    订
    日
    期：
    -> 签订日期：
    """
    merged = []
    buffer = []

    def flush_buffer():
        nonlocal buffer
        if buffer:
            merged.append("".join(buffer))
            buffer = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            flush_buffer()
            continue

        # 很短的行，通常是竖排拆开的字
        if len(stripped) <= 2:
            buffer.append(stripped)
        else:
            flush_buffer()
            merged.append(stripped)

    flush_buffer()
    return merged


def is_section_title(line: str) -> bool:
    """
    判断是否为章节标题，如：
    一、劳动合同期限
    二、工作内容和工作地点
    """
    return bool(re.match(r"^[一二三四五六七八九十]+、", line.strip()))


def is_clause_header(line: str) -> bool:
    """
    判断是否为条款标题，如：
    第一条
    第二条
    """
    return bool(re.match(r"^第[一二三四五六七八九十百零\d]+条", line.strip()))


def is_attachment_header(line: str) -> bool:
    """
    判断是否为附件标题，如：
    附件1
    附件2
    """
    return bool(re.match(r"^附件\d+", line.strip()))


def is_subpoint_header(line: str) -> bool:
    """
    判断是否为小点标题，如：
    1、...
    2. ...
    （3）...
    """
    stripped = line.strip()
    return bool(
        re.match(r"^(?:[（(]?\d{1,2}[）)\.、]|[①②③④⑤⑥⑦⑧⑨⑩])", stripped)
    )


def should_keep_separate(line: str) -> bool:
    """
    这些行应保留为独立行，不要和前后句子合并
    """
    stripped = line.strip()
    if not stripped:
        return True

    if is_section_title(stripped):
        return True
    if is_clause_header(stripped):
        return True
    if is_attachment_header(stripped):
        return True
    if is_subpoint_header(stripped):
        return True

    # 关键信息字段，保留单独展示
    prefixes = [
        "甲方（用人单位）",
        "乙方（劳动者）",
        "统一社会信用代码",
        "法定代表人",
        "注册地",
        "经营地",
        "联系电话",
        "居民身份证号码",
        "户籍地址",
        "经常居住地",
        "签订日期",
    ]
    if any(stripped.startswith(p) for p in prefixes):
        return True

    return False


def merge_broken_sentence_lines(lines: List[str], mode: str = "legacy") -> List[str]:
    """
    合并因为 PDF 抽取导致的句子断行，但尽量保留：
    - 章节标题
    - 条款标题
    - 附件标题
    - 关键字段行
    """
    if not lines:
        return []

    result = []

    for line in lines:
        current = line.strip()
        if not current:
            continue

        if not result:
            result.append(current)
            continue

        prev = result[-1]

        # 当前行如果应该单独保留，则直接新增
        if should_keep_separate(current):
            result.append(current)
            continue

        # 上一行如果是独立标题类，也直接新增
        if should_keep_separate(prev):
            result.append(current)
            continue

        # 多模态模式：默认保留边界，避免过度合并导致“大长条款”
        if mode == "multimodal":
            # 仅在明显是短碎片时再合并
            if len(current) <= 3 and not prev.endswith(("。", "；", "！", "？")):
                result[-1] = prev + current
            else:
                result.append(current)
            continue

        # 上一行已经结束，不合并
        if prev.endswith(("。", "；", "！", "？")):
            result.append(current)
            continue

        # 否则合并到上一行
        result[-1] = prev + current

    return result


def post_process_full_text(text: str, mode: str = "legacy") -> str:
    """
    对合并后的全文做后处理：
    1. 在章节标题前补换行
    2. 在第X条前补换行
    3. 在附件前补换行
    4. 清理多余空行
    """
    # 在 一、二、三... 前补换行
    text = re.sub(r"(?<!\n)([一二三四五六七八九十]+、)", r"\n\1", text)

    # 在 第X条 前补换行
    text = re.sub(r"(?<!\n)(第[一二三四五六七八九十百零\d]+条)", r"\n\1", text)

    # 在 附件 前补换行
    text = re.sub(r"(?<!\n)(附件\d+)", r"\n\1", text)

    if mode == "multimodal":
        # 在小点序号前补换行（避免被并成一段）
        text = re.sub(r"(?<!\n)([（(]?\d{1,2}[）)\.、])", r"\n\1", text)
        text = re.sub(r"(?<!\n)([①②③④⑤⑥⑦⑧⑨⑩])", r"\n\1", text)

    # 清理多余空行
    text = re.sub(r"\n{2,}", "\n", text)

    return text.strip()


def clean_page_text(text: str) -> str:
    """
    清洗单页文本
    """
    text = normalize_whitespace(text)

    # 拆成行
    lines = [line.strip() for line in text.split("\n")]

    # 去掉空行
    lines = [line for line in lines if line.strip()]

    # 去掉页码行
    lines = remove_page_number_lines(lines)

    # 合并单字断行
    lines = merge_short_lines(lines)

    # 再去空
    lines = [line for line in lines if line.strip()]

    return "\n".join(lines).strip()


def clean_pages(pages: List[Dict], mode: str = "legacy") -> List[Dict]:
    """
    按页清洗
    """
    result = []
    for page in pages:
        cleaned_text = clean_page_text(page["text"])
        result.append({
            "page_no": page["page_no"],
            "text": cleaned_text,
            "blocks": page.get("blocks", []),
            "parse_mode": page.get("parse_mode"),
        })
    return result


def merge_pages(pages: List[Dict], mode: str = "legacy") -> str:
    """
    合并多页文本，并做跨页级别的进一步清洗
    """
    text = "\n".join(page["text"] for page in pages if page["text"].strip())
    text = normalize_whitespace(text)

    # 拆行
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]

    # 再次去掉页码
    lines = remove_page_number_lines(lines)

    # 合并断裂句子
    lines = merge_broken_sentence_lines(lines, mode=mode)

    # 去掉多余空格
    cleaned_lines = []
    for line in lines:
        line = re.sub(r"[ ]{2,}", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    final_text = "\n".join(cleaned_lines)
    final_text = re.sub(r"\n{2,}", "\n", final_text)

    # 最后补关键换行
    final_text = post_process_full_text(final_text, mode=mode)

    return final_text.strip()
