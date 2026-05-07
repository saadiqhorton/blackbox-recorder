from pathlib import Path


def resolve_project_dir(
    claude_dir: str | Path = "~/.claude",
    cwd: str | Path | None = None,
) -> Path:
    """Derive the Claude Code project session directory from CWD.

    Claude Code stores sessions at ``~/.claude/projects/<derived-name>/``
    where ``derived-name`` is the absolute CWD with ``/`` replaced by ``-``
    and prefixed with ``-`` (e.g. ``/home/user/proj`` → ``-home-user-proj``).
    """
    base = Path(claude_dir).expanduser().resolve()
    cwd_path = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    project_dir_name = "-" + str(cwd_path).strip("/").replace("/", "-")
    return base / "projects" / project_dir_name


def find_latest_sessions(project_dir: Path, n: int = 1) -> list[Path]:
    """Return the *n* most recently modified ``.jsonl`` session files."""
    if not project_dir.is_dir():
        return []

    jsonl_files = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return jsonl_files[:n]
