"""Multi-source web scraper supporting both static HTML pages and JSON APIs."""

import html
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

import requests
from bs4 import BeautifulSoup


# Beijing timezone (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


def normalize_article_title(title: str) -> str:
    """Normalize article titles to keep only the core title text."""
    cleaned = html.unescape(title or "").strip()
    if not cleaned:
        return ""

    prefix_patterns = [
        r"^南方日报评论员(?:\s*[-_—|｜]{1,}\s*|\s*[：:]\s*)",
        r"^南方日报(?:\s*[-_—|｜]{1,}\s*|\s*[：:]\s*)",
        r"^人民网评(?:\s*[-_—|｜]{1,}\s*|\s*[：:]\s*)",
        r"^人民时评(?:\s*[-_—|｜]{1,}\s*|\s*[：:]\s*)",
        r"^人民论坛网评(?:\s*[-_—|｜]{1,}\s*|\s*[：:]\s*)",
        r"^人民论坛(?:\s*[-_—|｜]{1,}\s*|\s*[：:]\s*)",
    ]
    for pattern in prefix_patterns:
        cleaned = re.sub(pattern, "", cleaned)

    date_patterns = [
        r"^\s*\d{4}[-/年.]\d{1,2}([-/月.]\d{1,2}日?)?\s*[-_|：:]\s*",
        r"\s*[-_|：:]\s*\d{4}[-/年.]\d{1,2}([-/月.]\d{1,2}日?)?\s*$",
        r"\s*[（(]\d{4}[-/年.]\d{1,2}([-/月.]\d{1,2}日?)?[)）]\s*$",
    ]
    source_suffix_patterns = [
        r"\s*[-_|｜|]\s*南方网\s*$",
        r"\s*[-_|｜|]\s*南方日报\s*$",
        r"\s*[-_|｜|]\s*人民论坛网评\s*$",
        r"\s*[-_|｜|]\s*人民论坛\s*$",
        r"\s*[-_|｜|]\s*人民时评\s*$",
        r"\s*[-_|｜|]\s*人民网评\s*$",
        r"\s*[（(]南方网[)）]\s*$",
        r"\s*[（(]南方日报[)）]\s*$",
        r"\s*[（(]人民论坛网评[)）]\s*$",
        r"\s*[（(]人民论坛[)）]\s*$",
        r"\s*[（(]人民时评[)）]\s*$",
        r"\s*[（(]人民网评[)）]\s*$",
        r"\s*[（(]南方网\s*$",
        r"\s*[（(]南方日报\s*$",
        r"\s*[（(]人民论坛网评\s*$",
        r"\s*[（(]人民论坛\s*$",
        r"\s*[（(]人民时评\s*$",
        r"\s*[（(]人民网评\s*$",
    ]

    changed = True
    while changed:
        changed = False
        for pattern in date_patterns + source_suffix_patterns:
            updated = re.sub(pattern, "", cleaned).strip()
            if updated != cleaned:
                cleaned = updated
                changed = True

    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_|：:()（）")
    return cleaned or title.strip()


@dataclass
class Article:
    """Represents a scraped article."""
    title: str
    url: str
    content: str                # Plain text, cleaned
    source_name: str = ""       # Name of the source (e.g. "人民时评")
    content_html: str = ""      # Original HTML snippet
    date: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.now)


