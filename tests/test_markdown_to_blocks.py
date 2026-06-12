"""Unit tests for markdown_to_blocks module."""

from src.markdown_to_blocks import markdown_to_feishu_blocks


def test_heading1():
    """Test # heading → block_type 3 (heading1)."""
    blocks = markdown_to_feishu_blocks("# Heading 1")
    assert len(blocks) == 1
    assert blocks[0]["block_type"] == 3
    assert "heading1" in blocks[0]
    assert blocks[0]["heading1"]["elements"][0]["text_run"]["content"] == "Heading 1"


def test_heading2():
    """Test ## heading → block_type 4 (heading2)."""
    blocks = markdown_to_feishu_blocks("## Heading 2")
    assert len(blocks) == 1
    assert blocks[0]["block_type"] == 4
    assert "heading2" in blocks[0]


def test_heading3():
    """Test ### heading → block_type 5 (heading3)."""
    blocks = markdown_to_feishu_blocks("### Heading 3")
    assert len(blocks) == 1
    assert blocks[0]["block_type"] == 5
    assert "heading3" in blocks[0]


def test_paragraph():
    """Test plain text → block_type 2 (text)."""
    blocks = markdown_to_feishu_blocks("This is a paragraph.")
    assert len(blocks) == 1
    assert blocks[0]["block_type"] == 2
    assert "text" in blocks[0]


def test_bullet_list():
    """Test - item → block_type 12 (bullet)."""
    blocks = markdown_to_feishu_blocks("- Item 1\n- Item 2")
    assert len(blocks) == 2
    assert blocks[0]["block_type"] == 12
    assert "bullet" in blocks[0]


def test_ordered_list():
    """Test 1. item → block_type 13 (ordered)."""
    blocks = markdown_to_feishu_blocks("1. First\n2. Second")
    assert len(blocks) == 2
    assert blocks[0]["block_type"] == 13
    assert "ordered" in blocks[0]


def test_code_block():
    """Test fenced code block → block_type 14 (code)."""
    blocks = markdown_to_feishu_blocks("```python\nprint('hello')\n```")
    assert len(blocks) == 1
    assert blocks[0]["block_type"] == 14
    assert "code" in blocks[0]


def test_quote():
    """Test > quote → block_type 15 (quote)."""
    blocks = markdown_to_feishu_blocks("> This is a quote")
    assert len(blocks) == 1
    assert blocks[0]["block_type"] == 15
    assert "quote" in blocks[0]


def test_divider():
    """Test --- → block_type 22 (divider)."""
    blocks = markdown_to_feishu_blocks("---")
    assert len(blocks) == 1
    assert blocks[0]["block_type"] == 22
    assert "divider" in blocks[0]


def test_bold_inline():
    """Test **bold** text inline styling."""
    blocks = markdown_to_feishu_blocks("**Bold text**")
    assert len(blocks) == 1
    elements = blocks[0]["text"]["elements"]
    assert elements[0]["text_run"]["text_element_style"]["bold"] is True
    assert elements[0]["text_run"]["content"] == "Bold text"


def test_italic_inline():
    """Test *italic* text inline styling."""
    blocks = markdown_to_feishu_blocks("*Italic text*")
    assert len(blocks) == 1
    elements = blocks[0]["text"]["elements"]
    assert elements[0]["text_run"]["text_element_style"]["italic"] is True


def test_bold_and_italic_do_not_get_confused():
    """Regular bold markdown should stay bold instead of being parsed as italic."""
    blocks = markdown_to_feishu_blocks("**bold** and *italic*")
    elements = blocks[0]["text"]["elements"]

    assert elements[0]["text_run"]["content"] == "bold"
    assert elements[0]["text_run"]["text_element_style"] == {"bold": True}
    assert elements[2]["text_run"]["content"] == "italic"
    assert elements[2]["text_run"]["text_element_style"] == {"italic": True}


def test_inline_code():
    """Test `code` inline styling."""
    blocks = markdown_to_feishu_blocks("`inline code`")
    assert len(blocks) == 1
    elements = blocks[0]["text"]["elements"]
    assert elements[0]["text_run"]["text_element_style"]["inline_code"] is True


