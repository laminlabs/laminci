from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from subprocess import PIPE, run

import tomllib
from packaging.version import Version, parse

from ._env import get_package_name

parser = argparse.ArgumentParser("laminci")
subparsers = parser.add_subparsers(dest="command")
release = subparsers.add_parser(
    "release",
    help="Help with release",
    description=(
        "Assumes you manually prepared the release commit!\n\n"
        "Please edit the version number in your package and prepare the release notes!"
    ),
)
aa = release.add_argument
aa("--pypi", default=False, action="store_true", help="Publish to PyPI")
aa("--changelog", default=None, help="Link to changelog entry")
subparsers.add_parser(
    "doc-changes",
    help="Write latest changes",
)
upload_docs = subparsers.add_parser(
    "upload-docs",
)
aa = upload_docs.add_argument
aa("--dir", default="./docs", help="Docs dir link")
aa("--in-pr", default=False, action="store_true", help="Also uplod in PR")


def update_readme_version(file_path, new_version):
    # Read the content of the file
    with open(file_path) as file:
        content = file.read()

    # Use regex to find and replace the version
    updated_content = re.sub(
        r"Version: `[0-9.]+`", f"Version: `{new_version}`", content
    )

    # Write the updated content back to the file
    with open(file_path, "w") as file:
        file.write(updated_content)


def get_last_version_from_tags():
    proc = run(["git", "tag"], text=True, stdout=PIPE)
    tags = proc.stdout.splitlines()
    newest = "0.0.0"
    for tag in tags:
        if parse(tag) > parse(newest):
            newest = tag
    return newest


def validate_version(version_str: str):
    version = parse(version_str)
    if version.is_prerelease:
        if not len(version.release) == 2:
            raise SystemExit(
                f"Pre-releases should be of form 0.42a1 or 0.42rc1, yours is {version}"
            ) from None
        else:
            return None
    if len(version.release) != 3:
        raise SystemExit(
            f"Version should be of form 0.1.2, yours is {version}"
        ) from None


def publish_github_release(
    repo_name: str,
    version: str | Version,
    release_name: str,
    body: str = "",
    draft: bool = False,
    generate_release_notes: bool = True,
    cwd: str | None | Path = None,
):
    version = parse(version)

    try:
        cwd = Path.cwd() if cwd is None else Path(cwd)
        # account for repo_name sometimes being a package
        repo_name_standardized = repo_name.split("/")[1]
        if not repo_name_standardized == cwd.name:
            raise ValueError(f"Don't match: {repo_name_standardized} != {cwd.name}")
        subprocess.run(["gh", "--version"], check=True, stdout=subprocess.PIPE, cwd=cwd)
        try:
            command = [
                "gh",
                "release",
                "create",
                f"{version}",
                "--title",
                release_name,
                "--notes",
                body,
            ]
            if generate_release_notes:
                command.append("--generate-notes")
            if version.is_prerelease:
                command.append("--prerelease")

            print(f"\nrun: {' '.join(command)}")
            subprocess.run(command, check=True, stdout=subprocess.PIPE, cwd=cwd)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            if input("GitHub release error. Continue? ") != "y":
                raise e
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            from github import Github, GithubException

            token = (
                os.getenv("GITHUB_TOKEN")
                if os.getenv("GITHUB_TOKEN")
                else input("Github token:")
            )
            g = Github(token)

            try:
                repo = g.get_repo(repo_name)
                repo.create_git_release(
                    tag=str(version),
                    name=release_name,
                    message=body,
                    draft=draft,
                    prerelease=version.is_prerelease,
                    generate_release_notes=generate_release_notes,
                )
            except GithubException as e:
                raise SystemExit(
                    f"Error creating GitHub release using `PyGithub`: {e}"
                ) from None
        except ImportError:
            raise SystemExit(
                "Neither the Github CLI ('gh') nor PyGithub were accessible.\n"
                "Please install one of the two."
            ) from None


def check_only_version_bump_staged(
    package_name: str, additional_staged_files: list[str] | None = None
):
    # Check that the expected files are staged and no others
    init_file_path = f"{package_name}/__init__.py"
    expected_files = {init_file_path}
    if additional_staged_files:
        expected_files.update(additional_staged_files)

    # Get list of staged files
    import subprocess

    staged_files = (
        subprocess.check_output(["git", "diff", "--name-only", "--cached"], text=True)
        .strip()
        .split("\n")
    )

    # Check if staged_files is empty (no staged files)
    if not staged_files or staged_files == [""]:
        raise ValueError(
            f"{init_file_path} is not staged in git. Please stage it before releasing."
        )

    # Check if all expected files are staged
    missing_files = [f for f in expected_files if f not in staged_files]
    if missing_files:
        raise ValueError(
            f"Missing staged files: {', '.join(missing_files)}. Please stage them before releasing."
        )

    # Check if any additional files are staged
    if len(staged_files) > len(expected_files):
        other_files = [f for f in staged_files if f not in expected_files]
        raise ValueError(
            f"Additional files are staged for commit: {', '.join(other_files)}. "
            f"Please unstage these files before releasing."
        )


