#!/usr/bin/env python3
"""
Phase 2 脚本 - 将原始数据写入飞书多维表格
将 knowledge/raw/ 目录下的 JSON 数据写入飞书"小红书待发库"表
"""

import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 飞书 API 配置
FEISHU_APP_ID = 'cli_a94f8e0eaf389cb5'
FEISHU_APP_SECRET = 'GnuQ5bYbtA5cEnruSodlffpj1TpHQEIU'
FEISHU_BASE_URL = 'https://open.feishu.cn/open-apis/bitable/v1/apps/SaJRbnG3xak87Esqq6pcxnJQnFf'
FEISHU_TABLE_ID = 'tbllcMygUwgaKJ14'  # 小红书待发库表

# 飞书 API 端点
FEISHU_TOKEN_URL = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/'
FEISHU_CREATE_RECORD_URL = f'{FEISHU_BASE_URL}/tables/{FEISHU_TABLE_ID}/records'

# 知识库目录
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), 'knowledge', 'raw')

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

def create_feishu_record(token: str, fields: Dict[str, Any]) -> bool:
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
            logger.error(f"创建记录失败: 状态码={response.status_code}, 响应={result}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"创建记录请求失败: {e}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"创建记录响应 JSON 解析失败: {e}")
        return False

def read_today_json_files() -> List[Dict[str, Any]]:
    """
    读取今天的 JSON 文件，返回所有条目
    """
    today = datetime.now().strftime('%Y-%m-%d')
    github_file = os.path.join(KNOWLEDGE_DIR, f'github-trending-{today}.json')
    hn_file = os.path.join(KNOWLEDGE_DIR, f'hackernews-top-{today}.json')
    
    all_items = []
    
    # 读取 GitHub 数据
    if os.path.exists(github_file):
        try:
            with open(github_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            items = data.get('items', [])
            source = data.get('source', 'github')
            
            for item in items:
                item['_source'] = source
                all_items.append(item)
            
            logger.info(f"从 {github_file} 读取到 {len(items)} 条 GitHub 数据")
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"读取 GitHub 文件失败: {e}")
    else:
        logger.warning(f"GitHub 文件不存在: {github_file}")
    
    # 读取 Hacker News 数据
    if os.path.exists(hn_file):
        try:
            with open(hn_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            items = data.get('items', [])
            source = data.get('source', 'hackernews')
            
            for item in items:
                item['_source'] = source
                all_items.append(item)
            
            logger.info(f"从 {hn_file} 读取到 {len(items)} 条 Hacker News 数据")
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"读取 Hacker News 文件失败: {e}")
    else:
        logger.warning(f"Hacker News 文件不存在: {hn_file}")
    
    logger.info(f"总共读取到 {len(all_items)} 条数据")
    return all_items

def prepare_record_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    准备飞书记录字段
    """
    source = item.get('_source', '')
    title = item.get('title', '')
    url = item.get('url', '') or item.get('hn_url', '')
    
    # 构建选题字段
    if source == 'github':
        # GitHub 仓库，使用仓库名
        topic = f"[GitHub] {title}"
    elif source == 'hackernews':
        # Hacker News 文章
        topic = f"[HN] {title}"
    else:
        topic = f"[{source.upper()}] {title}"
    
    # 构建备注字段（URL）
    note = url
    
    # 构建字段字典
    fields = {
        "选题": topic,
        "状态": "待分析",
        "对话锚点": "",
        "核心角度": "",
        "预计发布": None,  # 日期字段设为 null
        "实际发布": None,  # 日期字段设为 null
        "备注": note
    }
    
    return fields

def main():
    """主函数"""
    logger.info("=== Phase 2: 数据写入飞书表格开始 ===")
    
    # 1. 读取今天的 JSON 文件
    items = read_today_json_files()
    if not items:
        logger.error("没有找到任何数据，程序退出")
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
        
        logger.info(f"处理第 {i}/{total_count} 条: {source} - {item_id}")
        
        # 准备字段
        fields = prepare_record_fields(item)
        
        # 写入飞书
        if create_feishu_record(token, fields):
            success_count += 1
            logger.info(f"✓ 成功写入: {fields.get('选题', 'N/A')}")
        else:
            logger.error(f"✗ 写入失败: {fields.get('选题', 'N/A')}")
        
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