def test_link_inline():
    """Test [text](url) inline styling."""
    blocks = markdown_to_feishu_blocks("[Link text](https://example.com)")
    assert len(blocks) == 1
    elements = blocks[0]["text"]["elements"]
    assert elements[0]["text_run"]["text_element_style"]["link"]["url"] == "https://example.com"


def test_mixed_inline():
    """Test mixed inline styles."""
    blocks = markdown_to_feishu_blocks("**Bold** and *italic* and `code`")
    assert len(blocks) == 1
    elements = blocks[0]["text"]["elements"]
    assert len(elements) == 5  # bold, " and ", italic, " and ", code


def test_blank_lines_skipped():
    """Test that blank lines are skipped."""
    blocks = markdown_to_feishu_blocks("# Heading\n\n\nParagraph\n\n")
    assert len(blocks) == 2


def test_complex_markdown():
    """Test a complex markdown document."""
    md = """# Title

This is a paragraph with **bold** and *italic*.

## Section 1

- Item 1
- Item 2

1. First
2. Second

> A quote

---

```
code block
```
"""
    blocks = markdown_to_feishu_blocks(md)
    assert len(blocks) == 10  # 1 heading + 1 paragraph + 1 heading + 2 bullets + 2 ordered + 1 quote + 1 divider + 1 code


# ── Table tests ──────────────────────────────────────────────────────
# Tables are kept as an internal table representation and expanded by the
# uploader into regular Feishu text/list blocks before upload.


def _cell_text(cell_block: dict) -> str:
    """Helper: extract plain text from an internal table cell."""
    return "".join(
        elem["text_run"]["content"]
        for elem in cell_block.get("elements", [])
        if "text_run" in elem
    )


def _block_text(block: dict) -> str:
    """Helper: extract plain text from a regular text-like block."""
    for key in ("text", "bullet", "ordered", "quote", "heading1", "heading2", "heading3"):
        if key in block:
            return "".join(
                elem["text_run"]["content"]
                for elem in block[key].get("elements", [])
                if "text_run" in elem
            )
    return ""


def test_table_basic():
    """Test basic markdown table → internal table format."""
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    blocks = markdown_to_feishu_blocks(md)
    assert len(blocks) == 1
    tbl = blocks[0]
    assert tbl["block_type"] == 31

    prop = tbl["table"]["property"]
    assert prop["row_size"] == 2
    assert prop["column_size"] == 2

    rows = tbl["_table_rows"]
    assert len(rows) == 2
    assert len(rows[0]) == 2
    assert len(rows[1]) == 2

    assert _cell_text(rows[0][0]) == "A"
    assert _cell_text(rows[0][1]) == "B"
    assert _cell_text(rows[1][0]) == "1"
    assert _cell_text(rows[1][1]) == "2"


def test_table_with_bold():
    """Test table cells with bold formatting."""
    md = "| Header |\n|---|\n| **bold** |"
    blocks = markdown_to_feishu_blocks(md)
    rows = blocks[0]["_table_rows"]
    assert len(rows) == 2

    # Data cell has bold styling
    data_cell = rows[1][0]
    elements = data_cell["elements"]
    assert elements[0]["text_run"]["text_element_style"]["bold"] is True
    assert elements[0]["text_run"]["content"] == "bold"


def test_table_with_italic():
    """Test table cells with italic formatting."""
    md = "| Header |\n|---|\n| *italic* |"
    blocks = markdown_to_feishu_blocks(md)
    elements = blocks[0]["_table_rows"][1][0]["elements"]
    assert elements[0]["text_run"]["text_element_style"]["italic"] is True


def test_table_with_link():
    """Test table cells with links."""
    md = "| Link |\n|---|\n| [text](http://x.com) |"
    blocks = markdown_to_feishu_blocks(md)
    elements = blocks[0]["_table_rows"][1][0]["elements"]
    assert elements[0]["text_run"]["content"] == "text"
    assert elements[0]["text_run"]["text_element_style"]["link"]["url"] == "http://x.com"


def test_table_with_underline_italic():
    """Test table cells with <u>*text*</u> formatting."""
    md = "| Quote |\n|---|\n| <u>*italic underline*</u> |"
    blocks = markdown_to_feishu_blocks(md)
    elements = blocks[0]["_table_rows"][1][0]["elements"]
    assert elements[0]["text_run"]["text_element_style"]["italic"] is True
    assert elements[0]["text_run"]["content"] == "italic underline"


