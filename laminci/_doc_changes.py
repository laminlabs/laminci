# The code in this file is based on the latest-changes tool of Sebastian Ramirez
# See the original license
# Since mid 2024, the tool has been developed by Lamin within the proprietary
# laminci package

# MIT License

# Copyright (c) 2020 Sebastián Ramírez

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path

from github import Github
from github.PullRequest import PullRequest
from jinja2 import Template
from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings


class Section(BaseModel):
    label: str
    header: str


class Settings(BaseSettings):
    github_repository: str
    github_event_path: Path
    github_event_name: str | None = None
    repo_token: SecretStr  # typically GITHUB_TOKEN
    docs_token: SecretStr | None = None  # needed when writing to lamin-docs
    changelog_file: Path = Path("docs/changelog.md")
    doc_changes_header: str = "# Changelog\n\n"
    input_end_regex: str = "(^### .*)|(^## .*)"
    input_debug_logs: bool | None = False
    input_labels: list[Section] = [
        Section(label="breaking", header="Breaking Changes"),
        Section(label="security", header="Security Fixes"),
        Section(label="feature", header="Features"),
        Section(label="bug", header="Fixes"),
        Section(label="refactor", header="Refactors"),
        Section(label="upgrade", header="Upgrades"),
        Section(label="docs", header="Docs"),
    ]
    input_label_header_prefix: str = "#### "


class PartialGitHubEventInputs(BaseModel):
    number: int


class PartialGitHubEvent(BaseModel):
    number: int | None = None
    inputs: PartialGitHubEventInputs | None = None


class TemplateDataUser(BaseModel):
    login: str
    html_url: str


class TemplateDataPR(BaseModel):
    number: int
    title: str
    html_url: str
    user: TemplateDataUser


class SectionContent(BaseModel):
    label: str
    header: str
    content: str
    index: int


logging.basicConfig(level=logging.INFO)


def generate_content(
    *,
    content: str,
    settings: Settings,
    pr: PullRequest | TemplateDataPR,
    labels: list[str],
) -> str:
    header_match = re.search(settings.doc_changes_header, content, flags=re.MULTILINE)
    if not header_match:
        logging.info(
            f"The latest changes file at: {settings.changelog_file} doesn't"
            f" seem to contain the header RegEx: {settings.doc_changes_header}"
        )
        header_match_end = 0
    else:
        header_match_end = header_match.end()
    template_content = (
        "- {{pr.title}} [PR]({{pr.html_url}})"
        " [@{{pr.user.login}}]({{pr.user.html_url}})"
    )
    template = Template(template_content)
    message = template.render(pr=pr)
    if message in content:
        raise RuntimeError(
            f"It seems these PR's latest changes were already added: {pr.number}"
        )
    pre_header_content = content[:header_match_end].strip()
    post_header_content = content[header_match_end:].strip()
    next_release_match = re.search(
        settings.input_end_regex, post_header_content, flags=re.MULTILINE
    )
    release_end = (
        len(content)
        if not next_release_match
        else header_match_end + next_release_match.start()
    )
    release_content = content[header_match_end:release_end].strip()
    post_release_content = content[release_end:].strip()
    sections: list[SectionContent] = []
    sectionless_content = ""
    for label in settings.input_labels:
        label_match = re.search(
            f"^{settings.input_label_header_prefix}{label.header}",
            release_content,
            flags=re.MULTILINE,
        )
        if not label_match:
            continue
        next_label_match = re.search(
            f"^{settings.input_label_header_prefix}",
            release_content[label_match.end() :],
            flags=re.MULTILINE,
        )
        label_section_end = (
            len(release_content)
            if not next_label_match
            else label_match.end() + next_label_match.start()
        )
        label_content = release_content[label_match.end() : label_section_end].strip()
        section = SectionContent(
            label=label.label,
            header=label.header,
            content=label_content,
            index=label_match.start(),
        )
        sections.append(section)
    sections.sort(key=lambda x: x.index)
    sections_keys = {section.label: section for section in sections}
    if not sections:
        sectionless_content = release_content
    elif sections[0].index > 0:
        sectionless_content = release_content[: sections[0].index].strip()
    new_sections: list[SectionContent] = []
    found = False
    for label in settings.input_labels:
        if label.label in sections_keys:
            section = sections_keys[label.label]
        else:
            section = SectionContent(
                label=label.label,
                header=label.header,
                content="",
                index=-1,
            )
            sections_keys[label.label] = section
        if label.label in labels and not found:
            found = True
            section.content = f"{message}\n{section.content}".strip()
        new_sections.append(section)
    if not found:
        if sectionless_content:
            sectionless_content = f"{message}\n{sectionless_content}"
        else:
            sectionless_content = f"{message}"
    new_release_content = ""
    if sectionless_content:
        new_release_content = f"{sectionless_content}"
    use_sections = [
        f"{settings.input_label_header_prefix}{section.header}\n\n{section.content}"
        for section in new_sections
        if section.content
    ]
    updated_content = "\n\n".join(use_sections)
    if new_release_content:
        if updated_content:
            new_release_content += f"\n\n{updated_content}"
    else:
        new_release_content = updated_content

    new_content = (
        f"{pre_header_content}\n\n{new_release_content}\n\n{post_release_content}"
        .strip()
        + "\n"
    )
    return new_content


