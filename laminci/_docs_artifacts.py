import json
import os
import re
from pathlib import Path
from subprocess import run
from zipfile import ZipFile

SOURCE_BADGE_IMG = "https://img.shields.io/badge/source-green"


def get_repo_name() -> str:
    """Return the current directory name, validated as a git repo with lowercase name."""
    repo_name = Path.cwd().name
    assert "." not in repo_name  # doesn't have a weird suffix
    assert Path(".git/").exists()  # is git repo
    assert repo_name.lower() == repo_name  # is all lower-case
    return repo_name


def _is_executable_markdown(path: Path) -> bool:
    head = "\n".join(path.read_text().splitlines()[:20])
    return "execute_via:" in head


def _make_source_badge(rel_path: Path) -> str:
    repo_name = get_repo_name()
    source_url = (
        f"https://github.com/laminlabs/{repo_name}/blob/main/{rel_path.as_posix()}"
    )
    return f"[![.md]({SOURCE_BADGE_IMG})]({source_url})"


def _insert_source_badge(content: str, badge: str, *, require_heading: bool) -> str:
    if SOURCE_BADGE_IMG in content:
        return content
    if re.search(r"^# ", content, flags=re.MULTILINE):
        return re.sub(r"^(# .*)$", r"\1 " + badge, content, count=1, flags=re.MULTILINE)
    if require_heading:
        return content
    return f"{badge}\n\n{content}"


def _tracked_markdown(docs_dir: Path) -> set[str]:
    result = run(
        ["git", "ls-files", "-z", "--", str(docs_dir)],
        capture_output=True,
        check=True,
    )
    tracked: set[str] = set()
    for entry in result.stdout.decode().split("\0"):
        if entry.endswith(".md"):
            tracked.add(Path(entry).as_posix())
    return tracked


def add_source_badges(docs_dir: str = "./docs", *, tracked_only: bool = True) -> None:
    """Add the GitHub source badge to plain markdown pages.

    Notebook pages get the badge in `process_markdown_file` when they are
    converted. Plain pages skip that path, so the docs build and the uploaded
    artifact add the same badge on the first H1.

    Fragments are left unchanged: directories named `includes`, files with no
    H1, and pages that declare `execute_via`. With `tracked_only`, pulled pages
    in an aggregate checkout are not relabeled with the aggregate repository.
    """
    docs_root = Path(docs_dir)
    if not docs_root.exists():
        return
    tracked = _tracked_markdown(docs_root) if tracked_only else None
    cwd = Path.cwd().resolve()
    for md_path in sorted(docs_root.glob("**/*.md")):
        if "includes" in md_path.parts or ".ipynb_checkpoints" in md_path.parts:
            continue
        rel_path = md_path.resolve().relative_to(cwd)
        if tracked is not None and rel_path.as_posix() not in tracked:
            continue
        if _is_executable_markdown(md_path):
            continue
        content = md_path.read_text()
        updated = _insert_source_badge(
            content, _make_source_badge(rel_path), require_heading=True
        )
        if updated != content:
            md_path.write_text(updated)


def zip_docs_dir(zip_filename: str, docs_dir: str = "./docs") -> None:
    with ZipFile(zip_filename, "w") as zf:
        zf.write("README.md")
        for f in Path(docs_dir).glob("**/*"):
            if ".ipynb_checkpoints" in str(f):
                continue
            if f.suffix in {".md", ".ipynb", ".png", ".jpg", ".svg", ".py", ".R"}:
                # do not duplicate markdown and ipynb files
                if f.suffix == ".md" and f.with_suffix(".ipynb").exists():
                    continue
                zf.write(f, f.relative_to(docs_dir))  # add at root level


def zip_docs(docs_dir: str = "./docs"):
    repo_name = get_repo_name()
    zip_filename = f"{repo_name}.zip"
    zip_docs_dir(zip_filename, docs_dir)
    return repo_name, zip_filename


def process_markdown_file(input_file: str, output_file: str):
    """Process a raw markdown document.

    Add hide-output tags to all code cells in a markdown file.
    Add a badge with the source code link on GitHub.
    """
    rel_path = Path(input_file).resolve().relative_to(Path.cwd().resolve())
    content = Path(input_file).read_text()
    content = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL)
    content = re.sub(r"```python\n", r'```python tags=["hide-output"]\n', content)
    content = re.sub(r"```bash\n", r'```bash tags=["hide-output"]\n', content)
    content = _insert_source_badge(
        content, _make_source_badge(rel_path), require_heading=False
    )
    Path(output_file).write_text(content)


def convert_executable_md_files(docs_dir: str = "./docs") -> None:
    """Convert executable markdown to notebooks and badge the other pages."""
    add_source_badges(docs_dir)
    for md_path in Path(docs_dir).glob("**/*.md"):
        if not _is_executable_markdown(md_path):
            continue
        stem = md_path.stem
        processed = md_path.parent / f"{stem}_processed.md"
        notebook_path = md_path.parent / f"{stem}.ipynb"
        process_markdown_file(str(md_path), str(processed))
        os.system(
            f"jupytext --from md:markdown {processed} --to notebook --output {notebook_path}"
        )
        # jupytext --from md:markdown does not write kernelspec/language_info.
        # myst-nb then warns "No source code lexer found" for every code cell.
        nb = json.loads(notebook_path.read_text())
        metadata = nb.setdefault("metadata", {})
        metadata.setdefault(
            "kernelspec",
            {"display_name": "Python 3", "language": "python", "name": "python3"},
        )
        metadata.setdefault("language_info", {"name": "python"})
        notebook_path.write_text(json.dumps(nb, indent=1) + "\n")
        os.system(f"rm {md_path} {processed}")


def upload_docs_artifact(
    aws: bool = False, docs_dir: str = "./docs", in_pr: bool = False
) -> None:
    if not in_pr:
        if os.getenv("GITHUB_EVENT_NAME") not in {"push", "repository_dispatch"}:
            print("Only upload docs artifact for push event.")
            return None
    if aws:
        print("aws arg no longer needed")
    # Include generated pages that are not committed yet. This runs in the
    # source repository, after aggregate checkouts have already pulled artifacts.
    add_source_badges(docs_dir, tracked_only=False)
    _, zip_filename = zip_docs(docs_dir)
    run(  # noqa: S602
        f"aws s3 cp {zip_filename} s3://lamin-site-assets/docs/{zip_filename}",
        shell=True,
    )
