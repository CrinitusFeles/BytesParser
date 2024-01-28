# BytesParser
Python flexible frame parser

## Installation

```
poetry add git+https://github.com/CrinitusFeles/BytesParser.git
```

or

```
pip install git+https://github.com/CrinitusFeles/BytesParser.git
```

## Using

First of all, you need to create your frames. Every frame is created with `Frame` class, which has next attributes:

* `frame_type`: __str__ - you can using it at lower level parse process of frames distinguish
* `rows`: __list[Row]__ - it is a list of all Frame's fields
* `byte_order`: __Literal['big', 'little']__ - global settings for all fields in frame. By default it set to `'big'`. If all your fields has little endian format you can set this argument to `'little'`.


Every field in your frame is created with `Row` class, which has next attributes:

* `label`: __str__ - is a field label in result table
* `size`: __int__ - field size in bytes. You have to check
* `args`: __list__ - arguments for field formatter callback. By default it set to `['d']`. It means that by default all fields will be printed as decimal numbers.
* `parser`: __Callable[[bytes, str, list, dict], str | list[tuple[str, str]]]__ - field formatter callback. Your callbacks have to take next arguments:
    1) raw_field_data: bytes
    2) field_format: str
    3) *args: Iterable
    4) **kwargs: dict

    and return string or list of strings, when you need to parse bit field.
    By default all fields parsed with `dummy` function which just converts bytes to readable format or in format what you pass as argument in `args`.
* `kwargs`: __dict__ - usually using for changing field bytes order. E.x.: `{'byte_order': 'little'}`


```python

from bytes_parser.frame import Frame, Row


def bit_fields( val: bytes, str_format: str, labels: list[str],
               *args, **kwargs) -> list[tuple[str, str]]:
    return [(label, f"{((int.from_bytes(val) & (0x01 << i)) >> i):{str_format}}")
            for i, label in enumerate(labels)]


my_frame: Frame = Frame('my_frame_1', [
    Row('FIELD_1', 1, ['X']),
    Row('FIELD_2', 2, ['b']),
    Row('FIELD_3', 2, ['b']),
    Row('FIELD_4', 2),
    Row('FIELD_5', 4),
    Row('FIELD_6', 4),
    Row("BITFIELD", 2, ['d', [*[f"BIT{i}" for i in range(16)]]], bit_fields),
    Row('CRC8', 1, ['X']),
], 'little')


my_frame2: Frame = Frame('my_frame_2', [
    Row('FIELD_1', 1, ['X']),
    Row('FIELD_2', 2, ['b']),
    Row('FIELD_3', 2, ['b']),
    Row('FIELD_4', 2),
    Row('FIELD_5', 4),
    Row('CRC8', 1, ['X']),
], 'little')


unknown_frame: Frame = Frame('UndefinedFrame', [
    Row('UndefinedData', 0, ['X'])
], 'little')

```

After creation frames we can try to parse random bytes:

```python

import random

from pandas import DataFrame
from bytes_parser.formatter import frame_field_formatter

raw_data: bytes = random.randbytes(18)
raw_data2: bytes = random.randbytes(12)


def parse(data: bytes) -> DataFrame:
    if len(data) == 12:
        return frame_field_formatter(my_frame, data)
    elif len(data) == 18:
        return frame_field_formatter(my_frame2, data)
    else:
        return frame_field_formatter(unknown_frame, data)


print(parse(raw_data))
print(parse(raw_data2))
print(parse(b'gsdssf'))
```

```
raw_data= 58 35 4D 51 C9 23 C1 20 78 38 88 DF E0 65 8C BE 7D 26
raw_data2= B3 5C 05 C2 7A BE AF DE D1 2E B8 B3


       Name             Value
0   FIELD_1              0x58
1   FIELD_2   100110100110101
2   FIELD_3  1100100101010001
3   FIELD_4             49443
4   FIELD_5        2285402144
5   FIELD_6        2355486943
6      BIT0                 1
7      BIT1                 0
8      BIT2                 1
9      BIT3                 1
10     BIT4                 1
11     BIT5                 1
12     BIT6                 1
13     BIT7                 0
14     BIT8                 0
15     BIT9                 1
16    BIT10                 1
17    BIT11                 1
18    BIT12                 1
19    BIT13                 1
20    BIT14                 0
21    BIT15                 1
22     CRC8              0x26


      Name            Value
0  FIELD_1             0xB3
1  FIELD_2      10101011100
2  FIELD_3  111101011000010
3  FIELD_4            44990
4  FIELD_5       3090076126
5     CRC8             0xB3


            Name           Value
0  UndefinedData  0x667373647367
```