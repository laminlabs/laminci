"""Internal CI tools.

Import the package::

   import laminci

"""

__version__ = "0.1.0"  # denote a pre-release for 0.1.0 with 0.1a1

from . import db, nox
from ._artifacts import upload_docs_dir
from ._env import get_package_name, get_schema_handle