def _run_checked(command: list[str], cwd: str | None = None):
    print(f"\nrun: {' '.join(command)}")
    subprocess.run(command, check=True, cwd=cwd)


def _build_wheel_with_pyproject(pyproject_file: Path, dist_dir: Path) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    _run_checked(["flit", "-f", str(pyproject_file), "build", "--format", "wheel"])
    project_name = tomllib.loads(pyproject_file.read_text())["project"]["name"]
    wheel_prefix = project_name.replace("-", "_")
    source_wheels = sorted(
        Path("dist").glob(f"{wheel_prefix}-*.whl"), key=lambda p: p.stat().st_mtime
    )
    if not source_wheels:
        raise SystemExit(f"No wheel for {project_name} was produced in dist/")
    built_wheel = source_wheels[-1]
    target_wheel = dist_dir / built_wheel.name
    shutil.copy2(built_wheel, target_wheel)
    return target_wheel


def _wheel_has_lamindb_package(wheel_path: Path) -> bool:
    with zipfile.ZipFile(wheel_path, "r") as zf:
        return any(name.startswith("lamindb/") for name in zf.namelist())


def _assert_lamindb_dependency_pin(version: str):
    pyproject = Path("pyproject.full.toml").read_text()
    expected = f'"lamindb-core=={version}"'
    if expected not in pyproject:
        raise SystemExit(
            f"Please pin {expected} in pyproject.full.toml before releasing lamindb."
        ) from None


