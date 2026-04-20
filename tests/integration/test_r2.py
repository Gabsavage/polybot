import pytest

from polybot.config import Settings
from polybot.storage.r2 import R2Client


@pytest.fixture
def r2_settings() -> Settings:
    """Load real R2 credentials from .env."""
    return Settings()


@pytest.fixture
def r2(r2_settings: Settings) -> R2Client:
    return R2Client(r2_settings)


@pytest.mark.integration
def test_upload_and_read_back(r2: R2Client):
    key = "_test/integration_test.txt"
    data = b"hello from polybot integration test"

    r2.upload_bytes(key, data)
    result = r2.get_bytes(key)
    assert result == data

    r2.delete_object(key)


@pytest.mark.integration
def test_list_objects(r2: R2Client):
    key = "_test/list_test.txt"
    r2.upload_bytes(key, b"test")

    keys = r2.list_keys(prefix="_test/")
    assert key in keys

    r2.delete_object(key)
