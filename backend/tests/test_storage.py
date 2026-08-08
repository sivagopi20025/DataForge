from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.models import GeneratedFile
from backend.app.services.storage import LocalStorageService


def test_local_storage_records_safe_metadata(tmp_path):
    output_dir = tmp_path / "output"
    source = output_dir / "run-1" / "customers.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"ok": true}', encoding="utf-8")

    stored = LocalStorageService(output_dir).save_generated_file(source, object_key="run-1/customers.json")

    assert stored.storage_backend == "local"
    assert stored.object_key == "run-1/customers.json"
    assert stored.size_bytes == source.stat().st_size
    assert stored.content_type == "application/json"
    assert Path(stored.file_path).resolve() == source.resolve()


def test_local_storage_rejects_unsafe_object_key(tmp_path):
    output_dir = tmp_path / "output"
    source = output_dir / "run-1" / "customers.json"
    source.parent.mkdir(parents=True)
    source.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsafe object key"):
        LocalStorageService(output_dir).save_generated_file(source, object_key="../customers.json")


def test_local_storage_download_rejects_path_escape(tmp_path):
    output_dir = tmp_path / "output"
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    generated_file = GeneratedFile(
        run_id="run-1",
        file_name="outside.json",
        file_path=str(outside),
        storage_backend="local",
        object_key="../outside.json",
        file_format="json",
        size_bytes=outside.stat().st_size,
        file_size_mb=0.0,
        content_type="application/json",
    )

    with pytest.raises(ValueError, match="Unsafe object key"):
        LocalStorageService(output_dir).download_response(generated_file)
