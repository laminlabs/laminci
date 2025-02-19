from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import subprocess
from pathlib import Path
from subprocess import PIPE, run

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


def main():
    args = parser.parse_args()

    if args.command == "release":
        package_name = get_package_name()
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
                    "Please pass a link to the changelog entry via: --changelog"
                    " 'your-link'"
                ) from None
            if Path("./LICENSE").exists() and not args.pypi:
                raise SystemExit(
                    "ERROR: Did you forget to add the `--pypi` flag? A LICENSE file"
                    " exists and I assume this is an open-source package."
                ) from None
            repo_name = package_name.replace("_", "-")
        else:
            assert Path.cwd().name == "laminhub"  # noqa: S101
            repo_name = "laminhub"
            if not (Path.cwd().parent / "laminhub-public").exists():
                raise ValueError(
                    "Please clone the laminhub-public repository into the same parent"
                    " directory as laminhub."
                )
            is_laminhub = True
            with open("ui/package.json") as file:
                version = json.load(file)["version"]

        print(f"INFO: You will add this changelog link: {args.changelog}")
        print(
            "WARNING: This will run `git add -u` & commit everything into the release"
            " commit. Please ensure all your current changes should appear in the"
            " release commit. Typically, you only bump the version number. "
        )
        pypi = " & publish to PyPI" if args.pypi else ""
        response = input(f"Bump {previous_version} to {version}{pypi}? (y/n)")
        if response != "y":
            return None

        commands = [
            # please don't add git add -u here to not accidentally commit other files
            f"git commit -m 'Release {version}'",
            # please don't add an auto-pull here to not conflate when the release was made
            "git push",
            f"git tag {version}",
            f"git push origin {version}",
        ]
        for command in commands:
            print(f"\nrun: {command}")
            run(command, shell=True)  # noqa: S602

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
            update_readme_version("../laminhub-public/README.md", version)
            for command in commands:
                print(f"\nrun: {command}")
                run(command, shell=True, cwd="../laminhub-public")  # noqa: S602
            publish_github_release(
                repo_name="laminlabs/laminhub-public",
                version=version,
                body=f"See {changelog_link}",
                release_name=f"Release {version}",
                generate_release_notes=False,
                cwd="../laminhub-public",
            )

        if args.pypi:
            command = "flit publish"
            print(f"\nrun: {command}")
            run(command, shell=True)  # noqa: S602
    elif args.command == "doc-changes":
        from ._doc_changes import doc_changes

        doc_changes()
