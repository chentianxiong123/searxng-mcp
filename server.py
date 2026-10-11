"""
SearXNG MCP Server - Streamable HTTP Transport
标准的 MCP HTTP 传输实现，支持单个 /mcp 端点
"""

import asyncio
import json
import os
import re
import time
import uuid
import secrets
from collections import defaultdict
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse
import httpx
import logging

# ============== 配置 ==============
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://192.168.31.82:8080")
TIMEOUT = int(os.getenv("SEARXNG_TIMEOUT", "15"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "10"))
PROTOCOL_VERSION = "2025-03-26"
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")

# ============== 日志配置 ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============== 全局状态 ==============
SERVER_VERSION = "1.0.0"
SERVER_START_TIME = time.time()
request_stats = {
    "total": 0,
    "success": 0,
    "error": 0,
    "by_tool": defaultdict(int)
}
rate_limit = defaultdict(lambda: {"count": 0, "reset": time.time()})
sessions = {}  # session_id -> session_data

# ============== 工具定义 ==============
TOOLS = [
    {
        "name": "search_web",
        "description": "通用网页搜索，支持中文和英文",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词", "maxLength": 500},
                "language": {"type": "string", "description": "语言代码", "default": "zh-CN", "enum": ["zh-CN", "en", "ja", "ko", "fr", "de"]},
                "engines": {"type": "string", "description": "指定搜索引擎，用逗号分隔", "default": None},
                "num_results": {"type": "integer", "description": "返回结果数量", "default": 10, "minimum": 1, "maximum": 20}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_science",
        "description": "科研论文搜索，支持 arXiv、Crossref、EuropePMC 等",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词（建议英文）", "maxLength": 500},
                "engine": {"type": "string", "description": "搜索引擎", "default": "arxiv", "enum": ["arxiv", "crossref", "europepmc"]},
                "num_results": {"type": "integer", "description": "返回结果数量", "default": 10, "minimum": 1, "maximum": 20}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_technical",
        "description": "技术文档搜索，支持 StackOverflow、PyPI、crates.io 等",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词（建议英文）", "maxLength": 500},
                "engine": {"type": "string", "description": "搜索引擎", "default": "stackoverflow", "enum": ["stackoverflow", "askubuntu", "superuser", "pypi", "crates.io"]},
                "num_results": {"type": "integer", "description": "返回结果数量", "default": 10, "minimum": 1, "maximum": 20}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_engine_list",
        "description": "获取可用搜索引擎列表",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# ============== 工具映射 ==============
TOOLS_MAP = {}


# ============== 搜索工具实现 ==============
async def _search_sixbox(params: dict, num_results: int, engine_name: str = "searxng") -> List[Dict]:
    """内部搜索函数，带重试机制"""
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SEARXNG_URL}/search",
                    params=params,
                    timeout=TIMEOUT
                )
                response.raise_for_status()
                html = response.text
                
                # 解析 HTML 结果
                results = []
                articles = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
                
                for article in articles[:num_results]:
                    title_match = re.search(r'<h3[^>]*>.*?<a[^>]*>(.*?)</a>', article, re.DOTALL)
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
                    
                    url_match = re.search(r'<a[^>]*href="([^"]*)"', article)
                    url = url_match.group(1) if url_match else ""
                    
                    content_match = re.search(r'<p[^>]*class="content"[^>]*>(.*?)</p>', article, re.DOTALL)
                    content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip() if content_match else ""
                    
                    results.append({
                        "title": title,
                        "url": url,
                        "content": content,
                        "engine": engine_name
                    })
                
                return results
                
        except httpx.TimeoutException as e:
            last_error = f"请求超时（尝试 {attempt}/{MAX_RETRIES}）"
            logger.warning(f"请求超时，重试 {attempt}/{MAX_RETRIES}")
            await asyncio.sleep(2 ** attempt)
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP 错误 {e.response.status_code}（尝试 {attempt}/{MAX_RETRIES}）"
            logger.error(f"HTTP 错误: {e.response.status_code}")
            if e.response.status_code >= 500:
                await asyncio.sleep(2 ** attempt)
            else:
                break
        except Exception as e:
            last_error = f"错误: {str(e)}"
            logger.error(f"搜索错误: {e}")
            break
    
    return [{"error": last_error, "message": f"搜索失败: {last_error}"}]


