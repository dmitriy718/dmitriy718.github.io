from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from .agent import Agent, build_rbac
from .analysis.diagnostics import DiagnosticsCollector
from .analysis.llm_client import LLMClient
from .analysis.log_analyzer import LogAnalyzer
from .audit import AuditLogger
from .config import AgentConfig, load_config
from .logging_setup import setup_logging
from .memory import MemoryStore
from .notifications.base import NotificationManager
from .notifications.email import EmailNotifier
from .notifications.slack import SlackNotifier
from .notifications.telegram import TelegramNotifier
from .repair.auto_heal import AutoHealer
from .repair.deployment import DeploymentManager
from .repair.patcher import PatchApplier
from .webhooks.server import create_app
from .utils.env import get_env


async def _run_agent(config: AgentConfig) -> None:
    setup_logging(config.paths.logs_dir)
    audit = AuditLogger(config.paths.audit_log)
    memory = MemoryStore(config.paths.memory_db)
    rbac = build_rbac(config)
    llm = LLMClient(config.llm) if config.llm.enabled else None
    analyzer = LogAnalyzer(llm)
    diagnostics = DiagnosticsCollector(rbac, audit)
    deployment = DeploymentManager(rbac, audit)
    patcher = PatchApplier(rbac, audit)
    auto_healer = AutoHealer(
        rbac=rbac,
        audit=audit,
        memory=memory,
        diagnostics=diagnostics,
        analyzer=analyzer,
        deployment=deployment,
        patcher=patcher,
        llm=llm,
    )

    notifiers = []
    if config.notifications.slack.enabled:
        notifiers.append(SlackNotifier(config.notifications.slack.webhook_url_env))
    if config.notifications.email.enabled:
        notifiers.append(
            EmailNotifier(
                smtp_host=config.notifications.email.smtp_host,
                smtp_port=config.notifications.email.smtp_port,
                username_env=config.notifications.email.username_env,
                password_env=config.notifications.email.password_env,
                from_addr=config.notifications.email.from_addr,
                to_addrs=config.notifications.email.to_addrs,
            )
        )
    if config.notifications.telegram.enabled:
        notifiers.append(
            TelegramNotifier(
                bot_token_env=config.notifications.telegram.bot_token_env,
                chat_id=config.notifications.telegram.chat_id,
            )
        )
    notifier = NotificationManager(notifiers)

    agent = Agent(
        config=config,
        audit=audit,
        memory=memory,
        rbac=rbac,
        notifier=notifier,
        auto_healer=auto_healer,
    )

    webhook_queue = None
    if config.webhooks.enabled:
        import uvicorn

        webhook_queue = asyncio.Queue()
        shared_secret = get_env(config.webhooks.shared_secret_env, default="")
        app = create_app(webhook_queue, shared_secret)
        server_config = uvicorn.Config(
            app,
            host=config.webhooks.host,
            port=config.webhooks.port,
            log_level="info",
        )
        server = uvicorn.Server(server_config)
        asyncio.create_task(server.serve())

    await agent.run(webhook_queue=webhook_queue)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic Uptime Maintenance Agent")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yml"),
        help="Path to config YAML",
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=Path(".env"),
        help="Path to .env file",
    )
    args = parser.parse_args()
    if args.env.exists():
        load_dotenv(args.env)
    config = load_config(args.config)
    asyncio.run(_run_agent(config))


if __name__ == "__main__":
    main()
