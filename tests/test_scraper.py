"""Unit tests for the multi-source scraper module."""

import pytest
from unittest.mock import patch, MagicMock

from src.scraper import MultiSourceScraper, Article, BEIJING_TZ
from datetime import datetime


@pytest.fixture
def scraper_config():
    """Create a test scraper config with multi-source setup."""
    return {
        "scraper": {
            "sources": [
                {
                    "name": "Test HTML Source",
                    "type": "html",
                    "url": "https://example.com/articles",
                    "base_url": "https://example.com",
                    "selectors": {
                        "list_items": "ul li",
                        "article_link": "a",
                        "date_selector": "i.gray",
                    },
                    "detail_selectors": {
                        "title": "h1",
                        "content": "div.content",
                    },
                },
            ],
            "request_delay": 0.01,
            "request_timeout": 5,
            "user_agent": "TestBot/1.0",
            "max_content_length": 1000,
        }
    }


@pytest.fixture
def api_scraper_config():
    """Create a test scraper config with API source."""
    return {
        "scraper": {
            "sources": [
                {
                    "name": "Test API Source",
                    "type": "api",
                    "url": "https://api.example.com/search",
                    "params": {"keyword": "test", "page": 1},
                    "api": {
                        "items_path": "data.list",
                        "title_field": "title",
                        "content_field": "post.content",
                        "date_field": "pub_time",
                        "url_field": "url",
                    },
                },
            ],
            "request_delay": 0.01,
            "request_timeout": 5,
            "user_agent": "TestBot/1.0",
            "max_content_length": 1000,
        }
    }


def test_article_dataclass():
    """Test Article dataclass with source_name."""
    article = Article(
        title="Test Title",
        url="https://example.com/test",
        content="Test content",
        source_name="Test Source",
        date="2026-06-11",
    )
    assert article.title == "Test Title"
    assert article.source_name == "Test Source"
    assert article.date == "2026-06-11"


def test_scraper_init(scraper_config):
    """Test MultiSourceScraper initialization."""
    scraper = MultiSourceScraper(scraper_config)
    assert len(scraper.sources) == 1
    assert scraper.sources[0]["name"] == "Test HTML Source"


@patch("src.scraper.requests.Session")
def test_html_source_filters_by_date(mock_session, scraper_config):
    """Test that HTML source only returns today's articles."""
    today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
    yesterday = "2020-01-01"

    # Mock listing page
    listing_resp = MagicMock()
    listing_resp.text = f"""
    <html><body><ul>
        <li><a href="/article/today">Today Article</a><i class="gray">{today}</i></li>
        <li><a href="/article/old">Old Article</a><i class="gray">{yesterday}</i></li>
    </ul></body></html>
    """
    listing_resp.apparent_encoding = "utf-8"
    listing_resp.raise_for_status = MagicMock()

    # Mock detail page
    detail_resp = MagicMock()
    detail_resp.text = """
    <html><body>
        <h1>Today Article Title</h1>
        <div class="content"><p>Content paragraph 1</p><p>Content paragraph 2</p></div>
    </body></html>
    """
    detail_resp.apparent_encoding = "utf-8"
    detail_resp.raise_for_status = MagicMock()

    mock_session_instance = MagicMock()

    def get_side_effect(url, **kwargs):
        if "example.com/articles" in url:
            return listing_resp
        return detail_resp

    mock_session_instance.get.side_effect = get_side_effect
    mock_session.return_value = mock_session_instance

    scraper = MultiSourceScraper(scraper_config)
    articles = scraper.scrape()

    # Only today's article should be returned
    assert len(articles) == 1
    assert "Today Article" in articles[0].title


@patch("src.scraper.requests.Session")
def test_html_source_filters_by_target_date(mock_session, scraper_config):
    """Test that HTML source respects an explicit target date."""
    target_date = "2026-06-10"
    other_date = "2026-06-11"

    listing_resp = MagicMock()
    listing_resp.text = f"""
    <html><body><ul>
        <li><a href="/article/target">Target Article</a><i class="gray">{target_date}</i></li>
        <li><a href="/article/other">Other Article</a><i class="gray">{other_date}</i></li>
    </ul></body></html>
    """
    listing_resp.apparent_encoding = "utf-8"
    listing_resp.raise_for_status = MagicMock()

    detail_resp = MagicMock()
    detail_resp.text = """
    <html><body>
        <h1>Target Article Title</h1>
        <div class="content"><p>Target content</p></div>
    </body></html>
    """
    detail_resp.apparent_encoding = "utf-8"
    detail_resp.raise_for_status = MagicMock()

    mock_session_instance = MagicMock()

    def get_side_effect(url, **kwargs):
        if "example.com/articles" in url:
            return listing_resp
        return detail_resp

    mock_session_instance.get.side_effect = get_side_effect
    mock_session.return_value = mock_session_instance

    scraper = MultiSourceScraper(scraper_config, target_date=target_date)
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].date == target_date


