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
parser.add_argument("--test")

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
