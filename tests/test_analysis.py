from pathlib import Path

from agentic_uptime.analysis.code_introspect import CodeIntrospector
from agentic_uptime.analysis.log_analyzer import LogAnalyzer


def test_log_analyzer_pattern_match() -> None:
    analyzer = LogAnalyzer()
    report = analyzer.analyze({"log": "connection refused while connecting"})
    assert "connection refused" in report.suspected_cause.lower()


def test_code_introspector_search(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "app.py"
    target.write_text("def handler():\n    return 'ok'\n", encoding="utf-8")
    inspector = CodeIntrospector()
    context = inspector.search(repo, ["handler"])
    assert context.files
    assert "handler" in context.snippets[str(target)]
