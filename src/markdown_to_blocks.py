"""Markdown to Feishu Docx Block format converter."""

import re
from typing import Any, Dict, List

BOLD_HIGHLIGHT_COLOR = 3
ITALIC_HIGHLIGHT_COLOR = 4
PARENTHETICAL_HIGHLIGHT_COLOR = 5


def markdown_to_feishu_blocks(md: str) -> List[Dict]:
    """
    Convert a markdown string into a list of Feishu docx block dicts.

    Feishu block types:
    - 2: text (paragraph)
    - 3: heading1
    - 4: heading2
    - 5: heading3
    - 12: bullet (unordered list)
    - 13: ordered (ordered list)
    - 14: code block
    - 15: quote
    - 22: divider (horizontal rule)
    - 31: table (internal representation, expanded before upload)
    """
    lines = md.split("\n")
    blocks = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Blank line → skip
        if not stripped:
            i += 1
            continue

        # Headings (must check ### before ## before #)
        if stripped.startswith("### "):
            blocks.append(_heading(5, stripped[4:]))
        elif stripped.startswith("## "):
            blocks.append(_heading(4, stripped[3:]))
        elif stripped.startswith("# "):
            blocks.append(_heading(3, stripped[2:]))

        # Horizontal rule (---, ***, or ___)
        elif re.match(r"^-{3,}$", stripped) or re.match(r"^\*{3,}$", stripped) or re.match(r"^_{3,}$", stripped):
            blocks.append({"block_type": 22, "divider": {}})

        # Bullet list (- or *)
        elif re.match(r"^[\-\*] ", stripped):
            text = re.sub(r"^[\-\*] ", "", stripped)
            blocks.append(_block(12, "bullet", text))

        # Ordered list (1. 2. etc.)
        elif re.match(r"^\d+\. ", stripped):
            text = re.sub(r"^\d+\. ", "", stripped)
            blocks.append(_block(13, "ordered", text))

        # Fenced code block
        elif stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append(_code_block("\n".join(code_lines)))

        # Block quote
        elif stripped.startswith("> "):
            blocks.append(_block(15, "quote", stripped[2:]))

        # Original section with inline highlights
        elif stripped == "【原文】":
            blocks.append(_original_label_block())
            i += 1
            while i < len(lines):
                nested_stripped = lines[i].strip()
                if not nested_stripped:
                    i += 1
                    continue
                if _is_original_terminator(nested_stripped):
                    i -= 1
                    break
                blocks.append(_original_body_block(nested_stripped))
                i += 1

        # Original text with inline highlights
        elif stripped.startswith("【原文】"):
            blocks.append(_original_text_block(stripped))

        # Analysis callout
        elif _is_analysis_callout_marker(stripped):
            callout_lines = []
            i += 1
            while i < len(lines):
                nested_line = lines[i]
                nested_stripped = nested_line.strip()
                if _is_callout_terminator(nested_stripped):
                    i -= 1
                    break
                callout_lines.append(nested_line)
                i += 1
            blocks.extend(_analysis_callouts(callout_lines))

        # Markdown table (starts with | and has | separator line following)
        elif stripped.startswith("|"):
            # Collect all table lines (header + separator + body)
            table_lines = [stripped]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            blocks.append(_table(table_lines))

        # Regular paragraph
        else:
            blocks.append(_block(2, "text", stripped))

        i += 1

    return blocks


def _text_elements(text: str) -> List[Dict]:
    """Parse inline markdown formatting into Feishu text_run elements.

    Handles: **bold**, *italic*, <u>underline</u>, <u>*underline+italic*</u>,
             `inline_code`, [link](url), and plain text.
    Strips HTML entities like &emsp; and <u>/<em> wrappers while preserving content.
    """
    # Strip &emsp; and similar non-breaking space entities
    text = text.replace("&emsp;", "").replace("&nbsp;", " ")

    # Use named groups so bold/italic handling stays explicit and regression-safe.
    pattern = re.compile(
        r"\*\*(?P<bold>.+?)\*\*"
        r"|<u>\*(?P<underline_italic>.+?)\*</u>"
        r"|<u>(?P<underline>.+?)</u>"
        r"|\*(?P<italic>.+?)\*"
        r"|`(?P<code>.+?)`"
        r"|\[(?P<link_text>.+?)\]\((?P<link_url>.+?)\)"
        r"|(?P<plain>[^*`\\[<]+)"
        r"|(?P<fallback>.)"
    )
    elements = []
    for m in pattern.finditer(text):
        if m.group("bold"):
            elements.append(_run(m.group("bold"), {"bold": True}))
        elif m.group("underline_italic"):
            elements.append(_run(m.group("underline_italic"), {"italic": True}))
        elif m.group("underline"):
            elements.append(_run(m.group("underline"), {}))
        elif m.group("italic"):
            elements.append(_run(m.group("italic"), {"italic": True}))
        elif m.group("code"):
            elements.append(_run(m.group("code"), {"inline_code": True}))
        elif m.group("link_text"):
            elements.append(_run(m.group("link_text"), {"link": {"url": m.group("link_url")}}))
        elif m.group("plain"):
            elements.append(_run(m.group("plain"), {}))
        elif m.group("fallback"):
            elements.append(_run(m.group("fallback"), {}))

    return elements or [_run(text, {})]


