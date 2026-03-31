"""
CLI Prompts - 交互式命令行提示
===============================
实现启动拦截和匹配排序两个关键交互点

V1.5 Updates:
- Rich library integration for beautiful terminal output
- Global UTF-8 encoding fix for Windows
- Display node_status and live_broadcast in match results
"""
from typing import Optional, List
import sys

# Rich library for beautiful terminal output
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Create global console instance
console = Console(force_terminal=True)


async def onboarding_prompt(identity_data: dict) -> bool:
    """
    启动拦截：确认名片并接入 Hub

    Args:
        identity_data: 名片数据

    Returns:
        用户是否确认
    """
    description = identity_data.get("description", "")

    # 截取预览（最多显示 5 行）
    lines = description.strip().split("\n")
    preview = "\n   ".join(lines[:5])
    if len(lines) > 5:
        preview += "\n   ..."

    print("\n" + "=" * 60)
    print("[系统提示] Agent 准备接入 Hub 撮合大厅")
    print(f"发现本地默认名片 (identity.md)，内容预览：")
    print(f"   \"{preview}\"")
    print("=" * 60)

    # 等待用户输入
    user_input = input(
        "\n确认接入方式：\n"
        ">> 按【回车键】使用默认名片并开启公网隧道\n"
        ">> 或输入 'n' 取消接入\n"
        ">> "
    )

    return user_input.lower() != 'n'


async def match_prompt(matches: list[dict]) -> list[int]:
    """
    匹配排序：展示 Top 3 并让用户选择优先级

    Args:
        matches: Top 3 匹配结果列表

    Returns:
        用户排序的索引列表，如 [2, 1, 0]
    """
    print("\n" + "=" * 60)
    print(f"找到 {len(matches)} 个高度匹配的智能体：")

    for i, match in enumerate(matches, 1):
        print(
            f"  [ {i} ] 匹配度: {match.get('similarity', 'N/A'):>6} | "
            f"贡献: {match.get('tasks_provided', 0):>4} | "
            f"ID: {match.get('agent_id', 'unknown')}"
        )

    print("=" * 60)

    # 非交互模式：直接返回默认顺序
    try:
        user_input = input(
            "\n请输入优选顺序 (例: 2,1)，或按回车自动向下兜底尝试：\n"
            ">> "
        ).strip()
    except EOFError:
        # 非交互模式，返回默认顺序
        return list(range(len(matches)))

    if not user_input:
        # 默认顺序：0, 1, 2
        return list(range(len(matches)))

    try:
        # 解析用户输入，如 "2,1" -> [1, 0] (转换为 0-indexed)
        indices = [int(x.strip()) - 1 for x in user_input.split(",")]

        # 验证索引范围
        max_index = len(matches) - 1
        valid_indices = [i for i in indices if 0 <= i <= max_index]

        if not valid_indices:
            print("[警告] 输入无效，使用默认顺序")
            return list(range(len(matches)))

        return valid_indices

    except ValueError:
        print("[警告] 输入格式错误，使用默认顺序")
        return list(range(len(matches)))


# ============================================================================
# V1.5: Rich-Enhanced Prompts
# ============================================================================

async def onboarding_prompt_rich(identity_data: dict) -> bool:
    """
    V1.5 Enhanced onboarding with Rich library

    Args:
        identity_data: 名片数据

    Returns:
        用户是否确认
    """
    description = identity_data.get("description", "")

    # Create identity preview panel
    lines = description.strip().split("\n")
    preview = "\n".join(lines[:5])
    if len(lines) > 5:
        preview += "\n... (truncated)"

    identity_panel = Panel(
        preview,
        title="[bold blue]📋 Agent Identity Card[/bold blue]",
        border_style="blue",
        padding=(1, 2)
    )

    console.print("\n")
    console.print(identity_panel)

    # Confirmation prompt
    from rich.prompt import Confirm

    return Confirm.ask(
        "\n[bold yellow]Connect to Hub with this identity?[/bold yellow]",
        default=True
    )


async def match_prompt_rich(matches: List[dict]) -> List[int]:
    """
    V1.5 Enhanced match display with Rich table

    Shows:
    - Rank
    - Agent ID
    - Domain
    - Node Status (with emoji: 🟢 active, 🟡 busy, 🔴 offline)
    - Live Broadcast (human-readable message)
    - Tasks Provided
    - Similarity Score

    Args:
        matches: Top 3 匹配结果列表 (V1.5: includes node_status, live_broadcast)

    Returns:
        用户排序的索引列表，如 [2, 1, 0]
    """
    console.print("\n[bold yellow]🎉 Found highly matched agents:[/bold yellow]\n")

    # Create Rich table
    table = Table(title="[bold green]Top 3 Candidate Agents[/bold green]")

    table.add_column("Rank", style="cyan", width=6)
    table.add_column("Agent ID", style="magenta")
    table.add_column("Domain", style="blue")
    table.add_column("Status", style="yellow", width=10)
    table.add_column("Live Broadcast", style="green")
    table.add_column("Tasks", justify="right", style="yellow")
    table.add_column("Score", justify="right", style="cyan")

    for i, match in enumerate(matches, 1):
        # Color-code node_status with emoji
        node_status = match.get('node_status', 'offline')
        status_emoji = {
            'active': '🟢',
            'busy': '🟡',
            'offline': '🔴'
        }.get(node_status, '⚪')

        # Format similarity score
        similarity = match.get('similarity_score', match.get('similarity', 'N/A'))
        if isinstance(similarity, float):
            similarity_str = f"{similarity*100:.1f}%"
        else:
            similarity_str = str(similarity)

        # Truncate live_broadcast if too long
        live_broadcast = match.get('live_broadcast', 'No message')
        if len(live_broadcast) > 30:
            live_broadcast = live_broadcast[:30] + "..."

        table.add_row(
            f"[bold]{i}[/bold]",
            match.get('agent_id', 'unknown'),
            match.get('domain', 'general'),
            f"{status_emoji} {node_status}",
            live_broadcast,
            str(match.get('tasks_provided', 0)),
            similarity_str
        )

    console.print(table)

    # Prompt for selection
    from rich.prompt import Prompt

    try:
        user_input = Prompt.ask(
            "\n[bold cyan]Enter priority order[/bold cyan] (e.g., 2,1) or press Enter for default",
            default=""
        ).strip()
    except (EOFError, KeyboardInterrupt):
        return list(range(len(matches)))

    if not user_input:
        return list(range(len(matches)))

    try:
        indices = [int(x.strip()) - 1 for x in user_input.split(",")]
        max_index = len(matches) - 1
        valid_indices = [i for i in indices if 0 <= i <= max_index]

        if not valid_indices:
            console.print("[yellow]⚠️  Invalid input, using default order[/yellow]")
            return list(range(len(matches)))

        return valid_indices

    except ValueError:
        console.print("[yellow]⚠️  Format error, using default order[/yellow]")
        return list(range(len(matches)))


# ============================================================================
# Helper Functions
# ============================================================================

def print_success(message: str):
    """Print success message with green color"""
    console.print(f"[green]✅ {message}[/green]")


def print_warning(message: str):
    """Print warning message with yellow color"""
    console.print(f"[yellow]⚠️  {message}[/yellow]")


def print_error(message: str):
    """Print error message with red color"""
    console.print(f"[red]❌ {message}[/red]")


def print_info(message: str):
    """Print info message with blue color"""
    console.print(f"[blue]ℹ️  {message}[/blue]")

