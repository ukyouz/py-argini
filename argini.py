import configparser
from abc import ABC
from argparse import ArgumentParser
from argparse import Namespace
from typing import Any


class MissingRequiredArgument(Exception):
    """ missing required argument """


class NotSupportError(Exception):
    """ error usage for this package """


# https://stackoverflow.com/questions/30239092/how-to-get-multiline-input-from-the-user
def input_multilines(title: str="") -> list[str]:
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


class IterableType(Validator):
    @staticmethod
    def get_value_repr(val) -> str:
        return " ".join([str(x) for x in val])

    @staticmethod
    def get_value_from_input(input: str | list) -> list:
        if isinstance(input, str):
            l = input.split(" ")
            return [x.strip() for x in l if x]
        else:
            return input


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


DEFAULT_VALIDATOR = {
    str: StrType,
    list: IterableType,
    tuple: IterableType,
    bool: BoolType,
}


def _iter_actions(
    parser: ArgumentParser,
    args: Namespace=None,
    user_validators: dict[str, Validator]=None
):
    args = args or Namespace()
    for action in parser._actions:
        if action.dest == "help":
            continue
        if action.dest in user_validators:
            validator = user_validators[action.dest]
        else:
            t = type(getattr(args, action.dest, action.default)) or str
            validator = DEFAULT_VALIDATOR.get(t, DummyType)

        yield action, validator


def import_from_ini(
    parser: ArgumentParser,
    ini_file: str,
    user_validators: dict[str, Validator]=None
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
        if validator.validate_input(data):
            val = validator.get_value_from_input(data)
            init_configs[action.dest] = val
    parser.set_defaults(**init_configs)


def get_user_inputs(
    parser: ArgumentParser,
    only_asks: list[str]=None,
    user_validators: dict[str, Validator]=None,
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
            if action.nargs in {"*", "+"}:
                data = input_multilines(action.dest + "? ")
            else:
                data = input(action.dest + "? " + opts)
            if data == "" and default_txt:
                data = default_txt

            # Validation
            if action.choices:
                if data in action.choices:
                    break
                else:
                    print("Oops! not a valid choice.")
            elif validator.validate_input(data):
                break

        value = validator.get_value_from_input(data)
        setattr(args, action.dest, value)

    return args


def save_to_ini(
    parser: ArgumentParser,
    ini_file: str,
    args: Namespace,
    user_validators: dict[str, Validator]=None
):
    user_validators = user_validators or {}
    config = configparser.ConfigParser()
    config.read(ini_file)
    default_section = config["DEFAULT"]
    for action, val_func in _iter_actions(parser, args, user_validators):
        val = getattr(args, action.dest)
        if val is not None:
            default_section[action.dest] = val_func.get_value_repr(val)

    with open(ini_file, 'w') as config_file:
        config.write(config_file)


if __name__ == "__main__":
    # manually simple cli test
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test")  # line
    parser.add_argument("--fruit", choices=["apple", "banana"])  # choice
    parser.add_argument("--description", nargs="*")  # multiline text
    if len(sys.argv) == 1:
        args = get_user_inputs(parser)
    else:
        args = parser.parse_args()
    save_to_ini(parser, "test.ini", args)