def test_table_with_mixed_formatting():
    """Test table with bold, italic, and plain text cells."""
    md = "| A | B | C |\n|---|---|---|\n| **bold** | plain | *italic* |"
    blocks = markdown_to_feishu_blocks(md)
    row = blocks[0]["_table_rows"][1]

    assert _cell_text(row[0]) == "bold"
    assert row[0]["elements"][0]["text_run"]["text_element_style"]["bold"] is True
    assert _cell_text(row[1]) == "plain"
    assert row[2]["elements"][0]["text_run"]["text_element_style"]["italic"] is True


def test_table_with_empty_cell():
    """Test that empty cells get a space character."""
    md = "| A | B |\n|---|---|\n|  | x |"
    blocks = markdown_to_feishu_blocks(md)
    row = blocks[0]["_table_rows"][1]
    assert _cell_text(row[0]) == " "


def test_real_analysis_table():
    """Test a table matching the actual analysis output format."""
    md = (
        "| 段落 | 论点 | 核心关键词 | 在文中的层次 |\n"
        "|------|------|-----------|-------------|\n"
        "| P1-P4 | 贸易需算综合账 | 订单回流 | 引论/总起 |\n"
        "| P5-P6 | 大市场优势 | 供需双强 | 本论一 |\n"
    )
    blocks = markdown_to_feishu_blocks(md)
    assert len(blocks) == 1
    tbl = blocks[0]
    assert tbl["block_type"] == 31

    prop = tbl["table"]["property"]
    assert prop["row_size"] == 3
    assert prop["column_size"] == 4
    assert len(tbl["_table_rows"]) == 3
    assert len(tbl["_table_rows"][0]) == 4


def test_table_surrounded_by_content():
    """Test table embedded in a larger document."""
    md = "# Title\n\nIntro text.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nOutro text.\n"
    blocks = markdown_to_feishu_blocks(md)
    block_types = [b["block_type"] for b in blocks]
    assert block_types == [3, 2, 31, 2]  # heading, text, table, text


def test_multiple_tables():
    """Document with multiple tables."""
    md = "| A |\n|---|\n| 1 |\n\nSome text.\n\n| B | C |\n|---|---|\n| 2 | 3 |"
    blocks = markdown_to_feishu_blocks(md)
    tables = [b for b in blocks if b["block_type"] == 31]
    assert len(tables) == 2
    assert len(tables[0]["_table_rows"]) == 2
    assert len(tables[1]["_table_rows"]) == 2
    assert _cell_text(tables[0]["_table_rows"][0][0]) == "A"
    assert _cell_text(tables[1]["_table_rows"][0][0]) == "B"


def test_analysis_marker_becomes_callout():
    """Analysis sections should be converted into internal callout blocks."""
    md = "【解析】：\n **段落结构：**\n  说明内容\n\n## 下一节"
    blocks = markdown_to_feishu_blocks(md)

    assert blocks[0]["block_type"] == 19
    assert blocks[0]["callout"]["background_color"] == 2
    assert blocks[0]["_children"][0]["block_type"] == 2
    assert blocks[1]["block_type"] == 4


def test_analysis_modules_support_mixed_colon_formats():
    """Analysis module markers should handle the mixed formatting used by LLM output."""
    md = (
        "【解析】\n"
        "  **段落结构：**\n"
        "    说明内容\n"
        "  **✨金句: **\n"
        "    金句内容\n"
        "  **做法要点: **\n"
        "    1. 要点一\n"
        "  **📜事例:**\n"
        "    事例内容\n"
        "  **🚀升华分析:** \n"
        "    升华内容\n"
    )
    blocks = markdown_to_feishu_blocks(md)

    assert [block["block_type"] for block in blocks] == [19, 19, 19, 19, 19]
    assert [block["callout"]["background_color"] for block in blocks] == [2, 5, 3, 6, 1]
    assert _block_text(blocks[0]["_children"][0]) == "段落结构："
    assert _block_text(blocks[1]["_children"][0]) == "✨金句: "
    assert _block_text(blocks[2]["_children"][0]) == "做法要点: "
    assert _block_text(blocks[3]["_children"][0]) == "📜事例:"
    assert _block_text(blocks[4]["_children"][0]) == "🚀升华分析:"


