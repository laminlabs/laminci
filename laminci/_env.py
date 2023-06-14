from pathlib import Path
from typing import Optional

import toml  # type: ignore
import yaml  # type: ignore


def load_project_yaml(root_directory: Optional[Path] = None) -> dict:
    yaml_file = Path("lamin-project.yaml")
    if root_directory is None:
        root_directory = Path(".")
    yaml_file = root_directory / yaml_file
    with yaml_file.open() as f:
        d = yaml.safe_load(f)
    return d


def get_package_name(root_directory: Optional[Path] = None) -> str:
    if Path("lamin-project.yaml").exists():
        return load_project_yaml(root_directory=root_directory)["package_name"]
    else:
        with open("pyproject.toml") as f:
            d = toml.load(f)
        return d["project"]["name"].replace("-", "_")


def get_schema_handle() -> Optional[str]:
    package_name = get_package_name()
    if package_name.startswith("lnschema_"):
        return package_name.replace("lnschema_", "")
    else:
        return None
