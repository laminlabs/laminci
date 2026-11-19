import subprocess
from pathlib import Path

import pytest
from laminci._docs_artifacts import add_source_badges, process_markdown_file

BADGE = "https://img.shields.io/badge/source-green"


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "sampledocs"
    root.mkdir()
    monkeypatch.chdir(root)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    (root / "docs").mkdir()
    return root


def _badge_for(rel_path: str) -> str:
    return (
        f"[![.md]({BADGE})]"
        f"(https://github.com/laminlabs/sampledocs/blob/main/{rel_path})"
    )


def test_add_source_badges_on_plain_markdown(repo: Path) -> None:
    page = repo / "docs" / "security.md"
    page.write_text(
        "# Security\n\nPlain text.\n\n```python\n# not a heading\nprint(1)\n```\n"
    )
    fragment = repo / "docs" / "notes.md"
    fragment.write_text("no heading\n")
    included = repo / "docs" / "includes" / "snippet.md"
    included.parent.mkdir()
    included.write_text("# Not a page\n")
    executable = repo / "docs" / "tutorial.md"
    executable.write_text("---\nexecute_via: python\n---\n\n# Tutorial\n")
    draft = repo / "docs" / "draft.md"
    draft.write_text("# Draft\n")
    subprocess.run(
        [
            "git",
            "add",
            "docs/security.md",
            "docs/notes.md",
            "docs/includes/snippet.md",
            "docs/tutorial.md",
        ],
        check=True,
    )

    add_source_badges("docs")

    text = page.read_text()
    assert text.startswith(f"# Security {_badge_for('docs/security.md')}\n")
    assert 'tags=["hide-output"]' not in text
    assert "```python\n# not a heading\nprint(1)\n```" in text
    assert fragment.read_text() == "no heading\n"
    assert included.read_text() == "# Not a page\n"
    assert executable.read_text().startswith("---\n")
    assert BADGE not in executable.read_text()
    assert draft.read_text() == "# Draft\n"

    add_source_badges("docs")
    assert page.read_text() == text

    add_source_badges("docs", tracked_only=False)
    assert draft.read_text().startswith(f"# Draft {_badge_for('docs/draft.md')}\n")
    assert included.read_text() == "# Not a page\n"


def test_process_markdown_file_adds_badge_and_hides_output(repo: Path) -> None:
    source = repo / "docs" / "tutorial.md"
    source.write_text(
        "---\nexecute_via: python\n---\n\n# Tutorial\n\n"
        "```python\nprint(1)\n```\n\n```bash\necho hi\n```\n"
    )
    dest = repo / "docs" / "tutorial_processed.md"
    process_markdown_file(str(source), str(dest))
    content = dest.read_text()
    assert f"# Tutorial {_badge_for('docs/tutorial.md')}\n" in content
    assert "execute_via" not in content
    assert '```python tags=["hide-output"]\nprint(1)' in content
    assert '```bash tags=["hide-output"]\necho hi' in content


def test_process_markdown_file_without_heading_prefixes_badge(repo: Path) -> None:
    source = repo / "docs" / "bare.md"
    source.write_text("hello\n")
    dest = repo / "docs" / "bare_out.md"
    process_markdown_file(str(source), str(dest))
    assert dest.read_text() == f"{_badge_for('docs/bare.md')}\n\nhello\n"
