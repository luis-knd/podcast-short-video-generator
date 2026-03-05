import pytest

from src.domain.ports import IVideoProcessor


def test_ivideoprocessor_is_abstract():
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IVideoProcessor()
