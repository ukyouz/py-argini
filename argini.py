import configparser
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from typing import Any


class MissingRequiredArgument(Exception):
    """ missing required argument """


class Validator(ABC):
    @staticmethod
    def support_types() -> list[str]:
        return [""]

    @staticmethod
    def get_value_repr(val: Any) -> str:
        return repr(val)

    @staticmethod
    def validate_input(input: str) -> bool:
        return input != ""

    @staticmethod
    def get_value_from_input(input: str) -> Any:
        return input

    @staticmethod
    def get_validator(type):
        type_name = type.__name__
        subclasses = Validator.__subclasses__()
        for c in subclasses:
            if type_name in c.support_types():
                return c
        return None


class DummyType(Validator):
    @staticmethod
    def support_types() -> list[str]:
        return ["NoneType"]

    @staticmethod
    def get_value_repr(val: Any) -> str:
        return ""


class StrType(Validator):
    @staticmethod
    def support_types() -> list[str]:
        return ["str"]

    @staticmethod
    def get_value_repr(val: str) -> str:
        return val

    @staticmethod
    def get_value_from_input(input: str) -> bool:
        return input.strip()


class IterableType(Validator):
    @staticmethod
    def support_types() -> list[str]:
        return ["list", "typle"]

    @staticmethod
    def get_value_repr(val) -> str:
        return " ".join([str(x) for x in val])

    @staticmethod
    def get_value_from_input(input: str) -> list:
        l = input.split(" ")
        return [x.strip() for x in l if x]


class BoolType(Validator):
    @staticmethod
    def support_types() -> list[str]:
        return ["bool"]

    @staticmethod
    def get_value_from_input(input: str) -> bool:
        return input.strip().lower() in {
            "1",
            "true",
            "yes",
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
            val_func = user_validators[action.dest]()
        else:
            t = type(getattr(args, action.dest, action.default)) or str
            val_func = Validator.get_validator(t)()

        yield action, val_func


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
    for action, val_func in _iter_actions(parser, user_validators=user_validators):
        if action.dest not in default_section:
            continue
        data = default_section[action.dest]
        if val_func.validate_input(data):
            val = val_func.get_value_from_input(data)
            init_configs[action.dest] = val
    parser.set_defaults(**init_configs)


def get_user_inputs(
    parser: ArgumentParser,
    only_asks: list[str]=None,
    user_validators: dict[str, Validator]=None
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
    for action, val_func in _iter_actions(parser, user_validators=user_validators):

        if only_asks:
            if action is not None and action.dest not in only_asks:
                if action.required and action.default is not None:
                    raise MissingRequiredArgument(action.dest)
                setattr(args, action.dest, action.default)
                continue

        default_txt = val_func.get_value_repr(action.default)
        q = f" (Default: {default_txt}) " if default_txt else ""

        print(action.help + q)
        while True:
            data = input("? ")
            if data == "" and default_txt:
                data = default_txt
                break
            if val_func.validate_input(data):
                break

        value = val_func.get_value_from_input(data)
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
