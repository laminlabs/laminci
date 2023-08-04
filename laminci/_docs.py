import os
import shutil

from ._env import load_project_yaml


def move_built_docs_to_slash_project_slug():
    if os.environ["GITHUB_EVENT_NAME"] != "push":
        return
    yaml = load_project_yaml()
    shutil.move("_build/html", "_build/html_tmp")
    os.makedirs("_build/html")
    shutil.move("_build/html_tmp", f"_build/html/{yaml['project_slug']}")


def move_built_docs_to_docs_slash_project_slug():
    if os.environ["GITHUB_EVENT_NAME"] != "push":
        return
    yaml = load_project_yaml()
    shutil.move("_build/html", f"_build/{yaml['project_slug']}")
    os.makedirs("_build/html/docs")
    shutil.move(f"_build/{yaml['project_slug']}", "_build/html/docs")
