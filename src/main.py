#!/usr/bin/env python3
"""Main entry point: scrape -> analyze -> publish pipeline."""

import argparse
import sys
import re
from datetime import datetime
from pathlib import Path

import yaml

from src.config_loader import load_config
from src.scraper import BEIJING_TZ, MultiSourceScraper
from src.llm_analyzer import LLMAnalyzer
from src.feishu_uploader import FeishuUploader
from src.readme_generator import ReadmeGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Article Scraper + Qwen Analyzer + Feishu Publisher"
    )
    parser.add_argument("--config", default="config/config.yaml", help="Path to config file")
    parser.add_argument(
        "--date",
        dest="target_date",
        help="Target article date in YYYY-MM-DD (defaults to Beijing today)",
    )
    parser.add_argument(
        "--update-readme",
        action="store_true",
        help="Rewrite README.md with the latest analysis",
    )
    parser.add_argument(
        "--upload-analysis-dir",
        dest="upload_analysis_dir",
        help="Upload existing markdown files from an analysis directory to Feishu",
    )
    parser.add_argument("--url", help="Scrape a single article URL instead of daily source listings")
    parser.add_argument(
        "--feishu-node",
        type=int,
        choices=(1, 2, 3, 4),
        help="Feishu source node for --url mode: 1=人民网-人民时评, 2=南方网-南方日报评论员, 3=人民论坛网评, 4=其它来源",
    )
    parser.add_argument("--skip-feishu", action="store_true", help="Skip Feishu upload even if configured")
    parser.add_argument("--dry-run", action="store_true", help="Scrape only, don't analyze or upload")
    args = parser.parse_args()

    target_date = _resolve_target_date(args.target_date)

    # ── Step 1: Load configuration ──────────────────────────────────
    print("📋 Loading configuration...")
    config = load_config(args.config)
    sources = config["scraper"].get("sources", [])
    print(f"   Sources: {len(sources)}")
    for s in sources:
        print(f"     - {s.get('name', 'Unknown')} ({s.get('type', 'html')})")
    print(f"   LLM model: {config['llm']['model']}")

    if args.upload_analysis_dir:
        print("\n📤 Uploading existing analysis files to Feishu...")
        _upload_analysis_directory(Path(args.upload_analysis_dir), config)
        print("\n🎉 Analysis upload complete!")
        return

    if args.url:
        print("\n🔗 Scraping a single article URL...")
        _process_single_url(args.url, args.feishu_node, config, target_date, skip_feishu=args.skip_feishu, dry_run=args.dry_run)
        print("\n🎉 Single URL pipeline complete!")
        return

    # ── Step 2: Scrape articles ─────────────────────────────────────
    print("\n🕷️  Scraping articles...")
    scraper = MultiSourceScraper(config, target_date=target_date)
    articles = scraper.scrape()
    print(f"   Found {len(articles)} articles")

    if not articles:
        print("⚠️  No articles found. Exiting gracefully.")
        sys.exit(0)

    # ── Step 3: Save raw articles (optional) ────────────────────────
    if config["output"].get("save_raw_articles"):
        _save_raw_articles(articles, config, target_date)

    if args.dry_run:
        print("\n🏁 Dry run complete. Skipping analysis and upload.")
        return

    # ── Step 4: Analyze each article and upload one-by-one ──────────
    print("\n🤖 Analyzing articles with Qwen...")
    analyzer = LLMAnalyzer(config)
    uploaded_urls = []
    analysis_sections = []
    analysis_output_dir = Path(config["output"].get("analysis_output_dir", "output/analysis"))
    save_individual_analysis = config["output"].get("save_analysis", False)
    if save_individual_analysis:
        analysis_output_dir.mkdir(parents=True, exist_ok=True)

    feishu_enabled = (
        not args.skip_feishu
        and config["feishu"].get("upload_enabled", False)
        and config["feishu"].get("wiki_space_id")
    )

    uploader = FeishuUploader(config) if feishu_enabled else None
    if feishu_enabled:
        print("\n📤 Uploading to Feishu Wiki...")
    else:
        print("\n⏭️  Skipping Feishu upload (disabled or not configured)")

    for index, article in enumerate(articles, start=1):
        print(f"  Article {index}/{len(articles)}: {article.title}")
        article_analysis = analyzer.analyze([article])
        article_document_title = _build_article_document_title(article.title, target_date)
        analysis_sections.append(f"# {article_document_title}\n\n{article_analysis}")

        if save_individual_analysis:
            article_analysis_path = analysis_output_dir / f"{index:02d}_{_safe_filename(article.title)}.md"
            article_analysis_path.write_text(
                _render_analysis_file(
                    title=article_document_title,
                    source_name=article.source_name,
                    article_url=article.url,
                    target_date=target_date,
                    body=article_analysis,
                ),
                encoding="utf-8",
            )
            print(f"   Saved to {article_analysis_path}")

        if uploader:
            try:
                uploaded_url = uploader.upload(
                    article_document_title,
                    article_analysis,
                    source_name=article.source_name,
                )
                uploaded_urls.append(uploaded_url)
                print(f"   ✅ Uploaded: {uploaded_url}")
            except Exception as e:
                print(f"   ⚠️  Feishu upload failed for '{article.title}': {e}")

    analysis_markdown = "\n\n---\n\n".join(analysis_sections)

    # ── Step 5: Save combined analysis output ───────────────────────
    if config["output"].get("save_analysis"):
        analysis_path = Path(config["output"]["analysis_file"])
        analysis_path.parent.mkdir(parents=True, exist_ok=True)
        header = f"# 文章分析 - {target_date} {datetime.now().strftime('%H:%M')}\n\n"
        analysis_path.write_text(header + analysis_markdown, encoding="utf-8")
        print(f"   Saved to {analysis_path}")

    # ── Step 6: Update README.md (optional) ────────────────────────
    if args.update_readme:
        print("\n📝 Updating README.md...")
        readme_gen = ReadmeGenerator(config)
        readme_gen.generate(articles, analysis_markdown, uploaded_urls[-1] if uploaded_urls else None, target_date=target_date)
    else:
        print("\n⏭️  Skipping README.md update (use --update-readme to enable)")

    print("\n🎉 Pipeline complete!")