def run_lamindb_dual_smoke_checks(version: str):
    # Pre-publish safety check for lamindb dual-distribution releases.
    # We intentionally create an isolated venv and install dependencies to ensure
    # the published wheels behave correctly across install/uninstall sequences.
    core_pyproject = Path("pyproject.toml")
    full_pyproject = Path("pyproject.full.toml")
    if not full_pyproject.exists():
        raise SystemExit("Missing pyproject.full.toml for lamindb dual release flow.")

    print(
        "\nINFO: Running lamindb dual-package smoke checks before publish.\n"
        "INFO: This will build both wheels and install packages in a temporary venv."
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        print(f"INFO: Building wheels from {core_pyproject} and {full_pyproject}")
        core_wheel = _build_wheel_with_pyproject(core_pyproject, tmpdir_path / "core")
        full_wheel = _build_wheel_with_pyproject(full_pyproject, tmpdir_path / "full")

        if "lamindb_core-" not in core_wheel.name:
            raise SystemExit(f"Unexpected lamindb-core wheel name: {core_wheel.name}")
        if "lamindb-" not in full_wheel.name:
            raise SystemExit(f"Unexpected lamindb wheel name: {full_wheel.name}")
        if not _wheel_has_lamindb_package(core_wheel):
            raise SystemExit(f"{core_wheel.name} does not contain lamindb/ package")
        if _wheel_has_lamindb_package(full_wheel):
            raise SystemExit(
                f"{full_wheel.name} unexpectedly contains lamindb/ package"
            )

        venv_dir = tmpdir_path / "venv"
        print(f"INFO: Creating temporary smoke-test environment at {venv_dir}")
        _run_checked(["python", "-m", "venv", str(venv_dir)])
        pip = str(venv_dir / "bin" / "pip")
        python = str(venv_dir / "bin" / "python")

        _run_checked([pip, "install", "--upgrade", "pip"])
        print(
            "INFO: Installing core runtime dependencies into temp venv "
            "(expected and required for the smoke check)."
        )
        _run_checked(
            [
                pip,
                "install",
                "lamin_utils==0.16.4",
                "lamin_cli==1.14.1",
                "lamindb_setup[aws]==1.22.0",
                "pyyaml",
                "typing_extensions!=4.6.0",
                "python-dateutil",
                "scipy<1.17.0",
                "fsspec",
                "graphviz",
                "psycopg2-binary",
            ]
        )
        _run_checked([pip, "install", str(core_wheel)])
        _run_checked([python, "-c", "import lamindb"])
        print("INFO: Core wheel import check passed.")
        _run_checked([pip, "install", str(full_wheel)])
        _run_checked([python, "-c", "import lamindb"])
        print("INFO: Full wheel import check passed.")
        _run_checked([pip, "uninstall", "-y", "lamindb"])
        _run_checked([python, "-c", "import lamindb"])
        print("INFO: Uninstall check passed (lamindb-core still imports).")


def publish_lamindb_dual():
    core_pyproject = Path("pyproject.toml")
    full_pyproject = Path("pyproject.full.toml")
    if not full_pyproject.exists():
        raise SystemExit("Missing pyproject.full.toml for lamindb dual release flow.")

    _run_checked(["flit", "-f", str(core_pyproject), "publish"])
    _run_checked(["flit", "-f", str(full_pyproject), "publish"])


def main():
    args = parser.parse_args()

    if args.command == "release":
        package_name = get_package_name()
        is_lamindb_dual_release = False
        if (
            package_name == "lamindb_core"
            and Path("pyproject.full.toml").exists()
            and Path("lamindb/__init__.py").exists()
        ):
            package_name = "lamindb"
            is_lamindb_dual_release = True
        # cannot do the below as this wouldn't register immediate changes
        # from importlib.metadata import version as get_version
        # version = get_version(package_name)
        is_laminhub = False
        previous_version = get_last_version_from_tags()
        if package_name is not None:
            module = importlib.import_module(package_name, package=".")
            version = module.__version__
            validate_version(version)
            if parse(version) <= parse(previous_version):
                raise SystemExit(
                    f"Your version ({version}) should increment the previous version"
                    f" ({previous_version})"
                )
            if package_name == "lamindb" and args.changelog is None:
                raise SystemExit(
                    "Please pass a link to the changelog entry via, e.g.: --changelog"
                    " https://docs.lamin.ai/changelog/2026#db-2-1-1"
                ) from None
            if Path("./LICENSE").exists() and not args.pypi:
                raise SystemExit(
                    "ERROR: Did you forget to add the `--pypi` flag? A LICENSE file"
                    " exists and I assume this is an open-source package."
                ) from None
            repo_name = package_name.replace("_", "-")
        else:
            assert Path.cwd().name == "laminhub"
            repo_name = "laminhub"
            if not (Path.cwd() / "laminhub-public/README.md").exists():
                raise ValueError("Please update the laminhub-public git submodule.")
            is_laminhub = True
            with open("ui/package.json") as file:
                version = json.load(file)["version"]

        print(f"INFO: You will add this changelog link: {args.changelog}")
        print(
            "WARNING: This assumes you staged your bumped version tag for laminci to commit it."
        )
        pypi = " & publish to PyPI" if args.pypi else ""
        response = input(f"Bump {previous_version} to {version}{pypi}? (y/n)")
        if response != "y":
            return None

        # add all current files, assuming a clean directory
        run("git add -u", shell=True)  # noqa: S602
        # check only the expected version bump files are staged
        additional_staged_files = (
            ["pyproject.full.toml"] if is_lamindb_dual_release else None
        )
        check_only_version_bump_staged(
            package_name, additional_staged_files=additional_staged_files
        )
        expected_message = f"🔖 Release {version}"
        commands = [
            # please don't add git add -u here to not accidentally commit other files
            f'git commit -m "{expected_message}"',
            # please don't add an auto-pull here to not conflate when the release was made
            "git push",
            f"git tag {version}",
            f"git push origin {version}",
        ]
        for command in commands:
            print(f"\nrun: {command}")
            run(command, shell=True)  # noqa: S602
            # gitmoji might add a second emoji; ensure message starts with "🔖 Release"
            if command.startswith("git commit -m "):
                result = run(
                    ["git", "log", "-1", "--format=%s"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and not result.stdout.strip().startswith(
                    "🔖 Release"
                ):
                    print(f'\nrun: git commit --amend -m "{expected_message}"')
                    run(f'git commit --amend -m "{expected_message}"', shell=True)  # noqa: S602

        changelog_link = (
            args.changelog
            if args.changelog is not None
            else "https://docs.lamin.ai/changelog"
        )
        # breakpoint()
        publish_github_release(
            repo_name=f"laminlabs/{repo_name}",
            version=version,
            release_name=f"Release {version}",
            body=f"See {changelog_link}",
        )
        if is_laminhub:
            update_readme_version("./laminhub-public/README.md", version)
            for command in commands:
                print(f"\nrun: {command}")
                run(command, shell=True, cwd="./laminhub-public")  # noqa: S602
            publish_github_release(
                repo_name="laminlabs/laminhub-public",
                version=version,
                body=f"See {changelog_link}",
                release_name=f"Release {version}",
                generate_release_notes=False,
                cwd="./laminhub-public",
            )

        if args.pypi:
            if is_lamindb_dual_release:
                print(
                    "INFO: Detected lamindb dual-release mode (core + full). "
                    "Running pre-publish consistency and smoke checks."
                )
                _assert_lamindb_dependency_pin(version)
                run_lamindb_dual_smoke_checks(version)
                publish_lamindb_dual()
            else:
                command = "flit publish"
                print(f"\nrun: {command}")
                run(command, shell=True)  # noqa: S602
    elif args.command == "doc-changes":
        from ._doc_changes import doc_changes

        doc_changes()
    elif args.command == "upload-docs":
        from ._docs_artifacts import upload_docs_artifact

        upload_docs_artifact(docs_dir=args.dir, in_pr=args.in_pr)
