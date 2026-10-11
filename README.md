# SearXNG MCP Server

为 AI 提供搜索能力的 MCP（Model Context Protocol）服务器，实现 MCP 2025-03-26 Streamable HTTP 传输。

## 功能

- **search_web** - 通用网页搜索（中英文）
- **search_science** - 科研论文搜索（arXiv, Crossref, EuropePMC）
- **search_technical** - 技术文档搜索（StackOverflow, PyPI, crates.io 等）
- **get_engine_list** - 获取可用搜索引擎列表

## 特性

- ✅ 标准 MCP 2025-03-26 Streamable HTTP 传输
- ✅ 单一 `/mcp` 端点，兼容标准 MCP 客户端
- ✅ 会话管理（Mcp-Session-Id）
- ✅ 速率限制与并发控制
- ✅ Origin 验证（防 DNS 重绑定攻击）
- ✅ 纯 Python 实现，无 MCP SDK 依赖
- ✅ Docker 支持

## 快速开始

### 方式 1：直接运行

```bash
cd searxng-mcp
pip install -r requirements.txt
python server.py --http
```

### 方式 2：Docker

```bash
docker-compose up -d
```

### 环境变量配置

```bash
# SearXNG 服务器地址（默认 http://192.168.31.82:8080）
export SEARXNG_URL=http://192.168.31.82:8080

# 监听地址和端口
export MCP_HOST=0.0.0.0
export MCP_PORT=3000

# 超时和重试
export SEARXNG_TIMEOUT=15
export MAX_RETRIES=3

# 并发控制
export MAX_CONCURRENT=10

# 允许的 Origin（可选）
export ALLOWED_ORIGINS=http://localhost,http://127.0.0.1
```

## 在 omp 中使用

编辑 `~/.omp/agent/mcp.json`：

```json
{
  "$schema": "https://raw.githubusercontent.com/can1357/oh-my-pi/main/packages/coding-agent/src/config/mcp-schema.json",
  "mcpServers": {
    "searxng": {
      "type": "http",
      "url": "http://192.168.31.82:3000/mcp"
    }
  }
}
```

## 在 Claude Desktop 中使用

编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "searxng": {
      "url": "http://192.168.31.82:3000/mcp"
    }
  }
}
```

## 在 VS Code 中使用

编辑 `.vscode/mcp.json` 或用户配置：

```json
{
  "mcpServers": {
    "searxng": {
      "type": "http",
      "url": "http://192.168.31.82:3000/mcp"
    }
  }
}
```

## 工具列表

### 1. search_web - 通用网页搜索

```json
{
  "query": "人工智能",
  "language": "zh-CN",
  "engines": "bing,360search",
  "num_results": 10
}
```

### 2. search_science - 科研论文搜索

```json
{
  "query": "machine learning",
  "engine": "arxiv",
  "num_results": 10
}
```

### 3. search_technical - 技术文档搜索

```json
{
  "query": "python list",
  "engine": "stackoverflow",
  "num_results": 10
}
```

### 4. get_engine_list - 获取可用引擎

```json
{}
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

## API 测试

### 初始化

```bash
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "MCP-Protocol-Version: 2025-03-26" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}'
```

### 获取工具列表

```bash
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "MCP-Protocol-Version: 2025-03-26" \
  -H "Mcp-Session-Id: <session-id>" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

### 调用工具

```bash
curl -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "MCP-Protocol-Version: 2025-03-26" \
  -H "Mcp-Session-Id: <session-id>" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_web","arguments":{"query":"test","num_results":5}}}'
```

## 开发

### 项目结构

```
searxng-mcp/
├── server.py           # MCP 服务器主文件
├── requirements.txt    # Python 依赖
├── README.md           # 本文档
├── Dockerfile          # Docker 构建文件
├── docker-compose.yml  # Docker Compose 配置
├── LICENSE             # MIT 许可证
└── examples/           # 使用示例
```

### 测试服务器

```bash
# 启动服务器
python server.py --http

# 检查服务器状态
curl http://localhost:3000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}}'
```

## 故障排除

### 连接失败

```bash
# 检查 SearXNG 是否运行
curl http://192.168.31.82:8080/

# 检查环境变量
echo $SEARXNG_URL
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

- v1.1.0 - 支持 Streamable HTTP 传输
- v1.0.0 - 初始版本
- 支持 SearXNG 4.0.0
- 支持 MCP 2025-03-26 协议
