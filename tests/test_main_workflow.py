"""Unit tests for the main pipeline workflow."""

from unittest.mock import MagicMock, patch

from src.scraper import Article


def _make_article(title: str, source_name: str) -> Article:
    return Article(
        title=title,
        url=f"https://example.com/{title}",
        content=f"Content for {title}",
        source_name=source_name,
        date="2026-06-12",
    )


@patch("src.main.ReadmeGenerator")
@patch("src.main.FeishuUploader")
@patch("src.main.LLMAnalyzer")
@patch("src.main.MultiSourceScraper")
@patch("src.main.load_config")
def test_main_processes_articles_one_by_one(
    mock_load_config,
    mock_scraper_cls,
    mock_analyzer_cls,
    mock_uploader_cls,
    mock_readme_cls,
    monkeypatch,
):
    """Test that each article is analyzed and uploaded separately."""
    from src import main as main_module

    config = {
        "scraper": {"sources": [{"name": "Source 1"}, {"name": "Source 2"}, {"name": "Source 3"}]},
        "llm": {"model": "qwen-plus"},
        "output": {
            "save_raw_articles": False,
            "save_analysis": False,
            "readme_path": "README.md",
            "analysis_file": "output/latest_analysis.md",
        },
        "feishu": {
            "upload_enabled": True,
            "wiki_space_id": "space-123",
            "node_title_template": "每日评论分析 - {date}",
        },
    }
    mock_load_config.return_value = config

    articles = [
        _make_article("文章一", "人民网-人民时评"),
        _make_article("文章二", "南方网-南方日报评论员"),
        _make_article("文章三", "人民网-壹时评"),
    ]

    mock_scraper = MagicMock()
    mock_scraper.scrape.return_value = articles
    mock_scraper_cls.return_value = mock_scraper

    mock_analyzer = MagicMock()
    mock_analyzer.analyze.side_effect = ["analysis-1", "analysis-2", "analysis-3"]
    mock_analyzer_cls.return_value = mock_analyzer

    mock_uploader = MagicMock()
    mock_uploader.upload.side_effect = ["url-1", "url-2", "url-3"]
    mock_uploader_cls.return_value = mock_uploader

    mock_readme = MagicMock()
    mock_readme_cls.return_value = mock_readme

    monkeypatch.setattr("sys.argv", ["main.py", "--config", "config/config.yaml"])
    main_module.main()

    assert mock_analyzer.analyze.call_count == 3
    assert mock_analyzer.analyze.call_args_list[0].args[0] == [articles[0]]
    assert mock_analyzer.analyze.call_args_list[1].args[0] == [articles[1]]
    assert mock_analyzer.analyze.call_args_list[2].args[0] == [articles[2]]

    assert mock_uploader.upload.call_count == 3
    assert mock_uploader.upload.call_args_list[0].args[0] == "文章一"
    assert mock_uploader.upload.call_args_list[1].args[0] == "文章二"
    assert mock_uploader.upload.call_args_list[2].args[0] == "文章三"


@patch("src.main.FeishuUploader")
@patch("src.main.LLMAnalyzer")
@patch("src.main.MultiSourceScraper")
@patch("src.main.load_config")
def test_main_processes_single_url_with_feishu_node_mapping(
    mock_load_config,
    mock_scraper_cls,
    mock_analyzer_cls,
    mock_uploader_cls,
    monkeypatch,
):
    """Single URL mode should map feishu_node to the configured source key."""
    from src import main as main_module

    config = {
        "scraper": {"sources": []},
        "llm": {"model": "qwen-plus"},
        "output": {
            "save_raw_articles": False,
            "save_analysis": False,
            "analysis_file": "output/latest_analysis.md",
        },
        "feishu": {
            "upload_enabled": True,
            "wiki_space_id": "space-123",
        },
    }
    mock_load_config.return_value = config

    article = _make_article("单篇文章", "南方网-南方日报评论员")
    mock_scraper = MagicMock()
    mock_scraper.scrape_url.return_value = article
    mock_scraper_cls.return_value = mock_scraper

    mock_analyzer = MagicMock()
    mock_analyzer.analyze.return_value = "analysis-single"
    mock_analyzer_cls.return_value = mock_analyzer

    mock_uploader = MagicMock()
    mock_uploader.upload.return_value = "uploaded-url"
    mock_uploader_cls.return_value = mock_uploader

    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--config",
            "config/config.yaml",
            "--url",
            "https://example.com/single",
            "--feishu-node",
            "2",
        ],
    )
    main_module.main()

    mock_scraper.scrape_url.assert_called_once_with(
        "https://example.com/single",
        source_name="南方网-南方日报评论员",
    )
    mock_uploader.upload.assert_called_once()
    assert mock_uploader.upload.call_args.kwargs["source_name"] == "南方网-南方日报评论员"


def test_build_article_document_title_returns_clean_title():
    """Document titles should keep only the core article title."""
    from src import main as main_module

    assert main_module._build_article_document_title("南方日报评论员：全力打造“旅游友好型城市”", "2026-06-12") == "全力打造“旅游友好型城市”"
    assert main_module._build_article_document_title("文章标题-2026-06-12", "2026-06-12") == "文章标题"
    assert main_module._build_article_document_title("人民论坛网评___“一县一业”撬动大市场", "2026-06-12") == "“一县一业”撬动大市场"


def test_resolve_feishu_source_name_defaults_to_other():
    """Unknown or missing feishu_node should fall back to the other-source bucket."""
    from src import main as main_module

    assert main_module._resolve_feishu_source_name(1) == "人民网-人民时评"
    assert main_module._resolve_feishu_source_name(2) == "南方网-南方日报评论员"
    assert main_module._resolve_feishu_source_name(3) == "人民论坛网评"
    assert main_module._resolve_feishu_source_name(4) == "其它来源"
    assert main_module._resolve_feishu_source_name(None) == "其它来源"
