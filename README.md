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
from pandas import DataFrame
from bytes_parser import Frame, Row


def bit_fields( val: bytes, struct: Row) -> list[tuple[str, str]]:
    def calc_bit(pos: int) -> int:
        return ((int.from_bytes(val) & (0x01 << pos)) >> pos)

    return [(label, f"{calc_bit(i):{struct.str_format}}")
            for i, label in enumerate(struct.nested_fields)]


my_frame: Frame = Frame('my_frame_1', [
    Row('FIELD_1', 1, 'X', min_value=0, max_value=90),
    Row('FIELD_2', 2, 'b'),
    Row('FIELD_3', 2, 'b'),
    Row('FIELD_4', 2),
    Row('FIELD_5', 4),
    Row('FIELD_6', 4),
    Row("BITFIELD", 2, 'd', parser=bit_fields,
        nested_fields=[*[f"BIT{i}" for i in range(16)]]),
    Row('CRC8', 1, 'X'),
], 'little')


my_frame2: Frame = Frame('my_frame_2', [
    Row('FIELD_1', 1, 'X'),
    Row('FIELD_2', 2, 'b'),
    Row('FIELD_3', 2, 'b'),
    Row('FIELD_4', 2),
    Row('FIELD_5', 4, '.2f'),
    Row('CRC8', 1, 'X'),
], 'little')


unknown_frame: Frame = Frame('UndefinedFrame', [
    Row('UndefinedData', 0, 'X')
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
    if len(data) == 18:
        return my_frame.parse(data)
    elif len(data) == 12:
        return my_frame2.parse(data)
    else:
        return unknown_frame.parse(data)

print('raw_data=', raw_data.hex(' ').upper())
print('raw_data2=', raw_data2.hex(' ').upper())
print(parse(raw_data))
print(parse(raw_data2))
print(parse(b'gsdssf'))
print(my_frame)
```

```
raw_data= DF A2 B3 A7 52 6B 99 C6 60 0B 93 A2 35 93 35 8D 04 23
raw_data2= 9A 99 18 4E D3 6C 0C 63 7C D9 2A 63


       Name               Value   IsOK  ErrCnt
0   FIELD_1                0xDF  False       1
1   FIELD_2  0b1011001110100010   True       0
2   FIELD_3   0b101001010100111   True       0
3   FIELD_4               39275   True       0
4   FIELD_5          2466996422   True       0
5   FIELD_6           898839970   True       0
6      BIT0                   0   True       0
7      BIT1                   0   True       0
8      BIT2                   1   True       0
9      BIT3                   0   True       0
10     BIT4                   0   True       0
11     BIT5                   0   True       0
12     BIT6                   0   True       0
13     BIT7                   0   True       0
14     BIT8                   1   True       0
15     BIT9                   0   True       0
16    BIT10                   1   True       0
17    BIT11                   1   True       0
18    BIT12                   0   True       0
19    BIT13                   0   True       0
20    BIT14                   0   True       0
21    BIT15                   1   True       0
22     CRC8                0x23   True       0


      Name               Value  IsOK  ErrCnt
0  FIELD_1                0x9A  True       0
1  FIELD_2     0b1100010011001  True       0
2  FIELD_3  0b1101001101001110  True       0
3  FIELD_4                3180  True       0
4  FIELD_5        718896227.00  True       0
5     CRC8                0x63  True       0


            Name           Value  IsOK  ErrCnt
0  UndefinedData  0x667373647367  True       0
```