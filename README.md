# 📰 每日评论文章自动抓取 + AI 分析 + 飞书知识库发布

这是一个面向评论文章整理场景的自动化系统：按指定日期抓取人民网、南方网等来源的评论文章，逐篇调用通义千问生成结构化解析，保存本地 Markdown 归档，并按来源目录上传到飞书知识库。

当前主流程是“单篇抓取 → 单篇分析 → 单篇落盘 → 单篇上传”，也支持单 URL 补抓、历史分析重传和 README 自动更新。

## 🎯 当前监控源

| # | 来源 | 类型 | 说明 |
|---|------|------|------|
| 1 | [人民时评](http://opinion.people.com.cn/GB/8213/49160/49219/index.html) | HTML | 人民日报评论部「人民时评」专栏 |
| 2 | [南方日报评论员](https://search.southcn.com/) | API + 详情 API | 先走南方网搜索接口，再按文章 `key` 请求详情接口拿正文 |

默认按北京时间“今天”抓取，也可以通过 `--date YYYY-MM-DD` 指定任意目标日期。

## 🚀 功能特性

- 按日期抓取，支持回溯指定日期
- 多源采集，支持 HTML 列表页、JSON API、API 详情页补全正文
- 可按 `source_name` 自动进入不同飞书目录
- 支持把 `output/analysis` 里的历史 Markdown 批量重传到飞书
- 支持直接传入文章 URL 走完整流程
- `【解析】` 会拆成彩色 callout，`【原文】` 支持重点高亮

## 📋 快速开始

### 1. 安装

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp config/config.example.yaml config/config.yaml
cp .env.example .env
```

编辑 `config/config.yaml`：

- 配置 `scraper.sources`
- 设置 `feishu.wiki_space_id`
- 可选设置 `feishu.parent_node_token`
- 可选设置 `feishu.source_parent_node_tokens`

编辑 `.env`：

- `DASHSCOPE_API_KEY`
- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`

### 3. 运行

```bash
# 仅抓取
python -m src.main --config config/config.yaml --dry-run

# 按日期抓取并分析，但不上传飞书
python -m src.main --config config/config.yaml --date 2026-06-12 --skip-feishu

# 完整流程
python -m src.main --config config/config.yaml

# 完整流程并更新 README
python -m src.main --config config/config.yaml --update-readme
```

### 4. 单篇补抓

```bash
python -m src.main --config config/config.yaml --url "https://example.com/article" --feishu-node 4
```

`--feishu-node` 仅在 `--url` 模式下生效：

- `1` = 人民网-人民时评
- `2` = 南方网-南方日报评论员
- `3` = 人民论坛网评
- `4` = 其它来源

### 5. 重传历史分析

```bash
python -m src.main --config config/config.yaml --upload-analysis-dir output/analysis
```

如果 Markdown 文件带有 YAML front matter，会优先使用其中的 `title`、`source_name`、`article_url`、`date`。

### 6. 运行测试

```bash
python -m pytest tests/ -v
```

## ✨ 飞书渲染效果

- 表格会以真实 `Table` block 上传
- `【解析】` 会拆成多个彩色 callout
- `【原文】` 支持中心句、金句、括号内行文思路高亮

## 📁 项目结构

```text
feishu/
├── config/
├── docs/
├── output/
├── src/
├── templates/
├── tests/
├── .env.example
├── README.md
└── requirements.txt
```

## 🔑 所需密钥

| 密钥 | 说明 |
|------|------|
| `DASHSCOPE_API_KEY` | 通义千问 API Key |
| `FEISHU_APP_ID` | 飞书应用 ID |
| `FEISHU_APP_SECRET` | 飞书应用密钥 |

详细配置步骤请查看 [飞书自建应用配置指南](docs/FEISHU_SETUP.md)。

## 📝 命令行参数

```bash
python -m src.main [OPTIONS]

Options:
  --config PATH              配置文件路径
  --date YYYY-MM-DD          指定抓取日期，默认北京时间当天
  --update-readme            用最新分析结果重写 README.md
  --upload-analysis-dir DIR  上传已存在的分析目录到飞书
  --url URL                  抓取指定文章链接并走分析/上传流程
  --feishu-node N            仅在 --url 模式下生效
  --skip-feishu              跳过飞书上传
  --dry-run                  仅抓取，不分析、不上传
```

## 🛠️ 技术栈

- Python + requests + BeautifulSoup + lxml
- 通义千问（DashScope OpenAI 兼容接口）
- 飞书 Wiki API + Docx Block API + descendant API
- YAML 配置 + 环境变量插值
- pytest

## ⚠️ 注意事项

1. HTML 源只适用于服务端渲染页面。
2. 日期过滤依赖列表页日期文本或 URL 日期特征。
3. 飞书应用必须具备 `wiki:wiki` 和 `docx:document` 权限，并被加入目标知识库。
4. `source_parent_node_tokens` 的 key 必须和 `source_name` 完全一致。
5. `--upload-analysis-dir` 适合补传历史文档。

## 📖 参考文档

- [飞书自建应用配置指南](docs/FEISHU_SETUP.md)
- [飞书开放平台文档](https://open.feishu.cn/document)
- [DashScope 通义千问文档](https://help.aliyun.com/zh/dashscope/)
