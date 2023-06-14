import argparse
import importlib
from subprocess import PIPE, run

from packaging.version import parse

from ._env import get_package_name

parser = argparse.ArgumentParser("laminci")
subparsers = parser.add_subparsers(dest="command")
migr = subparsers.add_parser(
    "release",
    help="Help with release",
    description=(
        "Assumes you manually prepared the release commit!\n\nPlease edit the version"
        " number in your package and prepare the release notes!"
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
        pypi = " & publish to PyPI" if args.pypi else ""
        response = input(f"Bump {previous_version} to {version}{pypi}? (y/n)")
        if response != "y":
            return None
        run("git add -u", shell=True)
        run(f"git commit -m 'Release {version}'", shell=True)
        run("git push", shell=True)
        run(f"git tag {version}", shell=True)
        run(f"git push origin {version}", shell=True)
        if args.pypi:
            run("flit publish", shell=True)
