"""Unit tests for configuration loader and settings verification."""

from src.config.settings import get_settings


def test_settings_initialization():
    """Verify settings defaults and bounding box values."""
    settings = get_settings()
    assert settings.APP_NAME == "ResQtech"
    assert settings.CRS_GEOGRAPHIC == "EPSG:4326"
    assert settings.CRS_PROJECTED_UTM == "EPSG:32646"

    # Test NER bounding box tuple output
    min_lon, min_lat, max_lon, max_lat = settings.ner_bbox
    assert min_lon < max_lon
    assert min_lat < max_lat
    assert 87.0 <= min_lon <= 89.0
    assert 21.0 <= min_lat <= 23.0