class MultiSourceScraper:
    """
    Scrapes articles from multiple sources (HTML pages and JSON APIs).
    Filters articles by a target date (Beijing time by default).
    """

    def __init__(self, config: dict, target_date: Optional[str] = None):
        self.cfg = config["scraper"]
        self.sources = self.cfg.get("sources", [])
        self.request_delay = self.cfg.get("request_delay", 2.0)
        self.request_timeout = self.cfg.get("request_timeout", 30)
        self.max_content_length = self.cfg.get("max_content_length", 50000)
        self.target_date = target_date or datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.cfg.get(
                "user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ),
        })

    def scrape(self) -> List[Article]:
        """Main entry: scrape all sources and return articles for the target date."""
        target_date = self.target_date
        print(f"  Target date: {target_date}")

        all_articles = []
        for source in self.sources:
            source_name = source.get("name", "Unknown")
            source_type = source.get("type", "html")
            print(f"\n  === Source: {source_name} (type: {source_type}) ===")
            try:
                if source_type == "html":
                    articles = self._scrape_html_source(source)
                elif source_type == "api":
                    articles = self._scrape_api_source(source)
                else:
                    print(f"  Unknown source type: {source_type}")
                    continue
                all_articles.extend(articles)
            except Exception as e:
                print(f"  Warning: failed to scrape source {source_name}: {e}")

        print(f"\n  Total articles found for {target_date}: {len(all_articles)}")
        return all_articles

    def scrape_url(self, url: str, source_name: str = "") -> Optional[Article]:
        """Scrape a single article URL using generic title/content extraction."""
        soup = self._fetch_page(url)
        if not soup:
            return None

        title = normalize_article_title(self._extract_title_from_page(soup))
        content = self._extract_content_from_page(soup)
        if not content:
            print(f"  Warning: could not extract article content from {url}")
            return None

        if len(content) > self.max_content_length:
            content = content[:self.max_content_length] + "\n... [truncated]"

        return Article(
            title=title or url,
            url=url,
            content=content,
            source_name=source_name,
            date=self.target_date,
        )

    # ── HTML Source ─────────────────────────────────────────────────

    def _scrape_html_source(self, source: dict) -> List[Article]:
        """Scrape articles from a static HTML listing page."""
        url = source["url"]
        base_url = source.get("base_url", url)
        selectors = source["selectors"]
        target_date = self.target_date

        # Step 1: Fetch listing page
        soup = self._fetch_page(url)
        if not soup:
            return []

        # Step 2: Parse list items
        list_selector = selectors["list_items"]
        items = soup.select(list_selector)
        print(f"  Found {len(items)} items on listing page")

        articles = []
        for item in items:
            # Extract link
            a_tag = item.select_one(selectors.get("article_link", "a"))
            if not a_tag or not a_tag.get("href"):
                continue

            href = a_tag.get("href")
            article_url = urllib.parse.urljoin(base_url, href)
            title = normalize_article_title(a_tag.get_text(strip=True))

            # Extract date
            date_text = ""
            date_sel = selectors.get("date_selector")
            if date_sel:
                date_tag = item.select_one(date_sel)
                if date_tag:
                    date_text = date_tag.get_text(strip=True)

            # Filter: only target-date articles
            # Handle both "2026-06-11" and "2026-06-11 09:33" formats
            if date_text and not date_text.startswith(target_date):
                continue

            if not date_text:
                # If no date selector, check URL for date pattern /YYYY/MMDD/
                if target_date.replace("-", "")[:8] not in article_url:
                    continue

            print(f"  Today's article: {title}")

            # Fetch detail page
            time.sleep(self.request_delay)
            article = self._scrape_article_detail(
                article_url, source.get("detail_selectors"),
                source.get("name", ""), title, date_text,
            )
            if article:
                articles.append(article)

        return articles

    def _scrape_article_detail(
        self, url: str, detail_selectors: Optional[dict],
        source_name: str, fallback_title: str, date: str,
    ) -> Optional[Article]:
        """Fetch and parse an article detail page."""
        soup = self._fetch_page(url)
        if not soup:
            return None

        if not detail_selectors:
            detail_selectors = {}

        # Extract title
        title_sel = detail_selectors.get("title", "h1")
        title_tag = soup.select_one(title_sel)
        title = normalize_article_title(title_tag.get_text(strip=True) if title_tag else fallback_title)

        # Extract content
        content_sel = detail_selectors.get("content", "article")
        content_tag = soup.select_one(content_sel)
        if not content_tag:
            print(f"  Warning: content selector not found for {url}")
            return None

        # Remove script/style tags from content
        for tag in content_tag.select("script, style, noscript"):
            tag.decompose()

        # Get paragraphs, filter empty
        paragraphs = content_tag.select("p")
        if paragraphs:
            lines = []
            for p in paragraphs:
                # Skip empty paragraphs and image-only paragraphs
                text = p.get_text(strip=True)
                if text and len(text) > 2:
                    lines.append(text)
            content = "\n\n".join(lines)
        else:
            content = content_tag.get_text(separator="\n", strip=True)

        # Truncate if too long
        if len(content) > self.max_content_length:
            content = content[:self.max_content_length] + "\n... [truncated]"

        return Article(
            title=title,
            url=url,
            content=content,
            source_name=source_name,
            content_html=str(content_tag),
            date=date,
        )

    # ── API Source ──────────────────────────────────────────────────

    def _scrape_api_source(self, source: dict) -> List[Article]:
        """Scrape articles from a JSON API endpoint."""
        url = source["url"]
        params = source.get("params", {})
        api_config = source["api"]
        method = source.get("method", "post").upper()  # Default to POST
        target_date = self.target_date
        source_headers = source.get("headers", {})
        request_headers = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,zh-TW;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://search.southcn.com",
            "Referer": "https://search.southcn.com/?keyword=%E5%8D%97%E6%96%B9%E6%97%A5%E6%8A%A5%E8%AF%84%E8%AE%BA%E5%91%98&s=time&page=1",
            "X-Requested-With": "XMLHttpRequest",
        }
        request_headers.update(source_headers)

        print(f"  Fetching API ({method}): {url}")
        try:
            if method == "GET":
                resp = self.session.get(
                    url,
                    params=params,
                    headers=request_headers,
                    timeout=self.request_timeout,
                )
            else:
                resp = self.session.post(
                    url,
                    data=params,
                    headers=request_headers,
                    timeout=self.request_timeout,
                )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Warning: API request failed: {e}")
            return []

        # Navigate to the items list using dot-separated path
        items = data
        for key in api_config["items_path"].split("."):
            if key.isdigit():
                items = items[int(key)]
            else:
                items = items.get(key, [])
            if items is None:
                break

        if not items:
            print("  No items found in API response")
            return []

        print(f"  Found {len(items)} items in API response")

        # Filter by target date
        date_field = api_config["date_field"]
        title_filter = api_config.get("title_filter", "")  # Optional: must appear in title
        today_items = [
            item for item in items
            if item.get(date_field, "").startswith(target_date)
        ]
        print(f"  {len(today_items)} items match target date ({target_date})")

        articles = []
        detail_api = api_config.get("detail_api")

        for item in today_items:
            # Title may contain HTML tags (<em> for search highlighting)
            raw_title = item.get(api_config["title_field"], "")
            title = normalize_article_title(BeautifulSoup(raw_title, "lxml").get_text())

            # Apply title filter if configured
            if title_filter and title_filter not in title:
                print(f"  Skipped (title filter): {title[:40]}")
                continue

            # URL
            article_url = item.get(api_config.get("url_field", "url"), "")

            # If detail_api is configured, fetch full content from it
            if detail_api:
                content = self._fetch_api_detail_content(item, detail_api)
            else:
                # Fall back to list API content field
                content_field = api_config.get("content_field", "content")
                content = item
                for key in content_field.split("."):
                    content = content.get(key, "") if isinstance(content, dict) else ""
                content = html.unescape(content) if content else ""

            # Skip articles with no content
            if not content or len(content.strip()) < 10:
                print(f"  Skipped (no content): {title[:40]}")
                continue

            # Truncate if too long
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length] + "\n... [truncated]"

            article = Article(
                title=title,
                url=article_url,
                content=content,
                source_name=source.get("name", ""),
                date=item.get(date_field, ""),
            )
            articles.append(article)
            print(f"  Today's article: {title}")

        return articles

    # ── Helpers ─────────────────────────────────────────────────────

    def _fetch_api_detail_content(self, item: Dict, detail_api: dict) -> str:
        """Fetch full article content from a detail API endpoint.

        detail_api config:
          url: URL template with {field_name} placeholders, e.g.
               "https://news.southcn.com/api/nodePost/getOne?key={key}"
          content_path: dot-separated path to content in response, e.g. "data.post.content"
          content_type: "html" (strip tags) or "text" (plain text). Default "html".
          prefetch:
            Optional request made before the detail request. Its extracted fields are
            merged into the URL template context. Supports the same placeholders.
        """
        context = dict(item)
        context.update(self._extract_context_values(item, detail_api.get("context_extract")))
        prefetch = detail_api.get("prefetch")
        if prefetch:
            fetched_values = self._fetch_detail_prefetch_values(item, prefetch)
            for key, value in fetched_values.items():
                if context.get(key) in (None, ""):
                    context[key] = value

        # Build URL by substituting placeholders from the request context
        url = self._render_template(detail_api["url"], context)
        missing_placeholders = self._find_missing_template_fields(detail_api["url"], context)
        if missing_placeholders:
            print(
                "  Warning: detail API request context missing fields "
                f"{missing_placeholders}; available item keys: {sorted(item.keys())}"
            )
            return ""

        try:
            time.sleep(self.request_delay)
            resp = self.session.get(url, timeout=self.request_timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Warning: detail API request failed for {url}: {e}")
            return ""

        content = self._extract_first_available_value(
            data,
            detail_api.get("content_paths") or [detail_api.get("content_path", "data.post.content")],
        )

        if not content:
            print(
                "  Warning: detail API returned no content. Tried paths: "
                f"{detail_api.get('content_paths') or [detail_api.get('content_path', 'data.post.content')]}"
            )
            return ""

        content = html.unescape(str(content))
        content_type = detail_api.get("content_type", "html")

        # If content is HTML, strip tags and join paragraphs
        if content_type == "html":
            soup = BeautifulSoup(content, "lxml")
            paragraphs = soup.find_all("p")
            if paragraphs:
                lines = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
                content = "\n\n".join(lines)
            else:
                content = soup.get_text(separator="\n", strip=True)

        return content

    def _fetch_detail_prefetch_values(self, item: Dict, prefetch: dict) -> Dict[str, str]:
        """Fetch and extract values needed before the detail API request."""
        method = prefetch.get("method", "GET").upper()
        url = self._render_template(prefetch["url"], item)
        headers = prefetch.get("headers")
        params = prefetch.get("params")

        try:
            time.sleep(self.request_delay)
            if method == "POST":
                resp = self.session.post(url, data=params, headers=headers, timeout=self.request_timeout)
            else:
                resp = self.session.get(url, params=params, headers=headers, timeout=self.request_timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Warning: detail prefetch request failed for {url}: {e}")
            return {}

        values = {}
        for output_key, path in (prefetch.get("extract") or {}).items():
            extracted_value = self._extract_first_available_value(data, path)
            if extracted_value not in (None, ""):
                values[output_key] = extracted_value
            else:
                print(f"  Warning: prefetch could not extract '{output_key}' from paths {path}")
        return values

    def _extract_context_values(self, item: Dict, field_mapping: Optional[Dict]) -> Dict[str, str]:
        """Extract placeholder values from the list item using candidate paths."""
        if not field_mapping:
            return {}

        values = {}
        for output_key, path in field_mapping.items():
            extracted_value = self._extract_first_available_value(item, path)
            if extracted_value not in (None, ""):
                values[output_key] = extracted_value
        return values

    def _render_template(self, template: str, values: Dict) -> str:
        """Fill {field} placeholders in a template string from a dict."""
        rendered = template
        for field_match in re.finditer(r"\{(\w+)\}", template):
            field_name = field_match.group(1)
            rendered = rendered.replace(f"{{{field_name}}}", str(values.get(field_name, "")))
        return rendered

    def _find_missing_template_fields(self, template: str, values: Dict) -> list[str]:
        """Return placeholders that are absent or empty in the context."""
        missing = []
        for field_match in re.finditer(r"\{(\w+)\}", template):
            field_name = field_match.group(1)
            if values.get(field_name) in (None, ""):
                missing.append(field_name)
        return missing

    def _extract_first_available_value(self, data, paths):
        """Try one or more paths and return the first non-empty value."""
        if isinstance(paths, str):
            paths = [paths]

        for path in paths or []:
            extracted_value = self._extract_value_by_path(data, path)
            if extracted_value not in (None, ""):
                return extracted_value
        return None

    def _extract_value_by_path(self, data, path: str):
        """Navigate nested dict/list data with dot-separated paths."""
        current = data
        for key in path.split("."):
            if isinstance(current, list):
                if not key.isdigit():
                    return None
                index = int(key)
                if index >= len(current):
                    return None
                current = current[index]
                continue
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        return current

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a URL and return a BeautifulSoup object, or None on error."""
        try:
            resp = self.session.get(url, timeout=self.request_timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            print(f"  Warning: HTTP error for {url}: {e}")
            return None

    def _extract_title_from_page(self, soup: BeautifulSoup) -> str:
        """Extract a best-effort article title from a page."""
        for selector in ("h1", "title"):
            tag = soup.select_one(selector)
            if tag:
                text = tag.get_text(strip=True)
                if text:
                    return text
        return ""

    def _extract_content_from_page(self, soup: BeautifulSoup) -> str:
        """Extract best-effort article body text from common content containers."""
        selectors = (
            "article",
            "main",
            '[role="main"]',
            ".article",
            ".article-content",
            ".content",
            ".post-content",
            ".entry-content",
            "#content",
        )

        content_tag = None
        for selector in selectors:
            candidate = soup.select_one(selector)
            if candidate and candidate.get_text(strip=True):
                content_tag = candidate
                break

        if content_tag is None:
            paragraphs = [
                p.get_text(strip=True)
                for p in soup.select("p")
                if p.get_text(strip=True) and len(p.get_text(strip=True)) > 2
            ]
            return "\n\n".join(paragraphs)

        for tag in content_tag.select("script, style, noscript"):
            tag.decompose()

        paragraphs = [
            p.get_text(strip=True)
            for p in content_tag.select("p")
            if p.get_text(strip=True) and len(p.get_text(strip=True)) > 2
        ]
        if paragraphs:
            return "\n\n".join(paragraphs)
        return content_tag.get_text(separator="\n", strip=True)
