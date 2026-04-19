#!/usr/bin/env python3
"""
Organizer 脚本 - 将分析后的数据写入飞书多维表格
将 knowledge/enriched/ 目录下的 JSON 数据写入飞书"小红书待发库"表，包含相关性评分和摘要
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
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
    """
    获取飞书 tenant_access_token
    """
    headers = {
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    data = {
        'app_id': FEISHU_APP_ID,
        'app_secret': FEISHU_APP_SECRET
    }
    
    try:
        response = requests.post(FEISHU_TOKEN_URL, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get('code') == 0:
            token = result.get('tenant_access_token')
            logger.info("成功获取飞书 tenant_access_token")
            return token
        else:
            logger.error(f"获取 token 失败: {result}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"获取飞书 token 请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"飞书 token 响应 JSON 解析失败: {e}")
        return None

def create_feishu_record(token: str, fields: Dict[str, Any], item_info: str = "") -> bool:
    """
    在飞书多维表格中创建记录
    """
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json; charset=utf-8'
    }
    
    data = {
        'fields': fields
    }
    
    try:
        response = requests.post(FEISHU_CREATE_RECORD_URL, headers=headers, json=data, timeout=10)
        
        # 飞书 API 返回状态码 200 但可能有错误码
        result = response.json()
        
        if response.status_code == 200 and result.get('code') == 0:
            record_id = result.get('data', {}).get('record', {}).get('record_id')
            logger.info(f"记录创建成功: {record_id}")
            return True
        else:
            # 记录详细错误信息
            error_msg = f"创建记录失败: 状态码={response.status_code}"
            if item_info:
                error_msg += f", 项目={item_info}"
            
            # 记录字段内容（截断以避免日志过长）
            fields_summary = {k: (v[:100] + "..." if isinstance(v, str) and len(v) > 100 else v) 
                            for k, v in fields.items()}
            logger.error(f"{error_msg}, 响应={result}, 字段={fields_summary}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"创建记录请求失败: {e}, 项目={item_info}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"创建记录响应 JSON 解析失败: {e}, 项目={item_info}, 响应文本={response.text[:200] if 'response' in locals() else 'N/A'}")
        return False

def read_enriched_data(min_score: float = 0.6) -> List[Dict[str, Any]]:
    """
    读取分析后的数据，返回相关性评分 >= min_score 的条目
    """
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 查找今天的分析文件
    github_file = os.path.join(ENRICHED_DIR, f'github-{today}-enriched.json')
    hn_file = os.path.join(ENRICHED_DIR, f'hackernews-{today}-enriched.json')
    
    # 如果今天的数据不存在，使用最新的文件
    if not os.path.exists(github_file) or not os.path.exists(hn_file):
        logger.warning(f"今天的分析文件不存在，查找最新文件")
        enriched_files = list(Path(ENRICHED_DIR).glob('*-enriched.json'))
        if not enriched_files:
            logger.error(f"未找到任何分析文件: {ENRICHED_DIR}")
            return []
        
        # 按修改时间排序，取最新的两个文件（假设一个是 GitHub，一个是 HN）
        enriched_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        github_file = str(enriched_files[0]) if len(enriched_files) > 0 else None
        hn_file = str(enriched_files[1]) if len(enriched_files) > 1 else github_file
    
    all_items = []
    
    # 读取 GitHub 数据
    if github_file and os.path.exists(github_file):
        try:
            with open(github_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            items = data.get('items', [])
            source = data.get('source', 'github')
            
            for item in items:
                # 过滤低相关性条目
                relevance_score = item.get('relevance_score', 0.0)
                if relevance_score >= min_score:
                    item['_source'] = source
                    all_items.append(item)
                else:
                    logger.debug(f"跳过低相关性条目: {item.get('title', 'Unknown')} (score: {relevance_score})")
            
            logger.info(f"从 {github_file} 读取到 {len(items)} 条 GitHub 数据，过滤后 {len(all_items)} 条")
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"读取 GitHub 分析文件失败: {e}")
    else:
        logger.warning(f"GitHub 分析文件不存在: {github_file}")
    
    # 读取 Hacker News 数据
    if hn_file and os.path.exists(hn_file) and hn_file != github_file:
        try:
            with open(hn_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            items = data.get('items', [])
            source = data.get('source', 'hackernews')
            
            hn_items_added = 0
            for item in items:
                relevance_score = item.get('relevance_score', 0.0)
                if relevance_score >= min_score:
                    item['_source'] = source
                    all_items.append(item)
                    hn_items_added += 1
                else:
                    logger.debug(f"跳过低相关性条目: {item.get('title', 'Unknown')} (score: {relevance_score})")
            
            logger.info(f"从 {hn_file} 读取到 {len(items)} 条 Hacker News 数据，过滤后 {hn_items_added} 条")
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"读取 Hacker News 分析文件失败: {e}")
    else:
        logger.warning(f"Hacker News 分析文件不存在: {hn_file}")
    
    logger.info(f"总共读取到 {len(all_items)} 条数据 (relevance_score >= {min_score})")
    return all_items

def clean_text(text: str) -> str:
    """
    清理文本，移除可能引起飞书API问题的特殊字符
    保留基本标点，但移除控制字符和可能的问题字符
    """
    if not text:
        return text
    
    # 移除控制字符（ASCII 0-31，127）
    cleaned = ''.join(char for char in text if ord(char) >= 32 and ord(char) != 127)
    
    # 替换常见的可能引起问题的字符
    # 保留基本的标点符号：.,;:!?()-[]{}'"/
    # 移除其他可能的问题字符
    replacements = {
        '\u2018': "'",  # 左单引号
        '\u2019': "'",  # 右单引号
        '\u201c': '"',  # 左双引号
        '\u201d': '"',  # 右双引号
        '\u2013': '-',  # 短破折号
        '\u2014': '-',  # 长破折号
        '\u2026': '...',  # 省略号
    }
    
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    
    # 截断过长的文本（飞书可能有长度限制）
    # 选题字段建议不超过200字符
    if len(cleaned) > 200:
        cleaned = cleaned[:197] + "..."
    
    return cleaned

def prepare_record_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    准备飞书记录字段，包含分析结果
    """
    source = item.get('_source', '')
    title = item.get('title', '')
    
    # 获取URL，优先使用原始URL，其次使用HN链接
    url = item.get('url', '')
    hn_url = item.get('hn_url', '')
    
    # 如果原始URL为空，使用HN链接
    if not url and hn_url:
        url = hn_url
    
    # 清理标题和URL
    cleaned_title = clean_text(title)
    cleaned_url = url  # URL通常不需要清理，但确保它是字符串
    
    # 构建选题字段
    if source == 'github':
        # GitHub 仓库，使用仓库名
        topic = f"[GitHub] {cleaned_title}"
    elif source == 'hackernews':
        # Hacker News 文章
        topic = f"[HN] {cleaned_title}"
    else:
        topic = f"[{source.upper()}] {cleaned_title}"
    
    # 构建备注字段（URL）
    note = str(cleaned_url) if cleaned_url else ""
    
    # 如果备注字段过长，进行截断（飞书可能限制URL长度）
    if len(note) > 500:
        note = note[:497] + "..."
    
    # 分析结果字段
    relevance_score = item.get('relevance_score', 0.0)
    summary = item.get('summary', '')
    tags = item.get('tags', [])
    collected_at = item.get('collected_at', '')
    
    # 清理摘要和标签
    cleaned_summary = clean_text(summary)
    # 标签转换为逗号分隔的字符串
    tags_str = ', '.join(tags) if isinstance(tags, list) else str(tags)
    cleaned_tags = clean_text(tags_str)
    
    # 来源字段
    source_cn = 'GitHub' if source == 'github' else 'Hacker News'
    
    # 构建字段字典（包含所有列）
    fields = {
        "选题": topic,
        "状态": "待分析",
        "对话锚点": "",
        "核心角度": "",
        "预计发布": None,  # 日期字段设为 null
        "实际发布": None,  # 日期字段设为 null
        "备注": note,
        # 新增字段
        "相关性分数": relevance_score,
        "英文摘要": cleaned_summary[:1000],  # 限制长度
        "标签": cleaned_tags[:200],  # 限制长度
        "来源": source_cn,
        "采集时间": collected_at
    }
    
    return fields

