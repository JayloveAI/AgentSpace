# -*- coding: utf-8 -*-
"""
全局通用 关键词/Tag 清洗工具
适用：中英文、日志、系统、SDK、OpenClaw、ClawHub 全场景
功能：过滤垃圾词、错误码、无意义碎片，保留专业关键词

使用方法：
    from client_sdk.utils.tag_utils import clean_extract_tags
    clean_tags = clean_extract_tags(['agentai', 'openclaw', '的行业临界点'])
    # 输出: ['agentai', 'openclaw']
"""

# ======================
# 【全局白名单】所有文件通用
# 强制保留：系统词、技术词、英文专有名词、金融领域词
# V1.6.3: 添加金融/证券领域专有词汇
# ======================
GLOBAL_WHITELIST = {
    # 核心系统
    "agentai", "openclaw", "clawhub", "hub", "bridge",
    "sdk", "api", "llm", "ui", "web", "server", "client",
    "plugin", "plugins", "tool", "tools", "service",

    # 技术通用
    "npm", "pip", "whl", "tgz", "json", "sqlite", "db",
    "http", "https", "rest", "rpc", "config", "env",
    "install", "deploy", "package", "packages", "script",

    # 业务功能
    "search", "match", "demand", "pending", "matched",
    "trigger", "callback", "route", "dispatch", "task",
    "session", "token", "user", "admin", "scope",

    # AI 通用
    "prompt", "agent", "model", "embedding", "context",
    "gpt", "claude", "gemini", "llama", "mistral",

    # 基础组件
    "system", "log", "data", "file", "path", "network",
    "local", "global", "online", "offline", "sync", "async",

    # 文件格式
    "csv", "xlsx", "pdf", "txt", "md", "py", "js", "html",

    # V1.6.3: 金融/证券领域专有词汇
    "量化看市场", "系列之四", "华创证券", "洪灝", "最危险的地方",
    "动力煤", "核心市场", "行业临界点", "研究报告", "策略报告",
    "宏观", "微观", "量化", "技术分析", "基本面",
}

# ======================
# 【全局黑名单】所有文件通用
# 自动过滤：错误码、垃圾词、助词、无意义碎片
# ======================
GLOBAL_BLACKLIST = {
    # HTTP 错误码
    "400", "401", "402", "403", "404",
    "500", "501", "502", "503", "504",
    "error", "fail", "failed", "exception", "null", "none", "undefined",

    # 中文无意义词（助词、虚词、碎片）
    "的", "了", "在", "是", "我", "你", "他", "它",
    "这", "那", "此", "该", "都", "就", "会", "可",
    "整", "篇", "全文", "内容", "报告", "完整版",
    "行业", "临界点", "这篇", "完", "全", "文", "本",
    "需要", "获取", "进行", "通过", "使用", "根据",
    "一个", "一些", "所有", "这个", "那个", "这些",

    # 英文无意义助词
    "the", "and", "or", "but", "in", "on", "at", "to",
    "of", "a", "an", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "could", "should", "may",
    "might", "must", "can", "for", "with", "from", "by",
}

# ======================
# 核心清洗函数（全场景通用）
# ======================
def clean_extract_tags(tags: list) -> list:
    """
    统一清洗 Tag / 关键词

    :param tags: 原始标签列表
    :return: 干净、去重、有序的关键词列表

    示例:
        >>> clean_extract_tags(['agentai', 'openclaw', '的行业临界点', '401'])
        ['agentai', 'openclaw']
    """
    if not tags:
        return []

    # 预处理：去空 + 去空格 + 小写
    tags = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
    valid_tags = []

    for tag in tags:
        # 1. 黑名单直接跳过
        if tag in GLOBAL_BLACKLIST:
            continue

        # 2. 白名单强制保留
        if tag in GLOBAL_WHITELIST:
            valid_tags.append(tag)
            continue

        # V1.6.3: 长度过滤（扩展到 20 字，支持中文专业词汇）
        tag_len = len(tag)
        if tag_len < 2 or tag_len > 20:
            continue

        # 4. 英文关键词：字母/数字/下划线/短横线 → 保留
        if tag.isascii() and all(c.isalnum() or c in "_-" for c in tag):
            valid_tags.append(tag)
            continue

        # 5. 中文过滤：包含垃圾字 → 跳过
        invalid_chars = ["的", "这", "那", "我", "你", "他", "整", "篇", "完", "全", "文"]
        if any(char in tag for char in invalid_chars):
            continue

        # 6. 合法中文关键词
        valid_tags.append(tag)

    # 去重 + 排序（稳定输出）
    valid_tags = sorted(list(set(valid_tags)))
    return valid_tags


# ======================
# 便捷函数：从文本直接提取并清洗
# ======================
def extract_and_clean(text: str, min_word_len: int = 3) -> list:
    """
    从文本中提取关键词并清洗

    :param text: 输入文本
    :param min_word_len: 英文单词最小长度
    :return: 清洗后的关键词列表

    示例:
        >>> extract_and_clean("需要《openclaw与AgentAI的行业临界点》报告")
        ['agentai', 'openclaw']
    """
    import re

    if not text:
        return []

    raw_tags = set()

    # 1. 提取书名号内容
    book_titles = re.findall(r"《([^》]+)》", text)
    for title in book_titles:
        # 从书名号中提取英文词
        english_words = re.findall(r"[A-Za-z]+", title)
        raw_tags.update(w.lower() for w in english_words if len(w) >= min_word_len)
        # 提取中文词组
        chinese_words = re.findall(r"[\u4e00-\u9fff]{2,4}", title)
        raw_tags.update(chinese_words)

    # 2. 提取英文专有名词（CamelCase 或全大写）
    camel_case = re.findall(r"\b[A-Z][a-z]+[A-Z][a-z]*\b", text)
    raw_tags.update(w.lower() for w in camel_case)
    uppercase = re.findall(r"\b[A-Z]{2,}[A-Za-z]*\b", text)
    raw_tags.update(w.lower() for w in uppercase)

    # 3. 提取普通英文单词
    english_words = re.findall(r"\b[a-z]{3,}\b", text.lower())
    raw_tags.update(english_words)

    # 4. 提取中文词组
    chinese_phrases = re.findall(r"[\u4e00-\u9fff]{2,6}", text)
    raw_tags.update(chinese_phrases)

    # 5. 统一清洗
    return clean_extract_tags(list(raw_tags))


# ======================
# 模块测试
# ======================
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        ['agentai', 'openclaw', '的行业临界点', '整全文内容', '这篇报告的完'],
        ['401', 'error', 'clawhub', 'sdk', 'api'],
        ['需要', '获取', '用户', '数据', 'file'],
        ['GPT-4', 'Claude3', 'AgentAI', 'OpenClaw'],
    ]

    print("=" * 50)
    print("Tag Utils 测试")
    print("=" * 50)

    for raw in test_cases:
        clean = clean_extract_tags(raw)
        print(f"输入: {raw}")
        print(f"输出: {clean}")
        print()

    # 测试 extract_and_clean
    print("=" * 50)
    print("extract_and_clean 测试")
    print("=" * 50)

    desc = "需要《openclaw与AgentAI的行业临界点》这篇报告的完整全文内容..."
    result = extract_and_clean(desc)
    print(f"输入: {desc}")
    print(f"输出: {result}")
