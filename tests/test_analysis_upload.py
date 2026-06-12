"""Tests for uploading existing analysis markdown files to Feishu."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src import main as main_module


def test_render_analysis_file_includes_metadata():
    """Saved analysis files should preserve source metadata for later uploads."""
    content = main_module._render_analysis_file(
        title="文章一",
        source_name="人民网-人民时评",
        article_url="https://example.com/a1",
        target_date="2026-06-12",
        article_date="2026-06-11",
        body="# 文章一\n\n内容",
    )

    assert "source_name: 人民网-人民时评" in content
    assert "article_url: https://example.com/a1" in content
    assert "date: '2026-06-11'" in content
    assert content.startswith("---\n")


def test_normalize_analysis_header_replaces_model_date():
    """The saved/uploaded body should use scraped metadata instead of model-guessed dates."""
    body = (
        "# 南方日报评论员：赋能千行百业 智向美好未来\n"
        "> 来源：南方日报 ｜ 日期：2024年 ｜ https://wrong.example.com\n\n"
        "正文"
    )

    normalized = main_module._normalize_analysis_header(
        body,
        source_name="南方网-南方日报评论员",
        article_url="https://news.southcn.com/node_ac2b0b62a4/24a27e6c7a.shtml",
        article_date="2026-06-09",
    )

    assert "> 来源：南方日报 ｜ 日期：2026-06-09 ｜ https://news.southcn.com/node_ac2b0b62a4/24a27e6c7a.shtml" in normalized


@patch("src.main.FeishuUploader")
def test_upload_analysis_directory_uses_metadata_source(mock_uploader_cls, tmp_path):
    """Uploading saved analysis files should route them to the matching Feishu directory."""
    mock_uploader = MagicMock()
    mock_uploader.upload.return_value = "https://feishu.example/wiki/node-1"
    mock_uploader_cls.return_value = mock_uploader

    analysis_file = tmp_path / "01_文章一.md"
    analysis_file.write_text(
        "---\n"
        "title: 文章一\n"
        "source_name: 人民网-人民时评\n"
        "article_url: https://example.com/a1\n"
        "date: 2026-06-12\n"
        "---\n\n"
        "# 文章一\n\n分析正文\n",
        encoding="utf-8",
    )

    config = {
        "scraper": {
            "sources": [
                {"name": "人民网-人民时评"},
                {"name": "南方网-南方日报评论员"},
                {"name": "人民网-壹时评"},
            ]
        },
        "feishu": {
            "upload_enabled": True,
            "wiki_space_id": "space-1",
            "parent_node_token": "",
            "source_parent_node_tokens": {"人民网-人民时评": "people-token"},
        },
    }

    main_module._upload_analysis_directory(tmp_path, config)

    assert mock_uploader.upload.call_count == 1
    assert mock_uploader.upload.call_args.kwargs["source_name"] == "人民网-人民时评"
    assert mock_uploader.upload.call_args.args[0] == "文章一"


@patch("src.main.FeishuUploader")
def test_upload_analysis_directory_infers_source_from_filename(mock_uploader_cls, tmp_path):
    """Legacy files without metadata should still infer the source from the file name."""
    mock_uploader = MagicMock()
    mock_uploader.upload.return_value = "https://feishu.example/wiki/node-2"
    mock_uploader_cls.return_value = mock_uploader

    analysis_file = tmp_path / "01_南方日报评论员：以一流营商环境助推高质量发展.md"
    analysis_file.write_text("# 南方日报评论员：以一流营商环境助推高质量发展-2026-06-10\n\n分析正文\n", encoding="utf-8")

    config = {
        "scraper": {
            "sources": [
                {"name": "人民网-人民时评"},
                {"name": "南方网-南方日报评论员"},
                {"name": "人民网-壹时评"},
            ]
        },
        "feishu": {
            "upload_enabled": True,
            "wiki_space_id": "space-1",
            "parent_node_token": "",
            "source_parent_node_tokens": {"南方网-南方日报评论员": "south-token"},
        },
    }

    main_module._upload_analysis_directory(tmp_path, config)

    assert mock_uploader.upload.call_count == 1
    assert mock_uploader.upload.call_args.kwargs["source_name"] == "南方网-南方日报评论员"
    assert mock_uploader.upload.call_args.args[0] == "以一流营商环境助推高质量发展"


def test_normalize_analysis_title_rewrites_h1_to_clean_title():
    """Analysis markdown should keep a clean H1 without source prefix or date."""
    body = "# 南方日报评论员：全力打造“旅游友好型城市”-2026-06-12\n\n正文"

    normalized = main_module._normalize_analysis_title(body, "南方日报评论员：全力打造“旅游友好型城市”")

    assert normalized.startswith("# 全力打造“旅游友好型城市”\n")


def test_normalize_analysis_title_removes_duplicate_leading_h1():
    """Analysis markdown should drop the duplicated model-generated title line."""
    body = "# 全力打造“旅游友好型城市”\n\n# 南方日报评论员：全力打造“旅游友好型城市”\n> 来源：南方日报 ｜ 日期：2026-06-12 ｜ https://example.com\n"

    normalized = main_module._normalize_analysis_title(body, "南方日报评论员：全力打造“旅游友好型城市”")

    assert normalized.count("# 全力打造“旅游友好型城市”") == 1
    assert "南方日报评论员：" not in normalized
