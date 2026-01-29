import os
import re
from pathlib import Path
from subprocess import run
from zipfile import ZipFile


def get_repo_name() -> str:
    """Return the current directory name, validated as a git repo with lowercase name."""
    repo_name = Path.cwd().name
    assert "." not in repo_name  # doesn't have a weird suffix
    assert Path(".git/").exists()  # is git repo
    assert repo_name.lower() == repo_name  # is all lower-case
    return repo_name


def zip_docs_dir(zip_filename: str, docs_dir: str = "./docs") -> None:
    with ZipFile(zip_filename, "w") as zf:
        zf.write("README.md")
        for f in Path(docs_dir).glob("**/*"):
            if ".ipynb_checkpoints" in str(f):
                continue
            if f.suffix in {".md", ".ipynb", ".png", ".jpg", ".svg", ".py", ".R"}:
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
    repo_name = get_repo_name()
    rel_path = Path(input_file).resolve().relative_to(Path.cwd())
    source_url = f"https://github.com/laminlabs/{repo_name}/blob/main/{rel_path}"
    badge = f"[![Markdown](https://img.shields.io/badge/Markdown-orange)]({source_url})"
    content = open(input_file).read()
    content = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL)
    content = re.sub(r"```python\n", r'```python tags=["hide-output"]\n', content)
    open(output_file, "w").write(f"{badge}\n\n{content}")


def convert_executable_md_files(docs_dir: str = "./docs") -> None:
    for md_path in Path(docs_dir).glob("*.md"):
        head = md_path.read_text().splitlines()[:20]
        if "execute_via:" not in "\n".join(head):
            continue
        stem = md_path.stem
        processed = md_path.parent / f"{stem}_processed.md"
        notebook_path = md_path.parent / f"{stem}.ipynb"
        process_markdown_file(str(md_path), str(processed))
        os.system(
            f"jupytext --from md:markdown {processed} --to notebook --output {notebook_path}"
        )
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
    _, zip_filename = zip_docs(docs_dir)
    run(  # noqa: S602
        f"aws s3 cp {zip_filename} s3://lamin-site-assets/docs/{zip_filename}",
        shell=True,
    )
