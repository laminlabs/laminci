import nox

nox.options.default_venv_backend = "none"


@nox.session
def lint(session: nox.Session) -> None:
    session.run(*"pip install pre-commit".split())
    session.run("pre-commit", "install")
    session.run("pre-commit", "run", "--all-files")


@nox.session(python=["3.7", "3.8", "3.9", "3.10", "3.11"])
def build(session):
    session.run(*"pip install .[dev]".split())
    session.run(
        "pytest",
        "-s",
        "--cov=laminci",
        "--cov-append",
        "--cov-report=term-missing",
    )
