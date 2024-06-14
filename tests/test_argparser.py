import argparse
import pytest
from pathlib import Path

import argini

TEST_INI_FILE = "__test.ini"

@pytest.fixture
def simple_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test")  # line
    parser.add_argument("--other")
    parser.add_argument("--fruit", choices=["apple", "banana"])  # choice
    parser.add_argument("--ok", action="store_true")  # flag
    return parser


def test_1_ini_io(simple_parser: argparse.ArgumentParser, mocker):
    args = simple_parser.parse_args(
        [
            "--test", "123",
            "--other", "aaa",
            "--fruit", "banana",
            "--ok"
        ]
    )
    argini.save_to_ini(simple_parser, TEST_INI_FILE, args)
    assert Path(TEST_INI_FILE).exists()

    argini.import_from_ini(simple_parser, TEST_INI_FILE)
    assert simple_parser.get_default("test") == "123"
    assert simple_parser.get_default("other") == "aaa"
    assert simple_parser.get_default("fruit") == "banana"
    assert simple_parser.get_default("ok") is True


def test_1(simple_parser, mocker):
    with mocker.patch("builtins.input", side_effect=(
        (
            "123",
            "aaa",
            "banana",
            "1",
        )
    )):
        args = argini.get_user_inputs(simple_parser)
    assert args.test == "123"
    assert args.other == "aaa"
    assert args.fruit == "banana"
    assert args.ok is True


def test_1_only_args(simple_parser: argparse.ArgumentParser, mocker):
    with mocker.patch("builtins.input", side_effect=(
        (
            "123",
        )
    )):
        args = argini.get_user_inputs(simple_parser, only_asks=["test"])
    assert args.other is None


def test_1_default(simple_parser: argparse.ArgumentParser, mocker):
    simple_parser.set_defaults(
        test="123",
        other="aaa",
        fruit="banana",
        ok=True,
    )
    with mocker.patch("builtins.input", return_value=""):
        args = argini.get_user_inputs(simple_parser)
    assert args.test == "123"
    assert args.other == "aaa"
    assert args.fruit == "banana"
    assert args.ok is True


@pytest.fixture
def multiline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--options", nargs="*")  # multiline text
    parser.add_argument("--flags", action="append")  # multiline text
    return parser


def test_multiline_ini_io(multiline_parser: argparse.ArgumentParser, mocker):
    args = multiline_parser.parse_args(
        [
            "--options", "aaa", "bbb",
            "--flags", "1",
            "--flags", "2",
        ]
    )
    argini.save_to_ini(multiline_parser, TEST_INI_FILE, args)
    assert Path(TEST_INI_FILE).exists()

    argini.import_from_ini(multiline_parser, TEST_INI_FILE)
    assert multiline_parser.get_default("options") == ["aaa", "bbb"]
    assert multiline_parser.get_default("flags") == ["1", "2"]


def test_multiline(multiline_parser: argparse.ArgumentParser, mocker):
    with mocker.patch("argini.input_multilines", side_effect=(
        (
            ["aaa", "bbb"],
            ["1", "2"],
        )
    )):
        args = argini.get_user_inputs(multiline_parser)
    assert args.options == ["aaa", "bbb"]
    assert args.flags == ["1", "2"]


def test_multiline_default(multiline_parser: argparse.ArgumentParser, mocker):
    multiline_parser.set_defaults(
        options=["aaa", "bbb"],
        flags=["1", "2"],
    )
    with mocker.patch("argini.input_multilines", return_value=[]):
        args = argini.get_user_inputs(multiline_parser)
    assert args.options == ["aaa", "bbb"]
    assert args.flags == ["1", "2"]