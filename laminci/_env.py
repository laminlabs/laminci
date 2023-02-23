from pathlib import Path
from typing import Optional

import yaml  # type: ignore


def get_package_name(root_directory: Optional[Path] = None) -> str:
    yaml_file = Path("lamin-project.yaml")
    if root_directory is None:
        root_directory = Path(".")
    yaml_file = root_directory / yaml_file
    with yaml_file.open() as f:
        package_name = yaml.safe_load(f)["package_name"]
    return package_name


def get_schema_handle() -> Optional[str]:
    package_name = get_package_name()
    if package_name.startswith("lnschema_"):
        return package_name.replace("lnschema_", "")
    else:
        return None
