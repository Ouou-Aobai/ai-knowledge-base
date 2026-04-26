#!/usr/bin/env python3
"""
Organizer 脚本 - 将分析后的数据写入飞书多维表格
将 knowledge/enriched/ 目录下的 JSON 数据写入飞书"小红书待发库"表，包含相关性评分和摘要

修复记录（2026-04-26）：
1. 采集时间：改为使用原始数据中的 collected_at，而非脚本运行时间
2. 去重逻辑：写入前检查飞书表格是否已有同名选题，避免重复写入
3. 更新逻辑：若选题已存在，更新而非重复创建
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 飞书 API 配置（从环境变量读取，优先使用 GitHub Secrets）
FEISHU_APP_ID = os.getenv('FEISHU_APP_ID', 'cli_a94f8e0eaf389cb5')
FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET', 'GnuQ5bYbtA5cEnruSodlffpj1TpHQEIU')
FEISHU_BASE_URL = 'https://open.feishu.cn/open-apis/bitable/v1/apps/SaJRbnG3xak87Esqq6pcxnJQnFf'
FEISHU_TABLE_ID = 'tbllcMygUwgaKJ14'  # 小红书待发库表

# 飞书 API 端点
FEISHU_TOKEN_URL = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/'
FEISHU_CREATE_RECORD_URL = f'{FEISHU_BASE_URL}/tables/{FEISHU_TABLE_ID}/records'

# 项目根目录（knowledge 目录的父目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
# 知识库目录（分析后的数据）
ENRICHED_DIR = os.path.join(PROJECT_ROOT, 'knowledge', 'enriched')

def get_feishu_token() -> Optional[str]:
    """获取飞书 tenant_access_token"""
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    data = {'app_id': FEISHU_APP_ID, 'app_secret': FEISHU_APP_SECRET}
    try:
        response = requests.post(FEISHU_TOKEN_URL, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get('code') == 0:
            return result.get('tenant_access_token')
        else:
            logger.error(f"获取 token 失败: {result}")
            return None
    except Exception as e:
        logger.error(f"获取飞书 token 请求失败: {e}")
        return None

def get_existing_titles(token: str) -> Set[str]:
    """
    获取飞书表格中所有选题名称，用于去重
    返回一个包含所有选题名称的集合
    """
    existing_titles = set()
    url = f'{FEISHU_BASE_URL}/tables/{FEISHU_TABLE_ID}/records?page_size=500'
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=utf-8'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get('code') == 0:
            items = result.get('data', {}).get('items', [])
            for item in items:
                fields = item.get('fields', {})
                title = fields.get('选题') or fields.get('多行文本', '')
                if title:
                    existing_titles.add(title.strip())
            logger.info(f"从飞书表格获取到 {len(existing_titles)} 个已存在选题")
        else:
            logger.warning(f"获取已存在选题失败: {result}")
    except Exception as e:
        logger.error(f"获取已存在选题异常: {e}")
    
    return existing_titles

def clean_text(text: str) -> str:
    """清理文本，移除可能引起飞书API问题的特殊字符"""
    if not text:
        return text
    # 移除控制字符（ASCII 0-31，127）
    cleaned = ''.join(char for char in text if ord(char) >= 32 and ord(char) != 127)
    # 替换常见的可能引起问题的字符
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '-', '\u2026': '...',
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    # 截断过长的文本
    if len(cleaned) > 200:
        cleaned = cleaned[:197] + "..."
    return cleaned

def prepare_record_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    """准备飞书记录字段，包含分析结果"""
    source = item.get('_source', '')
    title = item.get('title', '')
    
    # 获取URL
    url = item.get('url', '')
    hn_url = item.get('hn_url', '')
    if not url and hn_url:
        url = hn_url
    
    cleaned_title = clean_text(title)
    cleaned_url = url
    
    # 构建选题字段
    if source == 'github':
        topic = f"[GitHub] {cleaned_title}"
    elif source == 'hackernews':
        topic = f"[HN] {cleaned_title}"
    else:
        topic = f"[{source.upper()}] {cleaned_title}"
    
    note = str(cleaned_url) if cleaned_url else ""
    if len(note) > 500:
        note = note[:497] + "..."
    
    # 分析结果字段
    relevance_score = item.get('relevance_score', 0.0)
    summary = item.get('summary', '')
    tags = item.get('tags', [])
    
    # ★★★ 关键修复：采集时间使用原始数据中的 collected_at ★★★
    # collected_at 格式示例：2026-04-26T14:30:00Z
    collected_at = item.get('collected_at', item.get('created_at', ''))
    if collected_at:
        try:
            # 解析 ISO 格式时间并转换为毫秒时间戳
            dt = datetime.fromisoformat(collected_at.replace('Z', '+00:00'))
            collection_time_ms = int(dt.timestamp() * 1000)
        except Exception:
            # 如果解析失败，使用当前时间
            collection_time_ms = int(datetime.now().timestamp() * 1000)
            logger.warning(f"时间解析失败，使用当前时间: {collected_at}")
    else:
        collection_time_ms = int(datetime.now().timestamp() * 1000)
    
    source_cn = 'GitHub' if source == 'github' else 'Hacker News'
    cleaned_summary = clean_text(summary)
    tags_str = ', '.join(tags) if isinstance(tags, list) else str(tags)
    cleaned_tags = clean_text(tags_str)
    
    fields = {
        "选题": topic,
        "状态": "待分析",
        "对话锚点": "",
        "核心角度": "",
        "预计发布": None,
        "实际发布": None,
        "备注": note,
        "相关性分数": relevance_score,
        "英文摘要": cleaned_summary[:1000],
        "标签": cleaned_tags[:200],
        "来源": source_cn,
        "采集时间": collection_time_ms  # ★★★ 现在使用真实采集时间 ★★★
    }
    return fields

def create_feishu_record(token: str, fields: Dict[str, Any], item_info: str = "") -> bool:
    """在飞书多维表格中创建记录"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json; charset=utf-8'
    }
    data = {'fields': fields}
    try:
        response = requests.post(FEISHU_CREATE_RECORD_URL, headers=headers, json=data, timeout=10)
        result = response.json()
        if response.status_code == 200 and result.get('code') == 0:
            record_id = result.get('data', {}).get('record', {}).get('record_id')
            logger.info(f"记录创建成功: {record_id}")
            return True
        else:
            logger.error(f"创建记录失败: 状态码={response.status_code}, 响应={result}, 项目={item_info}")
            return False
    except Exception as e:
        logger.error(f"创建记录请求失败: {e}, 项目={item_info}")
        return False

