# 飞书自建应用配置指南 / Feishu Self-Built App Setup Guide

本指南详细说明如何创建飞书自建应用并配置权限，使自动化系统能将分析结果发布到飞书知识库。

---

## 第一步: 创建飞书自建应用

1. 打开 [飞书开放平台](https://open.feishu.cn/app) 并登录你的飞书账号
2. 确保你在正确的企业/组织下 (右上角切换)
3. 点击「创建企业自建应用」
4. 填写应用信息:
   - **应用名称**: 每日文章分析 (Daily Article Analysis)
   - **应用描述**: 自动化发布每日文章分析结果到知识库
   - **应用图标**: 选择一个图标 (可选)
5. 点击「创建」按钮

---

## 第二步: 获取应用凭证 (App ID & App Secret)

1. 进入刚创建的应用详情页
2. 左侧菜单点击「凭证与基础信息」(Credentials & Basic Info)
3. 记录以下信息:
   - **App ID**: 格式类似 `cli_a5xxxxxxxxxxxxx`
   - **App Secret**: 点击「显示」后复制
4. 将这两个值配置为 GitHub Secrets:
   - Repository → Settings → Secrets → Actions → New secret
   - 添加 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`

⚠️ **安全提醒**: 永远不要在代码或配置文件中硬编码这两个值。

---

## 第三步: 配置应用权限

在应用详情页，进入「权限管理」(Permissions & Scopes)。

### 必须开通的权限

#### 知识库权限 (Wiki)
| 权限 | 权限标识 | 说明 |
|------|----------|------|
| 查看、评论、编辑和管理知识库 | `wiki:wiki` | 创建知识库节点 |

#### 文档权限 (Docx)
| 权限 | 权限标识 | 说明 |
|------|----------|------|
| 查看、评论、编辑和管理新版文档 | `docx:document` | 创建和编辑文档内容 |

### 开通步骤:
1. 在权限管理页面搜索上述权限标识
2. 点击每个权限右侧的「开通」按钮
3. 部分权限需要企业管理员审批 → 提交审批请求

---

## 第四步: 发布应用版本

1. 左侧菜单 → 「版本管理与发布」
2. 点击「创建版本」
3. 填写:
   - 版本号: `1.0.0`
   - 更新说明: 初始版本，用于自动发布文章分析
4. 点击「保存」→「申请发布」
5. 等待企业管理员审批通过

---

## 第五步: 获取知识库 Space ID

### 方法 A: 从 URL 获取

1. 打开飞书知识库网页版
2. 进入目标知识库
3. 点击知识库名称旁的「⚙️ 设置」
4. URL 格式为: `https://your-domain.feishu.cn/wiki/settings/{space_id}`
5. 复制 URL 中的 `space_id` 部分

### 方法 B: 通过 API 获取

```bash
# 1. 获取 tenant_access_token
curl -s -X POST 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal' \
  -H 'Content-Type: application/json' \
  -d '{"app_id": "YOUR_APP_ID", "app_secret": "YOUR_APP_SECRET"}' | jq .

# 2. 列出所有知识库
curl -s -X GET 'https://open.feishu.cn/open-apis/wiki/v2/spaces?page_size=50' \
  -H 'Authorization: Bearer YOUR_TENANT_ACCESS_TOKEN' | jq .
```

### 填入配置:
将 `space_id` 填入 `config/config.yaml` 的 `feishu.wiki_space_id` 字段。

如果你的知识库已经有三个目录，可以继续配置 `feishu.source_parent_node_tokens`，把来源名映射到对应目录的 `parent_node_token`：

```yaml
feishu:
   source_parent_node_tokens:
      "人民网-人民时评": "token_1"
      "南方网-南方日报评论员": "token_2"
      "人民网-壹时评": "token_3"
```

---

## 第六步: 添加应用为知识库管理员 ⚠️ 关键步骤

**这一步至关重要！** 如果应用不是知识库成员，API 调用会返回 `permission denied`。

1. 打开目标知识库 (飞书网页版)
2. 点击右上角「⚙️ 设置」(齿轮图标)
3. 选择「成员管理」(Members)
4. 点击「添加成员」
5. 搜索你创建的应用名称 (如「每日文章分析」)
6. 将权限设置为「管理员」(Admin) 或「可编辑」(Can edit)
7. 确认添加

---

## 第七步: 测试配置

### 7.1 测试飞书认证

```bash
# 设置环境变量
export DASHSCOPE_API_KEY="sk-your-dashscope-key"
export FEISHU_APP_ID="cli_your_app_id"
export FEISHU_APP_SECRET="your_app_secret"

# 复制并编辑配置
cp config/config.example.yaml config/config.yaml
# 编辑 config.yaml，填入 wiki_space_id

# 运行测试
python -c "
from src.config_loader import load_config
from src.feishu_client import FeishuClient
config = load_config('config/config.yaml')
client = FeishuClient(config)
print('Token:', client.token[:20] + '...')
print('✅ 飞书认证成功!')
"
```

### 7.2 测试知识库写入

```bash
python -c "
from src.config_loader import load_config
from src.feishu_uploader import FeishuUploader
config = load_config('config/config.yaml')
uploader = FeishuUploader(config)
url = uploader.upload('测试文档', '# 测试\n\n这是一个测试文档。\n\n## 功能\n\n- 功能一\n- 功能二')
print('✅ 写入成功:', url)
"
```

### 7.3 完整流程测试

```bash
# 先测试不上传飞书
python -m src.main --config config/config.yaml --skip-feishu

# 测试完整流程
python -m src.main --config config/config.yaml
```

---

## 常见问题 (FAQ)

### Q: 报错 `permission denied` 或 `code: 10610`?
**A**: 确保:
1. 应用已发布并通过审批
2. 应用已添加为知识库成员
3. 权限 `wiki:wiki` 和 `docx:document` 已开通

### Q: Token 获取失败 (code: 10003)?
**A**: 检查 App ID 和 App Secret 是否正确。确保应用状态为「已启用」。

### Q: 如何切换到国际版 Lark?
**A**: 将 `config.yaml` 中 `feishu.base_url` 改为 `https://open.larksuite.com`

### Q: 知识库找不到应用?
**A**: 搜索时尝试用应用的英文 ID 或完整中文名称。确保应用已发布。

### Q: 如何撤销或删除应用?
**A**: 飞书开放平台 → 应用列表 → 找到应用 → 版本管理 → 申请下线。

---

## 权限汇总表

| 权限类别 | 权限标识 | 用途 | 必需 |
|---------|----------|------|------|
| 知识库 | `wiki:wiki` | 创建和管理知识库节点 | ✅ |
| 文档 | `docx:document` | 创建和编辑文档内容 | ✅ |
| 认证 | 自动获取 | 获取 tenant_access_token | ✅ |