from pathlib import Path


def test_package_scaffold_exists() -> None:
    package = Path(__file__).parents[1] / ".." / "src" / "autoapply"
    assert (package / "__init__.py").resolve().is_file()
    assert (package / "main.py").resolve().is_file()
