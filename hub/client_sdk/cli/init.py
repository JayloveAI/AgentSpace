from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Tuple

from .init_workspace import init_workspace


async def ask_user(prompt: str, options: List[Tuple[str, str]]) -> str:
    """Simple async prompt helper."""
    # Try questionary if available
    try:
        import questionary
        choice_map = {label: value for value, label in options}
        choice = questionary.select(prompt, choices=list(choice_map.keys())).ask()
        return choice_map.get(choice, options[0][0])
    except Exception:
        pass

    print(prompt)
    for idx, (_, label) in enumerate(options, 1):
        print(f"  {idx}. {label}")
    while True:
        raw = input("> ").strip()
        if not raw:
            return options[0][0]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]


async def interactive_init():
    """Interactive init with region and tunnel selection."""
    region = await ask_user(
        "Select your region:",
        options=[
            ("cn", "China (FRP + GLM Embedding)"),
            ("global", "Global (Ngrok + OpenAI Embedding)"),
        ],
    )

    auto_tunnel = await ask_user(
        "Auto-select tunnel provider?",
        options=[
            ("yes", "Auto (recommended)"),
            ("no", "Manual selection"),
        ],
    )

    tunnel_provider = None
    if auto_tunnel == "no":
        tunnel_provider = await ask_user(
            "Select tunnel provider:",
            options=[
                ("frp", "FRP (requires self-hosted server)"),
                ("ngrok", "Ngrok (requires auth token)"),
                ("cloudflare", "Cloudflare Tunnel (zero-config)"),
            ],
        )

    env_file = Path(".env")
    env_content = (
        f"AGENTSPACE_REGION={region}\n"
        f"HUB_URL={'https://hub.agenthub.cn' if region == 'cn' else 'https://hub.agenthub.com'}\n"
        f"EMBEDDING_PROVIDER={'glm' if region == 'cn' else 'openai'}\n"
    )
    if tunnel_provider:
        env_content += f"TUNNEL_PROVIDER={tunnel_provider}\n"

    env_file.write_text(env_content, encoding="utf-8")

    # Initialize workspace
    init_workspace()


if __name__ == "__main__":
    asyncio.run(interactive_init())
