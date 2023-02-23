from pathlib import Path
from typing import Optional

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
    return load_project_yaml(root_directory=root_directory)["package_name"]


def get_schema_handle() -> Optional[str]:
    package_name = get_package_name()
    if package_name.startswith("lnschema_"):
        return package_name.replace("lnschema_", "")
    else:
        return None
