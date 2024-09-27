import ast
import configparser
from abc import ABC
from argparse import ArgumentParser
from argparse import Namespace
from pathlib import Path
from typing import Any
from typing import Type


class MissingRequiredArgument(Exception):
    """missing required argument"""


class NotSupportError(Exception):
    """error usage for this package"""


# https://stackoverflow.com/questions/30239092/how-to-get-multiline-input-from-the-user
def input_multilines(title: str = "") -> list[str]:
    print(title + "Item per line. Press Ctrl-Z in a new line then Enter to continue.")
    contents = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        contents += line.splitlines()
    return contents


class Validator(ABC):
    @staticmethod
    def get_value_repr(val: Any) -> str:
        if isinstance(val, str):
            return val
        else:
            return repr(val)

    @staticmethod
    def validate_input(input: str | list) -> bool:
        return input != ""

    @staticmethod
    def get_value_from_input(input: str | list) -> Any:
        return input

    @staticmethod
    def match_action(action) -> bool:
        return False


class DummyType(Validator):
    @staticmethod
    def get_value_repr(val: Any) -> str:
        return ""


class StrType(Validator):
    @staticmethod
    def get_value_repr(val: str) -> str:
        return val

    @staticmethod
    def get_value_from_input(input: str | list) -> str:
        if not isinstance(input, str):
            raise NotSupportError(input)
        return input.strip()

    @staticmethod
    def match_action(action) -> bool:
        return not IterableType.match_action(action) and not BoolType.match_action(action)


class IterableType(Validator):
    @staticmethod
    def get_value_repr(val) -> str:
        return repr(val)

    @staticmethod
    def get_value_from_input(input: str | list) -> list:
        if isinstance(input, str):
            lst = ast.literal_eval(input)
        else:
            lst = input
        lst = [x.strip() for x in lst]
        return [x for x in lst if x]

    @staticmethod
    def match_action(action) -> bool:
        return action.nargs in {"*", "+"} or action.__class__.__name__ == "_AppendAction"


class BoolType(Validator):
    @staticmethod
    def get_value_from_input(input: str | list) -> bool:
        if not isinstance(input, str):
            raise NotSupportError(input)
        return input.strip().lower() in {
            "1",
            "true",
            "yes",
        }

    @staticmethod
    def match_action(action) -> bool:
        return isinstance(action.default, bool) or action.__class__.__name__ == "_StoreTrueAction"


DEFAULT_VALIDATOR = {
    list: IterableType,
    tuple: IterableType,
    bool: BoolType,
    str: StrType,
}


def _iter_actions(
    parser: ArgumentParser,
    args: Namespace = None,
    user_validators: dict[str, Type[Validator]] = None,
):
    args = args or Namespace()
    for action in parser._actions:
        if action.dest == "help":
            continue
        if action.dest in user_validators:
            validator = user_validators[action.dest]
        elif action.default is None and action.const is not None:
            raise NotImplementedError(action)
        else:
            validator = StrType
            possible_val = getattr(args, action.dest, action.default)
            if possible_val is None:
                for v in DEFAULT_VALIDATOR.values():
                    if v.match_action(action):
                        validator = v
                        break
            else:
                validator = DEFAULT_VALIDATOR.get(type(possible_val), DummyType)

        yield action, validator


def import_from_ini(
    parser: ArgumentParser, ini_file: str | Path, user_validators: dict[str, Type[Validator]] = None
):
    """
    import config settings from ini, and replace the default value in ArgumentParser
    """
    user_validators = user_validators or {}

    config = configparser.ConfigParser()
    config.read(ini_file)
    default_section = config["DEFAULT"]
    init_configs = {}
    for action, validator in _iter_actions(parser, user_validators=user_validators):
        if action.dest not in default_section:
            continue
        data = default_section[action.dest]
        val = validator.get_value_from_input(data)
        if validator.validate_input(val):
            init_configs[action.dest] = val
    parser.set_defaults(**init_configs)


