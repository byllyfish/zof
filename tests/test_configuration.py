"""Test zof.Configuration class."""

from zof.configuration import Configuration


def test_configuration():
    """Test Configuration class."""

    settings = Configuration(zof_driver_class='x')
    assert settings.zof_driver_class == 'x'
    assert settings.listen_versions == Configuration.listen_versions
