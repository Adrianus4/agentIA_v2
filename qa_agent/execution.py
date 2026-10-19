"""Aislamiento de workspace temporal, captura acotada y gestión de árbol de procesos (E05, F02, F03, F04)."""

from __future__ import annotations

import contextlib
import ctypes
import datetime
import os
import secrets
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

SCRATCH_OWNER_FILENAME = ".agentia-qa-scratch-owner"
MAX_CAPTURE_CHARS = 128000
READ_CHUNK_SIZE = 4096

COPY_DIRS: tuple[str, ...] = (
    "app",
    "agents",
    "services",
    "contracts",
    "profiles",
    "templates",
    "blueprints",
    "fixtures",
    "examples",
    "tests",
)

COPY_FILES: tuple[str, ...] = (
    "pyproject.toml",
    "Dockerfile",
    "main.py",
    "scripts/cli.py",
)

EXCLUDED_NAMES: set[str] = {
    ".git",
    ".env",
    ".venv",
    "venv",
    "env",
    "ENV",
    "node_modules",
    "dist",
    ".vite",
    ".agentia-state",
    ".agentia-runtime",
    "qa_tests",
    "qa_agent",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "video",
    "models",
    "tools",
    "setup_copilot_tcs.py",
    "run_setup.bat",
}

ALLOWED_ENV_KEYS: set[str] = {
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "PATH",
    "USERPROFILE",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "APPDATA",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "COMMONPROGRAMFILES",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "OS",
    "LANG",
    "LC_ALL",
}


@dataclass
class IsolatedWorkspace:
    trace_id: str
    scratch_root: Path
    repo_copy: Path
    pytest_basetemp: Path
    pytest_cache: Path
    raw_xml_path: Path
    env: dict[str, str]


@dataclass
class SubprocessOutcome:
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool
    interrupted: bool
    output_truncated: bool


def generate_trace_id() -> str:
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"qa-{stamp}-{secrets.token_hex(4)}"


def _ensure_safe_symlink(path: Path, repo_root: Path) -> None:
    if path.is_symlink():
        target = path.resolve()
        try:
            target.relative_to(repo_root.resolve())
        except ValueError as exc:
            raise RuntimeError(f"Enlace simbólico apunta fuera del repositorio: {path} -> {target}") from exc


def _inject_per_case_isolation(conftest_path: Path) -> None:
    """Inyecta aislamiento por caso para test_solution_generation.py sin imponer AGENTIA_WORKSPACE_ROOT globalmente."""
    conftest_path.parent.mkdir(parents=True, exist_ok=True)
    existing = conftest_path.read_text(encoding="utf-8") if conftest_path.is_file() else ""
    hook_code = """

# --- QA Runner Per-Case Isolation Hook ---
import os as _qa_os
import pytest as _qa_pytest

@_qa_pytest.fixture(autouse=True)
def _qa_isolate_solution_generation_workspace(request, monkeypatch):
    if request.node.fspath and "test_solution_generation.py" in str(request.node.fspath):
        isolated_root = _qa_os.environ.get("QA_ISOLATED_SOLUTIONS_ROOT")
        if isolated_root and "AGENTIA_WORKSPACE_ROOT" not in _qa_os.environ:
            monkeypatch.setenv("AGENTIA_WORKSPACE_ROOT", isolated_root)
"""
    conftest_path.write_text(existing + hook_code, encoding="utf-8")


def _safe_remove_scratch(scratch_root: Path, trace_id: str, user_repo_root: Path) -> None:
    """Elimina un directorio scratch verificando propiedad y asegurando no borrar rutas del usuario."""
    scratch = scratch_root.resolve()
    repo_resolved = user_repo_root.resolve()

    if scratch == repo_resolved or repo_resolved.is_relative_to(scratch):
        return

    marker = scratch / SCRATCH_OWNER_FILENAME
    if not marker.is_file():
        return
    try:
        owner = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if owner != trace_id:
        return

    shutil.rmtree(scratch, ignore_errors=True)


BATCH_FORBIDDEN_CHARS = set("&|><^%!();\r\n\x00")


