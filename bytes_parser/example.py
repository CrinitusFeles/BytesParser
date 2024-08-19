
import random

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