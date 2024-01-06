"""Internal CI tools.

Import the package::

   import laminci

"""

__version__ = "0.10.0"  # denote a pre-release for 0.1.0 with 0.1a1

from . import db, nox
from ._artifacts import upload_docs_artifact
from ._docs import (
    move_built_docs_to_docs_slash_project_slug,
    move_built_docs_to_slash_project_slug,
)
from ._env import get_package_name, get_schema_handle

# backward compat
upload_docs_dir = upload_docs_artifact