def build_windows_safe_argv(argv: list[str]) -> list[str]:
    """
    Valida y adapta un arreglo argv para ejecución segura sin inyección de shell ni de batch en Windows (RF-314, C05).
    Si el ejecutable es un wrapper .cmd/.bat, rechaza metacaracteres de cmd.exe y saltos de línea en todos los argumentos.
    """
    if not argv or not argv[0].strip():
        raise ValueError("El comando argv no puede estar vacío.")
    for token in argv:
        if "\x00" in token:
            raise ValueError(f"Argumento inválido con byte nulo: {token!r}")

    exe = argv[0]
    if exe.lower().endswith((".cmd", ".bat")):
        for token in argv:
            bad = [ch for ch in token if ch in BATCH_FORBIDDEN_CHARS]
            if bad:
                raise ValueError(
                    f"Metacaracteres de batch no permitidos ({bad}) al invocar wrapper de Windows: {token!r}"
                )
        if os.name == "nt":
            # Si es un script mvn.cmd/mvn.bat y podemos resolver plexus-classworlds con java.exe,
            # preferimos invocar java.exe directamente para evitar cmd.exe por completo.
            mvn_bin = Path(exe).resolve()
            mvn_home = mvn_bin.parent.parent
            boot_dir = mvn_home / "boot"
            m2_conf = mvn_home / "bin" / "m2.conf"
            if mvn_bin.stem.lower() == "mvn" and boot_dir.is_dir() and m2_conf.is_file():
                jars = list(boot_dir.glob("plexus-classworlds-*.jar"))
                java_exe = shutil.which("java")
                if not java_exe:
                    # Buscar en .agentia-runtime/toolchains
                    toolchains_root = mvn_home.parent
                    for cand in toolchains_root.glob("jdk*/bin/java.exe"):
                        if cand.is_file():
                            java_exe = str(cand.resolve())
                            break
                    if not java_exe:
                        for cand in toolchains_root.glob("jdk*/*/bin/java.exe"):
                            if cand.is_file():
                                java_exe = str(cand.resolve())
                                break
                if jars and java_exe:
                    return [
                        java_exe,
                        "-classpath",
                        str(jars[0].resolve()),
                        f"-Dclassworlds.conf={m2_conf.resolve()}",
                        f"-Dmaven.home={mvn_home.resolve()}",
                        f"-Dlibrary.jansi.path={mvn_home.resolve() / 'lib' / 'jansi-native'}",
                        "-Dmaven.multiModuleProjectDirectory=.",
                        "org.codehaus.plexus.classworlds.launcher.Launcher",
                        *argv[1:],
                    ]
    return list(argv)


def build_sanitized_environment(base_env: Any, scratch_root: Path) -> dict[str, str]:
    """Construye un entorno limpio con lista blanca y rutas temporales confinadas dentro de scratch_root."""
    tmp_dir = scratch_root / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    clean_env: dict[str, str] = {}
    for k, v in base_env.items():
        if str(k).upper() in ALLOWED_ENV_KEYS:
            clean_env[str(k)] = str(v)
    clean_env["TMP"] = str(tmp_dir)
    clean_env["TEMP"] = str(tmp_dir)
    clean_env["TMPDIR"] = str(tmp_dir)
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    clean_env["PYTHONUTF8"] = "1"
    return clean_env


