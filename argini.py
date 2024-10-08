import ast
import configparser
import os
import sys
import textwrap
from abc import ABC
from argparse import _HelpAction
from argparse import _SubParsersAction
from argparse import ArgumentParser
from argparse import Namespace
from io import StringIO
from pathlib import Path
from typing import Any
from typing import Type


class MissingRequiredArgument(Exception):
    """missing required argument"""


class NotSupportError(Exception):
    """error usage for this package"""


def format_card(text: str) -> str:
    lines = text.splitlines()
    terminal_width = os.get_terminal_size()[0] - 4
    max_len = min(max(len(x) for x in lines), terminal_width)
    card = StringIO()
    card.write("╭{}╮\n".format("─" * (max_len + 2)))
    for l in lines:
        wraps = textwrap.wrap(l, width=terminal_width)
        for wrapped_line in wraps:
            card.write(("│ {:<%d} │\n" % max_len).format(wrapped_line))
    card.write("╰{}╯".format("─" * (max_len + 2)))
    return card.getvalue()

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
        """default value repr"""
        if isinstance(val, str):
            return val
        else:
            return repr(val)

    @staticmethod
    def validate_input(input: str | list) -> bool:
        return input != ""

    @staticmethod
    def get_value_from_input(input: str | list) -> str | list:
        """convert the `input` to the actual python object"""
        return input

    @staticmethod
    def match_action(action) -> bool:
        """check whether this validator is a matched one for `action`"""
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
        return (
            isinstance(action.default, bool)
            or action.__class__.__name__ == "_StoreTrueAction"
            or action.__class__.__name__ == "_StoreConstAction"
        )


DEFAULT_VALIDATOR = {
    list: IterableType,
    tuple: IterableType,
    bool: BoolType,
    str: StrType,
}


class ValidatePath(StrType):
    @staticmethod
    def validate_input(input: str | list) -> bool:
        try:
            input = ValidatePath.get_value_from_input(input)
        except ValueError:
            return False
        ok = Path(input).exists()
        if not ok:
            print("Path not exist: %r" % input)
        return ok

    @staticmethod
    def get_value_from_input(input: str | list) -> str:
        if not isinstance(input, str):
            raise ValueError("Invalid input: %r" % input)
        input = input.strip()
        if input[0] == input[-1] == '"':
            input = input[1:-1]
        return input


class ValidateFile(StrType):
    @staticmethod
    def validate_input(input: str | list) -> bool:
        try:
            input = ValidatePath.get_value_from_input(input)
        except ValueError:
            return False
        ok = Path(input).is_file()
        if not ok:
            print("Path is not a file: %r" % input)
        return ok


class ValidateFolder(StrType):
    @staticmethod
    def validate_input(input: str | list) -> bool:
        try:
            input = ValidatePath.get_value_from_input(input)
        except ValueError:
            return False
        ok = Path(input).is_dir()
        if not ok:
            print("Path is not a folder: %r" % input)
        return ok


def _iter_actions(
    parser: ArgumentParser,
    args: Namespace = None,
    user_validators: dict[str, Type[Validator]] = None,
):
    args = args or Namespace()
    for action in parser._actions:
        dest = "__subcommand__" if isinstance(action, _SubParsersAction) else action.dest
        if isinstance(action, _HelpAction):
            continue
        if action.dest in user_validators:
            validator = user_validators[dest]
        elif isinstance(action, _SubParsersAction):
            validator = StrType
        elif action.default is None and action.const is not None:
            raise NotImplementedError(action)
        elif BoolType.match_action(action):
            validator = BoolType
        else:
            validator = StrType
            possible_val = getattr(args, dest, action.default)
            if possible_val is None:
                for v in DEFAULT_VALIDATOR.values():
                    if v.match_action(action):
                        validator = v
                        break
            else:
                validator = DEFAULT_VALIDATOR.get(type(possible_val), DummyType)

        yield action, validator