def _save_raw_articles(articles, config, date_str):
    """Save each article as a plain text file for reference."""
    articles_dir = Path(config["output"]["raw_articles_dir"])
    articles_dir.mkdir(parents=True, exist_ok=True)
    for i, article in enumerate(articles):
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in article.title)[:60].strip()
        filename = f"{date_str}_{i:02d}_{safe_title}.txt"
        path = articles_dir / filename
        path.write_text(
            f"Title:  {article.title}\n"
            f"Source: {article.source_name or 'N/A'}\n"
            f"URL:    {article.url}\n"
            f"Date:   {article.date or 'N/A'}\n"
            f"Scraped: {article.scraped_at.isoformat()}\n"
            f"\n{'='*60}\n\n"
            f"{article.content}\n",
            encoding="utf-8",
        )
    print(f"   Saved {len(articles)} raw articles to {articles_dir}")


def _build_article_document_title(article_title: str, date_str: str) -> str:
    """Build the Feishu document title for a single article."""
    return f"{article_title}-{date_str}"


def _render_analysis_file(title: str, source_name: str | None, article_url: str, target_date: str, body: str) -> str:
    """Render a markdown analysis file with YAML front matter for later re-upload."""
    front_matter = {
        "title": title,
        "source_name": source_name or "",
        "article_url": article_url,
        "date": target_date,
    }
    return (
        "---\n"
        f"{yaml.safe_dump(front_matter, allow_unicode=True, sort_keys=False).strip()}\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{body.rstrip()}\n"
    )


def _upload_analysis_directory(analysis_dir: Path, config: dict) -> None:
    """Upload saved analysis markdown files to Feishu using stored metadata."""
    if not analysis_dir.exists():
        print(f"   Analysis directory not found: {analysis_dir}")
        return

    feishu_enabled = config["feishu"].get("upload_enabled", False) and config["feishu"].get("wiki_space_id")
    if not feishu_enabled:
        print("   Feishu upload is disabled or not configured.")
        return

    uploader = FeishuUploader(config)
    files = sorted(analysis_dir.glob("*.md"))
    if not files:
        print(f"   No analysis files found in {analysis_dir}")
        return

    for file_path in files:
        metadata, body = _read_analysis_file(file_path, config)
        title = metadata.get("title") or _title_from_analysis_body(body) or _title_from_filename(file_path)
        source_name = metadata.get("source_name") or _infer_source_name(file_path, config)
        print(f"  Uploading {file_path.name} -> {title} (source: {source_name or 'Unknown'})")
        uploaded_url = uploader.upload(title, body, source_name=source_name)
        print(f"   ✅ Uploaded: {uploaded_url}")