def prepare_isolated_workspace(
    repo_root: Path,
    trace_id: str,
    suite_id: str = "python",
    extra_copy_dirs: tuple[str, ...] = (),
) -> IsolatedWorkspace:
    """Crea un directorio scratch con marcador de propiedad y recursos por suite, limpiándolo si falla la copia (F03, C05)."""
    scratch_root = Path(tempfile.mkdtemp(prefix=f"agentia-{trace_id}-")).resolve()
    marker = scratch_root / SCRATCH_OWNER_FILENAME
    marker.write_text(trace_id, encoding="utf-8")

    try:
        repo_copy = scratch_root / "repo"
        repo_copy.mkdir(parents=True, exist_ok=True)

        for rel_file in COPY_FILES:
            src = repo_root / rel_file
            if src.exists():
                _ensure_safe_symlink(src, repo_root)
                if src.is_file():
                    dst = repo_copy / rel_file
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)

        for top_item in repo_root.iterdir():
            if top_item.name in EXCLUDED_NAMES or top_item.name.startswith(".env"):
                continue
            if (
                top_item.is_file()
                and top_item.suffix in {".txt", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".json"}
                and top_item.name not in {"uv.lock", "openship.json"}
            ):
                _ensure_safe_symlink(top_item, repo_root)
                shutil.copy2(top_item, repo_copy / top_item.name)

        dirs_to_copy = list(COPY_DIRS)
        if suite_id in ("platform", "java", "playwright", "llm"):
            for req_dir in ("qa_scenarios", "qa_agent"):
                if req_dir not in dirs_to_copy:
                    dirs_to_copy.append(req_dir)
        if suite_id in ("frontend", "playwright") and "frontend" not in dirs_to_copy:
            dirs_to_copy.append("frontend")
        for ed in extra_copy_dirs:
            if ed not in dirs_to_copy:
                dirs_to_copy.append(ed)

        for rel_dir in dirs_to_copy:
            src_dir = repo_root / rel_dir
            dir_excluded = EXCLUDED_NAMES - ({rel_dir} if rel_dir == "qa_agent" else set())
            if not src_dir.is_dir():
                if rel_dir in ("qa_scenarios", "qa_agent"):
                    agent_root = Path(__file__).resolve().parents[1]
                    alt_src = agent_root / rel_dir
                    if alt_src.is_dir():
                        for item in alt_src.rglob("*"):
                            if any(part in dir_excluded for part in item.relative_to(agent_root).parts):
                                continue
                            if item.is_file():
                                rel_posix = item.relative_to(agent_root).as_posix()
                                dst = repo_copy / rel_posix
                                dst.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(item, dst)
                continue
            _ensure_safe_symlink(src_dir, repo_root)
            for item in src_dir.rglob("*"):
                rel_parts = item.relative_to(repo_root).parts
                if any(
                    part in dir_excluded
                    or part.startswith(".env")
                    or part.endswith((".pyc", ".pyo", ".db", ".db-journal", ".pdf", ".gguf", ".bin"))
                    for part in rel_parts
                ):
                    continue
                _ensure_safe_symlink(item, repo_root)
                if item.is_file():
                    rel_posix = item.relative_to(repo_root).as_posix()
                    dst = repo_copy / rel_posix
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dst)

        _inject_per_case_isolation(repo_copy / "tests" / "conftest.py")

        tmp_dir = scratch_root / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        state_dir = scratch_root / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        pytest_basetemp = scratch_root / "pytest-tmp"
        pytest_cache = scratch_root / "pytest-cache"
        raw_xml_path = scratch_root / f"raw-{suite_id}.junit.xml"

        clean_env: dict[str, str] = {}
        for k, v in os.environ.items():
            if k.upper() in ALLOWED_ENV_KEYS:
                clean_env[k] = v

        clean_env["TMP"] = str(tmp_dir)
        clean_env["TEMP"] = str(tmp_dir)
        clean_env["TMPDIR"] = str(tmp_dir)
        clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
        clean_env["PYTHONUTF8"] = "1"
        clean_env["ORCHESTRATOR_DATABASE_PATH"] = str(state_dir / "runs.db")
        clean_env["WORKFLOW_STATE_DIR"] = str(state_dir / "workflow-state")
        clean_env["VERIFIER_SCRATCH_DIR"] = str(tmp_dir / "verifier-scratch")
        clean_env["QA_ISOLATED_SOLUTIONS_ROOT"] = str(scratch_root / "managed-workspaces")

        return IsolatedWorkspace(
            trace_id=trace_id,
            scratch_root=scratch_root,
            repo_copy=repo_copy,
            pytest_basetemp=pytest_basetemp,
            pytest_cache=pytest_cache,
            raw_xml_path=raw_xml_path,
            env=clean_env,
        )
    except BaseException:
        _safe_remove_scratch(scratch_root=scratch_root, trace_id=trace_id, user_repo_root=repo_root)
        raise


def cleanup_isolated_workspace(workspace: IsolatedWorkspace, user_repo_root: Path) -> None:
    """Limpia exclusivamente directorios scratch propios verificando el marcador de propiedad."""
    _safe_remove_scratch(
        scratch_root=workspace.scratch_root,
        trace_id=workspace.trace_id,
        user_repo_root=user_repo_root,
    )


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("cntUsage", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", ctypes.c_uint32),
        ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32),
        ("pcPriClassBase", ctypes.c_int32),
        ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def _create_windows_job_for_process(proc: subprocess.Popen[str]) -> int | None:
    if os.name != "nt":
        return None
    try:
        kernel32 = getattr(ctypes, "windll", None)
        if kernel32 is None:
            return None
        k32 = kernel32.kernel32
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        k32.CreateJobObjectW.restype = ctypes.c_void_p
        k32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        k32.AssignProcessToJobObject.restype = ctypes.c_int
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.CloseHandle.restype = ctypes.c_int

        job_handle = k32.CreateJobObjectW(None, None)
        if not job_handle:
            return None
        proc_handle = int(getattr(proc, "_handle", 0))
        if not proc_handle:
            k32.CloseHandle(job_handle)
            return None
        ok = k32.AssignProcessToJobObject(job_handle, ctypes.c_void_p(proc_handle))
        if not ok:
            k32.CloseHandle(job_handle)
            return None
        return int(job_handle)
    except OSError:
        return None


