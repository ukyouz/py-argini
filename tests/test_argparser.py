import argparse
import pytest
import builtins
from functools import partial
from pathlib import Path
from typing import Iterable

import argini


@pytest.fixture
def simple_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test")  # line
    parser.add_argument("--other")
    parser.add_argument("--fruit", choices=["apple", "banana"])  # choice
    parser.add_argument("--ok", action="store_true")  # flag
    return parser


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
    with mocker.patch("argini.input_multilines", side_effect=(
        (
            [],
            [],
        )
    )):
        args = argini.get_user_inputs(multiline_parser)
    assert args.options == ["aaa", "bbb"]
    assert args.flags == ["1", "2"]