async def search_web(query: str, language: str = "zh-CN", engines: Optional[str] = None, num_results: int = 10) -> List[Dict]:
    """通用网页搜索"""
    if not query or len(query) > 500:
        return [{"error": "invalid_query", "message": "查询不能为空且不超过 500 字符"}]
    
    params = {"q": query, "language": language}
    if engines:
        params["engines"] = engines
    
    return await _search_sixbox(params, num_results)


async def search_science(query: str, engine: str = "arxiv", num_results: int = 10) -> List[Dict]:
    """科研论文搜索"""
    if not query or len(query) > 500:
        return [{"error": "invalid_query", "message": "查询不能为空且不超过 500 字符"}]
    
    params = {"q": query, "language": "en", "engines": engine}
    return await _search_sixbox(params, num_results, engine)


async def search_technical(query: str, engine: str = "stackoverflow", num_results: int = 10) -> List[Dict]:
    """技术文档搜索"""
    if not query or len(query) > 500:
        return [{"error": "invalid_query", "message": "查询不能为空且不超过 500 字符"}]
    
    params = {"q": query, "language": "en", "engines": engine}
    return await _search_sixbox(params, num_results, engine)


async def get_engine_list() -> str:
    """获取可用搜索引擎列表"""
    return """可用搜索引擎：
通用搜索：bing, google, duckduckgo, 360search, sogou, baidu
科研论文：arxiv, crossref, europepmc
技术文档：stackoverflow, askubuntu, superuser, pypi, crates.io"""


TOOLS_MAP.update({
    "search_web": search_web,
    "search_science": search_science,
    "search_technical": search_technical,
    "get_engine_list": get_engine_list
})