def main():
    """主函数"""
    logger.info("=== Organizer: 分析数据写入飞书表格开始 ===")
    
    # 1. 读取分析后的数据 (relevance_score >= 0.6)
    items = read_enriched_data(min_score=0.6)
    if not items:
        logger.error("没有找到任何符合条件的分析数据，程序退出")
        sys.exit(1)
    
    # 2. 获取飞书 token
    token = get_feishu_token()
    if not token:
        logger.error("获取飞书 token 失败，程序退出")
        sys.exit(1)
    
    # 3. 遍历数据并写入飞书
    success_count = 0
    total_count = len(items)
    
    for i, item in enumerate(items, 1):
        source = item.get('_source', 'unknown')
        item_id = item.get('id', 'N/A')
        title = item.get('title', '')[:50]  # 截断标题以便日志显示
        
        logger.info(f"处理第 {i}/{total_count} 条: {source} - {item_id} - {title}")
        
        # 准备字段
        fields = prepare_record_fields(item)
        
        # 构建项目信息用于错误日志
        item_info = f"{source}:{item_id}:{title}"
        
        # 写入飞书
        if create_feishu_record(token, fields, item_info):
            success_count += 1
            logger.info(f"✓ 成功写入: {fields.get('选题', 'N/A')}")
        else:
            logger.error(f"✗ 写入失败: {fields.get('选题', 'N/A')}")
            # 记录原始数据以便调试
            logger.debug(f"失败项目原始数据: {json.dumps(item, ensure_ascii=False)[:200]}...")
        
        # 避免请求过快，添加延迟
        if i < total_count:
            time.sleep(0.5)  # 500ms 延迟
    
    # 4. 输出结果
    logger.info(f"=== Phase 2 完成 ===")
    logger.info(f"总计处理: {total_count} 条")
    logger.info(f"成功写入: {success_count} 条")
    logger.info(f"失败: {total_count - success_count} 条")
    
    if success_count > 0:
        print(f"已写入飞书表格：{success_count} 条")
    else:
        print("没有成功写入任何数据到飞书表格")

if __name__ == '__main__':
    main()