def _import_from_ini_section(
    config,
    section: str,
    parser: ArgumentParser,
    user_validators: dict[str, Type[Validator]]
):
    init_configs = {}
    for action, validator in _iter_actions(parser, user_validators=user_validators):
        if isinstance(action, _SubParsersAction):
            val = config[section].get("__subcommand__", None)
            action.default = val
            for subcmd in action.choices.keys():
                if not config.has_section(subcmd):
                    continue
                _import_from_ini_section(config, subcmd, action.choices[subcmd], user_validators)
        else:
            if action.dest not in config[section]:
                continue
            data = config[section][action.dest]
            val = validator.get_value_from_input(data)
            if validator.validate_input(val):
                init_configs[action.dest] = val
    parser.set_defaults(**init_configs)


def _make_args(action, value: str | list) -> list[str]:
    args = []

    opt_str = action.option_strings[0] if action.option_strings else ""
    if BoolType.match_action(action):
        if value:
            args.append(opt_str)
    else:
        if isinstance(value, list):
            if action.nargs in {"*", "+"}:
                if opt_str:
                    args.append(opt_str)
                for x in value:
                    args.append(x)
            else:
                for x in value:
                    if opt_str:
                        args.append(opt_str)
                    args.append(x)
        else:
            if opt_str:
                args.append(opt_str)
            args.append(value)

    return args


def import_from_ini(
    parser: ArgumentParser,
    ini_file: str | Path,
    user_validators: dict[str, Type[Validator]] = None
):
    """
    import config settings from ini, and replace the default value in ArgumentParser
    """
    user_validators = user_validators or {}

    config = configparser.ConfigParser()
    config.read(ini_file)
    _import_from_ini_section(config, config.default_section, parser, user_validators)


def print_help(parser: ArgumentParser):
    help_str = StringIO()
    parser.print_help(file=help_str)
    print(format_card(help_str.getvalue()))


