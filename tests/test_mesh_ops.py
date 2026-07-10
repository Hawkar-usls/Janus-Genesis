from pathlib import Path

import trimesh

from janus_genesis.mesh_ops import discover_models, metrics


def test_discover_models_filters_files(tmp_path: Path) -> None:
    (tmp_path / "part.stl").write_text("solid empty\nendsolid empty\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    assert discover_models(tmp_path) == [tmp_path / "part.stl"]


def test_box_metrics() -> None:
    box = trimesh.creation.box(extents=[10.0, 20.0, 30.0])
    report = metrics(box)
    assert report.watertight is True
    assert report.volume_mm3 == 6000.0
    assert report.extents_mm == [10.0, 20.0, 30.0]
