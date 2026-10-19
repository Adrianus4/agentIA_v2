from pathlib import Path

from app.core.llm.client import FakeLLMClient
from app.orchestrator.pipeline import PipelineGraph
from contracts.models import ScaffoldResult, VerificationResult

BLUEPRINT = {
    "serviceName": "billing",
    "packageName": "com.example.billing",
    "framework": "quarkus",
    "version": "3",
    "entities": [{"name": "Invoice"}],
    "userStories": [],
    "scaffold": True,
}


class Runner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, request):
        self.commands.append(request.command)
        return VerificationResult(
            success=True,
            exit_code=0,
            wall_time_seconds=0.01,
            issues=[],
            raw_output="BUILD SUCCESS",
            runner_name="fake",
            image="fake",
        )


class Scaffolder:
    def scaffold(self, request, profile):
        Path(request.workspace_path, "pom.xml").write_text("<project/>", encoding="utf-8")
        return ScaffoldResult(
            success=True,
            tool=profile.scaffold.tool,
            tool_version=profile.scaffold.tool_version,
            extensions=request.extensions,
            manifest=[],
            wall_time_seconds=0.01,
            exit_code=0,
        )


def test_scaffold_stage_precedes_generation(tmp_path: Path) -> None:
    runner = Runner()
    state = PipelineGraph(
        FakeLLMClient("class Generated {}"),
        runner=runner,
        scaffolder=Scaffolder(),
    ).run(str(tmp_path), BLUEPRINT, "trace-scaffold")

    assert state.outcome == "SUCCESS"
    assert runner.commands[0] == ["mvn", "-o", "-q", "test-compile"]
    assert runner.commands[1] == ["mvn", "clean", "test"]
