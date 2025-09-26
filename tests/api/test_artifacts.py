"""Tests for artifact management functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from comma_tools.api.artifacts import ArtifactManager


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def artifact_manager(temp_storage):
    """Create artifact manager with temp storage."""
    return ArtifactManager(temp_storage)


def test_register_artifact(artifact_manager, temp_storage):
    """Test artifact registration."""
    test_file = temp_storage / "test.csv"
    test_file.write_text("test,data\n1,2\n")

    artifact_id = artifact_manager.register_artifact("test-run", test_file)

    assert artifact_id in artifact_manager.artifacts
    metadata = artifact_manager.artifacts[artifact_id]
    assert metadata.run_id == "test-run"
    assert metadata.filename == "test.csv"
    assert metadata.content_type == "text/csv"
    assert metadata.size_bytes > 0


def test_get_artifacts_for_run(artifact_manager, temp_storage):
    """Test getting artifacts for a run."""
    test_file1 = temp_storage / "test1.csv"
    test_file1.write_text("data1")
    test_file2 = temp_storage / "test2.json"
    test_file2.write_text('{"data": 2}')

    artifact_manager.register_artifact("run1", test_file1)
    artifact_manager.register_artifact("run1", test_file2)
    artifact_manager.register_artifact("run2", test_file1)

    run1_artifacts = artifact_manager.get_artifacts_for_run("run1")
    assert len(run1_artifacts) == 2

    run2_artifacts = artifact_manager.get_artifacts_for_run("run2")
    assert len(run2_artifacts) == 1


def test_get_artifact_file_path(artifact_manager, temp_storage):
    """Test getting artifact file path."""
    test_file = temp_storage / "test.html"
    test_file.write_text("<html></html>")

    artifact_id = artifact_manager.register_artifact("test-run", test_file)
    file_path = artifact_manager.get_artifact_file_path(artifact_id)

    assert file_path.exists()
    assert file_path.name == "test.html"
    assert file_path.read_text() == "<html></html>"


def test_get_artifact_file_path_not_found(artifact_manager):
    """Test getting artifact file path for non-existent artifact."""
    with pytest.raises(KeyError, match="Artifact 'nonexistent' not found"):
        artifact_manager.get_artifact_file_path("nonexistent")