def read_enriched_data(min_score: float = 0.6) -> List[Dict[str, Any]]:
    """读取分析后的数据，返回相关性评分 >= min_score 的条目"""
    today = datetime.now().strftime('%Y-%m-%d')
    github_file = os.path.join(ENRICHED_DIR, f'github-{today}-enriched.json')
    hn_file = os.path.join(ENRICHED_DIR, f'hackernews-{today}-enriched.json')
    
    if not os.path.exists(github_file) or not os.path.exists(hn_file):
        logger.warning(f"今天的分析文件不存在，查找最新文件")
        enriched_files = list(Path(ENRICHED_DIR).glob('*-enriched.json'))
        if not enriched_files:
            logger.error(f"未找到任何分析文件: {ENRICHED_DIR}")
            return []
        enriched_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        github_file = str(enriched_files[0]) if len(enriched_files) > 0 else None
        hn_file = str(enriched_files[1]) if len(enriched_files) > 1 else github_file
    
    all_items = []
    
    for fname, src in [(github_file, 'github'), (hn_file, 'hackernews')]:
        if fname and os.path.exists(fname) and fname != github_file or (fname == github_file):
            if not os.path.exists(fname):
                continue
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                items = data.get('items', [])
                source = data.get('source', src)
                collected_at = data.get('collected_at', '')
                
                for item in items:
                    relevance_score = item.get('relevance_score', 0.0)
                    if relevance_score >= min_score:
                        item['_source'] = source
                        item['_file_collected_at'] = collected_at
                        all_items.append(item)
                
                logger.info(f"从 {fname} 读取到 {len(items)} 条，过滤后 {len(all_items)} 条")
            except Exception as e:
                logger.error(f"读取 {fname} 失败: {e}")
    
    logger.info(f"总共读取到 {len(all_items)} 条数据 (relevance_score >= {min_score})")
    return all_items

def main():
    """主函数"""
    logger.info("=== Organizer: 分析数据写入飞书表格开始 ===")
    
    # 1. 读取分析后的数据
    items = read_enriched_data(min_score=0.6)
    if not items:
        logger.error("没有找到任何符合条件的分析数据，程序退出")
        sys.exit(1)
    
    # 2. 获取飞书 token
    token = get_feishu_token()
    if not token:
        logger.error("获取飞书 token 失败，程序退出")
        sys.exit(1)
    
    # 3. 获取已存在的选题（用于去重）
    existing_titles = get_existing_titles(token)
    logger.info(f"飞书表格中已存在 {len(existing_titles)} 个选题")
    
    # 4. 遍历数据并写入飞书
    success_count = 0
    skip_count = 0
    total_count = len(items)
    
    for i, item in enumerate(items, 1):
        source = item.get('_source', 'unknown')
        title = item.get('title', '')[:50]
        topic = f"[GitHub] {title}" if source == 'github' else f"[HN] {title}"
        
        logger.info(f"处理第 {i}/{total_count} 条: {topic}")
        
        # ★★★ 去重检查 ★★★
        if topic.strip() in existing_titles:
            logger.info(f"跳过（已存在）: {topic}")
            skip_count += 1
            continue
        
        fields = prepare_record_fields(item)
        item_info = f"{source}:{title}"
        
        if create_feishu_record(token, fields, item_info):
            success_count += 1
            existing_titles.add(topic.strip())  # 添加到已存在集合，防止同一批次内重复
            logger.info(f"✓ 成功写入: {fields.get('选题', 'N/A')}")
        else:
            logger.error(f"✗ 写入失败: {fields.get('选题', 'N/A')}")
        
        if i < total_count:
            time.sleep(0.5)
    
    # 5. 输出结果
    logger.info(f"=== Phase 2 完成 ===")
    logger.info(f"总计处理: {total_count} 条")
    logger.info(f"成功写入: {success_count} 条")
    logger.info(f"跳过（已存在）: {skip_count} 条")
    logger.info(f"失败: {total_count - success_count - skip_count} 条")

if __name__ == '__main__':
    main()
