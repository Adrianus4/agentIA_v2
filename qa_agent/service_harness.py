from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qa_agent.execution import (
    MAX_CAPTURE_CHARS,
    _BoundedStreamReader,
    _close_windows_job,
    _create_windows_job_for_process,
    _snapshot_windows_descendants,
    build_windows_safe_argv,
    build_sanitized_environment,
    terminate_process_tree,
)

SERVICE_ROLES: tuple[str, ...] = (
    "validator",
    "generator",
    "verifier",
    "repair",
    "orchestrator",
)


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    """Comprueba si un puerto TCP loopback puede enlazarse actualmente."""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def allocate_loopback_ports(
    count: int,
    host: str = "127.0.0.1",
    exclude_ports: set[int] | None = None,
    max_attempts: int = 20,
) -> list[int]:
    """
    Reserva `count` puertos efímeros distintos en `127.0.0.1` simultáneamente antes de liberarlos,
    minimizando colisiones sin asumir 8000–8004 ni matar procesos ajenos (P01, C05).
    """
    if count <= 0:
        return []
    excluded = set(exclude_ports or set())
    for _ in range(max_attempts):
        sockets: list[socket.socket] = []
        ports: list[int] = []
        try:
            while len(ports) < count:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sockets.append(sock)
                sock.bind((host, 0))
                port = int(sock.getsockname()[1])
                if port not in excluded and port not in ports:
                    ports.append(port)
            return ports
        except OSError:
            continue
        finally:
            for s in sockets:
                with contextlib.suppress(OSError):
                    s.close()
    raise RuntimeError(f"No fue posible asignar {count} puertos libres en {host} tras {max_attempts} intentos.")


class ManagedDaemonProcess:
    """
    Proceso persistente administrado con drenaje concurrente acotado (F04) y terminación completa de árbol (F02).
    Nunca mata procesos que no fueron iniciados por esta instancia (C05, P01).
    """

    def __init__(
        self,
        name: str,
        argv: list[str],
        cwd: Path,
        env: dict[str, str],
        max_capture_chars: int = MAX_CAPTURE_CHARS,
    ) -> None:
        self.name = name
        self.argv = build_windows_safe_argv(argv)
        self.cwd = cwd
        self.env = dict(env)
        self.max_capture_chars = max_capture_chars

        self._proc: subprocess.Popen[str] | None = None
        self._job_handle: int | None = None
        self._tracked_pids: set[int] = set()
        self._out_reader: _BoundedStreamReader | None = None
        self._err_reader: _BoundedStreamReader | None = None
        self.started_at: float | None = None

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc is not None else None

    @property
    def returncode(self) -> int | None:
        if self._proc is None:
            return None
        return self._proc.poll()

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        if self._proc is not None:
            raise RuntimeError(f"El proceso administrado '{self.name}' ya fue iniciado.")

        popen_kwargs: dict[str, Any] = {
            "cwd": str(self.cwd),
            "env": self.env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "shell": False,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True

        self.started_at = time.perf_counter()
        self._proc = subprocess.Popen(self.argv, **popen_kwargs)
        self._job_handle = _create_windows_job_for_process(self._proc)
        if self._proc.pid is not None:
            self._tracked_pids.add(self._proc.pid)
        if os.name == "nt":
            self._tracked_pids = _snapshot_windows_descendants(self._tracked_pids)

        self._out_reader = _BoundedStreamReader(self._proc.stdout, max_chars=self.max_capture_chars)
        self._err_reader = _BoundedStreamReader(self._proc.stderr, max_chars=self.max_capture_chars)
        self._out_reader.start()
        self._err_reader.start()

    def refresh_descendants(self) -> set[int]:
        if os.name == "nt" and self._tracked_pids:
            self._tracked_pids = _snapshot_windows_descendants(self._tracked_pids)
        return set(self._tracked_pids)

    def stdout_text(self) -> str:
        return self._out_reader.get_value() if self._out_reader is not None else ""

    def stderr_text(self) -> str:
        return self._err_reader.get_value() if self._err_reader is not None else ""

    def stop(self) -> None:
        if self._proc is None:
            return
        try:
            self.refresh_descendants()
            terminate_process_tree(
                self._proc,
                tracked_pids=self._tracked_pids,
                job_handle=self._job_handle,
            )
            self._job_handle = None
        finally:
            if self._job_handle is not None:
                _close_windows_job(self._job_handle, terminate=True)
                self._job_handle = None
            if self._out_reader is not None:
                self._out_reader.join(timeout=1.5)
            if self._err_reader is not None:
                self._err_reader.join(timeout=1.5)


def wait_for_http_health(
    url: str,
    proc: ManagedDaemonProcess,
    timeout_seconds: float = 20.0,
) -> None:
    """Espera a que `url` responda HTTP 200 o falla temprano si `proc` termina."""
    deadline = time.perf_counter() + timeout_seconds
    last_error = ""
    while time.perf_counter() < deadline:
        if not proc.is_running():
            rc = proc.returncode
            err = proc.stderr_text()[-1200:]
            out = proc.stdout_text()[-600:]
            raise RuntimeError(
                f"El servicio '{proc.name}' terminó prematuramente (exit={rc}) antes de pasar healthcheck ({url}).\n"
                f"STDOUT: {out}\nSTDERR: {err}"
            )
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.08)

    err = proc.stderr_text()[-1200:]
    raise TimeoutError(
        f"Healthcheck agotó el tiempo ({timeout_seconds}s) para '{proc.name}' en {url}. Último error: {last_error}. STDERR: {err}"
    )


