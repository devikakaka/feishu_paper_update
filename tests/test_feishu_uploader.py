"""Unit tests for FeishuUploader."""

from unittest.mock import MagicMock, patch

from src.feishu_uploader import FeishuUploader


@patch("src.feishu_uploader.FeishuClient")
@patch("src.feishu_uploader.markdown_to_feishu_blocks")
def test_upload_uses_source_specific_directory(mock_blocks, mock_client_cls):
    """Uploads should use the mapped parent node token for a known source."""
    mock_blocks.return_value = [{"block_type": 2, "text": {"elements": [], "style": {}}}]

    mock_client = MagicMock()
    mock_client.request.side_effect = [
        {"data": {"node": {"node_token": "node-1", "obj_token": "doc-1"}}},
        {"code": 0},
    ]
    mock_client_cls.return_value = mock_client

    config = {
        "feishu": {
            "base_url": "https://open.feishu.cn",
            "wiki_space_id": "space-1",
            "app_id": "app-1",
            "app_secret": "secret-1",
            "parent_node_token": "default-token",
            "source_parent_node_tokens": {
                "人民网-人民时评": "people-token",
            },
        }
    }

    uploader = FeishuUploader(config)
    url = uploader.upload("文章一-2026-06-12", "# demo", source_name="人民网-人民时评")

    assert url.endswith("/wiki/node-1")
    assert mock_client.request.call_args_list[0].kwargs["json"]["parent_node_token"] == "people-token"


@patch("src.feishu_uploader.FeishuClient")
@patch("src.feishu_uploader.markdown_to_feishu_blocks")
def test_upload_falls_back_to_default_directory(mock_blocks, mock_client_cls):
    """Uploads should fall back to the default parent token when no source mapping exists."""
    mock_blocks.return_value = [{"block_type": 2, "text": {"elements": [], "style": {}}}]

    mock_client = MagicMock()
    mock_client.request.side_effect = [
        {"data": {"node": {"node_token": "node-2", "obj_token": "doc-2"}}},
        {"code": 0},
    ]
    mock_client_cls.return_value = mock_client

    config = {
        "feishu": {
            "base_url": "https://open.feishu.cn",
            "wiki_space_id": "space-1",
            "app_id": "app-1",
            "app_secret": "secret-1",
            "parent_node_token": "default-token",
            "source_parent_node_tokens": {},
        }
    }

    uploader = FeishuUploader(config)
    uploader.upload("文章二-2026-06-12", "# demo", source_name="未知来源")

    assert mock_client.request.call_args_list[0].kwargs["json"]["parent_node_token"] == "default-token"


@patch("src.feishu_uploader.FeishuClient")
@patch("src.feishu_uploader.markdown_to_feishu_blocks")
def test_upload_uses_descendant_api_for_tables(mock_blocks, mock_client_cls):
    """Table blocks should be uploaded through the descendant API as real tables."""
    mock_blocks.return_value = [
        {"block_type": 2, "text": {"elements": [], "style": {}}},
        {
            "block_type": 31,
            "table": {"property": {"row_size": 2, "column_size": 2}},
            "_table_rows": [
                [
                    {"text": "列1", "elements": [{"text_run": {"content": "列1", "text_element_style": {}}}]},
                    {"text": "列2", "elements": [{"text_run": {"content": "列2", "text_element_style": {}}}]},
                ],
                [
                    {"text": "甲", "elements": [{"text_run": {"content": "甲", "text_element_style": {}}}]},
                    {"text": "乙", "elements": [{"text_run": {"content": "乙", "text_element_style": {}}}]},
                ],
            ],
        },
    ]

    mock_client = MagicMock()
    mock_client.request.side_effect = [
        {"data": {"node": {"node_token": "node-3", "obj_token": "doc-3"}}},
        {"code": 0},
        {"code": 0},
    ]
    mock_client_cls.return_value = mock_client

    config = {
        "feishu": {
            "base_url": "https://open.feishu.cn",
            "wiki_space_id": "space-1",
            "app_id": "app-1",
            "app_secret": "secret-1",
            "parent_node_token": "default-token",
            "source_parent_node_tokens": {},
        }
    }

    uploader = FeishuUploader(config)
    uploader.upload("文章三-2026-06-12", "# demo", source_name="未知来源")

    children_calls = [
        call for call in mock_client.request.call_args_list
        if "/open-apis/docx/v1/documents/" in call.args[1]
        and call.args[1].endswith("/children")
    ]
    descendant_calls = [
        call for call in mock_client.request.call_args_list
        if "/open-apis/docx/v1/documents/" in call.args[1]
        and call.args[1].endswith("/descendant")
    ]

    assert len(children_calls) == 1
    assert len(descendant_calls) == 1

    first_children = children_calls[0].kwargs["json"]["children"]
    assert first_children[0]["block_type"] == 2

    payload = descendant_calls[0].kwargs["json"]
    assert len(payload["children_id"]) == 1
    assert payload["descendants"][0]["block_type"] == 31
    assert payload["descendants"][0]["children"] == ["cell_2", "cell_4", "cell_6", "cell_8"]
    assert payload["descendants"][1]["block_type"] == 32
    assert payload["descendants"][2]["block_type"] == 2
    assert payload["descendants"][2]["text"]["elements"][0]["text_run"]["content"] == "列1"


