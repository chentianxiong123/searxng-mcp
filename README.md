# SearXNG MCP Server

为 AI 提供搜索能力的 MCP（Model Context Protocol）服务器

## 功能

- **search_web** - 通用网页搜索（中英文）
- **search_science** - 科研论文搜索（arXiv, Crossref）
- **search_technical** - 技术文档搜索（StackOverflow, PyPI 等）
- **get_engine_list** - 获取可用搜索引擎列表
- **engines://available** - 查看可用引擎（资源）
- **help://usage** - 使用帮助（资源）

## 快速开始

### 1. 安装依赖

```bash
cd Z:\searxng-mcp
pip install -r requirements.txt
```

### 2. 配置环境变量（可选）

```bash
# 默认使用 hi-box 上的 SearXNG
set SEARXNG_URL=http://192.168.31.82:8080

# 或者指定其他地址
set SEARXNG_URL=http://your-ip:8080
```

### 3. 运行服务器

```bash
# 开发模式（带 MCP Inspector）
mcp dev server.py

# 生产模式（stdio）
python server.py

# 生产模式（HTTP）
mcp run server.py --transport http --port 3000
```

## 在 Claude Desktop 中使用

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "searxng": {
      "command": "python",
      "args": ["Z:/searxng-mcp/server.py"],
      "env": {
        "SEARXNG_URL": "http://192.168.31.82:8080"
      }
    }
  }
}
```

## 工具列表

### 1. search_web - 通用网页搜索

```python
{
  "query": "人工智能",
  "language": "zh-CN",
  "engines": "bing,360search",
  "num_results": 10
}
```

### 2. search_science - 科研论文搜索

```python
{
  "query": "machine learning",
  "engine": "arxiv",
  "num_results": 10
}
```

### 3. search_technical - 技术文档搜索

```python
{
  "query": "python list",
  "engine": "stackoverflow",
  "num_results": 10
}
```

### 4. get_engine_list - 获取可用引擎

```python
{
  # 无参数
}
```

## 可用搜索引擎

### 网页搜索
- bing - 最稳定，中英文都支持
- 360search - 中文搜索
- sogou - 有微信公众号
- mojeek - 隐私搜索
- startpage - Google 结果
- swisscows - 瑞士搜索

### 科研搜索
- arxiv - 学术论文（54万+篇）
- crossref - 学术引用
- europepmc - 医学论文

### 技术搜索
- stackoverflow - 编程问题
- askubuntu - Linux 问题
- superuser - IT 问题
- pypi - Python 包
- crates.io - Rust 包

### 文档/维基
- arch linux wiki
- nixos wiki
- azure
- cloudflareai

## 示例

### 给 AI 提供搜索结果

```json
{
  "tool": "search_web",
  "arguments": {
    "query": "机器学习入门",
    "language": "zh-CN",
    "engines": "bing"
  }
}
```

返回结果：

```json
[
  {
    "title": "机器学习入门 - 百度百科",
    "url": "https://baike.baidu.com/item/机器学习",
    "content": "机器学习是一门多领域交叉学科...",
    "engine": "bing"
  }
]
```

### 科研论文搜索

```json
{
  "tool": "search_science",
  "arguments": {
    "query": "transformer model",
    "engine": "arxiv"
  }
}
```

### 技术问题搜索

```json
{
  "tool": "search_technical",
  "arguments": {
    "query": "pandas dataframe",
    "engine": "stackoverflow"
  }
}
```

## 开发

### 项目结构

```
searxng-mcp/
├── server.py           # MCP 服务器主文件
├── requirements.txt    # Python 依赖
├── README.md           # 本文档
└── examples/           # 使用示例
```

### 开发模式

```bash
# 启动开发模式
mcp dev server.py

# 打开 MCP Inspector
# 在浏览器中测试工具和资源
```

## 故障排除

### 连接失败

```bash
# 检查 SearXNG 是否运行
curl http://192.168.31.82:8080/

# 检查环境变量
echo %SEARXNG_URL%
```

### 搜索无结果

- 检查搜索引擎是否可用
- 尝试不同的语言参数
- 检查网络连接

### 常见错误

```json
{
  "error": "搜索失败",
  "message": "ConnectError: Connection refused"
}
```

表示 SearXNG 未运行或地址错误。

## 许可证

MIT License

## 版本

- v1.0.0 - 初始版本
- 支持 SearXNG 4.0.0
- 支持 MCP Python SDK 1.0+
