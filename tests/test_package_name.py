from laminci import get_package_name


def test_get_package_name():
    assert get_package_name() == "laminci"
