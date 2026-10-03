import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from laminci.__main__ import _call_with_lamindb_agent_docs
from laminci._agent_docs import (
    remove_lamindb_agent_docs,
    sync_lamindb_agent_docs,
)


def _checkout(root: Path) -> None:
    (root / "lamindb").mkdir()
    (root / "lamindb" / "__init__.py").write_text("")
    docs = root / "docs"
    (docs / "faq").mkdir(parents=True)
    (root / "README.md").write_text("# LaminDB\n")
    (docs / "guide.md").write_text("# Guide\n")
    (docs / "tutorial.md").write_text("# Tutorial\n")
    (docs / "faq" / "search.md").write_text("# Search\n")
    (docs / "notes.txt").write_text("skip")


def test_sync_copies_markdown_then_remove_deletes_it(tmp_path: Path):
    _checkout(tmp_path)
    dest = sync_lamindb_agent_docs(tmp_path)
    assert (dest / "README.md").read_text() == "# LaminDB\n"
    assert (dest / "guide.md").read_text() == "# Guide\n"
    assert (dest / "tutorial.md").is_file()
    assert (dest / "faq" / "search.md").is_file()
    assert not (dest / "notes.txt").exists()
    remove_lamindb_agent_docs(tmp_path)
    assert not dest.exists()


def test_sync_refuses_when_readme_is_missing(tmp_path: Path):
    _checkout(tmp_path)
    (tmp_path / "README.md").unlink()
    with pytest.raises(SystemExit, match="README.md"):
        sync_lamindb_agent_docs(tmp_path)
    assert not (tmp_path / "lamindb" / ".agents" / "docs").exists()


def test_sync_refuses_when_prepare_deleted_executable_pages(tmp_path: Path):
    _checkout(tmp_path)
    (tmp_path / "docs" / "tutorial.md").unlink()
    with pytest.raises(SystemExit, match="docs/tutorial.md"):
        sync_lamindb_agent_docs(tmp_path)
    assert not (tmp_path / "lamindb" / ".agents" / "docs").exists()


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(root: Path) -> None:
    _checkout(root)
    (root / "lamindb" / "__init__.py").write_text(
        '"""Test package."""\n\n__version__ = "0.0.1"\n'
    )
    (root / "pyproject.toml").write_text(
        """\
[build-system]
requires = ["flit_core >=3.2,<4"]
build-backend = "flit_core.buildapi"

[project]
name = "lamindb-core"
authors = [{name = "Test", email = "t@example.com"}]
readme = "README.md"
dynamic = ["version", "description"]

[tool.flit.module]
name = "lamindb"
"""
    )
    _git(root, "init", "-b", "main")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "init")


def _staged_docs(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        line
        for line in result.stdout.splitlines()
        if line.startswith("lamindb/.agents/docs/")
    ]


def test_release_stages_docs_for_the_build_then_removes_them(
    tmp_path: Path, monkeypatch
):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    seen = {}

    def _during_build():
        seen["guide"] = (
            tmp_path / "lamindb" / ".agents" / "docs" / "guide.md"
        ).is_file()
        seen["staged"] = _staged_docs(tmp_path)

    _call_with_lamindb_agent_docs(_during_build)
    assert seen["guide"]
    assert "lamindb/.agents/docs/README.md" in seen["staged"]
    assert "lamindb/.agents/docs/guide.md" in seen["staged"]
    assert "lamindb/.agents/docs/tutorial.md" in seen["staged"]
    assert "lamindb/.agents/docs/faq/search.md" in seen["staged"]
    assert not (tmp_path / "lamindb" / ".agents" / "docs").exists()
    assert _staged_docs(tmp_path) == []


def test_release_removes_docs_when_the_build_fails(tmp_path: Path, monkeypatch):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    def _fail():
        raise RuntimeError("publish failed")

    with pytest.raises(RuntimeError, match="publish failed"):
        _call_with_lamindb_agent_docs(_fail)
    assert not (tmp_path / "lamindb" / ".agents" / "docs").exists()
    assert _staged_docs(tmp_path) == []


def test_staged_docs_land_in_the_wheel_flit_publishes(tmp_path: Path, monkeypatch):
    if shutil.which("flit") is None:
        pytest.skip("flit is not installed")
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    packed = {}

    def _build():
        subprocess.run(["flit", "build"], cwd=tmp_path, check=True)
        wheels = list((tmp_path / "dist").glob("*.whl"))
        assert len(wheels) == 1
        with zipfile.ZipFile(wheels[0]) as zf:
            packed["names"] = set(zf.namelist())

    _call_with_lamindb_agent_docs(_build)
    assert "lamindb/.agents/docs/README.md" in packed["names"]
    assert "lamindb/.agents/docs/guide.md" in packed["names"]
    assert "lamindb/.agents/docs/tutorial.md" in packed["names"]
    assert "lamindb/.agents/docs/faq/search.md" in packed["names"]
    assert not (tmp_path / "lamindb" / ".agents" / "docs").exists()