# ============== MCP 请求处理器 ==============
class MCPHandler(BaseHTTPRequestHandler):
    """MCP HTTP 处理器，实现 Streamable HTTP 传输"""
    
    active_requests = 0
    max_requests = MAX_CONCURRENT
    
    def _check_rate_limit(self, client_ip: str) -> bool:
        """检查速率限制（每分钟 60 次请求）"""
        now = time.time()
        if now - rate_limit[client_ip]["reset"] > 60:
            rate_limit[client_ip]["count"] = 0
            rate_limit[client_ip]["reset"] = now
        
        rate_limit[client_ip]["count"] += 1
        return rate_limit[client_ip]["count"] <= 60
    
    def _check_concurrency(self) -> bool:
        """检查并发限制"""
        if MCPHandler.active_requests >= MCPHandler.max_requests:
            return False
        MCPHandler.active_requests += 1
        return True
    
    def _release_concurrency(self):
        """释放并发"""
        MCPHandler.active_requests -= 1
    
    def _get_client_ip(self) -> str:
        """获取客户端 IP"""
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0]
    
    def _validate_headers(self) -> Optional[Dict]:
        """验证必需的 Headers"""
        # 检查 Origin header（防止 DNS 重绑定攻击）
        origin = self.headers.get("Origin")
        if origin and ALLOWED_ORIGINS:
            if origin not in ALLOWED_ORIGINS:
                return {
                    "error": "ForbiddenOrigin",
                    "message": f"Origin {origin} not allowed"
                }
        
        # 检查 Accept header
        accept = self.headers.get("Accept", "")
        if "application/json" not in accept and "text/event-stream" not in accept:
            return {
                "error": "Invalid Accept header",
                "message": "Must include application/json or text/event-stream"
            }
        
        # 检查 MCP-Protocol-Version header
        protocol_version = self.headers.get("MCP-Protocol-Version")
        if protocol_version and protocol_version != PROTOCOL_VERSION:
            # 兼容旧版本
            if protocol_version not in ["2024-11-05", "2025-03-26", "2025-06-18"]:
                return {
                    "error": "UnsupportedProtocolVersion",
                    "message": f"Protocol version {protocol_version} not supported. Supported: {PROTOCOL_VERSION}"
                }
        
        return None
    
    def _validate_session(self, request: Dict) -> Optional[Dict]:
        """验证会话 ID"""
        method = request.get("method", "")
        
        # initialize 不需要 session ID
        if method == "initialize":
            return None
        
        # 其他方法需要 session ID
        session_id = self.headers.get("Mcp-Session-Id")
        if not session_id:
            return {
                "error": "MissingSessionId",
                "message": "Missing Mcp-Session-Id header"
            }
        
        if session_id not in sessions:
            return {
                "error": "InvalidSessionId",
                "message": "Invalid or expired session ID"
            }
        
        return None
    
    def _send_json_response(self, status_code: int, data: Dict, extra_headers: Optional[Dict] = None):
        """发送 JSON 响应"""
        body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, MCP-Protocol-Version, Mcp-Method, Mcp-Name, Mcp-Session-Id")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)
    
    def _send_sse_response(self, events: List[Dict]):
        """发送 SSE 响应"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        for event in events:
            # SSE event format
            if event.get("event"):
                self.wfile.write(f"event: {event['event']}\n".encode('utf-8'))
            self.wfile.write(f"data: {event['data']}\n".encode('utf-8'))
            self.wfile.write(b"\n")
            self.wfile.flush()
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, MCP-Protocol-Version, Mcp-Method, Mcp-Name, Mcp-Session-Id")
        self.end_headers()
    
    def do_GET(self):
        """处理 GET 请求 - 返回 405 Method Not Allowed"""
        self.send_response(405)
        self.send_header("Content-Type", "application/json")
        self.send_header("Allow", "POST, OPTIONS")
        self.end_headers()
        body = json.dumps({"error": "Method not allowed. Use POST instead."}).encode('utf-8')
        self.wfile.write(body)
    
    def do_POST(self):
        """处理 POST 请求 - 标准的 MCP 端点"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # 速率限制检查
        if not self._check_rate_limit(self._get_client_ip()):
            self._send_json_response(429, {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": "Rate limit exceeded",
                    "data": {"retry_after": 60}
                }
            })
            return
        
        # 并发限制检查
        if not self._check_concurrency():
            self._send_json_response(503, {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": "Server busy",
                    "data": {"retry_after": 5}
                }
            })
            return
        
        try:
            # 验证 Headers
            header_error = self._validate_headers()
            if header_error:
                self._send_json_response(400, {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32000,
                        "message": header_error["message"],
                        "data": {"error": header_error["error"]}
                    }
                })
                return
            
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 1024 * 1024:  # 1MB 限制
                self._send_json_response(413, {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32000,
                        "message": "Request body too large (max 1MB)"
                    }
                })
                return
            
            body = self.rfile.read(content_length)
            
            try:
                request = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                self._send_json_response(400, {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": "Parse error: Invalid JSON"
                    }
                })
                return
            
            # 验证会话
            session_error = self._validate_session(request)
            if session_error:
                self._send_json_response(400, {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32000,
                        "message": session_error["message"],
                        "data": {"error": session_error["error"]}
                    }
                })
                return
            
            # 处理 JSON-RPC 请求
            result = self._handle_jsonrpc_request(request)
            
            # 根据请求类型决定响应格式
            if result.get("_use_sse"):
                events = result.pop("events")
                self._send_sse_response(events)
            else:
                # 检查是否是 initialize 响应，需要添加 session ID header
                extra_headers = None
                session_id = result.pop("_session_id", None)
                if session_id:
                    extra_headers = {"Mcp-Session-Id": session_id}
                self._send_json_response(200, result, extra_headers)
                
        except Exception as e:
            logger.error(f"服务器错误: {e}", exc_info=True)
            self._send_json_response(500, {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            })
            
        finally:
            self._release_concurrency()
    
    def _handle_jsonrpc_request(self, request: Dict) -> Dict:
        """处理 JSON-RPC 请求"""
        request_id = request.get("id")
        method = request.get("method", "")
        
        # 统计
        request_stats["total"] += 1
        
        try:
            # 处理不同方法
            if method == "initialize":
                # 初始化握手
                params = request.get("params", {})
                session_id = str(uuid.uuid4())
                sessions[session_id] = {
                    "created": time.time(),
                    "protocol_version": params.get("protocolVersion", PROTOCOL_VERSION)
                }
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "serverInfo": {
                            "name": "SearXNG MCP Server",
                            "version": SERVER_VERSION
                        },
                        "capabilities": {
                            "tools": {
                                "listChanged": False
                            }
                        }
                    },
                    "_session_id": session_id
                }
                
            elif method == "notifications/initialized":
                # 初始化完成通知（无响应）
                request_stats["success"] += 1
                return {
                    "jsonrpc": "2.0",
                    "result": {}
                }
                
            elif method == "tools/list":
                # 工具列表
                request_stats["success"] += 1
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": TOOLS
                    }
                }
                
            elif method == "tools/call":
                # 工具调用
                params = request.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if tool_name not in TOOLS_MAP:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32602,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }
                
                # 调用工具
                tool_func = TOOLS_MAP[tool_name]
                result = asyncio.run(tool_func(**arguments))
                
                request_stats["success"] += 1
                request_stats["by_tool"][tool_name] += 1
                
                # 返回结果
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, ensure_ascii=False, indent=2)
                            }
                        ]
                    }
                }
                
            elif method == "resources/list":
                # 资源列表（空）
                request_stats["success"] += 1
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "resources": []
                    }
                }
                
            elif method == "prompts/list":
                # 提示列表（空）
                request_stats["success"] += 1
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "prompts": []
                    }
                }
                
            elif method == "ping":
                # 心跳
                request_stats["success"] += 1
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {}
                }
                
            else:
                # 未知方法
                request_stats["error"] += 1
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
                
        except Exception as e:
            logger.error(f"JSON-RPC 错误: {e}", exc_info=True)
            request_stats["error"] += 1
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    def log_message(self, format, *args):
        """自定义日志"""
        if "POST" in str(args):
            logger.info(f"{self.client_address[0]} - {args[0]} {args[1]} {args[2]}")