@patch("src.scraper.requests.Session")
def test_api_source_filters_by_date(mock_session, api_scraper_config):
    """Test that API source only returns today's articles."""
    today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "list": [
                {
                    "title": "Today Article",
                    "pub_time": today,
                    "url": "https://example.com/today",
                    "post": {"content": "Today's content"},
                },
                {
                    "title": "Old Article",
                    "pub_time": "2020-01-01",
                    "url": "https://example.com/old",
                    "post": {"content": "Old content"},
                },
            ]
        }
    }
    mock_resp.raise_for_status = MagicMock()

    mock_session_instance = MagicMock()
    mock_session_instance.post.return_value = mock_resp
    mock_session.return_value = mock_session_instance

    scraper = MultiSourceScraper(api_scraper_config)
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].title == "Today Article"
    assert articles[0].content == "Today's content"


@patch("src.scraper.requests.Session")
def test_api_source_filters_by_target_date(mock_session, api_scraper_config):
    """Test that API source respects an explicit target date."""
    target_date = "2026-06-10"

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "list": [
                {
                    "title": "Target Article",
                    "pub_time": target_date,
                    "url": "https://example.com/target",
                    "post": {"content": "Target content"},
                },
                {
                    "title": "Other Article",
                    "pub_time": "2026-06-11",
                    "url": "https://example.com/other",
                    "post": {"content": "Other content"},
                },
            ]
        }
    }
    mock_resp.raise_for_status = MagicMock()

    mock_session_instance = MagicMock()
    mock_session_instance.post.return_value = mock_resp
    mock_session.return_value = mock_session_instance

    scraper = MultiSourceScraper(api_scraper_config, target_date=target_date)
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].title == "Target Article"
    assert articles[0].date == target_date


@patch("src.scraper.requests.Session")
def test_api_source_sends_custom_headers(mock_session, api_scraper_config):
    """Test that API source forwards configured headers to the POST request."""
    today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    api_scraper_config["scraper"]["sources"][0]["headers"] = {
        "Origin": "https://search.southcn.com",
        "Referer": "https://search.southcn.com/?keyword=test",
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "list": [
                {
                    "title": "Today Article",
                    "pub_time": today,
                    "url": "https://example.com/today",
                    "post": {"content": "Today's content"},
                },
            ]
        }
    }
    mock_resp.raise_for_status = MagicMock()

    mock_session_instance = MagicMock()
    mock_session_instance.post.return_value = mock_resp
    mock_session.return_value = mock_session_instance

    scraper = MultiSourceScraper(api_scraper_config)
    articles = scraper.scrape()

    assert len(articles) == 1
    _, kwargs = mock_session_instance.post.call_args
    assert kwargs["headers"]["Origin"] == "https://search.southcn.com"
    assert kwargs["headers"]["Referer"] == "https://search.southcn.com/?keyword=test"
    assert kwargs["headers"]["X-Requested-With"] == "XMLHttpRequest"


@patch("src.scraper.requests.Session")
def test_api_source_strips_html_from_title(mock_session, api_scraper_config):
    """Test that HTML tags are stripped from API titles."""
    today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "list": [
                {
                    "title": "<em>南方</em><em>日报</em>评论员：标题",
                    "pub_time": today,
                    "url": "https://example.com/test",
                    "post": {"content": "这是一篇南方日报评论员文章的正文内容，足够长了。"},
                },
            ]
        }
    }
    mock_resp.raise_for_status = MagicMock()

    mock_session_instance = MagicMock()
    mock_session_instance.post.return_value = mock_resp
    mock_session.return_value = mock_session_instance

    scraper = MultiSourceScraper(api_scraper_config)
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].title == "标题"


def test_normalize_article_title_removes_source_and_date_variants():
    """Title normalization should strip source labels and dates across common formats."""
    from src.scraper import normalize_article_title

    assert normalize_article_title("南方日报评论员：全力打造“旅游友好型城市”") == "全力打造“旅游友好型城市”"
    assert normalize_article_title("人民论坛网评___“一县一业”撬动大市场") == "“一县一业”撬动大市场"
    assert normalize_article_title("人民论坛网评 | “一县一业”撬动大市场") == "“一县一业”撬动大市场"
    assert normalize_article_title("考出“三夏”好成绩（人民时评）") == "考出“三夏”好成绩"
    assert normalize_article_title("考出“三夏”好成绩（人民时评") == "考出“三夏”好成绩"
    assert normalize_article_title("全力打造“旅游友好型城市”-2026-06-12") == "全力打造“旅游友好型城市”"


@patch("src.scraper.requests.Session")
def test_html_source_handles_http_error(mock_session, scraper_config):
    """Test graceful handling of HTTP errors."""
    import requests

    mock_session_instance = MagicMock()
    mock_session_instance.get.side_effect = requests.RequestException("Connection error")
    mock_session.return_value = mock_session_instance

    scraper = MultiSourceScraper(scraper_config)
    articles = scraper.scrape()

    # Should return empty list, not raise
    assert articles == []


