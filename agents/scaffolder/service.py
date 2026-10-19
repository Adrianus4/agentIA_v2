from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path

from agents.scaffolder.command import build_argv
from agents.scaffolder.safety import collect_manifest, validate_request
from contracts.models import FrameworkProfile, ScaffoldRequest, ScaffoldResult

MAX_OUTPUT = 100_000


class Scaffolder(ABC):
    @abstractmethod
    def scaffold(
        self,
        request: ScaffoldRequest,
        profile: FrameworkProfile,
    ) -> ScaffoldResult:
        raise NotImplementedError


class SubprocessScaffolder(Scaffolder):
    def scaffold(
        self,
        request: ScaffoldRequest,
        profile: FrameworkProfile,
    ) -> ScaffoldResult:
        config = profile.scaffold
        if config is None:
            raise ValueError("profile does not define scaffold configuration")
        validate_request(request)
        workspace = Path(request.workspace_path).expanduser().resolve(strict=True)
        argv = build_argv(config, request)
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                argv,
                cwd=workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
                shell=False,
            )
            exit_code = completed.returncode
            output = completed.stdout or ""
            error_code = None if exit_code == 0 else "SCAFFOLD_FAILED"
        except subprocess.TimeoutExpired as exc:
            exit_code = None
            output = str(exc.stdout or "")
            error_code = "SCAFFOLD_TIMEOUT"
        except OSError as exc:
            exit_code = 127
            output = str(exc)
            error_code = "SCAFFOLD_EXECUTION_ERROR"

        truncated = len(output) > MAX_OUTPUT
        output = output[:MAX_OUTPUT]
        manifest = collect_manifest(str(workspace))
        if not manifest and exit_code == 0 and error_code is None:
            success = False
            error_code = "EMPTY_MANIFEST"
        else:
            success = exit_code == 0 and bool(manifest) and error_code is None
        return ScaffoldResult(
            success=success,
            tool=config.tool,
            tool_version=config.tool_version,
            extensions=request.extensions,
            manifest=manifest,
            wall_time_seconds=round(time.perf_counter() - started, 3),
            exit_code=exit_code,
            raw_output=output,
            raw_output_truncated=truncated,
            error_code=error_code,
        )