def _snapshot_windows_descendants(known_pids: set[int]) -> set[int]:
    """Descubre procesos hijos/nietos activos en Windows mediante CreateToolhelp32Snapshot."""
    if os.name != "nt" or not known_pids:
        return set(known_pids)
    try:
        kernel32 = getattr(ctypes, "windll", None)
        if kernel32 is None:
            return set(known_pids)
        k32 = kernel32.kernel32
        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        k32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
        k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PROCESSENTRY32W)]
        k32.Process32FirstW.restype = ctypes.c_int
        k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PROCESSENTRY32W)]
        k32.Process32NextW.restype = ctypes.c_int
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.CloseHandle.restype = ctypes.c_int

        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snap or snap == INVALID_HANDLE_VALUE:
            return set(known_pids)

        children_by_parent: dict[int, list[int]] = {}
        try:
            entry = _PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
            has_item = k32.Process32FirstW(snap, ctypes.byref(entry))
            while has_item:
                pid = int(entry.th32ProcessID)
                ppid = int(entry.th32ParentProcessID)
                if pid > 0 and pid != ppid:
                    children_by_parent.setdefault(ppid, []).append(pid)
                has_item = k32.Process32NextW(snap, ctypes.byref(entry))
        finally:
            k32.CloseHandle(snap)

        expanded = set(known_pids)
        frontier = list(known_pids)
        while frontier:
            curr = frontier.pop()
            for child_pid in children_by_parent.get(curr, ()):
                if child_pid not in expanded and child_pid != os.getpid():
                    expanded.add(child_pid)
                    frontier.append(child_pid)
        return expanded
    except OSError:
        return set(known_pids)


def _close_windows_job(job_handle: int | None, terminate: bool = False) -> None:
    if os.name != "nt" or not job_handle:
        return
    with contextlib.suppress(OSError):
        kernel32 = getattr(ctypes, "windll", None)
        if kernel32 is None:
            return
        k32 = kernel32.kernel32
        if terminate:
            k32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            k32.TerminateJobObject.restype = ctypes.c_int
            k32.TerminateJobObject(ctypes.c_void_p(job_handle), 1)
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        k32.CloseHandle.restype = ctypes.c_int
        k32.CloseHandle(ctypes.c_void_p(job_handle))


def _terminate_windows_pid(pid: int) -> None:
    if os.name != "nt" or pid <= 0 or pid == os.getpid():
        return
    with contextlib.suppress(OSError):
        kernel32 = getattr(ctypes, "windll", None)
        if kernel32 is not None:
            k32 = kernel32.kernel32
            PROCESS_TERMINATE = 0x0001
            SYNCHRONIZE = 0x00100000
            k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            k32.OpenProcess.restype = ctypes.c_void_p
            k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            k32.TerminateProcess.restype = ctypes.c_int
            k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            k32.WaitForSingleObject.restype = ctypes.c_uint32
            k32.CloseHandle.argtypes = [ctypes.c_void_p]
            k32.CloseHandle.restype = ctypes.c_int

            h_proc = k32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, 0, pid)
            if h_proc:
                try:
                    k32.TerminateProcess(h_proc, 1)
                    k32.WaitForSingleObject(h_proc, 500)
                finally:
                    k32.CloseHandle(h_proc)


def terminate_process_tree(
    proc: subprocess.Popen[str],
    tracked_pids: set[int] | None = None,
    job_handle: int | None = None,
) -> None:
    """Detiene el proceso padre y todos los descendientes rastreados en Windows o POSIX (F02)."""
    all_pids: set[int] = set(tracked_pids or set())
    if proc.pid is not None:
        all_pids.add(proc.pid)

    if os.name == "nt":
        all_pids = _snapshot_windows_descendants(all_pids)
        _close_windows_job(job_handle, terminate=True)
        for pid in sorted(all_pids, reverse=True):
            _terminate_windows_pid(pid)
        for pid in sorted(all_pids, reverse=True):
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=3,
                    shell=False,
                )
        with contextlib.suppress(OSError):
            proc.kill()
    else:
        killpg_fn = getattr(os, "killpg", None)
        getpgid_fn = getattr(os, "getpgid", None)
        sigkill = getattr(signal, "SIGKILL", signal.SIGTERM)
        if proc.pid is not None and callable(killpg_fn) and callable(getpgid_fn):
            with contextlib.suppress(OSError):
                killpg_fn(getpgid_fn(proc.pid), sigkill)
        for pid in sorted(all_pids, reverse=True):
            with contextlib.suppress(OSError):
                os.kill(pid, sigkill)
        with contextlib.suppress(OSError):
            proc.kill()

    with contextlib.suppress(OSError, subprocess.SubprocessError):
        proc.wait(timeout=2)


