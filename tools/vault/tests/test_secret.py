"""The Secret wrapper never shows its value and refuses to be serialised."""

import copy
import pickle

import pytest

from vault.secret import Secret


def test_secret_is_hidden_from_repr_str_format_pickle_and_copy():
    secret = Secret("hunter2")

    for shown in (repr(secret), str(secret), f"{secret}", repr([secret])):
        assert "hunter2" not in shown
    with pytest.raises(TypeError):
        pickle.dumps(secret)
    with pytest.raises(TypeError):
        copy.copy(secret)
    assert secret.reveal() == "hunter2"
