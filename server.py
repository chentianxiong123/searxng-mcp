"""
SearXNG MCP Server
为 AI 提供搜索能力的 MCP 服务器
"""

from mcp.server import MCPServer
from typing import List, Dict, Optional
import httpx
import os

# SearXNG 配置
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://192.168.31.82:8080")
TIMEOUT = 15

mcp = MCPServer("SearXNG Search")


@mcp.tool()
async def search_web(
    query: str,
    language: str = "zh-CN",
    engines: Optional[str] = None,
    num_results: int = 10
) -> List[Dict]:
    """
    通用网页搜索
    
    支持中文和英文搜索，可以指定搜索引擎。
    
    Args:
        query: 搜索关键词
        language: 语言代码 (zh-CN, en, ja, etc.)
        engines: 指定搜索引擎，用逗号分隔 (bing, 360search, sogou)
        num_results: 返回结果数量
        
    Returns:
        搜索结果列表，包含 title, url, content, engine
    """
    params = {
        "q": query,
        "language": language,
        "format": "json"
    }
    
    if engines:
        params["engines"] = engines
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SEARXNG_URL}/search",
                params=params,
                timeout=TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            # 提取结果
            results = []
            for result in data.get("results", [])[:num_results]:
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "engine": result.get("engine", "")
                })
            
            return results
            
    except Exception as e:
        return [{"error": str(e), "message": f"搜索失败: {str(e)}"}]


@mcp.tool()
async def search_science(
    query: str,
    engine: str = "arxiv",
    num_results: int = 10
) -> List[Dict]:
    """
    科研论文搜索
    
    搜索学术论文，支持 arXiv, Crossref, EuropePMC 等。
    
    Args:
        query: 搜索关键词（建议英文）
        engine: 搜索引擎 (arxiv, crossref, europepmc)
        num_results: 返回结果数量
        
    Returns:
        科研论文列表，包含 title, url, content, author, published
    """
    params = {
        "q": query,
        "language": "en",
        "engines": engine,
        "format": "json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SEARXNG_URL}/search",
                params=params,
                timeout=TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            # 提取结果
            results = []
            for result in data.get("results", [])[:num_results]:
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "author": result.get("author", ""),
                    "published": result.get("publishedDate", "")
                })
            
            return results
            
    except Exception as e:
        return [{"error": str(e), "message": f"科研搜索失败: {str(e)}"}]


@mcp.tool()
async def search_technical(
    query: str,
    engine: str = "stackoverflow",
    num_results: int = 10
) -> List[Dict]:
    """
    技术文档搜索
    
    搜索技术文档和代码，支持 StackOverflow, PyPI, crates.io 等。
    
    Args:
        query: 搜索关键词（建议英文）
        engine: 搜索引擎 (stackoverflow, askubuntu, superuser, pypi, crates.io)
        num_results: 返回结果数量
        
    Returns:
        技术文档列表，包含 title, url, content, votes, accepted
    """
    params = {
        "q": query,
        "language": "en",
        "engines": engine,
        "format": "json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SEARXNG_URL}/search",
                params=params,
                timeout=TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            # 提取结果
            results = []
            for result in data.get("results", [])[:num_results]:
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "votes": result.get("votes", ""),
                    "accepted": result.get("accepted", False)
                })
            
            return results
            
    except Exception as e:
        return [{"error": str(e), "message": f"技术搜索失败: {str(e)}"}]


@mcp.tool()
async def get_engine_list() -> str:
    """
    获取可用搜索引擎列表
    
    Returns:
        可用搜索引擎列表
    """
    return """
可用搜索引擎:

网页搜索:
  - bing (必应) - 最稳定，中英文都支持
  - 360search (360搜索) - 中文搜索
  - sogou (搜狗) - 有微信公众号
  - mojeek (隐私搜索) - 英文搜索
  - startpage (Google结果) - 英文搜索
  - swisscows (瑞士搜索) - 英文搜索

科研搜索:
  - arxiv (学术论文) - 54万+篇论文
  - crossref (学术引用) - DOI 查询
  - europepmc (医学论文) - 生物医学

技术搜索:
  - stackoverflow (编程问题) - 最全面
  - askubuntu (Linux问题) - Ubuntu 相关
  - superuser (IT问题) - 系统管理
  - pypi (Python包) - Python 生态
  - crates.io (Rust包) - Rust 生态

文档/维基:
  - arch linux wiki - Arch Linux
  - nixos wiki - NixOS
  - azure - 微软文档
  - cloudflareai - AI 搜索
"""


@mcp.resource("engines://available")
def available_engines() -> str:
    """
    获取可用搜索引擎列表（资源格式）
    """
    return get_engine_list.__wrapped__()


@mcp.resource("help://usage")
def usage_help() -> str:
    """
    使用帮助文档
    """
    return """
SearXNG MCP Server 使用指南

工具:
  1. search_web - 通用网页搜索
     参数: query, language, engines, num_results
     示例: search_web(query="人工智能", language="zh-CN", engines="bing")
     
  2. search_science - 科研论文搜索
     参数: query, engine, num_results
     示例: search_science(query="machine learning", engine="arxiv")
     
  3. search_technical - 技术文档搜索
     参数: query, engine, num_results
     示例: search_technical(query="python list", engine="stackoverflow")
     
  4. get_engine_list - 获取可用引擎列表
     无参数
     示例: get_engine_list()

资源:
  - engines://available - 查看可用引擎
  - help://usage - 本帮助文档

配置:
  - SEARXNG_URL 环境变量 - 设置 SearXNG 地址
  - 默认: http://192.168.31.82:8080

示例:
  1. 中文搜索:
     search_web(query="机器学习入门", language="zh-CN")
     
  2. 科研论文:
     search_science(query="transformer model", engine="arxiv")
     
  3. 技术问题:
     search_technical(query="pandas dataframe", engine="stackoverflow")
"""


if __name__ == "__main__":
    mcp.run()