def _run(content: str, style: Dict) -> Dict:
    """Create a text_run element."""
    return {"text_run": {"content": content, "text_element_style": style}}


def _block(block_type: int, key: str, text: str) -> Dict:
    """Create a standard block (text, bullet, ordered, quote)."""
    return {
        "block_type": block_type,
        key: {
            "elements": _text_elements(text),
            "style": {},
        },
    }


def _heading(level: int, text: str) -> Dict:
    """Create a heading block. block_type 3=heading1, 4=heading2, 5=heading3."""
    key = f"heading{level - 2}"
    return {
        "block_type": level,
        key: {
            "elements": _text_elements(text),
            "style": {},
        },
    }


def _code_block(code: str) -> Dict:
    """Create a code block."""
    return {
        "block_type": 14,
        "code": {
            "elements": [_run(code, {})],
            "style": {"language": 1},  # 1 = PlainText
        },
    }


def _callout(lines: List[str], style: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Create an internal callout block."""
    inner_markdown = "\n".join(lines).strip("\n")
    children = markdown_to_feishu_blocks(inner_markdown) if inner_markdown.strip() else [_block(2, "text", " ")]
    return {
        "block_type": 19,
        "callout": style or {
            "background_color": 15,
            "border_color": 7,
        },
        "_children": children,
    }


def _analysis_callouts(lines: List[str]) -> List[Dict[str, Any]]:
    """Split one analysis section into multiple colored callout blocks."""
    modules: List[List[str]] = []
    current: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                current.append(line)
            continue
        if _is_analysis_module_marker(stripped):
            if current:
                modules.append(current)
            title, inline_body = _split_analysis_module_line(stripped)
            current = [title]
            if inline_body:
                current.append(inline_body)
            continue
        if not current:
            current = [stripped]
            continue
        current.append(line)

    if current:
        modules.append(current)

    if not modules:
        return [_callout(lines)]

    return [_callout(module_lines, _analysis_module_style(module_lines[0].strip())) for module_lines in modules]


def _table(lines: List[str]) -> Dict[str, Any]:
    """
    Convert a markdown table into an internal table representation.

    Feishu's docx block API rejects the nested ``table_cell -> children`` payload
    we previously generated. We therefore keep the table semantics here and let
    the uploader expand them into regular paragraph/list blocks before upload.
    """
    # Parse cells from all lines (skip the separator line)
    parsed_rows: List[List[str]] = []
    for line in lines:
        if _is_table_separator(line):
            continue
        cells = _parse_table_row(line)
        if cells:
            parsed_rows.append(cells)

    if not parsed_rows:
        return _block(2, "text", " | ".join(lines))

    num_rows = len(parsed_rows)
    num_cols = max(len(row) for row in parsed_rows)

    table_rows = []
    for row in parsed_rows:
        table_row = []
        for col_idx in range(num_cols):
            cell_text = row[col_idx].strip() if col_idx < len(row) else ""
            cell_text = cell_text or " "
            table_row.append({
                "text": cell_text,
                "elements": _text_elements(cell_text),
            })
        table_rows.append(table_row)

    return {
        "block_type": 31,
        "table": {
            "property": {
                "row_size": num_rows,
                "column_size": num_cols,
            }
        },
        "_table_rows": table_rows,
    }


def _is_analysis_callout_marker(text: str) -> bool:
    """Check whether a line marks the start of an analysis callout."""
    return text in {"【解析】：", "【解析】:", "【解析】"}


def _is_analysis_module_marker(text: str) -> bool:
    """Check whether a line starts an analysis module."""
    normalized = text.strip()
    return _split_analysis_module_line(normalized) is not None


def _split_analysis_module_line(text: str) -> tuple[str, str] | None:
    """Split an analysis module line into its title and any same-line body text."""
    normalized = text.strip()
    match = re.match(r"^(\*\*.+?[：:]\s*\*\*)(.*)$", normalized)
    if not match:
        return None

    title = match.group(1).strip()
    inline_body = match.group(2).strip()
    return title, inline_body


def _analysis_module_style(text: str) -> Dict[str, Any]:
    """Pick a callout color by module title."""
    module_styles = [
        ("段落结构", {"background_color": 2, "border_color": 2}),
        ("金句", {"background_color": 5, "border_color": 5}),
        ("关键词句", {"background_color": 3, "border_color": 3}),
        ("做法要点", {"background_color": 4, "border_color": 4}),
        ("事例", {"background_color": 6, "border_color": 6}),
        ("升华分析", {"background_color": 1, "border_color": 1}),
    ]
    for keyword, style in module_styles:
        if keyword in text:
            return style
    return {"background_color": 15, "border_color": 7}


def _is_callout_terminator(text: str) -> bool:
    """Check whether a line should end the current analysis callout."""
    if not text:
        return False
    if text.startswith("#"):
        return True
    if text.startswith("|"):
        return True
    return (
        re.match(r"^-{3,}$", text) is not None
        or re.match(r"^\*{3,}$", text) is not None
        or re.match(r"^_{3,}$", text) is not None
    )


def _original_text_block(text: str) -> Dict[str, Any]:
    """Create an original-text block with semantic highlights."""
    prefix = "【原文】"
    body = text[len(prefix):].lstrip()
    elements = [_run(prefix, {})]
    if body:
        elements.append(_run(" ", {}))
        elements.extend(_original_text_elements(body))
    return _text_block_from_elements(elements)


def _original_label_block() -> Dict[str, Any]:
    """Create the standalone label block for an original-text section."""
    return _text_block_from_elements([_run("【原文】", {})])


def _original_body_block(text: str) -> Dict[str, Any]:
    """Create a body block inside an original-text section."""
    return _text_block_from_elements(_original_text_elements(text))


def _text_block_from_elements(elements: List[Dict]) -> Dict[str, Any]:
    """Create a plain text block from prebuilt elements."""
    return {
        "block_type": 2,
        "text": {
            "elements": elements,
            "style": {},
        },
    }


def _original_text_elements(text: str) -> List[Dict]:
    """Parse original-text content and highlight key spans."""
    pattern = re.compile(
        r"\*\*\*(.+?)\*\*\*"
        r"|\*\*(.+?)\*\*"
        r"|\*(.+?)\*"
        r"|`(.+?)`"
        r"|\[(.+?)\]\((.+?)\)"
        r"|([^*`\[]+)"
        r"|(.)"
    )
    elements = []
    for match in pattern.finditer(text):
        if match.group(1):
            elements.extend(_split_parenthetical_text(match.group(1), {"bold": True, "italic": True, "background_color": BOLD_HIGHLIGHT_COLOR}))
        elif match.group(2):
            elements.extend(_split_parenthetical_text(match.group(2), _original_bold_style(match.group(2))))
        elif match.group(3):
            elements.extend(_split_parenthetical_text(match.group(3), {"italic": True, "background_color": ITALIC_HIGHLIGHT_COLOR}))
        elif match.group(4):
            elements.append(_run(match.group(4), {"inline_code": True}))
        elif match.group(5):
            elements.append(_run(match.group(5), {"link": {"url": match.group(6)}}))
        elif match.group(7):
            elements.extend(_split_parenthetical_text(match.group(7), {}))
        elif match.group(8):
            elements.extend(_split_parenthetical_text(match.group(8), {}))
    return elements or [_run(text, {})]


def _original_bold_style(text: str) -> Dict[str, Any]:
    """Style bold emphasis in original text as the dedicated bold highlight color."""
    return {"bold": True, "background_color": BOLD_HIGHLIGHT_COLOR}


def _split_parenthetical_text(text: str, base_style: Dict[str, Any]) -> List[Dict]:
    """Split text so only explicit double-parenthesis annotations get a blue background."""
    pattern = re.compile(r"(（（[^）]*））|\(\([^)]*\)\))")
    parts = pattern.split(text)
    elements = []
    for part in parts:
        if not part:
            continue
        style = dict(base_style)
        if pattern.fullmatch(part):
            style["background_color"] = PARENTHETICAL_HIGHLIGHT_COLOR
        elements.append(_run(part, style))
    return elements


def _is_original_terminator(text: str) -> bool:
    """Check whether an original-text section should end."""
    if text.startswith("【解析】"):
        return True
    if text.startswith("#"):
        return True
    if text.startswith("|"):
        return True
    return (
        re.match(r"^-{3,}$", text) is not None
        or re.match(r"^\*{3,}$", text) is not None
        or re.match(r"^_{3,}$", text) is not None
    )


def _is_table_separator(line: str) -> bool:
    """Check if a table line is the separator (e.g., |---|---|---|)."""
    stripped = line.strip().lstrip("|").rstrip("|")
    parts = [p.strip() for p in stripped.split("|")]
    return all(
        all(c in "-: " for c in part) and len(part) > 0
        for part in parts
    )


def _parse_table_row(line: str) -> List[str]:
    """Parse a markdown table row into a list of cell strings."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    cells = [c.strip() for c in stripped.split("|")]
    # Remove trailing empty cell from rows ending with |
    if cells and cells[-1] == "":
        cells.pop()
    return cells
