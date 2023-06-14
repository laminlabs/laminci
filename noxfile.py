import nox

nox.options.default_venv_backend = "none"


@nox.session
def lint(session: nox.Session) -> None:
    session.run(*"pip install pre-commit".split())
    session.run("pre-commit", "install")
    session.run("pre-commit", "run", "--all-files")


@nox.session
def build(session):
    session.run(*"pip install .[dev]".split())
    session.run(
        "pytest",
        "-s",
        "--cov=laminci",
        "--cov-append",
        "--cov-report=term-missing",
    )
