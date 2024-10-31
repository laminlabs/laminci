from __future__ import annotations

import argparse

from .release import release

parser = argparse.ArgumentParser("laminci")
subparsers = parser.add_subparsers(dest="command")
parser = subparsers.add_parser(
    "release",
    help="Help with release",
    description=(
        "Assumes you manually prepared the release commit!\n\n"
        "Please edit the version number in your package and prepare the release notes!"
    ),
)
aa = parser.add_argument
aa("--pypi", default=False, action="store_true", help="Publish to PyPI")
aa("--changelog", default=None, help="Link to changelog entry")
aa(
    "--no-release",
    default=False,
    help="Do not create a release. This is used when you already created"
    "a release to get the changelog.",
)
subparsers.add_parser(
    "doc-changes",
    help="Write latest changes",
)


def main():
    args = parser.parse_args()

    if args.command == "release":
        release(
            changelog_link=args.changelog, pypi=args.pypi, no_release=args.no_release
        )

    elif args.command == "doc-changes":
        from ._doc_changes import doc_changes

        doc_changes()