@dataclass
class PlatformServiceHarness:
    """
    Harness local de 5 servicios FastAPI reales en procesos Python separados sobre `127.0.0.1` (Trabajo 3 / Trabajo 4).
    - Asigna puertos dinámicos por ejecución con reintento acotado si un puerto es ocupado en carrera.
    - Configura directorios independientes para SQLite, workflow_state, workspaces y verifier_scratch.
    - Retira únicamente los procesos iniciados por esta instancia en `stop()` / `finally`.
    """

    repo_root: Path
    harness_root: Path
    mode: str = "platform"  # "platform" (compiler=double, llm=double) o "java" (compiler=real, llm=double)
    orchestrator_api_key: str = "qa-orch-synthetic-key-004"
    gateway_api_key: str = "qa-gateway-synthetic-key-004"
    python_executable: str = field(default_factory=lambda: sys.executable)
    extra_env: dict[str, str] = field(default_factory=dict)
    forced_ports: dict[str, int] = field(default_factory=dict)
    excluded_ports: set[int] = field(default_factory=set)
    fail_on_occupied_forced_port: bool = False

    ports: dict[str, int] = field(default_factory=dict, init=False)
    processes: dict[str, ManagedDaemonProcess] = field(default_factory=dict, init=False)
    sqlite_path: Path = field(init=False)
    workflow_state_dir: Path = field(init=False)
    workspaces_dir: Path = field(init=False)
    verifier_scratch_dir: Path = field(init=False)
    control_file: Path = field(init=False)
    telemetry_file: Path = field(init=False)

    def __post_init__(self) -> None:
        self.harness_root = self.harness_root.resolve()
        self.repo_root = self.repo_root.resolve()
        state_root = self.harness_root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = state_root / "orchestrator.db"
        self.workflow_state_dir = state_root / "workflows"
        self.workspaces_dir = self.harness_root / "ws"
        self.verifier_scratch_dir = self.harness_root / "vs"
        self.control_file = self.harness_root / "scenario_control.json"
        self.telemetry_file = self.harness_root / "scenario_telemetry.jsonl"
        for d in (self.workflow_state_dir, self.workspaces_dir, self.verifier_scratch_dir):
            d.mkdir(parents=True, exist_ok=True)
        if not self.control_file.exists():
            self.set_control({})

    def set_control(self, config: dict[str, Any]) -> None:
        """Actualiza atómicamente la configuración de dobles de frontera / fallos controlados del escenario."""
        payload = json.dumps(config, indent=2)
        for attempt in range(5):
            try:
                tmp_file = self.control_file.with_suffix(f".{os.getpid()}.{attempt}.tmp")
                tmp_file.write_text(payload, encoding="utf-8")
                tmp_file.replace(self.control_file)
                return
            except OSError:
                time.sleep(0.02)
        self.control_file.write_text(payload, encoding="utf-8")

    def update_control(self, **kwargs: Any) -> dict[str, Any]:
        """Actualiza claves específicas en el archivo de control conservando el resto."""
        current: dict[str, Any] = {}
        if self.control_file.is_file():
            with contextlib.suppress(OSError, json.JSONDecodeError):
                current = json.loads(self.control_file.read_text(encoding="utf-8"))
        current.update(kwargs)
        self.set_control(current)
        return current

    def read_telemetry(self) -> list[dict[str, Any]]:
        """Lee los eventos registrados por los procesos de servicio y dobles de frontera."""
        if not self.telemetry_file.is_file():
            return []
        events: list[dict[str, Any]] = []
        for line in self.telemetry_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            with contextlib.suppress(json.JSONDecodeError):
                events.append(json.loads(line))
        return events

    def clear_telemetry(self) -> None:
        if self.telemetry_file.is_file():
            self.telemetry_file.unlink()

    def service_url(self, role: str) -> str:
        return f"http://127.0.0.1:{self.ports[role]}"

    @property
    def orchestrator_url(self) -> str:
        return self.service_url("orchestrator")

    def _build_service_env(self, role: str, role_extra_env: dict[str, str] | None = None) -> dict[str, str]:
        base_env = build_sanitized_environment(os.environ, self.harness_root)
        # Configurar PYTHONPATH para que el servicio importe desde repo_root
        existing_py = base_env.get("PYTHONPATH", "")
        base_env["PYTHONPATH"] = (
            f"{self.repo_root}{os.pathsep}{existing_py}" if existing_py else str(self.repo_root)
        )
        base_env["AGENTIA_WORKSPACE_ROOT"] = str(self.workspaces_dir)
        base_env["ORCHESTRATOR_DATABASE_PATH"] = str(self.sqlite_path)
        base_env["WORKFLOW_STATE_DIR"] = str(self.workflow_state_dir)
        base_env["VERIFIER_SCRATCH_DIR"] = str(self.verifier_scratch_dir)
        base_env["ORCHESTRATOR_API_KEY"] = self.orchestrator_api_key
        base_env["AGENT_GATEWAY_API_KEY"] = self.gateway_api_key
        base_env["BLUEPRINT_VALIDATOR_URL"] = self.service_url("validator")
        base_env["GENERATOR_URL"] = self.service_url("generator")
        base_env["VERIFIER_URL"] = self.service_url("verifier")
        base_env["REPAIR_URL"] = self.service_url("repair")
        base_env["QA_HARNESS_MODE"] = self.mode
        base_env["QA_SCENARIO_CONTROL_FILE"] = str(self.control_file)
        base_env["QA_SCENARIO_TELEMETRY_FILE"] = str(self.telemetry_file)
        base_env["QA_SERVICE_ROLE"] = role
        if self.mode == "platform":
            base_env["VERIFIER_DRY_RUN"] = "0"
            base_env["VERIFIER_RUNNER"] = "host"
        elif self.mode == "java":
            base_env["VERIFIER_DRY_RUN"] = "0"
            base_env["VERIFIER_RUNNER"] = "host"
            base_env["VERIFIER_KEEP_WORKSPACE"] = "1"

        base_env.update(self.extra_env)
        if role_extra_env:
            base_env.update(role_extra_env)
        return base_env

    def _spawn_role(
        self,
        role: str,
        startup_timeout_seconds: float = 20.0,
        role_extra_env: dict[str, str] | None = None,
    ) -> ManagedDaemonProcess:
        port = self.ports[role]
        env = self._build_service_env(role, role_extra_env=role_extra_env)
        argv = [
            self.python_executable,
            "-m",
            "qa_scenarios.support.service_node_runner",
            "--role",
            role,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--mode",
            self.mode,
        ]
        proc = ManagedDaemonProcess(
            name=f"qa-{role}-{port}",
            argv=argv,
            cwd=self.repo_root,
            env=env,
        )
        proc.start()
        self.processes[role] = proc
        wait_for_http_health(
            url=f"http://127.0.0.1:{port}/health",
            proc=proc,
            timeout_seconds=startup_timeout_seconds,
        )
        return proc

    def start(self, startup_timeout_seconds: float = 25.0) -> None:
        """
        Inicia los 5 servicios reales y verifica `/health` en cada uno.
        Si un puerto está ocupado y no se forzó el fallo, reasigna puertos dinámicamente.
        Si cualquier servicio falla en arrancar, retira inmediatamente todos los procesos propios iniciados.
        """
        base_excluded = set(self.excluded_ports) | set(self.forced_ports.values())
        allocated = allocate_loopback_ports(len(SERVICE_ROLES), exclude_ports=base_excluded)
        for idx, role in enumerate(SERVICE_ROLES):
            if role in self.forced_ports:
                forced_port = self.forced_ports[role]
                if not is_port_free(forced_port) and not self.fail_on_occupied_forced_port:
                    # Reasignar automáticamente un puerto libre sin matar el proceso ocupante (P01)
                    replacement = allocate_loopback_ports(
                        1, exclude_ports=base_excluded | set(allocated) | {forced_port}
                    )[0]
                    self.ports[role] = replacement
                else:
                    self.ports[role] = forced_port
            else:
                self.ports[role] = allocated[idx]

        try:
            for role in SERVICE_ROLES:
                self._spawn_role(role, startup_timeout_seconds=startup_timeout_seconds)
        except Exception:
            self.stop()
            raise

    def restart_service(
        self,
        role: str,
        startup_timeout_seconds: float = 20.0,
        role_extra_env: dict[str, str] | None = None,
    ) -> ManagedDaemonProcess:
        """Reinicia un servicio específico (p. ej. `orchestrator`) conservando su puerto, SQLite y estado en disco."""
        existing = self.processes.get(role)
        if existing is not None:
            existing.stop()
        # Si el puerto anterior sigue en TIME_WAIT/ocupado, esperar brevemente a que el SO lo suelte
        port = self.ports[role]
        deadline = time.perf_counter() + 3.0
        while time.perf_counter() < deadline and not is_port_free(port):
            time.sleep(0.05)
        return self._spawn_role(
            role,
            startup_timeout_seconds=startup_timeout_seconds,
            role_extra_env=role_extra_env,
        )

    def restart_orchestrator(
        self,
        startup_timeout_seconds: float = 20.0,
        role_extra_env: dict[str, str] | None = None,
    ) -> ManagedDaemonProcess:
        return self.restart_service(
            "orchestrator",
            startup_timeout_seconds=startup_timeout_seconds,
            role_extra_env=role_extra_env,
        )

    def stop(self) -> None:
        """Detiene todos los procesos iniciados por este harness en orden inverso."""
        for role in reversed(SERVICE_ROLES):
            proc = self.processes.get(role)
            if proc is not None:
                with contextlib.suppress(Exception):
                    proc.stop()
        self.processes.clear()

    def __enter__(self) -> PlatformServiceHarness:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.stop()
