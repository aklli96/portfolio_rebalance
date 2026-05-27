import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"


def _venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _same_path(path_a: Path, path_b: Path) -> bool:
    resolved_a = Path(path_a).resolve()
    resolved_b = Path(path_b).resolve()
    try:
        return resolved_a.samefile(resolved_b)
    except OSError:
        return str(resolved_a).lower() == str(resolved_b).lower()


def _find_requirements_file() -> Path | None:
    for filename in ("requirements.txt", "requirement.txt"):
        candidate = PROJECT_ROOT / filename
        if candidate.exists():
            return candidate
    return None


def _create_virtual_environment(venv_dir: Path) -> None:
    print("No virtual environment found. Creating .venv...")
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)], cwd=PROJECT_ROOT)


def _install_dependencies(venv_python: Path, requirements_file: Path | None) -> None:
    if requirements_file is None:
        print("No requirements file found (requirements.txt or requirement.txt). Skipping install.")
        return

    print(f"Installing dependencies from {requirements_file.name}...")
    subprocess.check_call(
        [str(venv_python), "-m", "pip", "install", "-r", str(requirements_file)],
        cwd=PROJECT_ROOT,
    )


def ensure_environment(entry_script: Path | None = None) -> None:
    """Ensure project virtual environment exists, then relaunch the script using it."""
    if entry_script is None:
        entry_script = PROJECT_ROOT / "main.py"

    venv_python = _venv_python_path(VENV_DIR)
    created_venv = False

    if not venv_python.exists():
        _create_virtual_environment(VENV_DIR)
        created_venv = True
        venv_python = _venv_python_path(VENV_DIR)

    if created_venv:
        _install_dependencies(venv_python, _find_requirements_file())

    if not _same_path(Path(sys.executable), venv_python):
        command = [str(venv_python), str(entry_script), *sys.argv[1:]]
        raise SystemExit(subprocess.call(command, cwd=PROJECT_ROOT))

    # Sanity check: at this point we must be running inside the venv.
    if not _same_path(Path(sys.executable), venv_python):
        raise RuntimeError(
            f"Expected venv Python:\n  {venv_python}\n"
            f"but process is running with:\n  {sys.executable}"
        )