def doc_changes() -> None:
    # Ref: https://github.com/actions/runner/issues/2033
    logging.info(
        "GitHub Actions workaround for git in containers, ref:"
        " https://github.com/actions/runner/issues/2033"
    )
    safe_directory_config_content = "[safe]\n\tdirectory = /github/workspace"
    dotgitconfig_path = Path.home() / ".gitconfig"
    dotgitconfig_path.write_text(safe_directory_config_content)
    settings = Settings()
    if settings.input_debug_logs:
        logging.info(f"Using config: {settings.json()}")
    g = Github(settings.repo_token.get_secret_value())
    repo = g.get_repo(settings.github_repository)
    if not settings.github_event_path.is_file():
        logging.error(f"No event file was found at: {settings.github_event_path}")
        sys.exit(1)
    contents = settings.github_event_path.read_text()
    event = PartialGitHubEvent.model_validate_json(contents)
    if event.number is not None:
        number = event.number
    elif event.inputs and event.inputs.number:
        number = event.inputs.number
    else:
        logging.error(
            "No PR number was found (PR number or workflow input) in the event file"
            f" at: {settings.github_event_path}"
        )
        sys.exit(1)
    pr = repo.get_pull(number)
    if not pr.merged:
        logging.info("The PR was not merged, nothing else to do.")
        sys.exit(0)
    # clone lamin-docs
    if settings.changelog_file.as_posix().startswith("lamin-docs"):
        subprocess.run(
            [
                "git",
                "clone",
                "--depth=1",
                "https://github.com/laminlabs/lamin-docs",
            ]
        )
        cwd = "lamin-docs"
    else:
        cwd = None
    if not settings.changelog_file.is_file():
        logging.error(
            f"The latest changes files doesn't seem to exist: {settings.changelog_file}"
        )
        sys.exit(1)
    logging.info("Setting up GitHub Actions git user")
    subprocess.run(
        ["git", "config", "user.name", "github-actions"], check=True, cwd=cwd
    )
    subprocess.run(
        ["git", "config", "user.email", "github-actions@github.com"],
        check=True,
        cwd=cwd,
    )
    number_of_trials = 10
    logging.info(f"Number of trials (for race conditions): {number_of_trials}")
    for trial in range(10):
        logging.info(f"Running trial: {trial}")
        content = settings.changelog_file.read_text()

        new_content = generate_content(
            content=content,
            settings=settings,
            pr=pr,
            labels=[label.name for label in pr.labels],
        )
        settings.changelog_file.write_text(new_content)
        logging.info(f"Committing changes to: {settings.changelog_file}")
        subprocess.run(
            [
                "git",
                "add",
                str(settings.changelog_file).replace("lamin-docs/", ""),
            ],
            check=True,
            cwd=cwd,
        )
        subprocess.run(
            ["git", "commit", "-m", "📝 Update changelog"], check=True, cwd=cwd
        )
        logging.info(f"Pushing changes: {settings.changelog_file}")
        if settings.docs_token is None:
            token = settings.repo_token.get_secret_value()
        else:
            token = settings.docs_token.get_secret_value()
        subprocess.run(
            [
                "git",
                "remote",
                "set-url",
                "origin",
                f"https://x-access-token:{token}@github.com/laminlabs/lamin-docs.git",
            ],
            check=True,
            cwd=cwd,
        )
        subprocess.run(["git", "push"], check=True, cwd=cwd)
        break
    logging.info("Finished")
