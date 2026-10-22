"""The Orca entrypoint must not wrap sys.stdout.buffer on Windows."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ORCA_FILES = (
    ROOT / "aureon-os-upstream" / "aureon" / "bots" / "orca_complete_kill_cycle.py",
    ROOT / "aureon_radar" / "bots" / "orca_complete_kill_cycle.py",
)


def _main_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    marker = 'if __name__ == "__main__":'
    assert marker in text
    return text[text.rindex(marker) :]


def test_orca_main_does_not_wrap_stdout_buffer() -> None:
    for path in ORCA_FILES:
        block = _main_block(path)
        assert "codecs.getwriter" not in block
        assert "sys.stdout.buffer" not in block
        assert "sys.stdout.reconfigure" in block
        assert "sys.stderr.reconfigure" in block
        assert "PYTHONUTF8" in block
