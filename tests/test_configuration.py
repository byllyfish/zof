from zof.configuration import Configuration


def test_configuration():
    """Test Configuration class."""

    settings = Configuration(driver_class='x')
    assert settings.driver_class == 'x'
    assert settings.listen_versions == Configuration.listen_versions
