from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..analysis.code_introspect import CodeIntrospector
from ..analysis.diagnostics import DiagnosticsCollector
from ..analysis.log_analyzer import LogAnalyzer
from ..analysis.llm_client import LLMClient
from ..audit import AuditLogger
from ..config import ServiceConfig
from ..memory import MemoryStore
from ..rbac import RBAC
from .deployment import DeploymentManager
from .patcher import PatchApplier


@dataclass
class IncidentContext:
    incident_id: int
    check_name: str
    status: str
    message: str


class AutoHealer:
    def __init__(
        self,
        rbac: RBAC,
        audit: AuditLogger,
        memory: MemoryStore,
        diagnostics: DiagnosticsCollector,
        analyzer: LogAnalyzer,
        deployment: DeploymentManager,
        patcher: PatchApplier,
        llm: Optional[LLMClient] = None,
    ) -> None:
        self.rbac = rbac
        self.audit = audit
        self.memory = memory
        self.diagnostics = diagnostics
        self.analyzer = analyzer
        self.deployment = deployment
        self.patcher = patcher
        self.llm = llm
        self.introspector = CodeIntrospector()
        self.logger = logging.getLogger(__name__)

    def handle_incident(
        self, incident: IncidentContext, service: Optional[ServiceConfig]
    ) -> Dict[str, Any]:
        if not service:
            return {"status": "skipped", "reason": "No service mapping"}
        diagnostics = self.diagnostics.collect(
            log_paths=service.log_paths,
            systemd_service=service.systemd_service,
            repo_path=service.repo_path,
            docker_container=service.docker_container,
        )
        analysis = self.analyzer.analyze(diagnostics)
        results: List[Dict[str, Any]] = []
        for step in service.runbook:
            try:
                if step.action == "apply_patch":
                    output = self._apply_patch_step(step.args, service, incident, analysis)
                else:
                    output = self.deployment.execute_step(step.action, step.args)
                results.append({"action": step.action, "status": "ok", "output": output})
                self.memory.record_action(incident.incident_id, step.action, "ok", output)
            except Exception as exc:
                error = str(exc)
                results.append({"action": step.action, "status": "error", "output": error})
                self.memory.record_action(incident.incident_id, step.action, "error", error)
                self.logger.exception("Runbook step failed")
                break
        return {
            "status": "completed",
            "analysis": analysis.__dict__,
            "results": results,
        }

    def _apply_patch_step(
        self,
        args: Dict[str, Any],
        service: ServiceConfig,
        incident: IncidentContext,
        analysis: Any,
    ) -> str:
        if not service.repo_path:
            raise RuntimeError("apply_patch requires repo_path")
        diff_text = args.get("diff")
        if not diff_text:
            if not self.llm:
                raise RuntimeError("LLM required to generate patch")
            diff_text = self._generate_patch_with_llm(service, incident, analysis)
        applied = self.patcher.apply_patch(service.repo_path, diff_text)
        if service.tests_command:
            self.patcher.run_tests(service.repo_path, service.tests_command)
        return applied

    def _generate_patch_with_llm(
        self, service: ServiceConfig, incident: IncidentContext, analysis: Any
    ) -> str:
        keywords = [incident.check_name, incident.message, analysis.suspected_cause]
        context = self.introspector.search(service.repo_path, keywords)
        snippet_text = "\n\n".join(
            f"File: {path}\n{context.snippets[str(path)]}"
            for path in context.files
        )
        prompt = [
            {
                "role": "system",
                "content": "You are a senior engineer. Produce a unified diff patch only.",
            },
            {
                "role": "user",
                "content": (
                    "Incident details:\n"
                    f"Check: {incident.check_name}\n"
                    f"Message: {incident.message}\n"
                    f"Suspected cause: {analysis.suspected_cause}\n\n"
                    "Code context:\n"
                    f"{snippet_text}\n\n"
                    "Generate a unified diff patch to fix the issue. "
                    "Only output the diff. Do not include markdown fences."
                ),
            },
        ]
        response = self.llm.chat(prompt) if self.llm else ""
        diff_match = re.search(r"(diff --git[\s\S]+)", response)
        return diff_match.group(1) if diff_match else response
