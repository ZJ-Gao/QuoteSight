<div align="center">

<img src="Assets/icon-1024.png" width="120" alt="QuoteSight 图标">

# QuoteSight 有据可查

**从真实文献中找到支撑学术观点的那句话**

输入一个观点，就能看到哪些文献支持它、哪些反驳它，每篇的原句，以及 PDF 原页上高亮的位置。索引全部在你的电脑上完成。用不用 Obsidian 都可以。

![macOS](https://img.shields.io/badge/macOS-Apple_Silicon_%7C_Intel-000000?style=flat-square&logo=apple&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?style=flat-square&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Local](https://img.shields.io/badge/索引-完全本地-0A84FF?style=flat-square)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[English](README.md) · **中文**

[开始前的选择](#开始前的选择) · [安装](#安装) · [使用](#使用) · [工作原理](#工作原理) · [体积与速度](#体积与速度) · [数据与隐私](#数据与隐私)

</div>

https://github.com/user-attachments/assets/22af025f-e684-41b7-8c81-9a2a768aa9d7

QuoteSight 读取一个文件夹里的所有 PDF，把文字切成段落，建两套索引：一套按关键词，一套按意思。你可以在本地网页（看板）里搜，也可以在命令行里搜，还可以让 Claude Code、Codex 这类 coding agent 替你搜。

- **简单**：运行一个安装脚本，回答四个问题，然后双击 *Start* 就能用。
- **准**：可以让 coding agent 读检索到的段落，挑出原句，标成*支持*、*反驳*或*背景*，QuoteSight 再把每句和 PDF 原文核对一遍。
- **私密**：PDF、笔记和索引都留在你的电脑上，你的文件只读不改。

## 开始前的选择

安装时会问四个问题，可以先想好：

| 问题 | 选项 | 拿不准就选 |
|---|---|---|
| **1. 你的系统** | macOS 或 Windows | 自动识别 |
| **2. 用哪个 coding agent** 做精准搜索 | Claude Code、Codex，或者不用 | 你平时在用的那个。不用的话，快速搜索照样能用 |
| **3. PDF 放在哪里** | 任意文件夹，包括子文件夹 | 你平时放文献的文件夹。如果它在 Obsidian 的 vault 里，每篇 PDF 会自动关联到对应的笔记 |
| **4. 索引放在哪里** | 任意文件夹 | 默认位置（QuoteSight 文件夹里的 `data`）。不要放在 PDF 文件夹里，也不要放在云同步的文件夹里 |

需要大约 3 GB 硬盘空间（Python 依赖和 embedding 模型），索引每 100 篇文献约 30 MB。

## 安装

### macOS

1. **Python 3.10 或更新。** 在终端里运行 `python3 --version` 查看版本。版本太旧或者没有的话，从 [python.org](https://www.python.org/downloads/) 安装（或者运行 `brew install python`）。
2. **下载 QuoteSight。** 在终端里运行：
   ```sh
   git clone https://github.com/ZJ-Gao/QuoteSight.git
   cd QuoteSight
   ```
   也可以在 GitHub 页面点绿色的 *Code* 按钮下载 ZIP，解压后用 `cd` 进入这个文件夹。
3. **运行安装脚本**，回答四个问题：
   ```sh
   ./scripts/install.sh
   ```
4. **启动**：双击 QuoteSight 文件夹里的 `Start.command`。第一次运行会下载 embedding 模型（约 550 MB）并给你的 PDF 建索引，然后在浏览器里打开看板。之后再打开，只处理新增或改动过的 PDF。

> [!TIP]
> 如果 macOS 第一次拦下 `Start.command`，右键点它，选"打开"，再点一次"打开"。

### Windows

1. **Python 3.10 或更新。** 从 [python.org](https://www.python.org/downloads/windows/) 安装，安装时勾选 *Add python.exe to PATH*。
2. **下载 QuoteSight。** 在 GitHub 页面点绿色的 *Code* 按钮下载 ZIP 并解压，或者用 Git：
   ```powershell
   git clone https://github.com/ZJ-Gao/QuoteSight.git
   cd QuoteSight
   ```
3. **运行安装脚本**：在 QuoteSight 文件夹里打开 PowerShell，运行下面这行，然后回答四个问题：
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
   ```
4. **启动**：双击 `Start.bat`。第一次运行会下载 embedding 模型并建索引，然后在浏览器里打开看板。

> [!TIP]
> 有 NVIDIA 显卡的话，在第 3 步之前先装好 CUDA 版的 PyTorch（[pytorch.org](https://pytorch.org/get-started/locally/)），建索引会快很多。没有的话就用处理器算，慢一些，但能用。

### Coding agent（可选）

要用精准搜索，先装好下面其中一个，并在终端里登录一次：
- **Claude Code**：见 [docs.anthropic.com/claude-code](https://docs.anthropic.com/en/docs/claude-code)，装好后运行一次 `claude` 登录。
- **Codex CLI**：见 [github.com/openai/codex](https://github.com/openai/codex)，装好后运行一次 `codex` 登录。

QuoteSight 直接用你现有的登录和订阅，不需要 API key。

### 让 agent 帮你安装

不想自己敲命令的话，在 QuoteSight 文件夹里打开 Claude Code 或 Codex，把 [`prompts/setup_with_ai.md`](prompts/setup_with_ai.md) 的内容贴进去。agent 每一步都会先问你：安装 QuoteSight、和你一起回答安装问题、建索引并测试。

## 使用

### 看板

双击 *Start*（或者运行 `quotesight-app`），输入一个观点或话题，回车。

- **左栏**：一段简短的总结，下面是文章列表，可以按*支持*、*反驳*、*背景*筛选。
- **中栏**：选中文章里挑出的原句，每句附一句说明；还有打开 PDF 的按钮（用 Obsidian 的话，是在 Obsidian 里打开笔记和 PDF）。
- **右栏**：PDF 原页，那句原文高亮显示。
- **顶部状态栏**：模型和 effort，这次搜索用了多少 token，以及 5 小时和 7 天额度还剩多少（只有 Claude 有）。

在顶部选择搜索方式：
- **Claude** 或 **Codex**：精准，每次约 30 秒、2.5 万到 4.6 万 token。
- **快速**：不用 agent，约 1 到 2 秒，不花 token。由 embedding 模型标出最相关的句子，代替 agent 挑的原句。

左上角的菜单切换主题：跟随系统、浅色或深色。拖动栏与栏之间的分隔线可以调宽度。**EN / 中英**切换语言：中英模式下，界面、说明和总结是中文，原句保留英文。左上角的**历史**默认收起，可以重新打开以前的搜索，不花 token。**更新索引**让索引和你的 PDF 文件夹保持一致（新增、改动、删除的 PDF 都会处理）。

### 命令行

在 macOS 上，命令前面加 `.venv/bin/`（比如 `.venv/bin/quotesight-search`）；在 Windows 上加 `.venv\Scripts\`。

```sh
quotesight-search -t -p "turbidity currents triggered by river floods"     # 易读格式，按文章汇总
quotesight-search -c -n 8 "submarine fans during sea-level highstand"       # 紧凑格式，给 agent 用
quotesight-search --ask -t "hyperpycnal flows can feed deep-water fans"     # 用 agent 做精准搜索
quotesight update                                                      # 加入新增或改动的 PDF
```

| 命令 | 作用 |
|---|---|
| `quotesight setup` | 重新回答四个问题 |
| `quotesight update` | 处理新增或改动的 PDF，移除已删除的，查标题和作者 |
| `quotesight doctor` | 检查安装和配置 |
| `quotesight stats` / `errors` | 数量和体积；解析失败、扫描版和重复的 PDF |
| `quotesight-search [选项] "查询"` | `-p` 按文章汇总，`-t` 易读，`-c` 紧凑，`-n` 结果数，`-f` 主题文件夹，`--ask` 精准搜索 |
| `quotesight-app` | 打开看板 |

### 让你的 coding agent 来搜

安装向导最后会打印一段说明，里面有 `quotesight-search` 的完整路径。把它贴进 `CLAUDE.md`（Claude Code）或 `AGENTS.md`（Codex），或者用 [`prompts/agent_instructions.md`](prompts/agent_instructions.md) 里更完整的版本。之后你的 agent 会先搜索引，再决定开不开 PDF。读 10 段检索结果大约 5000 token，比直接读 PDF 少 10 到 50 倍，因为 PDF 的每一页都是以文字加图片的形式发给模型的。

## 工作原理

1. **提取文字**：用 [pdf-inspector](https://github.com/firecrawl/pdf-inspector) 把每个 PDF 按页转成 Markdown，它也能识别扫描页。每页切成约 300 词的段落，所以每段都知道自己在第几页。参考文献列表和目录不参与搜索。
2. **查重**：如果一个 PDF 一半以上的段落已经属于另一个 PDF，QuoteSight 只保存一份，并列出它的其他位置。
3. **两套索引**：关键词索引（SQLite FTS5，BM25 排序）负责精确的名称和术语；语义索引用 [nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) 生成的向量，负责找到换了说法但意思相同的段落。embedding 模型在你的电脑上运行，可以用 Apple 芯片、NVIDIA 显卡或处理器。
4. **检索**：一个查询同时走两套索引，两个排名用 reciprocal rank fusion 合并。文章旁边的百分比是它在这次结果里的相对分数，用来比较文章，不是概率。
5. **标题和作者**：QuoteSight 从前两页找到 DOI，去 [Crossref](https://www.crossref.org/) 查询，只有查回来的标题能在 PDF 里找到才采用。查不到时，用 Obsidian 笔记里的属性或文件名。
6. **精准搜索**：coding agent 把你的输入拆成 2 到 4 条具体的查询，QuoteSight 去检索，把约 30 段交给 agent。agent 挑出原句，每句标上立场并写一句说明。QuoteSight 再把每句和原文核对，对不上的标为*未核验*。agent 只拿到文字，没有任何工具，也不能读写文件。提示词是 `quotesight/prompts/` 里的 Markdown 文件，可以按你的领域修改。
7. **高亮**：[pdf.js](https://mozilla.github.io/pdf.js/) 渲染页面的文字层，原句在文字层里逐字定位，所以高亮可以从一行的中间开始、在中间结束。有些老 PDF 的字体编码会让文字层变成乱码，这时看板会提示这一页没法高亮。

## 设置

安装向导把 `config.toml` 写到 `~/.config/quotesight/`（macOS）或 `%APPDATA%\quotesight\`（Windows）。重新运行 `quotesight setup` 可以修改主要选项，也可以直接编辑这个文件，[`config.example.toml`](config.example.toml) 里有每个选项的说明。最可能要改的几项：

- **主题文件夹**：PDF 文件夹下的第一层子文件夹会成为可以筛选的主题。`topic_pattern` 可以只索引名字符合规则的文件夹。
- **Obsidian**：笔记通过 `[[file.pdf]]` 链接和 PDF 对应，所以 Obsidian 的附件文件夹设成哪里都不影响。`skip_note_prefixes` 可以跳过索引类或总结类笔记。
- **Agent 的模型和 effort**：`claude_model`、`claude_effort`、`codex_model`、`codex_effort`（默认 Sonnet，medium）。
- **文献库描述**：一句话说明你的领域，会写进给 agent 的提示词。

## 体积与速度

在一台 Apple 芯片的 MacBook 上，用 565 篇 PDF（4.8 GB）测得：

| 步骤 | 结果 |
|---|---|
| 提取文字 | 565 篇共约 50 秒 |
| 生成向量（第一次） | 约 48 分钟；之后每篇新 PDF 几秒 |
| 索引体积 | 约 3.1 万段，约 160 MB |
| 搜索 | 看板里不到 0.1 秒；快速模式加上标句子约 1 到 2 秒；命令行约 6 秒，主要花在加载模型 |
| 精准搜索 | 约 30 秒；Claude Sonnet 约 2.7 万 token，Codex 约 4.6 万 |

## 数据与隐私

- **本地**：PDF、笔记和索引只存在你的电脑上，看板也只有你的电脑能访问（`127.0.0.1`）。
- **Crossref** 只收到 DOI 和简短的标题文字；只有你在设置里填了邮箱，才会附上邮箱。
- **精准搜索**会把你的输入和挑出的段落发给 Anthropic 或 OpenAI，按你账户的条款处理。快速搜索什么都不发送。
- **数据文件夹**（你选的索引位置）：`index.sqlite` 是索引，`history/` 里是每次精准搜索的结果。删掉这个文件夹就能从头开始。

## 常见问题

- **`'NomicBertModel' object has no attribute 'get_extended_attention_mask'`**：装上了更新版本的 `transformers`。运行 `.venv/bin/pip install "transformers==4.48.3" "sentence-transformers==3.4.1"`（Windows 用 `.venv\Scripts\pip`）。
- **搜不到某篇 PDF**：`quotesight errors` 会列出扫描版（没有文字层）和读取失败的 PDF。
- **找不到 `claude` 或 `codex`**：先安装，在终端里登录一次，再运行 `quotesight doctor`。
- **看板打不开**：可能有别的程序占用了 8765 端口，运行 `quotesight-app --port 8780`。

## 致谢

| 项目 | 用途 | 许可 |
|---|---|---|
| [pdf-inspector](https://github.com/firecrawl/pdf-inspector)（Firecrawl） | PDF 文字提取和扫描页识别，索引里的全部文字都来自它 | MIT |
| [nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)（Nomic AI） | embedding 模型 | Apache 2.0 |
| [sentence-transformers](https://github.com/UKPLab/sentence-transformers) | 运行 embedding 模型 | Apache 2.0 |
| [SQLite FTS5](https://www.sqlite.org/fts5.html) | 关键词索引 | 公有领域 |
| [pdf.js](https://github.com/mozilla/pdf.js)（Mozilla） | 渲染 PDF，提供高亮用的文字层 | Apache 2.0 |
| [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) | 标题、作者、期刊、DOI | 开放元数据 |
| [FastAPI](https://github.com/fastapi/fastapi) 和 [Uvicorn](https://github.com/encode/uvicorn) | 本地网页服务 | MIT、BSD |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 和 [Codex CLI](https://github.com/openai/codex) | 可选的精准搜索 | 各自的条款 |

原句和 PDF 文字层的逐字对齐，参考了 Obsidian 插件 [PDF++](https://github.com/RyotaUshio/obsidian-pdf-plus) 的选区链接做法。

## 许可证

本项目以 [MIT 许可证](LICENSE) 开源，© 2026 ZJ-Gao。上面用到的模型和第三方库各有自己的许可。
