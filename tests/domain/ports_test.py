import inspect

import pytest

from src.domain.ports import IVideoProcessor


def test_ivideoprocessor_is_abstract():
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IVideoProcessor()


def test_ivideoprocessor_generate_short_signature_defaults():
    signature = inspect.signature(IVideoProcessor.generate_short)

    assert signature.parameters["outro_filepath"].default is None
    assert signature.parameters["fade_duration"].default == 0.7
