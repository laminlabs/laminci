from __future__ import annotations

import logging
from collections.abc import Sequence

import nox
from nox.registry import _REGISTRY, Any, Callable, F, Func, Python, functools


def session_decorator(
    func: F | None = None,
    python: Python | None = None,
    py: Python | None = None,
    reuse_venv: bool | None = None,
    name: str | None = None,
    venv_backend: Any | None = None,
    venv_params: Any | None = None,
    tags: Sequence[str] | None = None,
) -> F | Callable[[F], F]:
    """Designate the decorated function as a session."""
    # If `func` is provided, then this is the decorator call with the function
    # being sent as part of the Python syntax (`@nox.session`).
    # If `func` is None, however, then this is a plain function call, and it
    # must return the decorator that ultimately is applied
    # (`@nox.session(...)`).
    #
    # This is what makes the syntax with and without parentheses both work.
    if func is None:
        return functools.partial(
            session_decorator,
            python=python,
            py=py,
            reuse_venv=reuse_venv,
            name=name,
            venv_backend=venv_backend,
            venv_params=venv_params,
            tags=tags,
        )

    if py is not None and python is not None:
        raise ValueError(
            "The py argument to nox.session is an alias for the python "
            "argument, please only specify one."
        )

    if python is None:
        python = py

    final_name = name or func.__name__
    fn = Func(
        func, python, reuse_venv, final_name, venv_backend, venv_params, tags=tags
    )
    _REGISTRY[final_name] = fn
    # this is the line we add to silence the httpx logger
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
    logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
    logging.getLogger("botocore.credentials").setLevel(logging.WARNING)
    logging.getLogger("botocore.loaders").setLevel(logging.WARNING)
    logging.getLogger("botocore.hooks").setLevel(logging.WARNING)
    logging.getLogger("botocore.configprovider").setLevel(logging.WARNING)
    logging.getLogger("botocore.retryhandler").setLevel(logging.WARNING)
    logging.getLogger("botocore.utils").setLevel(logging.WARNING)
    logging.getLogger("botocore.regions").setLevel(logging.WARNING)
    logging.getLogger("botocore.httpsession").setLevel(logging.WARNING)
    logging.getLogger("botocore.auth").setLevel(logging.WARNING)
    logging.getLogger("botocore.endpoint").setLevel(logging.WARNING)
    logging.getLogger("botocore.parsers").setLevel(logging.WARNING)
    return fn


nox.session = session_decorator
