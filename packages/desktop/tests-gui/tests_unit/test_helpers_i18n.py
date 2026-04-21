import pytest

from gpd_tests.helpers import i18n


@pytest.mark.unit
def test_t_returns_exact_match_for_known_key():
    assert i18n.t("common.close") == "Close"


@pytest.mark.unit
def test_t_raises_keyerror_for_missing_key():
    with pytest.raises(KeyError):
        i18n.t("definitely.not.a.key")


@pytest.mark.unit
def test_t_supports_dict_access_for_nested_keys():
    all_keys = i18n.all_keys()
    assert len(all_keys) > 500
    for key in all_keys[:5]:
        assert isinstance(i18n.t(key), str)
