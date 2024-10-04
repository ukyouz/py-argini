# py-argini
A python utility to store argparse arguments to ini file and vice versa

## Install

```bash
$ pip install git+https://github.com/ukyouz/py-argini
```

## Basic Usage

```python
import sys
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--test")  # basic input
parser.add_argument("--fields", nargs="*")  # multiline input

if len(sys.argv) == 1:
    import argini
    ini = Path(__file__).with_suffix(".ini")
    argini.import_from_ini(parser, ini)
    args = argini.get_user_inputs(parser, only_asks=['test'])
    argini.save_to_ini(parser, ini, args)
else:
    args = parser.parse_args()

# use args as usual.
print(args.test)
```

If you don't want to see the help text by default, turn off by setting `show_help` keyword argument to `False`:

```python
# ...
    args = argini.get_user_inputs(parser, show_help=False)
# ...
```

## Validator

### for specific argument

Validate user input by subclass `argini.Validator` class. For example,

```python
class ValidFile(argini.Validator):
    @staticmethod
    def validate_input(input: str) -> bool:
        return Path(input).exists()
```

then pass to `get_user_inputs` method,

```python
args = argini.get_uesr_inputs(parser, user_validators={
    "test": ValidFile,
}
```

### builtin validators

- ValidatePath
- ValidateFile
- ValidateFolder

usage is like:

```
args = argini.get_uesr_inputs(parser, user_validators={
    "test": argini.ValidateFile,
}
```

## With 3rd Party Package Installed

- pip install survey

```bash
args = argini.get_user_inputs_with_survey(parser)
```


## Development

You need to install these packages for testing:

```bash
> pip install pytest pytest-mock
```