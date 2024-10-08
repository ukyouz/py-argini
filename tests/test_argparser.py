import argparse
import pytest
import tempfile
from pathlib import Path

import argini

TEST_INI_FILE = "__test.ini"


def test_multiline_input(mocker):
    with mocker.patch("builtins.input", side_effect=(
        "aaa",
        "bbb",
        EOFError(),
    )):
        lines = argini.input_multilines()
    assert lines == ["aaa", "bbb"]


def test_validator_path():
    with tempfile.NamedTemporaryFile() as tmpfile:
        v = argini.ValidatePath()
        assert v.validate_input(tmpfile.name)
        assert not v.validate_input("aaa")

        v = argini.ValidateFile()
        assert v.validate_input(tmpfile.name)
        assert not v.validate_input("aaa")

    with tempfile.TemporaryDirectory() as tmpdir:
        v = argini.ValidatePath()
        assert v.validate_input(tmpdir)
        assert not v.validate_input("aaa")

        v = argini.ValidateFolder()
        assert v.validate_input(tmpdir)
        assert not v.validate_input("aaa")


@pytest.fixture
def simple_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test")  # line
    parser.add_argument("--other", default="other")
    parser.add_argument("--fruit", choices=["apple", "banana"], default="apple")  # choice
    parser.add_argument("--ok", action="store_true")  # flag
    parser.add_argument("--opt", action="store_const", default=2, const=5)  # flag
    return parser


def test_parse_1_ini_io(simple_parser: argparse.ArgumentParser, mocker):
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
    args = argini.get_user_inputs(simple_parser, only_asks=[])
    assert args.test == "123"
    assert args.other == "aaa"
    assert args.fruit == "banana"
    assert args.ok is True
    assert args.opt == 2


def test_parse_1(simple_parser, mocker):
    with mocker.patch("builtins.input", side_effect=(
        (
            "123",
            "aaa",
            "banana",
            "1",
            "1",
        )
    )):
        args = argini.get_user_inputs(simple_parser, show_help=False)
    assert args.test == "123"
    assert args.other == "aaa"
    assert args.fruit == "banana"
    assert args.ok is True
    assert args.opt == 5


def test_parse_2(simple_parser, mocker):
    with mocker.patch("builtins.input", side_effect=(
        (
            "123",
            "aaa",
            "banana",
            "0",
            "0",
        )
    )):
        args = argini.get_user_inputs(simple_parser, show_help=False)
    assert args.test == "123"
    assert args.other == "aaa"
    assert args.fruit == "banana"
    assert args.ok is False
    assert args.opt == 2


def test_parse_1_only_args(simple_parser: argparse.ArgumentParser, mocker):
    with mocker.patch("builtins.input", side_effect=(
        (
            "123",
        )
    )):
        args = argini.get_user_inputs(simple_parser, only_asks=["test"], show_help=False)
    assert args.other == "other"


def test_parse_1_default(simple_parser: argparse.ArgumentParser, mocker):
    simple_parser.set_defaults(
        test="123",
        other="aaa",
        fruit="banana",
        ok=True,
        opt=7,
    )
    with mocker.patch("builtins.input", return_value=""):
        args = argini.get_user_inputs(simple_parser, show_help=False)
    assert args.test == "123"
    assert args.other == "aaa"
    assert args.fruit == "banana"
    assert args.ok is True
    assert args.opt == 7


def test_parse_1_user_input(simple_parser: argparse.ArgumentParser, mocker):
    args = simple_parser.parse_args(
        [
            "--test", "123",
            "--other", "aaa",
            "--fruit", "banana",
            "--ok",
            "--opt",
        ]
    )
    argini.save_to_ini(simple_parser, TEST_INI_FILE, args)
    assert Path(TEST_INI_FILE).exists()

    with mocker.patch("builtins.input", side_effect=(
        (
            "456",
            "bbb",
            "apple",
            "n",
            "n",
        )
    )):
        args = argini.get_user_inputs(simple_parser, show_help=False)
    assert args.test == "456"
    assert args.other == "bbb"
    assert args.fruit == "apple"
    assert args.ok is False
    assert args.opt == 2


@pytest.fixture
def multiline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--options", nargs="*")  # multiline text
    parser.add_argument("--flags", action="append")  # multiline text
    return parser


def test_parse_multiline_ini_io(multiline_parser: argparse.ArgumentParser, mocker):
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
    args = argini.get_user_inputs(multiline_parser, only_asks=[])
    assert args.options == ["aaa", "bbb"]
    assert args.flags == ["1", "2"]


def test_parse_multiline(multiline_parser: argparse.ArgumentParser, mocker):
    with mocker.patch("argini.input_multilines", side_effect=(
        (
            ["aaa", "bbb"],
            ["1", "2"],
        )
    )):
        args = argini.get_user_inputs(multiline_parser, show_help=False)
    assert args.options == ["aaa", "bbb"]
    assert args.flags == ["1", "2"]


def test_parse_multiline_default(multiline_parser: argparse.ArgumentParser, mocker):
    multiline_parser.set_defaults(
        options=["aaa", "bbb"],
        flags=["1", "2"],
    )
    with mocker.patch("argini.input_multilines", return_value=[]):
        args = argini.get_user_inputs(multiline_parser, show_help=False)
    assert args.options == ["aaa", "bbb"]
    assert args.flags == ["1", "2"]


@pytest.fixture
def subparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subparser")
    subparser1 = subparsers.add_parser("sub1")
    subparser1.add_argument("--sub1")
    subparser2 = subparsers.add_parser("sub2")
    subparser2.add_argument("--sub2")
    return parser


def test_subparsers(subparser: argparse.ArgumentParser, mocker):
    with mocker.patch("builtins.input", side_effect=(
        (
            "sub1",
            "aaa",
        )
    )):
        args = argini.get_user_inputs(subparser, show_help=False)
    assert args.subparser == "sub1"
    assert args.sub1 == "aaa"


def test_subparsers_io(subparser: argparse.ArgumentParser, mocker):
    with mocker.patch("builtins.input", side_effect=(
        (
            "sub1",
            "aaa",
        )
    )):
        args = argini.get_user_inputs(subparser, show_help=False)
    argini.save_to_ini(subparser, TEST_INI_FILE, args)
    assert Path(TEST_INI_FILE).exists()

    argini.import_from_ini(subparser, TEST_INI_FILE)
    args = argini.get_user_inputs(subparser, only_asks=[])
    assert args.subparser == "sub1"
    assert args.sub1 == "aaa"