# ============== 服务器启动 ==============
def run_server(host: str = "0.0.0.0", port: int = 3000):
    """启动 MCP 服务器"""
    server = HTTPServer((host, port), MCPHandler)
    server.daemon_threads = True
    
    logger.info(f"=" * 60)
    logger.info(f"SearXNG MCP Server v{SERVER_VERSION}")
    logger.info(f"Protocol: MCP {PROTOCOL_VERSION}")
    logger.info(f"Transport: Streamable HTTP")
    logger.info(f"=" * 60)
    logger.info(f"SearXNG URL: {SEARXNG_URL}")
    logger.info(f"Timeout: {TIMEOUT}s")
    logger.info(f"Max Retries: {MAX_RETRIES}")
    logger.info(f"Max Concurrent: {MAX_CONCURRENT}")
    logger.info(f"Rate Limit: 60 req/min/IP")
    logger.info(f"=" * 60)
    logger.info(f"MCP Endpoint: http://{host}:{port}/mcp")
    logger.info(f"Configuration:")
    logger.info(f"  {{ \"url\": \"http://{host}:{port}/mcp\" }}")
    logger.info(f"=" * 60)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("服务器停止")
        logger.info(f"总请求数: {request_stats['total']}")
        logger.info(f"成功请求: {request_stats['success']}")
        logger.info(f"失败请求: {request_stats['error']}")
    finally:
        server.server_close()


if __name__ == "__main__":
    import sys
    
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "3000"))
    
    if "--http" in sys.argv or "--streamable" in sys.argv:
        run_server(host, port)
    elif "--test" in sys.argv:
        # 测试模式
        async def test():
            print("测试工具调用...")
            result = await search_web(query="test", num_results=3)
            print(f"结果数量: {len(result)}")
        asyncio.run(test())
    else:
        print(f"用法: python server.py [--http | --streamable | --test]")
        print(f"环境变量: MCP_HOST={host}, MCP_PORT={port}")
        print(f"  --http: 启动 HTTP 服务器（Streamable HTTP）")
        print(f"  --test: 运行测试")
