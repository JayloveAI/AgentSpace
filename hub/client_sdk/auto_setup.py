"""
ClawHub Auto Setup for OpenClaw
================================
全自动集成模块 - 用户无需任何代码修改

安装后自动生效：
  1. 自动监控 OpenClaw 的资源请求
  2. 资源缺失时自动发布 demand 到 Hub
  3. 文件送达后自动通知 OpenClaw

使用方法（只需一行）：
    import clawhub_auto_setup  # 放在 OpenClaw 启动文件的第一行
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Any, Callable, Optional
import functools
import asyncio

# 环境标记
_CLAWHUB_AUTO_SETUP = False


def enable_auto_setup():
    """
    启用全自动集成

    调用此函数后，ClawHub 会自动：
    1. 拦截 FileNotFoundError 和资源相关的异常
    2. 自动发布 demand 到 Hub
    3. 等待资源送达后继续执行
    """
    global _CLAWHUB_AUTO_SETUP

    if _CLAWHUB_AUTO_SETUP:
        return  # 已启用

    _CLAWHUB_AUTO_SETUP = True

    # 保存原始异常
    original_file_not_found = FileNotFoundError

    # 创建自动捕获的异常基类
    class AutoResourceMissing(FileNotFoundError):
        """自动捕获的资源缺失异常"""
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.resource_type = kwargs.get('resource_type', 'file')
            self.description = str(args[0]) if args else 'Unknown resource'

    # 替换 FileNotFoundError
    builtins = sys.modules.get('builtins')
    if builtins:
        builtins.FileNotFoundError = AutoResourceMissing

    # 设置异常钩子
    sys.excepthook = _auto_exception_hook

    print("[ClawHub] Auto setup enabled - resource requests will be automatically captured")


def _auto_exception_hook(exc_type, exc_value, exc_traceback):
    """全局异常钩子 - 自动捕获资源缺失"""

    # 检查是否是资源相关的异常
    if _is_resource_error(exc_type, exc_value):
        # 异步发布 demand
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # 发布 demand
        from .gateway.auto_catcher import ResourceMissingError
        from .gateway.router import UniversalResourceGateway

        error = ResourceMissingError(
            resource_type=_guess_resource_type(exc_value),
            description=str(exc_value)
        )

        gateway = UniversalResourceGateway()
        loop.create_task(gateway.publish_bounty_in_background(error, str(exc_value)))

        print(f"[ClawHub] Auto-captured resource error: {exc_value}")
        print("[ClawHub] Publishing demand to Hub...")

        # 不阻止程序继续运行
        return

    # 其他异常正常处理
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def _is_resource_error(exc_type, exc_value) -> bool:
    """判断是否是资源相关的错误"""
    # FileNotFoundError
    if issubclass(exc_type, FileNotFoundError):
        return True

    # 检查错误信息
    msg = str(exc_value).lower()
    resource_keywords = [
        'not found', 'missing', 'does not exist',
        '找不到', '不存在', '缺失', 'no such file'
    ]
    return any(kw in msg for kw in resource_keywords)


def _guess_resource_type(exc_value) -> str:
    """根据错误信息猜测资源类型"""
    msg = str(exc_value).lower()

    if '.pdf' in msg:
        return 'pdf'
    elif '.json' in msg:
        return 'json'
    elif '.csv' in msg:
        return 'csv'
    elif '.xlsx' in msg or '.xls' in msg:
        return 'xlsx'
    elif '.txt' in msg:
        return 'txt'

    # 从路径猜测
    if hasattr(exc_value, 'filename') and exc_value.filename:
        ext = Path(exc_value.filename).suffix.lower().lstrip('.')
        if ext:
            return ext

    return 'file'


def auto_catch_decorator(func: Callable) -> Callable:
    """
    自动捕获装饰器 - 可用于装饰 OpenClaw 的关键函数

    用法：
        from clawhub_auto_setup import auto_catch_decorator

        @auto_catch_decorator
        def openclaw_main():
            ...
    """
    from .gateway.auto_catcher import auto_catch_and_route
    return auto_catch_and_route(func)


def patch_openclaw():
    """
    自动 patch OpenClaw 的关键函数

    调用此函数会自动修改 OpenClaw 的行为，
    无需用户手动添加装饰器。
    """
    try:
        # 尝试导入 OpenClaw
        import openclaw

        # Patch 主要入口点
        if hasattr(openclaw, 'Agent'):
            original_run = openclaw.Agent.run

            @functools.wraps(original_run)
            def patched_run(self, *args, **kwargs):
                from .gateway.auto_catcher import auto_catch_and_route
                # 动态添加装饰器
                return auto_catch_and_route(original_run)(self, *args, **kwargs)

            openclaw.Agent.run = patched_run
            print("[ClawHub] OpenClaw Agent.run patched successfully")

    except ImportError:
        print("[ClawHub] OpenClaw not found - skipping patch")


# 自动启用（当模块被导入时）
def _auto_init():
    """模块导入时自动初始化"""
    # 检查环境变量
    if os.getenv('CLAWHUB_AUTO_SETUP', '').lower() in ('1', 'true', 'yes'):
        enable_auto_setup()

    # 检查配置文件
    config_file = Path.home() / ".clawhub" / "auto_setup.conf"
    if config_file.exists():
        enable_auto_setup()


# 执行自动初始化
_auto_init()


__all__ = [
    'enable_auto_setup',
    'auto_catch_decorator',
    'patch_openclaw',
]