def test_analysis_modules_split_same_line_title_and_body():
    """Analysis module markers should split same-line title/body into separate callouts."""
    md = (
        "【解析】\n"
        "  **段落结构：** 理念承接→总体布局→分区域举例。\n"
        "  **✨金句:** 友好温情，是文旅发展的价值所向；文旅资源，是产业提质的立身之本。\n"
        "    - 提炼仿写句式：[抽象理念]，是[领域A]的价值所向；[具体载体]，是[领域B]的立身之本。\n"
        "  **做法要点:** \n"
        "    1. 规划特色廊道\n"
        "  **📜事例:** 四大区域廊道建设案例。\n"
    )
    blocks = markdown_to_feishu_blocks(md)

    assert [block["block_type"] for block in blocks] == [19, 19, 19, 19]
    assert [block["callout"]["background_color"] for block in blocks] == [2, 5, 3, 6]
    assert _block_text(blocks[0]["_children"][0]) == "段落结构："
    assert _block_text(blocks[0]["_children"][1]) == "理念承接→总体布局→分区域举例。"
    assert _block_text(blocks[1]["_children"][0]) == "✨金句:"
    assert _block_text(blocks[1]["_children"][1]) == "友好温情，是文旅发展的价值所向；文旅资源，是产业提质的立身之本。"
    assert _block_text(blocks[3]["_children"][0]) == "📜事例:"
    assert _block_text(blocks[3]["_children"][1]) == "四大区域廊道建设案例。"


def test_original_text_highlights_emphasis():
    """Original text should convert bold emphasis into colored inline highlights."""
    md = "【原文】普通句。**“引用句”**。**非引用重点**。"
    blocks = markdown_to_feishu_blocks(md)

    elements = blocks[0]["text"]["elements"]
    quoted = next(elem for elem in elements if elem["text_run"]["content"] == "“引用句”")
    plain = next(elem for elem in elements if elem["text_run"]["content"] == "非引用重点")

    assert quoted["text_run"]["text_element_style"]["background_color"] == 3
    assert quoted["text_run"]["text_element_style"]["bold"] is True
    assert plain["text_run"]["text_element_style"]["background_color"] == 3
    assert plain["text_run"]["text_element_style"]["bold"] is True


def test_original_text_highlights_parenthetical_and_italic():
    """Original text should style writing-thought hints and italic gold quotes."""
    md = "【原文】前文。（原文自带括号） （（行文思路））*金句*"
    blocks = markdown_to_feishu_blocks(md)

    elements = blocks[0]["text"]["elements"]
    plain_parenthetical = next(elem for elem in elements if elem["text_run"]["content"] == "前文。（原文自带括号） ")
    parenthetical = next(elem for elem in elements if elem["text_run"]["content"] == "（（行文思路））")
    italic = next(elem for elem in elements if elem["text_run"]["content"] == "金句")

    assert plain_parenthetical["text_run"]["text_element_style"] == {}
    assert parenthetical["text_run"]["text_element_style"]["background_color"] == 5
    assert italic["text_run"]["text_element_style"]["background_color"] == 4
    assert italic["text_run"]["text_element_style"]["italic"] is True


def test_original_section_marker_on_own_line():
    """A standalone original-section marker should style following body lines."""
    md = "【原文】\n正文（原文括号） （（行文思路））**中心句***金句*\n【解析】：\n **段落结构：**\n  说明"
    blocks = markdown_to_feishu_blocks(md)

    body_elements = blocks[1]["text"]["elements"]
    plain_parenthetical = next(elem for elem in body_elements if elem["text_run"]["content"] == "正文（原文括号） ")
    parenthetical = next(elem for elem in body_elements if elem["text_run"]["content"] == "（（行文思路））")
    bold = next(elem for elem in body_elements if elem["text_run"]["content"] == "中心句")
    italic = next(elem for elem in body_elements if elem["text_run"]["content"] == "金句")

    assert plain_parenthetical["text_run"]["text_element_style"] == {}
    assert parenthetical["text_run"]["text_element_style"]["background_color"] == 5
    assert bold["text_run"]["text_element_style"] == {"bold": True, "background_color": 3}
    assert italic["text_run"]["text_element_style"] == {"italic": True, "background_color": 4}