def get_user_inputs(
    parser: ArgumentParser,
    only_asks: list[str] = None,
    user_validators: dict[str, Type[Validator]] = None,
    show_help = True,
    _args: list[str] = None
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

    args = _args or []
    ns = Namespace()
    _show_help = show_help

    for action, validator in _iter_actions(parser, user_validators=user_validators):
        dest = "__subcommand__" if isinstance(action, _SubParsersAction) else action.dest
        if only_asks:
            if action is not None and dest not in only_asks:
                if action.required and action.default is not None:
                    raise MissingRequiredArgument(dest)
                args.extend(_make_args(action, action.default))
                continue

        if _show_help:
            # only print help at the first question
            print_help(parser)
            _show_help = False

        default_txt = validator.get_value_repr(action.default)
        q = f" (Default: {default_txt}) " if default_txt else ""
        opts = "{%s}" % ",".join(action.choices) + " " if action.choices else ""

        if title := (action.help or "") + q:
            print(title)
        while True:
            # Get User Input
            if IterableType.match_action(action):
                data = input_multilines(dest + "? ")
            else:
                data = input(dest + "? " + opts)
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
        if isinstance(action, _SubParsersAction):
            args.extend(_make_args(action, value))
            setattr(ns, dest, value)
            get_user_inputs(
                action.choices[value],
                only_asks,
                user_validators,
                show_help,
                _args=args,
            )
        else:
            if data != default_txt or action.required:
                args.extend(_make_args(action, value))

    out_ns, _ = parser.parse_known_args(args, ns)

    return out_ns


def get_user_inputs_with_survey(
    parser: ArgumentParser,
    only_asks: list[str] = None,
    user_validators: dict[str, Type[Validator]] = None,
    show_help=True,
    _args: list[str] = None
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

    args = _args or []
    ns = Namespace()
    _show_help = show_help

    for action, validator in _iter_actions(parser, user_validators=user_validators):
        dest = "__subcommand__" if isinstance(action, _SubParsersAction) else action.dest
        if only_asks:
            if action is not None and dest not in only_asks:
                if action.required and action.default is not None:
                    raise MissingRequiredArgument(dest)
                args.extend(_make_args(action, action.default))
                continue

        if _show_help:
            # only print help at the first question
            print_help(parser)
            _show_help = False

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
                opts = list(action.choices)
                idx = survey.routines.select(
                    dest + "? ", options=opts, index=default
                )
                if isinstance(action.choices, dict):
                    value = opts[idx]
                else:
                    value = action.choices[idx]
                break

            if IterableType.match_action(action):
                data = survey.routines.input(
                    dest
                    + "? "
                    + "Item per line. Press Enter 3 times to continue.",
                    multi=True,
                )
                data = data.splitlines()
            elif BoolType.match_action(action):
                data = survey.routines.inquire(
                    dest + "? ",
                    default=BoolType.get_value_from_input(default_txt)
                )
            else:
                data = survey.routines.input(dest + "? ")
            if data == "" and default_txt:
                data = default_txt

            # Validation
            if validator.validate_input(data):
                if action.nargs == "+" and not data:
                    print("At least one is required!", file=sys.stderr)
                    continue
                value = data
                break

        if isinstance(action, _SubParsersAction):
            args.extend(_make_args(action, value))
            setattr(ns, dest, value)
            get_user_inputs_with_survey(
                action.choices[value],
                only_asks,
                user_validators,
                show_help,
                _args=args,
            )
        else:
            if value != action.default or action.required:
                args.extend(_make_args(action, value))

    out_ns, _ = parser.parse_known_args(args, ns)

    return out_ns


def _store_to_ini_section(
    args: Namespace,
    config: configparser.ConfigParser,
    section: str,
    parser: ArgumentParser,
    user_validators: dict[str, Type[Validator]]
):
    for action, val_func in _iter_actions(parser, args, user_validators):
        if isinstance(action, _SubParsersAction):
            dest = "__subcommand__"
            val = getattr(args, dest)
            if not config.has_section(val):
                config.add_section(val)
            config[section][dest] = val
            _store_to_ini_section(args, config, val, action.choices[val], user_validators)
        elif BoolType.match_action(action):
            dest = action.dest
            val = getattr(args, dest)
            if action.const is not None:
                config[section][dest] = str(val == action.const)
            elif isinstance(val, bool):
                config[section][dest] = str(val)
            else:
                raise NotImplementedError(action)
        else:
            dest = action.dest
            val = getattr(args, dest)
            if val is not None:
                config[section][dest] = val_func.get_value_repr(val)


def save_to_ini(
    parser: ArgumentParser,
    ini_file: str | Path,
    args: Namespace,
    user_validators: dict[str, Type[Validator]] = None,
):
    user_validators = user_validators or {}
    config = configparser.ConfigParser()
    config.read(ini_file)
    _store_to_ini_section(args, config, config.default_section, parser, user_validators)

    with open(ini_file, "w") as config_file:
        config.write(config_file)


if __name__ == "__main__":
    # manually simple cli test
    import sys

    parser = ArgumentParser()
    sub = parser.add_subparsers()

    sub1 = sub.add_parser("test", help="123 123 123")
    sub1.add_argument("--test", required=True)  # line
    sub1.add_argument("--fruit", choices=["apple", "banana"])  # choice

    sub2 = sub.add_parser("add", help="123 123 123")
    sub2.add_argument("--yyy", required=True)  # line
    sub2.add_argument("--xxx", choices=["apple", "banana"])  # choice

    # parser.add_argument("--ok", action="store_true")  # flag
    # parser.add_argument("--options", nargs="*")  # multiline text
    # parser.add_argument("--flags", action="append")  # multiline text
    if len(sys.argv) == 1:
        import_from_ini(parser, "test.ini")
        args = get_user_inputs_with_survey(parser)
        save_to_ini(parser, "test.ini", args)
    else:
        args = parser.parse_args()

    print(args)
