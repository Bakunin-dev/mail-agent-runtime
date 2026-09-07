"""Publication gate must reject accidental extra files, secrets and source drift."""
import json
import shutil
from pathlib import Path

import pytest

from tools.release import audit


@pytest.fixture
def public_copy(tmp_path):
    root = Path(__file__).resolve().parents[1]
    for name in json.loads((root / "public-files.json").read_text(encoding="utf-8")):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    return tmp_path


def test_publication_gate_rejects_unlisted_file(public_copy):
    (public_copy / "private.txt").write_text("not for publication", encoding="utf-8")
    with pytest.raises(ValueError, match="unlisted"):
        audit(public_copy)


def test_manifest_cannot_authorize_env_or_parent_path(public_copy):
    manifest = public_copy / "public-files.json"
    files = json.loads(manifest.read_text(encoding="utf-8"))
    for name in (".env", "../outside.py"):
        manifest.write_text(json.dumps([*files, name]), encoding="utf-8")
        with pytest.raises(ValueError, match="forbidden|unsafe"):
            audit(public_copy)


def test_original_source_drift_is_detected(public_copy):
    target = public_copy / "server/mail_query/projection.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# unintended edit\n", encoding="utf-8")
    with pytest.raises(ValueError, match="original source drift"):
        audit(public_copy)


@pytest.mark.parametrize("name", ["docs/assets/mail-agent-cover.png", "docs/assets/mail-scenario.gif"])
def test_readme_media_rejects_non_image_payload(public_copy, name):
    (public_copy / name).write_bytes(b"<script>not an image</script>")
    with pytest.raises(ValueError, match="invalid media header"):
        audit(public_copy)


def test_readme_media_has_bounded_size(public_copy):
    target = public_copy / "docs/assets/mail-scenario.gif"
    target.write_bytes(target.read_bytes() + b"\x00" * 2_000_000)
    with pytest.raises(ValueError, match="media exceeds size limit"):
        audit(public_copy)
