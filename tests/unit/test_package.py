"""Smoke tests for the repository scaffold."""


def test_package_imports() -> None:
    import beamnode

    assert beamnode.__version__ == "0.0.0"