def get_user_inputs(
    parser: ArgumentParser,
    only_asks: list[str] = None,
    user_validators: dict[str, Type[Validator]] = None,
) -> Namespace:
    """
    `only_asks`: choose which arguments to ask user
        others just use default values
    `user_validators`: specify customized validators,
        key is the argument key
        value is a subclass of argini.Validator
    """
    user_validators = user_validators or {}
    only_asks = only_asks or []

    args = Namespace()
    for action, validator in _iter_actions(parser, user_validators=user_validators):
        if only_asks:
            if action is not None and action.dest not in only_asks:
                if action.required and action.default is not None:
                    raise MissingRequiredArgument(action.dest)
                setattr(args, action.dest, action.default)
                continue

        default_txt = validator.get_value_repr(action.default)
        q = f" (Default: {default_txt}) " if default_txt else ""
        opts = "{%s}" % ",".join(action.choices) + " " if action.choices else ""

        if title := (action.help or "") + q:
            print(title)
        while True:
            # Get User Input
            if IterableType.match_action(action):
                data = input_multilines(action.dest + "? ")
            else:
                data = input(action.dest + "? " + opts)
            if not data and default_txt:
                data = default_txt

            # Validation
            if action.choices:
                if data in action.choices:
                    break
                else:
                    print("Oops! not a valid choice.", file=sys.stderr)
            elif validator.validate_input(data):
                break

        value = validator.get_value_from_input(data)
        setattr(args, action.dest, value)

    return args


def get_user_inputs_with_survey(
    parser: ArgumentParser,
    only_asks: list[str] = None,
    user_validators: dict[str, Type[Validator]] = None,
) -> Namespace:
    """
    `only_asks`: choose which arguments to ask user
        others just use default values
    `user_validators`: specify customized validators,
        key is the argument key
        value is a subclass of argini.Validator
    """
    import survey

    user_validators = user_validators or {}
    only_asks = only_asks or []

    args = Namespace()
    for action, validator in _iter_actions(parser, user_validators=user_validators):
        if only_asks:
            if action is not None and action.dest not in only_asks:
                if action.required and action.default is not None:
                    raise MissingRequiredArgument(action.dest)
                setattr(args, action.dest, action.default)
                continue

        default_txt = validator.get_value_repr(action.default)
        if BoolType.match_action(action) or action.choices:
            q = ""
        else:
            q = f" (Default: {default_txt}) "

        if title := (action.help or "") + q:
            print(title)
        while True:
            # Get User Input
            if action.choices:
                if default_txt in action.choices:
                    default = list(action.choices).index(default_txt)
                else:
                    default = 0
                idx = survey.routines.select(
                    action.dest + "? ", options=list(action.choices), index=default
                )
                value = action.choices[idx]
                break

            if IterableType.match_action(action):
                data = survey.routines.input(
                    action.dest
                    + "? "
                    + "Item per line. Press Enter 3 times to continue.",
                    multi=True,
                )
                data = data.splitlines()
            elif BoolType.match_action(action):
                data = survey.routines.inquire(action.dest + "? ", default=BoolType.get_value_from_input(default_txt))
            else:
                data = survey.routines.input(action.dest + "? ")
            if data == "" and default_txt:
                data = default_txt

            # Validation
            if validator.validate_input(data):
                if action.nargs == "+" and not data:
                    print("At least one is required!", file=sys.stderr)
                    continue
                value = data
                break

        setattr(args, action.dest, value)

    return args


def save_to_ini(
    parser: ArgumentParser,
    ini_file: str | Path,
    args: Namespace,
    user_validators: dict[str, Type[Validator]] = None,
):
    user_validators = user_validators or {}
    config = configparser.ConfigParser()
    config.read(ini_file)
    default_section = config["DEFAULT"]
    for action, val_func in _iter_actions(parser, args, user_validators):
        val = getattr(args, action.dest)
        if val is not None:
            default_section[action.dest] = val_func.get_value_repr(val)

    with open(ini_file, "w") as config_file:
        config.write(config_file)


if __name__ == "__main__":
    # manually simple cli test
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    # parser.add_argument("--test")  # line
    # parser.add_argument("--fruit", choices=["apple", "banana"])  # choice
    parser.add_argument("--ok", action="store_true")  # flag
    # parser.add_argument("--options", nargs="*")  # multiline text
    # parser.add_argument("--flags", action="append")  # multiline text
    if len(sys.argv) == 1:
        import_from_ini(parser, "test.ini")
        args = get_user_inputs(parser)
    else:
        args = parser.parse_args()
    save_to_ini(parser, "test.ini", args)

    print(args)