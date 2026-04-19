#!/usr/bin/env python3
"""
Collector 脚本 - 从 GitHub Trending 和 Hacker News 采集 AI 相关内容
输出原始数据到 knowledge/raw/ 目录
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_API_BASE = 'https://api.github.com'
HN_API_BASE = 'https://hacker-news.firebaseio.com/v0'
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'knowledge', 'raw')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# AI 相关关键词（用于过滤）
AI_KEYWORDS = [
    'ai', 'artificial intelligence', 'ml', 'machine learning',
    'llm', 'large language model', 'gpt', 'chatgpt', 'claude',
    'agent', 'agents', 'rag', 'retrieval augmented generation',
    'diffusion', 'stable diffusion', 'transformer', 'neural network',
    'deep learning', 'computer vision', 'nlp', 'natural language processing',
    'reinforcement learning', 'rl', 'mcp', 'model context protocol'
]

# GitHub 搜索关键词
GITHUB_SEARCH_KEYWORDS = [
    'AI', 'LLM', 'agent', 'GPT', 'ChatGPT', 'Claude',
    'diffusion', 'transformer', 'neural network', 'machine learning'
]

def is_ai_related(text: str) -> bool:
    """检查文本是否与 AI 相关"""
    if not text:
        return False
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in AI_KEYWORDS)

def fetch_github_trending() -> List[Dict[str, Any]]:
    """
    从 GitHub 搜索获取 AI 相关趋势仓库
    返回前 50 个符合条件的仓库
    """
    logger.info("开始抓取 GitHub AI 趋势仓库...")
    
    # 将关键词分成两组，每组不超过5个
    keywords_groups = [
        GITHUB_SEARCH_KEYWORDS[:5],  # 前5个关键词
        GITHUB_SEARCH_KEYWORDS[5:]   # 后5个关键词
    ]
    
    all_items = []
    
    # 时间范围：过去7天
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'AI-Knowledge-Collector/1.0'
    }
    
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    
    # 对每组关键词执行搜索
    for i, keywords in enumerate(keywords_groups):
        if not keywords:
            continue
            
        logger.info(f"执行第 {i+1} 次搜索，关键词: {keywords}")
        
        # 构建搜索查询
        query_parts = [f'"{keyword}"' for keyword in keywords]
        query = f'{" OR ".join(query_parts)} created:>={seven_days_ago}'
        
        # API 参数
        params = {
            'q': query,
            'sort': 'stars',
            'order': 'desc',
            'per_page': 100,  # 多取一些以便过滤
            'page': 1
        }
        
        try:
            response = requests.get(
                f'{GITHUB_API_BASE}/search/repositories',
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            items = data.get('items', [])
            logger.info(f"第 {i+1} 次搜索返回 {len(items)} 个仓库")
            
            all_items.extend(items)
            
            # 避免请求过快，在两次搜索之间添加短暂延迟
            if i < len(keywords_groups) - 1:
                time.sleep(1)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API 第 {i+1} 次搜索失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"响应状态码: {e.response.status_code}")
                logger.error(f"响应内容: {e.response.text[:200]}")
            continue
        except json.JSONDecodeError as e:
            logger.error(f"GitHub API 第 {i+1} 次响应 JSON 解析失败: {e}")
            continue
    
    logger.info(f"总共搜索到 {len(all_items)} 个仓库（去重前）")
    
    # 去重：基于仓库 full_name
    seen_ids = set()
    unique_items = []
    for item in all_items:
        repo_id = item.get('full_name')
        if repo_id and repo_id not in seen_ids:
            seen_ids.add(repo_id)
            unique_items.append(item)
    
    logger.info(f"去重后得到 {len(unique_items)} 个唯一仓库")
    
    # 过滤 AI 相关仓库
    ai_items = []
    for item in unique_items:
        # 检查仓库名称、描述、主题标签
        title = item.get('name', '')
        description = item.get('description', '')
        topics = item.get('topics', [])
        
        full_text = f"{title} {description} {' '.join(topics)}"
        if is_ai_related(full_text):
            ai_items.append({
                'id': item.get('full_name'),
                'title': title,
                'description': description,
                'url': item.get('html_url'),
                'stars': item.get('stargazers_count'),
                'language': item.get('language'),
                'topics': topics,
                'created_at': item.get('created_at'),
                'updated_at': item.get('pushed_at'),
                'forks': item.get('forks_count'),
                'open_issues': item.get('open_issues_count')
            })
            
            # 达到50条就停止
            if len(ai_items) >= 50:
                break
    
    logger.info(f"过滤后得到 {len(ai_items)} 个 AI 相关仓库")
    return ai_items

def fetch_hackernews_top() -> List[Dict[str, Any]]:
    """
    从 Hacker News 获取 Top Stories，过滤 AI 相关内容
    返回前 30 个符合条件的文章
    """
    logger.info("开始抓取 Hacker News Top Stories...")
    
    try:
        # 获取 Top Stories ID 列表
        response = requests.get(f'{HN_API_BASE}/topstories.json', timeout=30)
        response.raise_for_status()
        top_ids = response.json()
        
        logger.info(f"获取到 {len(top_ids)} 个 Top Stories ID")
        
        # 只取前 50 个 ID（预留一些空间用于过滤）
        target_ids = top_ids[:50]
        ai_items = []
        
        # 并发获取详情（简单串行实现，可根据需要改为并发）
        for story_id in target_ids:
            try:
                item_response = requests.get(f'{HN_API_BASE}/item/{story_id}.json', timeout=10)
                item_response.raise_for_status()
                item = item_response.json()
                
                # 检查是否是故事类型
                if item.get('type') != 'story':
                    continue
                
                # 检查标题和 URL 是否包含 AI 关键词
                title = item.get('title', '')
                url = item.get('url', '')
                
                if is_ai_related(title) or is_ai_related(url):
                    ai_items.append({
                        'id': item.get('id'),
                        'title': title,
                        'url': url,
                        'score': item.get('score', 0),
                        'comments': item.get('descendants', 0),
                        'author': item.get('by'),
                        'time': item.get('time'),
                        'hn_url': f'https://news.ycombinator.com/item?id={story_id}',
                        'text': item.get('text', '')[:500]  # 截取前500字符
                    })
                
                # 达到30条就停止
                if len(ai_items) >= 30:
                    break
                    
                # 避免请求过快
                time.sleep(0.1)
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"获取 Hacker News 项目 {story_id} 失败: {e}")
                continue
        
        logger.info(f"过滤后得到 {len(ai_items)} 个 AI 相关文章")
        return ai_items
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Hacker News API 请求失败: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Hacker News API 响应 JSON 解析失败: {e}")
        return []

def save_to_file(source: str, data: List[Dict[str, Any]]) -> str:
    """
    保存数据到文件
    返回文件路径
    """
    if not data:
        logger.warning(f"{source} 没有数据可保存")
        return ""
    
    # 生成文件名
    today = datetime.now().strftime('%Y-%m-%d')
    if source == 'github':
        filename = f'github-trending-{today}.json'
    elif source == 'hackernews':
        filename = f'hackernews-top-{today}.json'
    else:
        filename = f'{source}-{today}.json'
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # 检查文件是否已存在（幂等性）
    if os.path.exists(filepath):
        logger.info(f"文件已存在: {filepath}，读取并去重")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # 提取现有 ID
            existing_ids = set()
            if isinstance(existing_data, dict) and 'items' in existing_data:
                existing_items = existing_data['items']
                for item in existing_items:
                    item_id = str(item.get('id', ''))
                    if item_id:
                        existing_ids.add(item_id)
            
            # 去重
            new_items = []
            for item in data:
                item_id = str(item.get('id', ''))
                if item_id and item_id not in existing_ids:
                    new_items.append(item)
                    existing_ids.add(item_id)
            
            # 合并数据
            if 'items' in existing_data:
                existing_data['items'].extend(new_items)
                existing_data['count'] = len(existing_data['items'])
                existing_data['collected_at'] = datetime.now().isoformat() + 'Z'
            else:
                existing_data = {
                    'source': source,
                    'collected_at': datetime.now().isoformat() + 'Z',
                    'count': len(new_items),
                    'items': new_items
                }
            
            data_to_save = existing_data
            
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"读取现有文件失败，创建新文件: {e}")
            data_to_save = {
                'source': source,
                'collected_at': datetime.now().isoformat() + 'Z',
                'count': len(data),
                'items': data
            }
    else:
        # 新文件
        data_to_save = {
            'source': source,
            'collected_at': datetime.now().isoformat() + 'Z',
            'count': len(data),
            'items': data
        }
    
    # 保存文件
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        logger.info(f"数据已保存到: {filepath} (共 {len(data_to_save['items'])} 条)")
        return filepath
    except IOError as e:
        logger.error(f"保存文件失败: {e}")
        return ""

def main():
    """主函数"""
    logger.info("=== AI 知识库 Collector 开始运行 ===")
    
    # 抓取 GitHub 数据
    github_data = fetch_github_trending()
    if github_data:
        github_file = save_to_file('github', github_data)
        if github_file:
            logger.info(f"GitHub 数据保存成功: {github_file}")
    else:
        logger.warning("GitHub 数据抓取失败或没有相关数据")
    
    # 抓取 Hacker News 数据
    hn_data = fetch_hackernews_top()
    if hn_data:
        hn_file = save_to_file('hackernews', hn_data)
        if hn_file:
            logger.info(f"Hacker News 数据保存成功: {hn_file}")
    else:
        logger.warning("Hacker News 数据抓取失败或没有相关数据")
    
    logger.info("=== AI 知识库 Collector 运行结束 ===")
    
    # 检查是否至少有一个数据源成功
    if not github_data and not hn_data:
        logger.error("所有数据源都抓取失败")
        sys.exit(1)

if __name__ == '__main__':
    main()