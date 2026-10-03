from pathlib import Path

import pytest
from laminci._agent_docs import (
    remove_lamindb_agent_docs,
    sync_lamindb_agent_docs,
)


def _checkout(root: Path) -> None:
    (root / "lamindb").mkdir()
    (root / "lamindb" / "__init__.py").write_text("")
    docs = root / "docs"
    (docs / "faq").mkdir(parents=True)
    (docs / "guide.md").write_text("# Guide\n")
    (docs / "tutorial.md").write_text("# Tutorial\n")
    (docs / "faq" / "search.md").write_text("# Search\n")
    (docs / "notes.txt").write_text("skip")


def test_sync_copies_markdown_then_remove_deletes_it(tmp_path: Path):
    _checkout(tmp_path)
    dest = sync_lamindb_agent_docs(tmp_path)
    assert (dest / "guide.md").read_text() == "# Guide\n"
    assert (dest / "tutorial.md").is_file()
    assert (dest / "faq" / "search.md").is_file()
    assert not (dest / "notes.txt").exists()
    remove_lamindb_agent_docs(tmp_path)
    assert not dest.exists()


def test_sync_refuses_when_prepare_deleted_executable_pages(tmp_path: Path):
    _checkout(tmp_path)
    (tmp_path / "docs" / "tutorial.md").unlink()
    with pytest.raises(SystemExit, match="docs/tutorial.md"):
        sync_lamindb_agent_docs(tmp_path)
    assert not (tmp_path / "lamindb" / ".agents" / "docs").exists()
