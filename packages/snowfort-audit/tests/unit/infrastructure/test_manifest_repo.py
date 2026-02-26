from unittest.mock import MagicMock

from snowfort_audit.infrastructure.repositories.manifest import YamlManifestRepository


def test_load_definitions_success():
    mock_fs = MagicMock()
    mock_fs.join_path.return_value = "/path/to/manifest.yml"
    mock_fs.exists.return_value = True

    yaml_content = """
    definitions:
      table_1:
         type: TABLE
         retention: 1
    """
    mock_fs.read_text.return_value = yaml_content

    repo = YamlManifestRepository(mock_fs)
    defs = repo.load_definitions("/path/to")

    assert len(defs) == 1
    assert defs["table_1"]["type"] == "TABLE"
    mock_fs.join_path.assert_called_with("/path/to", "manifest.yml")


def test_load_definitions_not_found():
    mock_fs = MagicMock()
    mock_fs.join_path.return_value = "/path/to/manifest.yml"
    mock_fs.exists.return_value = False

    repo = YamlManifestRepository(mock_fs)
    defs = repo.load_definitions("/path/to")

    assert defs == {}


def test_load_definitions_yaml_error():
    mock_fs = MagicMock()
    mock_fs.exists.return_value = True
    mock_fs.read_text.return_value = "invalid: [ yaml"

    repo = YamlManifestRepository(mock_fs)
    defs = repo.load_definitions("/path/to")

    assert defs == {}


def test_load_definitions_empty_or_no_definitions_key():
    mock_fs = MagicMock()
    mock_fs.join_path.return_value = "/path/to/manifest.yml"
    mock_fs.exists.return_value = True
    mock_fs.read_text.return_value = ""

    repo = YamlManifestRepository(mock_fs)
    defs = repo.load_definitions("/path/to")

    assert defs == {}
