from __future__ import annotations

import re

from contracts.models import ScaffoldConfig, ScaffoldRequest

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def build_argv(config: ScaffoldConfig, request: ScaffoldRequest) -> list[str]:
    values = {
        "group_id": request.group_id,
        "artifact_id": request.artifact_id,
        "package_name": request.package_name,
        "java_version": request.java_version,
        "extensions": ",".join(request.extensions),
        "tool_version": config.tool_version,
    }
    argv: list[str] = []
    for token in config.command_template:
        placeholders = _PLACEHOLDER.findall(token)
        if any(name not in values for name in placeholders):
            raise ValueError(f"unsupported scaffold placeholder in {token!r}")
        argv.append(_PLACEHOLDER.sub(lambda match: values[match.group(1)], token))
    return argv
