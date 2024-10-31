import importlib
import json
import os
import re
import subprocess
from pathlib import Path
from subprocess import PIPE, run
from typing import Annotated

from packaging.version import Version, parse

from ._env import get_package_name


def _get_last_version_from_tags():
    proc = run(["git", "tag"], universal_newlines=True, stdout=PIPE)
    tags = proc.stdout.splitlines()
    newest = "0.0.0"
    for tag in tags:
        if parse(tag) > parse(newest):
            newest = tag
    return newest


def _validate_version(version_str: str):
    version = parse(version_str)
    if version.is_prerelease:
        if not len(version.release) == 2:
            raise SystemExit(
                f"Pre-releases should be of form 0.42a1 or 0.42rc1, yours is {version}"
            )
        else:
            return None
    if len(version.release) != 3:
        raise SystemExit(f"Version should be of form 0.1.2, yours is {version}")


def _publish_github_release(
    repo_name: str,
    version: str | Version,
    release_name: str,
    *,
    body: str = "",
    draft: bool = False,
    generate_release_notes: bool = True,
    cwd: str | None | Path = None,
):
    version = parse(version)  # type: ignore

    try:
        cwd = Path.cwd() if cwd is None else Path(cwd)
        # account for repo_name sometimes being a package
        repo_name_standardized = repo_name.split("/")[1]
        if not repo_name_standardized == cwd.name:
            raise ValueError(f"Don't match: {repo_name_standardized} != {cwd.name}")
        run(["gh", "--version"], check=True, stdout=subprocess.PIPE, cwd=cwd)

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
            run(command, check=True, stdout=subprocess.PIPE, cwd=cwd)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise Exception("Error creating GitHub release using `gh`") from e

    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            from github import Github, GithubException

            token = (
                os.getenv("GITHUB_TOKEN")
                if os.getenv("GITHUB_TOKEN")
                else input("GitHub token:")
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
                raise SystemExit(f"Error creating GitHub release using `PyGithub`: {e}")
        except ImportError as e:
            raise ImportError(
                "Neither the Github CLI ('gh') nor PyGithub were accessible.\n"
                "Please install one of the two."
            ) from e


def _update_readme_version(file_path, new_version):
    # Read the content of the file
    with open(file_path, "r") as file:
        content = file.read()

    # Use regex to find and replace the version
    updated_content = re.sub(
        r"Version: `[0-9.]+`", f"Version: `{new_version}`", content
    )

    # Write the updated content back to the file
    with open(file_path, "w") as file:
        file.write(updated_content)


def _prepare_package_name(
    previous_version: str, *, changelog_link: str | None, pypi: bool
) -> tuple[Annotated[str, "repo_name"], Annotated[str, "version"]]:
    # cannot do the below as this wouldn't register immediate changes
    # from importlib.metadata import version as get_version
    # version = get_version(package_name)

    package_name = get_package_name()
    if package_name is not None:
        module = importlib.import_module(package_name, package=".")
        version = module.__version__
        _validate_version(version)
        if parse(version) <= parse(previous_version):
            raise SystemExit(
                f"Your version ({version}) should increment the previous version"
                f" ({previous_version})"
            )
        if package_name == "lamindb" and changelog_link is None:
            raise SystemExit(
                "Please pass a link to the changelog entry via: --changelog 'your-link'"
            )
        if Path("./LICENSE").exists() and not pypi:
            raise SystemExit(
                "ERROR: Did you forget to add the `--pypi` flag? A LICENSE file"
                " exists and I assume this is an open-source package."
            )
        repo_name = package_name.replace("_", "-")
        return repo_name, version

    # LaminHub
    repo_name = "laminhub"
    assert Path.cwd().name == repo_name
    if not (Path.cwd().parent / "laminhub-public").exists():
        raise ValueError(
            "Please clone the laminhub-public repository into the same parent"
            " directory as that of laminhub."
        )
    version = json.loads(Path("ui/package.json").read_text())["version"]
    return repo_name, version


def release(*, changelog_link: str | None, pypi: bool, no_release: bool):
    """Create a release.
    1. Get the version number from the package (pyproject.toml or lamin-project.yaml or package.json).
    2. Create a commit tagged with the version number.
    3. Push the commit and tags to the remote.
    4. Create a release on GitHub.
    5. (If laminhub) Update the version in the README.md of laminhub-public.

    Args:
        changelog_link: _description_
        pypi: Update to PyPI using flit.
        no_release: Do not create a release. This is used when you already created a release to get the changelog.
    """

    changelog_link = changelog_link or "https://docs.lamin.ai/changelog"
    previous_version = _get_last_version_from_tags()
    repo_name, version = _prepare_package_name(
        previous_version, changelog_link=changelog_link, pypi=pypi
    )

    print(f"INFO: You will add this changelog link: {changelog_link}")
    print(
        "WARNING: This will run `git add -u`, commit everything into the release"
        " commit, add the release tags, and push to remote.\n\n"
        " Please ensure all your current changes should appear in the"
        " release commit. Typically, you only bump the version number. "
    )
    if repo_name == "laminhub":
        print(
            "INFO: This will also update the version in laminhub-public/README.md and create a release there."
        )

    _pypi_msg = " & publish to PyPI" if pypi else ""
    response = input(
        f"Commit and bump {previous_version} to {version}{_pypi_msg}? (y/n)"
    )
    if response != "y":
        return None

    commands = [
        "git add -u",
        f"git commit -m 'Release {version}'",
        "git push",
        f"git tag {version}",
        f"git push origin {version}",
    ]
    if not no_release:
        for command in commands:
            print(f"\nrun: {command}")
            run(command, shell=True, check=True)

        _publish_github_release(
            repo_name=f"laminlabs/{repo_name}",
            version=version,
            release_name=f"Release {version}",
            body=f"See {changelog_link}",
        )

    if repo_name == "laminhub":
        _update_readme_version("../laminhub-public/README.md", version)
        for command in commands:
            print(f"\nrun: {command}")
            run(command, shell=True, cwd="../laminhub-public", check=True)

        _publish_github_release(
            repo_name="laminlabs/laminhub-public",
            version=version,
            body=f"See {changelog_link}",
            release_name=f"Release {version}",
            generate_release_notes=False,
            cwd="../laminhub-public",
        )

    if pypi:
        command = "flit publish"
        print(f"\nrun: {command}")
        run(command, shell=True, check=True)
