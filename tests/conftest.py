import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def make_zip(tmp_path):
    def _make(files: dict[str, str], name: str = "instagram-test.zip") -> Path:
        p = tmp_path / name
        with zipfile.ZipFile(p, "w") as z:
            for member, content in files.items():
                z.writestr(member, content)
        return p

    return _make