class _BoundedStreamReader:
    """Drena un stream de forma concurrente limitando la memoria acumulada durante la lectura (F04)."""

    def __init__(self, stream: IO[str] | None, max_chars: int) -> None:
        self._stream = stream
        self._max_chars = max(1, max_chars)
        self._chunks: list[str] = []
        self._collected = 0
        self.truncated = False
        self._thread = threading.Thread(target=self._ReadLoop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout=timeout)

    def _ReadLoop(self) -> None:
        if self._stream is None:
            return
        try:
            while True:
                chunk = self._stream.read(READ_CHUNK_SIZE)
                if not chunk:
                    break
                if self._collected < self._max_chars:
                    remaining = self._max_chars - self._collected
                    if len(chunk) <= remaining:
                        self._chunks.append(chunk)
                        self._collected += len(chunk)
                    else:
                        self._chunks.append(chunk[:remaining])
                        self._collected = self._max_chars
                        self.truncated = True
                else:
                    self.truncated = True
        except (OSError, ValueError):
            pass
        finally:
            with contextlib.suppress(OSError, ValueError):
                self._stream.close()

    def get_value(self) -> str:
        return "".join(self._chunks)


def run_bounded_subprocess(
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
    max_capture_chars: int = MAX_CAPTURE_CHARS,
) -> SubprocessOutcome:
    """Ejecuta un comando argv registrado sin shell, con drenaje acotado en vivo y control de hijos (F02, F04, C05)."""
    argv = build_windows_safe_argv(argv)
    if env.get("QA_SIMULATE_INTERRUPT") == "1" or os.environ.get("QA_SIMULATE_INTERRUPT") == "1":
        return SubprocessOutcome(
            exit_code=None,
            stdout="",
            stderr="Ejecución interrumpida por solicitud del usuario.",
            duration_seconds=0.01,
            timed_out=False,
            interrupted=True,
            output_truncated=False,
        )

    interrupt_after: float | None = None
    raw_int_after = env.get("QA_INTERRUPT_AFTER_SECONDS") or os.environ.get("QA_INTERRUPT_AFTER_SECONDS")
    if raw_int_after:
        with contextlib.suppress(ValueError):
            interrupt_after = max(0.05, float(raw_int_after))

    popen_kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "env": env,
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

    t0 = time.perf_counter()
    proc = subprocess.Popen(argv, **popen_kwargs)
    job_handle = _create_windows_job_for_process(proc)
    tracked_pids: set[int] = {proc.pid} if proc.pid is not None else set()
    if os.name == "nt":
        tracked_pids = _snapshot_windows_descendants(tracked_pids)

    out_reader = _BoundedStreamReader(proc.stdout, max_chars=max_capture_chars)
    err_reader = _BoundedStreamReader(proc.stderr, max_chars=max_capture_chars)
    out_reader.start()
    err_reader.start()

    timed_out = False
    interrupted = False

    try:
        while True:
            if os.name == "nt":
                tracked_pids = _snapshot_windows_descendants(tracked_pids)

            proc_done = proc.poll() is not None
            streams_done = (not out_reader.is_alive()) and (not err_reader.is_alive())
            if proc_done and streams_done:
                break

            elapsed = time.perf_counter() - t0
            if interrupt_after is not None and elapsed >= interrupt_after:
                raise KeyboardInterrupt

            if elapsed >= timeout_seconds:
                timed_out = True
                terminate_process_tree(proc, tracked_pids=tracked_pids, job_handle=job_handle)
                job_handle = None
                break

            time.sleep(0.015)
    except KeyboardInterrupt:
        interrupted = True
        terminate_process_tree(proc, tracked_pids=tracked_pids, job_handle=job_handle)
        job_handle = None
    finally:
        if job_handle is not None:
            _close_windows_job(job_handle, terminate=timed_out or interrupted)

    out_reader.join(timeout=1.5)
    err_reader.join(timeout=1.5)

    duration = round(time.perf_counter() - t0, 4)
    stdout = out_reader.get_value()
    stderr = err_reader.get_value()
    truncated = out_reader.truncated or err_reader.truncated

    return SubprocessOutcome(
        exit_code=proc.returncode if not (timed_out or interrupted) else None,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
        timed_out=timed_out,
        interrupted=interrupted,
        output_truncated=truncated,
    )