@patch("src.feishu_uploader.FeishuClient")
@patch("src.feishu_uploader.markdown_to_feishu_blocks")
def test_upload_uses_descendant_api_for_callouts(mock_blocks, mock_client_cls):
    """Callout blocks should be uploaded through the descendant API."""
    mock_blocks.return_value = [
        {
            "block_type": 19,
            "callout": {"background_color": 5, "border_color": 5},
            "_children": [
                {
                    "block_type": 2,
                    "text": {
                        "elements": [{"text_run": {"content": "说明", "text_element_style": {}}}],
                        "style": {},
                    },
                }
            ],
        }
    ]

    mock_client = MagicMock()
    mock_client.request.side_effect = [
        {"data": {"node": {"node_token": "node-4", "obj_token": "doc-4"}}},
        {"code": 0},
    ]
    mock_client_cls.return_value = mock_client

    config = {
        "feishu": {
            "base_url": "https://open.feishu.cn",
            "wiki_space_id": "space-1",
            "app_id": "app-1",
            "app_secret": "secret-1",
            "parent_node_token": "default-token",
            "source_parent_node_tokens": {},
        }
    }

    uploader = FeishuUploader(config)
    uploader.upload("文章四-2026-06-12", "# demo", source_name="未知来源")

    descendant_calls = [
        call for call in mock_client.request.call_args_list
        if "/open-apis/docx/v1/documents/" in call.args[1]
        and call.args[1].endswith("/descendant")
    ]
    assert len(descendant_calls) == 1

    payload = descendant_calls[0].kwargs["json"]
    assert payload["descendants"][0]["block_type"] == 19
    assert payload["descendants"][1]["block_type"] == 2
    assert payload["descendants"][1]["text"]["elements"][0]["text_run"]["content"] == "说明"


def test_build_table_descendant_payload():
    """Descendant payload should encode table -> table_cell -> text hierarchy."""
    uploader = FeishuUploader.__new__(FeishuUploader)

    table_block = {
        "block_type": 31,
        "table": {"property": {"row_size": 2, "column_size": 2}},
        "_table_rows": [
            [
                {"text": "A", "elements": [{"text_run": {"content": "A", "text_element_style": {}}}]},
                {"text": "B", "elements": [{"text_run": {"content": "B", "text_element_style": {"bold": True}}}]},
            ],
            [
                {"text": "1", "elements": [{"text_run": {"content": "1", "text_element_style": {}}}]},
                {"text": "2", "elements": [{"text_run": {"content": "2", "text_element_style": {"italic": True}}}]},
            ],
        ],
    }

    payload = uploader._build_table_descendant_payload(table_block)

    assert payload["children_id"] == ["table_1"]
    assert payload["descendants"][0]["table"]["property"]["row_size"] == 2
    assert payload["descendants"][0]["table"]["property"]["column_size"] == 2
    assert payload["descendants"][0]["children"] == ["cell_2", "cell_4", "cell_6", "cell_8"]
    assert payload["descendants"][1]["children"] == ["cell_text_3"]
    assert payload["descendants"][2]["text"]["elements"][0]["text_run"]["content"] == "A"
    assert payload["descendants"][5]["text"]["elements"][0]["text_run"]["text_element_style"]["bold"] is True
    assert payload["descendants"][8]["text"]["elements"][0]["text_run"]["text_element_style"]["italic"] is True
    assert payload["descendants"][0]["table"]["property"]["column_width"] == [160, 160]


def test_estimate_column_widths_prefers_wider_columns():
    """Wider content should produce wider table columns within sane bounds."""
    uploader = FeishuUploader.__new__(FeishuUploader)
    rows = [
        [{"text": "短"}, {"text": "这一列内容明显更长一些"}],
        [{"text": "中等长度"}, {"text": "再长一点点内容用于拉开列宽"}],
    ]

    widths = uploader._estimate_column_widths(rows, 2)

    assert widths[0] == 160
    assert widths[1] > widths[0]
    assert widths[1] <= 420


def test_build_callout_descendant_payload():
    """Callout payload should encode callout -> child blocks hierarchy."""
    uploader = FeishuUploader.__new__(FeishuUploader)
    callout_block = {
        "block_type": 19,
        "callout": {"background_color": 5, "border_color": 5},
        "_children": [
            {"block_type": 2, "text": {"elements": [{"text_run": {"content": "分析内容", "text_element_style": {}}}], "style": {}}},
            {"block_type": 12, "bullet": {"elements": [{"text_run": {"content": "要点", "text_element_style": {}}}], "style": {}}},
        ],
    }

    payload = uploader._build_callout_descendant_payload(callout_block)

    assert payload["children_id"] == ["callout_1"]
    assert payload["descendants"][0]["block_type"] == 19
    assert payload["descendants"][0]["children"] == ["block_2_2", "block_12_3"]
    assert payload["descendants"][0]["callout"] == {"background_color": 5, "border_color": 5}
    assert payload["descendants"][1]["block_type"] == 2
    assert payload["descendants"][2]["block_type"] == 12
