"""Every test runs with a home folder of its own, whether or not it asks for one."""

from pathlib import Path


def test_a_test_that_asks_for_nothing_still_has_a_home_folder_of_its_own(tmp_path):
    assert Path.home() == tmp_path
    assert Path("~/tldl").expanduser().parent == tmp_path
