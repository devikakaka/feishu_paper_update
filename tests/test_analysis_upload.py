"""Tests for uploading existing analysis markdown files to Feishu."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src import main as main_module


def test_render_analysis_file_includes_metadata():
    """Saved analysis files should preserve source metadata for later uploads."""
    content = main_module._render_analysis_file(
        title="文章一-2026-06-12",
        source_name="人民网-人民时评",
        article_url="https://example.com/a1",
        target_date="2026-06-12",
        body="# 文章一\n\n内容",
    )

    assert "source_name: 人民网-人民时评" in content
    assert "article_url: https://example.com/a1" in content
    assert content.startswith("---\n")


@patch("src.main.FeishuUploader")
def test_upload_analysis_directory_uses_metadata_source(mock_uploader_cls, tmp_path):
    """Uploading saved analysis files should route them to the matching Feishu directory."""
    mock_uploader = MagicMock()
    mock_uploader.upload.return_value = "https://feishu.example/wiki/node-1"
    mock_uploader_cls.return_value = mock_uploader

    analysis_file = tmp_path / "01_文章一.md"
    analysis_file.write_text(
        "---\n"
        "title: 文章一-2026-06-12\n"
        "source_name: 人民网-人民时评\n"
        "article_url: https://example.com/a1\n"
        "date: 2026-06-12\n"
        "---\n\n"
        "# 文章一-2026-06-12\n\n分析正文\n",
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
    assert mock_uploader.upload.call_args.args[0] == "文章一-2026-06-12"


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
    assert mock_uploader.upload.call_args.args[0] == "南方日报评论员：以一流营商环境助推高质量发展-2026-06-10"