def _read_analysis_file(file_path: Path, config: dict) -> tuple[dict, str]:
    """Read analysis markdown, returning front matter metadata and the markdown body."""
    raw = file_path.read_text(encoding="utf-8")

    if not raw.startswith("---\n"):
        return {}, raw

    lines = raw.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}, raw

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, raw

    metadata_text = "\n".join(lines[1:end_index])
    metadata = yaml.safe_load(metadata_text) or {}
    body = "\n".join(lines[end_index + 1:]).lstrip("\n")
    return metadata, body


def _title_from_analysis_body(body: str) -> str:
    """Extract the first H1 title from a saved analysis body."""
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _title_from_filename(file_path: Path) -> str:
    """Fallback title for legacy analysis files."""
    stem = file_path.stem
    stem = re.sub(r"^\d+_", "", stem)
    return stem.replace("_", " ").strip()


def _infer_source_name(file_path: Path, config: dict) -> str:
    """Infer a source name from a file name when no front matter exists yet."""
    file_name = file_path.name
    stem = file_path.stem
    for source in config.get("scraper", {}).get("sources", []):
        source_name = source.get("name", "")
        if not source_name:
            continue

        candidates = {
            source_name,
            source_name.split("-")[-1],
        }
        candidates = {candidate for candidate in candidates if candidate}

        if any(candidate in file_name or candidate in stem for candidate in candidates):
            return source_name
    return ""


def _safe_filename(text: str) -> str:
    """Create a filesystem-safe filename fragment from article title text."""
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
    return cleaned or "article"


def _resolve_target_date(target_date: str | None) -> str:
    if not target_date:
        return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")

    try:
        parsed = datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("--date must use YYYY-MM-DD") from exc

    return parsed.strftime("%Y-%m-%d")


def _process_single_url(
    url: str,
    feishu_node: int | None,
    config: dict,
    target_date: str,
    *,
    skip_feishu: bool,
    dry_run: bool,
) -> None:
    """Scrape, analyze, and optionally upload one article URL."""
    source_name = _resolve_feishu_source_name(feishu_node)
    scraper = MultiSourceScraper(config, target_date=target_date)
    article = scraper.scrape_url(url, source_name=source_name)
    if not article:
        print("   Failed to scrape the given URL.")
        sys.exit(1)

    print(f"   Scraped: {article.title}")
    print(f"   Feishu source node: {source_name}")

    if config["output"].get("save_raw_articles"):
        _save_raw_articles([article], config, target_date)

    if dry_run:
        print("\n🏁 Dry run complete. Skipping analysis and upload.")
        return

    analyzer = LLMAnalyzer(config)
    article_analysis = analyzer.analyze([article])
    article_document_title = _build_article_document_title(article.title, target_date)

    if config["output"].get("save_analysis", False):
        analysis_output_dir = Path(config["output"].get("analysis_output_dir", "output/analysis"))
        analysis_output_dir.mkdir(parents=True, exist_ok=True)
        article_analysis_path = analysis_output_dir / f"01_{_safe_filename(article.title)}.md"
        article_analysis_path.write_text(
            _render_analysis_file(
                title=article_document_title,
                source_name=article.source_name,
                article_url=article.url,
                target_date=target_date,
                body=article_analysis,
            ),
            encoding="utf-8",
        )
        print(f"   Saved to {article_analysis_path}")

    feishu_enabled = (
        not skip_feishu
        and config["feishu"].get("upload_enabled", False)
        and config["feishu"].get("wiki_space_id")
    )
    if not feishu_enabled:
        print("\n⏭️  Skipping Feishu upload (disabled or not configured)")
        return

    uploader = FeishuUploader(config)
    uploaded_url = uploader.upload(
        article_document_title,
        article_analysis,
        source_name=source_name,
    )
    print(f"   ✅ Uploaded: {uploaded_url}")


def _resolve_feishu_source_name(feishu_node: int | None) -> str:
    """Map CLI feishu node choices to configured source-parent keys."""
    mapping = {
        1: "人民网-人民时评",
        2: "南方网-南方日报评论员",
        3: "人民论坛网评",
        4: "其它来源",
    }
    return mapping.get(feishu_node or 4, "其它来源")


if __name__ == "__main__":
    main()