@patch("src.scraper.requests.Session")
def test_content_extracts_paragraphs(mock_session, scraper_config):
    """Test that content extraction gets paragraphs and filters empty ones."""
    today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    listing_resp = MagicMock()
    listing_resp.text = f"""
    <html><body><ul>
        <li><a href="/article/1">Article</a><i class="gray">{today}</i></li>
    </ul></body></html>
    """
    listing_resp.apparent_encoding = "utf-8"
    listing_resp.raise_for_status = MagicMock()

    detail_resp = MagicMock()
    detail_resp.text = """
    <html><body>
        <h1>Test Title</h1>
        <div class="content">
            <p>First paragraph.</p>
            <p></p>
            <p>  </p>
            <p>Second paragraph.</p>
            <script>var x = 1;</script>
            <p>Third paragraph.</p>
        </div>
    </body></html>
    """
    detail_resp.apparent_encoding = "utf-8"
    detail_resp.raise_for_status = MagicMock()

    mock_session_instance = MagicMock()

    def get_side_effect(url, **kwargs):
        if "example.com/articles" in url:
            return listing_resp
        return detail_resp

    mock_session_instance.get.side_effect = get_side_effect
    mock_session.return_value = mock_session_instance

    scraper = MultiSourceScraper(scraper_config)
    articles = scraper.scrape()

    assert len(articles) == 1
    # Should have 3 paragraphs, empty ones filtered, script removed
    content = articles[0].content
    assert "First paragraph" in content
    assert "Second paragraph" in content
    assert "Third paragraph" in content
    assert "var x = 1" not in content


@patch("src.scraper.requests.Session")
def test_scrape_url_extracts_single_article(mock_session, scraper_config):
    """Single URL mode should extract title and paragraphs from a detail page."""
    detail_resp = MagicMock()
    detail_resp.text = """
    <html><head><title>备用标题</title></head><body>
        <article>
            <h1>单篇文章标题</h1>
            <p>第一段内容。</p>
            <p>第二段内容。</p>
        </article>
    </body></html>
    """
    detail_resp.apparent_encoding = "utf-8"
    detail_resp.raise_for_status = MagicMock()

    mock_session_instance = MagicMock()
    mock_session_instance.get.return_value = detail_resp
    mock_session.return_value = mock_session_instance

    scraper = MultiSourceScraper(scraper_config, target_date="2026-06-12")
    article = scraper.scrape_url("https://example.com/one", source_name="其它来源")

    assert article is not None
    assert article.title == "单篇文章标题"
    assert article.source_name == "其它来源"
    assert article.url == "https://example.com/one"
    assert article.content == "第一段内容。\n\n第二段内容。"


def test_extract_first_available_value():
    """Helper should return the first non-empty value from candidate paths."""
    scraper = MultiSourceScraper.__new__(MultiSourceScraper)
    data = {"data": {"content": "", "post": {"content": "正文"}}}

    assert scraper._extract_first_available_value(data, ["data.content", "data.post.content"]) == "正文"


@patch("src.scraper.requests.Session")
def test_api_source_fetches_detail_content_by_item_key(mock_session, api_scraper_config):
    """Southcn detail API should use the list item's key and return full post content."""
    today = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
    api_scraper_config["scraper"]["sources"][0]["api"].pop("content_field", None)
    api_scraper_config["scraper"]["sources"][0]["api"]["detail_api"] = {
        "context_extract": {"key": ["key"]},
        "url": "https://news.southcn.com/api/nodePost/getOne?key={key}",
        "content_path": "data.post.content",
        "content_type": "html",
    }

    list_resp = MagicMock()
    list_resp.json.return_value = {
        "data": {
            "list": [
                {
                    "title": "南方日报评论员：标题",
                    "pub_time": today,
                    "url": "https://example.com/test",
                    "key": "e19b4e996a",
                }
            ]
        }
    }
    list_resp.raise_for_status = MagicMock()

    detail_resp = MagicMock()
    detail_resp.json.return_value = {
        "data": {
            "post": {
                "content": "<p>第一段完整正文。</p><p>第二段完整正文。</p>"
            }
        }
    }
    detail_resp.raise_for_status = MagicMock()

    mock_session_instance = MagicMock()
    mock_session_instance.post.return_value = list_resp

    def get_side_effect(url, **kwargs):
        if "getOne" in url:
            assert "key=e19b4e996a" in url
            return detail_resp
        raise AssertionError(f"Unexpected URL: {url}")

    mock_session_instance.get.side_effect = get_side_effect
    mock_session.return_value = mock_session_instance

    scraper = MultiSourceScraper(api_scraper_config)
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].content == "第一段完整正文。\n\n第二段完整正文。"
