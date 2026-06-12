"""README generator module - creates/updates README.md with latest analysis."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from src.scraper import Article


class ReadmeGenerator:
    """Generates and updates README.md with analysis results and history."""

    def __init__(self, config: dict):
        self.config = config
        self.readme_path = Path(config["output"]["readme_path"])

    def generate(self, articles: list, analysis_md: str,
                 feishu_url: Optional[str] = None, target_date: Optional[str] = None) -> None:
        """Generate or update README.md with the latest analysis."""
        date_str = target_date or datetime.now().strftime("%Y-%m-%d")
        model = self.config["llm"]["model"]
        history_rows = self._build_history_table(date_str, len(articles), feishu_url)

        content = self._render(
            date=date_str,
            article_count=len(articles),
            model=model,
            latest_analysis=analysis_md,
            history_rows=history_rows,
        )
        self.readme_path.write_text(content, encoding="utf-8")
        print(f"  README.md updated ({len(content)} bytes)")

    def _build_history_table(self, latest_date: str, latest_count: int,
                             latest_feishu: Optional[str]) -> str:
        """Build the history table rows, with the latest run at the top."""
        rows = []

        # Latest run
        feishu_col = f"[飞书]({latest_feishu})" if latest_feishu else "—"
        rows.append(
            f"| {latest_date} | {latest_count} "
            f"| [查看](output/latest_analysis.md) | {feishu_col} |"
        )

        # Historical runs: scan output directory for dated analysis files
        analysis_path = Path(self.config["output"]["analysis_file"])
        max_days = self.config["output"].get("readme_history_days", 30)

        # Look for previous analysis files in output/
        output_dir = analysis_path.parent
        if output_dir.exists():
            dates_seen = set()
            for f in sorted(output_dir.glob("*.md"), reverse=True):
                # Skip the current latest_analysis.md
                if f.name == analysis_path.name:
                    continue
                date_part = f.stem.split("_")[0]  # e.g. "2026-06-10" from "2026-06-10_analysis.md"
                if date_part != latest_date and date_part not in dates_seen:
                    dates_seen.add(date_part)
                    rows.append(
                        f"| {date_part} | — | [查看](output/{f.name}) | — |"
                    )
                    if len(rows) >= max_days:
                        break

        return "\n".join(rows)

    def _render(self, **kwargs) -> str:
        """Render the README template with the given parameters."""
        return f"""# 📰 每日文章自动分析 / Daily Article Analysis

> ⏰ 自动运行: 每天 9:00 AM (北京时间) | GitHub Actions 驱动

## 📊 最新分析 / Latest Analysis

- **日期 (Date)**: {kwargs['date']}
- **文章数量 (Articles)**: {kwargs['article_count']}
- **分析模型 (Model)**: {kwargs['model']}

---

{kwargs['latest_analysis']}

---

## 📚 历史记录 / History

| 日期 | 文章数 | 本地文件 | 飞书文档 |
|------|--------|----------|----------|
{kwargs['history_rows']}

---

## 🛠️ 关于 / About

本仓库使用以下技术栈:
- **爬虫**: Python + requests + BeautifulSoup
- **分析**: Qwen (通义千问) via DashScope API
- **发布**: Feishu Wiki via Open API
- **调度**: GitHub Actions (cron)

详细配置说明请查看 `config/config.example.yaml` 和 `docs/FEISHU_SETUP.md`。

---
*由 GitHub Actions 自动生成 ⚡ Powered by Qwen + Feishu*
"""