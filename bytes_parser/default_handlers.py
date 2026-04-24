import struct
from collections.abc import Sequence
from typing import TYPE_CHECKING

from bytes_parser import BitFlag
from bytes_parser.bitfields import BitField

if TYPE_CHECKING:
    from bytes_parser.row import Row


def bit_fields(row: "Row",
               all_bits: bool = False) -> Sequence[BitField | BitFlag]:
    repr_list: list[BitField | BitFlag] = []
    for bit in row.bit_fields:
        val: int = int.from_bytes(row.raw_val, byteorder=row.byte_order)
        if isinstance(bit, BitFlag):
            bit._value = ((val & (0x01 << bit.pos)) >> bit.pos)
            bit._raw = bit._value.to_bytes()
            bit.is_valid = bit.ok_condition == bit._value
            if not bit.is_valid:
                bit.errors += 1
            if bit.is_valid and bit.show != 'always' and not all_bits:
                continue
            bit._repr = f'{bit._value}'
            repr_list.append(bit)
        elif isinstance(bit, BitField):
            mask: int = 0
            mask = [mask := mask | (1 << i) for i in range(bit.length)][-1]
            bit._value = (val >> bit.pos) & mask
            bit._raw = bit._value.to_bytes(bit.length // 8 + 1, row.byte_order)
            if bit.parser:
                bit._value = bit.parser(bit)
            if bit.validator:
                bit.is_valid = bit.validator(bit)
            else:
                bit.is_valid = bit.min_value < bit._value < bit.max_value
            if not bit.is_valid:
                bit.errors += 1
            if bit.representer:
                bit._repr = bit.representer(bit)
            else:
                if bit.str_format == 'd' and isinstance(bit._value, float):
                    bit.str_format = 'f'
                bit._repr = f'{bit._value:{bit.str_format}}'
            repr_list.append(bit)
        else:
            raise TypeError(f'Incorrect bitfield type: {type(bit)}')
    return repr_list


def parse(row: "Row") -> int | float:
    result: int | float = 0
    if 'f' in row.str_format and row.size == 4:
        bytes_order: str = [">", "<"][row.byte_order == "big"]
        result = struct.unpack(f'{bytes_order}f', row.raw_val)[0]
    else:
        result = int.from_bytes(row.raw_val, row.byte_order,
                                signed=row.signed)
    return result


def represent(row: "Row") -> str:
    if isinstance(row._parsed_val, float) and row.str_format == 'd':
        row.str_format = '.2f'
    result: str = f"{row.prefix}{row._parsed_val:{row.str_format}}"
    return result


def validate(row: "Row") -> bool:
    try:
        return row.min_value <= row._parsed_val <= row.max_value
    except Exception:  # noqa: BLE001
        return True
