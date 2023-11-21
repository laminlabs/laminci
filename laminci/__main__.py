import argparse
import importlib
import re
from subprocess import PIPE, run
from typing import TYPE_CHECKING

from packaging.version import parse

from ._env import get_package_name

if TYPE_CHECKING:
    from github.GitRelease import GitRelease

parser = argparse.ArgumentParser("laminci")
subparsers = parser.add_subparsers(dest="command")
migr = subparsers.add_parser(
    "release",
    help="Help with release",
    description=(
        "Assumes you manually prepared the release commit!\n\n"
        "Please edit the version number in your package and prepare the release notes!"
    ),
)
aa = migr.add_argument
aa("--pypi", default=False, action="store_true", help="Publish to PyPI")


def get_last_version_from_tags():
    proc = run(["git", "tag"], universal_newlines=True, stdout=PIPE)
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
            )
        else:
            return None
    if len(version.release) != 3:
        raise SystemExit(f"Version should be of form 0.1.2, yours is {version}")


def create_github_release(token: str, repo_name: str, version: str, release_name: str, body: str, draft: bool = False,
                          generate_release_notes: bool = True) -> GitRelease:
    from github import Github

    g = Github(token)

    repo = g.get_repo(repo_name)

    pre_release_pattern = re.compile(r'\d+(\.\d+)?[abc]\d*')
    is_pre_release = bool(pre_release_pattern.search(version))

    release = repo.create_git_release(
        tag=version,
        name=release_name,
        message=body,
        draft=draft,
        prerelease=is_pre_release,
        generate_release_notes=generate_release_notes
    )

    return release


def publish_tag_pypi_release(args, version: str):
    commands = [
        "git add -u",
        f"git commit -m 'Release {version}'",
        "git push",
        f"git tag {version}",
        f"git push origin {version}",
    ]
    for command in commands:
        print(f"\nrun: {command}")
        run(command, shell=True)
    if args.pypi:
        command = "flit publish"
        print(f"\nrun: {command}")
        run(command, shell=True)


def main():
    args = parser.parse_args()

    if args.command == "release":
        package_name = get_package_name()
        module = importlib.import_module(package_name, package=".")
        version = module.__version__
        previous_version = get_last_version_from_tags()
        validate_version(version)
        if parse(version) <= parse(previous_version):
            raise SystemExit(
                f"Your version ({version}) should increment the previous version"
                f" ({previous_version})"
            )

        token = "BLABLABLA"
        create_github_release(token,
                              repo_name=f"laminlabs/{package_name}",
                              version=version,
                              release_name=f"Release {version}",
                              body="Find the changelog on https://lamin.ai/docs/changelog"
                              )

        pypi = " & publish to PyPI" if args.pypi else ""
        response = input(f"Bump {previous_version} to {version}{pypi}? (y/n)")
        if response != "y":
            return None
        publish_tag_pypi_release(args, version)
