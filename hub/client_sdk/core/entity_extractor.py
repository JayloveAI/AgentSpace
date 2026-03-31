# -*- coding: utf-8 -*-
"""
Entity Extractor - 文件名/描述文本标签提取器

V1.6.3 重构：
- 使用全局 tag_utils 进行标签清洗
- 白名单/黑名单统一管理
- 支持文件名和描述文本两种模式
- 增强中文关键词提取（支持更长词组、领域专有词）
"""
from __future__ import annotations

import re
from client_sdk.utils.tag_utils import clean_extract_tags, GLOBAL_WHITELIST


class EntityExtractor:
    """
    Lightweight entity tag extractor for filenames and description text.

    Design:
    - No LLM usage.
    - Regex extraction + global tag_utils cleaning.
    - Supports both filenames and description text.
    - V1.6.3: Enhanced Chinese keyword extraction for finance/research domains.
    """

    # 领域关键词映射（用于分类）
    DOMAIN_KEYWORDS = {
        "finance": ["股票", "基金", "债券", "期货", "回测", "K线", "A股", "港股", "美股"],
        "education": ["教材", "习题", "课程", "K12", "试卷", "学习", "考试"],
        "coding": ["代码", "API", "SDK", "库", "框架", "开发", "程序"],
    }

    # V1.6.3: 金融/证券领域专有词汇（优先匹配）
    FINANCE_KEYWORDS = [
        "量化看市场", "系列之四", "华创证券", "洪灝", "最危险的地方",
        "动力煤", "核心市场", "行业临界点", "研究报告", "策略报告",
        "宏观", "微观", "量化", "技术分析", "基本面",
    ]

    # 正则模式（用于提取特定格式的实体）
    ENTITY_PATTERNS = {
        "stock_code": r"\b\d{6}\.(?:SH|SZ)\b",
        "date_range": r"\b\d{4}-\d{2}-\d{2}\b",
        "chinese_stock": r"(?:A股|港股|美股|中概股)",
        "keywords": r"(?:宏观经济|美联储|央行|通胀|GDP)",
    }

    # 中文话题模式（书名号、方括号、引号）
    CHINESE_TOPIC_PATTERNS = [
        r"《([^》]+)》",
        r"【([^\】]+)】",
        r'"([^"]+)"',
    ]

    def extract_tags(self, filename_or_description: str, content_preview: str = "") -> list[str]:
        """
        Extract entity tags from filename or description text.

        Args:
            filename_or_description: 文件名或描述文本
            content_preview: 可选的内容预览

        Returns:
            清洗后的标签列表
        """
        raw_tags = set()
        text = filename_or_description

        # V1.6.3: 先匹配领域专有词汇（优先级最高）
        combined_text = f"{filename_or_description} {content_preview}"
        for keyword in self.FINANCE_KEYWORDS:
            if keyword in combined_text:
                raw_tags.add(keyword)

        # 判断是文件名还是描述文本
        is_description = " " in text or len(re.findall(r"[\u4e00-\u9fff]", text)) > 3

        if is_description:
            raw_tags.update(self._extract_from_description(text))
        else:
            raw_tags.update(self._extract_from_filename(text))

        # 从内容预览提取
        if content_preview:
            raw_tags.update(self._extract_from_text(content_preview))

        # 域关键词匹配
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            if any(kw in combined_text for kw in keywords):
                raw_tags.add(domain)

        # 使用全局 tag_utils 清洗
        return clean_extract_tags(list(raw_tags))

    def _extract_from_filename(self, filename: str) -> set[str]:
        """从文件名提取标签"""
        tags = set()
        base_name = filename.rsplit(".", 1)[0] if "." in filename else filename

        # V1.6.3: 先匹配领域专有词汇
        for keyword in self.FINANCE_KEYWORDS:
            if keyword in filename:
                tags.add(keyword)

        # 提取英文单词
        words = re.findall(r"[a-z]{2,}[a-z0-9]*", base_name.lower())
        tags.update(words)

        # V1.6.3: 提取中文词组（扩展到 2-8 字，覆盖更多专业词汇）
        chinese_words = re.findall(r"[\u4e00-\u9fff]{2,8}", base_name)
        tags.update(chinese_words)

        # 提取文件扩展名
        if "." in filename:
            file_ext = filename.rsplit(".", 1)[-1].lower()
            tags.add(file_ext)

        # 从正则模式提取
        for pattern in self.ENTITY_PATTERNS.values():
            for match in re.findall(pattern, filename, re.IGNORECASE):
                if isinstance(match, tuple):
                    match = " ".join(part for part in match if part)
                if match:
                    tags.add(str(match))

        return tags

    def _extract_from_description(self, description: str) -> set[str]:
        """从描述文本提取标签"""
        tags = set()

        # V1.6.3: 先匹配领域专有词汇
        for keyword in self.FINANCE_KEYWORDS:
            if keyword in description:
                tags.add(keyword)

        # 1. 提取书名号、方括号、引号中的内容
        for pattern in self.CHINESE_TOPIC_PATTERNS:
            matches = re.findall(pattern, description)
            for match in matches:
                tags.update(self._extract_from_phrase(match))

        # 2. 提取英文专有名词（CamelCase）
        camel_case = re.findall(r"\b[A-Z][a-z]+[A-Z][a-z]*\b", description)
        tags.update(w.lower() for w in camel_case)

        # 3. 提取全大写缩写
        uppercase = re.findall(r"\b[A-Z]{2,}[A-Za-z0-9]*\b", description)
        tags.update(w.lower() for w in uppercase)

        # 4. 提取普通英文单词
        words = re.findall(r"\b[a-z]{3,}\b", description.lower())
        tags.update(words)

        # V1.6.3: 提取中文词组（扩展到 2-10 字）
        chinese_phrases = re.findall(r"[\u4e00-\u9fff]{2,10}", description)
        tags.update(chinese_phrases)

        return tags

    def _extract_from_phrase(self, phrase: str) -> set[str]:
        """从短语中提取关键词"""
        tags = set()

        # V1.6.3: 先匹配领域专有词汇
        for keyword in self.FINANCE_KEYWORDS:
            if keyword in phrase:
                tags.add(keyword)

        # 英文部分
        english_parts = re.findall(r"[A-Za-z]+", phrase)
        tags.update(p.lower() for p in english_parts if len(p) >= 2)

        # V1.6.3: 中文部分（扩展到 2-10 字）
        chinese_parts = re.findall(r"[\u4e00-\u9fff]{2,10}", phrase)
        tags.update(chinese_parts)

        return tags

    def _extract_from_text(self, text: str) -> set[str]:
        """从文本中提取特定格式实体"""
        entities = set()

        # V1.6.3: 先匹配领域专有词汇
        for keyword in self.FINANCE_KEYWORDS:
            if keyword in text:
                entities.add(keyword)

        for pattern in self.ENTITY_PATTERNS.values():
            for match in re.findall(pattern, text, re.IGNORECASE):
                if isinstance(match, tuple):
                    match = " ".join(part for part in match if part)
                if match:
                    entities.add(str(match))
        return entities
