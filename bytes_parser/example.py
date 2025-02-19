
import random
from typing import Callable

from pandas import DataFrame
from bytes_parser import Frame, Row, BitField, BitFlag


def get_field():
    return -30


def my_parser(row: Row) -> int:
    if row.kwargs:
        callback: Callable | None = row.kwargs.get('callback', None)
        if callback:
            field = callback()
            if field < 0:
                return -30
    return 0


my_frame: Frame = Frame('my_frame_1', [
    Row('FIELD_1', 1, 'X', min_value=0, max_value=90),
    Row('FIELD_2', 2, 'b'),
    Row('FIELD_3', 2, 'b'),
    Row('FIELD_4', 2),
    Row('FIELD_5', 4, parser=my_parser, kwargs={'callback': get_field}),
    Row('FIELD_6', 4),
    Row("BITFIELD", 2, 'X',
        bit_fields=[*[BitFlag(i, f"BIT{i}", True) for i in range(10)],
                    BitField(10, "Counter", length=6, max_value=50)]),
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


raw_data: bytes = random.randbytes(18)
raw_data2: bytes = random.randbytes(12)
raw_data3: bytes = random.randbytes(18)


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
print(parse(raw_data3))
print(parse(b'gsdssf'))
print(my_frame)