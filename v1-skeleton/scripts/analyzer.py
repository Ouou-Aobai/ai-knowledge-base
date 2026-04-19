#!/usr/bin/env python3
"""
AI 知识库 · Analyzer 阶段
使用 Tavily API 对原始条目进行分析，生成 relevance_score 和摘要。
"""

import os
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# 加载环境变量
load_dotenv(project_root / '.env')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Tavily API 配置
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')
if not TAVILY_API_KEY:
    logger.warning('TAVILY_API_KEY 未设置，将使用模拟分析')

def analyze_with_tavily(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用 Tavily API 分析单个条目
    
    返回新增的分析字段：
    - relevance_score: float (0-1)
    - summary: str (英文摘要)
    - tags: List[str] (标签)
    - analyzed_at: str (ISO 时间戳)
    """
    # 如果没有 API key，使用模拟分析
    if not TAVILY_API_KEY:
        return mock_analyze(item)
    
    try:
        from tavily import TavilyClient
        
        client = TavilyClient(api_key=TAVILY_API_KEY)
        
        # 构建搜索查询
        query = f"{item.get('title', '')} {item.get('description', '')}"
        if not query.strip():
            query = item.get('url', '')
        
        # 调用 Tavily Search API
        # 使用 include_answer=True 获取 AI 生成的摘要
        response = client.search(
            query=query,
            include_answer=True,
            max_results=3
        )
        
        # 提取分析结果
        relevance_score = calculate_relevance_score(item, response)
        summary = extract_summary(response, item)
        tags = extract_tags(item, response)
        
        return {
            'relevance_score': relevance_score,
            'summary': summary,
            'tags': tags,
            'analyzed_at': datetime.now(timezone.utc).isoformat(),
            'score_breakdown': {
                'tech_depth': 0.0,
                'practical_value': 0.0,
                'timeliness': 0.0,
                'community_heat': 0.0,
                'domain_match': 0.0
            }
        }
        
    except Exception as e:
        logger.error(f'Tavily API 分析失败: {e}')
        # 降级到模拟分析
        return mock_analyze(item)

def calculate_relevance_score(item: Dict[str, Any], tavily_response: Dict[str, Any]) -> float:
    """
    计算 relevance_score (0-1)
    
    初步实现：基于 Tavily 返回的结果数量和质量进行简单评分
    后续可改进为更精细的算法
    """
    # 如果 Tavily 返回了 answer，说明有较高相关性
    if tavily_response.get('answer'):
        base_score = 0.7
    else:
        base_score = 0.5
    
    # 根据结果数量调整
    results = tavily_response.get('results', [])
    if len(results) >= 3:
        base_score += 0.2
    elif len(results) >= 1:
        base_score += 0.1
    
    # 限制在 0-1 范围内
    return min(max(base_score, 0.0), 1.0)

def extract_summary(tavily_response: Dict[str, Any], item: Dict[str, Any]) -> str:
    """
    从 Tavily 响应中提取摘要
    
    优先使用 Tavily 生成的 answer，否则使用第一个结果的 content
    如果都没有，则使用条目的 description
    """
    # 使用 Tavily 的 AI 摘要
    if tavily_response.get('answer'):
        return tavily_response['answer']
    
    # 使用第一个结果的 content
    results = tavily_response.get('results', [])
    if results and results[0].get('content'):
        return results[0]['content'][:500]  # 截断
    
    # 回退到条目的 description
    description = item.get('description', '')
    if description:
        return description[:500]
    
    # 最后使用 title
    return item.get('title', 'No summary available')

def extract_tags(item: Dict[str, Any], tavily_response: Dict[str, Any]) -> List[str]:
    """
    提取标签
    
    优先使用 GitHub topics（如果有），否则从标题和摘要中提取关键词
    """
    tags = set()
    
    # 添加 GitHub topics
    if 'topics' in item and isinstance(item['topics'], list):
        for topic in item['topics']:
            # 清理 topic 字符串
            clean_topic = topic.lower().replace(' ', '-').replace('_', '-')
            tags.add(clean_topic)
    
    # 从标题中提取关键词
    title = item.get('title', '').lower()
    ai_keywords = ['ai', 'llm', 'agent', 'gpt', 'ml', 'machine-learning', 'deep-learning',
                   'artificial-intelligence', 'neural', 'transformer', 'diffusion']
    
    for keyword in ai_keywords:
        if keyword in title:
            tags.add(keyword)
    
    # 确保至少有基本标签
    if not tags:
        tags.add('ai')
    
    return list(tags)[:5]  # 最多返回 5 个标签

def mock_analyze(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    模拟分析（用于测试或当 API 不可用时）
    """
    logger.info(f'使用模拟分析: {item.get("title", "Unknown")}')
    
    # 基于标题是否包含 AI 相关关键词打分
    title = item.get('title', '').lower()
    ai_keywords = ['ai', 'llm', 'agent', 'gpt', 'ml', 'machine learning', 'deep learning']
    
    relevance_score = 0.3  # 基础分
    for keyword in ai_keywords:
        if keyword in title:
            relevance_score += 0.2
    
    # 限制在 0-1 范围内
    relevance_score = min(max(relevance_score, 0.0), 1.0)
    
    # 生成模拟摘要
    description = item.get('description', '')
    if description:
        summary = f"这是一个关于 {item.get('title', '该项目')} 的技术项目。{description[:200]}"
    else:
        summary = f"这是一个关于 {item.get('title', '该主题')} 的技术内容。"
    
    return {
        'relevance_score': relevance_score,
        'summary': summary,
        'tags': extract_tags(item, {}),
        'analyzed_at': datetime.now(timezone.utc).isoformat(),
        'score_breakdown': {
            'tech_depth': 0.0,
            'practical_value': 0.0,
            'timeliness': 0.0,
            'community_heat': 0.0,
            'domain_match': 0.0
        }
    }

def process_raw_file(raw_file_path: Path) -> Optional[Dict[str, Any]]:
    """
    处理单个原始数据文件，返回分析后的数据
    """
    try:
        with open(raw_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        source = data.get('source', 'unknown')
        collected_at = data.get('collected_at', datetime.now(timezone.utc).isoformat())
        items = data.get('items', [])
        
        logger.info(f'开始分析 {source} 数据，共 {len(items)} 条')
        
        # 分析每个条目
        analyzed_items = []
        for i, item in enumerate(items):
            logger.info(f'分析条目 {i+1}/{len(items)}: {item.get("title", "Unknown")[:50]}...')
            
            # 执行分析
            analysis = analyze_with_tavily(item)
            
            # 合并原始数据和分析结果
            analyzed_item = {**item, **analysis}
            analyzed_items.append(analyzed_item)
            
            # 避免速率限制，短暂暂停（仅当使用真实 API 时）
            if TAVILY_API_KEY:
                time.sleep(0.5)
        
        # 构建分析后的数据结构
        analyzed_data = {
            'source': source,
            'collected_at': collected_at,
            'analyzed_at': datetime.now(timezone.utc).isoformat(),
            'count': len(analyzed_items),
            'items': analyzed_items
        }
        
        logger.info(f'完成分析 {source} 数据')
        return analyzed_data
        
    except Exception as e:
        logger.error(f'处理文件 {raw_file_path} 失败: {e}')
        return None

def save_enriched_data(enriched_data: Dict[str, Any], output_dir: Path):
    """
    保存分析后的数据到 enriched 目录
    """
    source = enriched_data['source']
    analyzed_at = enriched_data['analyzed_at']
    
    # 从 analyzed_at 提取日期
    try:
        date_str = datetime.fromisoformat(analyzed_at.replace('Z', '+00:00')).strftime('%Y-%m-%d')
    except:
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    # 创建输出文件名
    filename = f"{source}-{date_str}-enriched.json"
    output_path = output_dir / filename
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enriched_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f'已保存分析结果到: {output_path}')
    return output_path

def main():
    """主函数"""
    # 路径配置
    project_root = Path(__file__).parent.parent
    raw_dir = project_root / 'knowledge' / 'raw'
    enriched_dir = project_root / 'knowledge' / 'enriched'
    
    # 检查 raw 目录是否存在
    if not raw_dir.exists():
        logger.error(f'原始数据目录不存在: {raw_dir}')
        sys.exit(1)
    
    # 查找今天的原始数据文件
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    raw_files = list(raw_dir.glob(f'*-{today}.json'))
    
    # 如果没有找到今天的文件，处理所有文件
    if not raw_files:
        logger.warning(f'未找到今天的原始数据文件，将处理所有文件')
        raw_files = list(raw_dir.glob('*.json'))
    
    if not raw_files:
        logger.error('未找到任何原始数据文件')
        sys.exit(1)
    
    logger.info(f'找到 {len(raw_files)} 个原始数据文件')
    
    # 处理每个文件
    successful_files = []
    for raw_file in raw_files:
        logger.info(f'处理文件: {raw_file.name}')
        
        enriched_data = process_raw_file(raw_file)
        if enriched_data:
            output_path = save_enriched_data(enriched_data, enriched_dir)
            successful_files.append(output_path)
    
    # 输出汇总信息
    logger.info('=' * 50)
    logger.info(f'分析完成! 成功处理 {len(successful_files)}/{len(raw_files)} 个文件')
    for path in successful_files:
        logger.info(f'  ✓ {path.relative_to(project_root)}')
    
    if successful_files:
        # 创建最新的索引文件（供后续阶段使用）
        index_file = enriched_dir / 'latest.json'
        index_data = {
            'last_analyzed': datetime.now(timezone.utc).isoformat(),
            'files': [str(p.relative_to(enriched_dir)) for p in successful_files]
        }
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f'已创建索引文件: {index_file}')
    
    logger.info('=' * 50)

if __name__ == '__main__':
    main()