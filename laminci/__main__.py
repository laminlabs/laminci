import argparse
import importlib
import os
import subprocess
from subprocess import PIPE, run

from packaging.version import Version, parse

from ._env import get_package_name

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


def create_github_release(
    repo_name: str,
    version: str | Version,
    release_name: str,
    body: str = "",
    draft: bool = False,
    generate_release_notes: bool = True,
):
    version = parse(version)

    try:
        subprocess.run(["gh", "--version"], check=True, stdout=subprocess.PIPE)

        try:
            gh_rl_cmd = [
                "gh",
                "release",
                "create",
                f"{version}",
                "--title",
                release_name,
                "--notes",
                body,
                "--generate-notes",
            ]
            if version.is_prerelease:
                gh_rl_cmd.append("--prerelease")
            subprocess.run(gh_rl_cmd, check=True, stdout=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            raise SystemExit(f"Error creating GitHub release using `gh`: {e}")
    except subprocess.CalledProcessError:
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
                raise SystemExit(f"Error creating GitHub release using `PyGithub`: {e}")
        except ImportError:
            raise SystemExit(
                "Neither the Github CLI ('gh') nor PyGithub were accessible.\n"
                "Please install one of the two."
            )


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

        create_github_release(
            repo_name=f"zethson/{package_name}",
            version=version,
            release_name=f"Release {version}",
        )

        pypi = " & publish to PyPI" if args.pypi else ""
        response = input(f"Bump {previous_version} to {version}{pypi}? (y/n)")
        if response != "y":
            return None
        publish_tag_pypi_release(args, version)
