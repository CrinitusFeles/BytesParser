from copy import deepcopy
from dataclasses import field, dataclass
from typing import Any, Callable, Iterable, Literal
from loguru import logger
from pandas import DataFrame


class Bit:
    label: str
    ok_condition: bool
    def __init__(self, label: str, ok_condition: bool):
        self.label = label
        self.ok_condition = ok_condition
        self._value: int = -1  # not for user!
        self._repr: str = '' # not for user!


def bit_fields(row: "Row") -> list[Bit]:
    repr_list: list[Bit] = []
    for pos, bit in row.bit_fields.items():
        val: int = int.from_bytes(row.raw_val, byteorder=row.byte_order)
        bit._value = ((val & (0x01 << pos)) >> pos)
        if bit._value != int(bit.ok_condition):
            bit.label = f'    $[{pos}]{bit.label}'
            bit._repr = f'{int(bit._value)}'
            repr_list.append(bit)
    return repr_list


def parse(row: "Row") -> Any:
    result: int = int.from_bytes(row.raw_val, row.byte_order,
                                 signed=row.signed)
    return result


def represent(row: "Row") -> str:
    result: str = f"{row.prefix}{row._parsed_val:{row.str_format}}"
    return result


def validate(row: "Row") -> bool:
    try:
        return row.min_value <= row._parsed_val <= row.max_value
    except Exception:
        return True


@dataclass
class Row:
    label: str
    size: int
    str_format: str = 'd'
    prefix: str = ''
    parser: Callable[["Row"], Any] = parse
    validator: Callable[["Row"], bool] = validate
    representer: Callable[["Row"], str] = represent
    args: Iterable = ()
    kwargs: dict = field(default_factory=dict)
    min_value: float = float('-inf')
    max_value: float = float('inf')
    byte_order: Literal['big', 'little'] = '' # type: ignore
    bit_fields: dict[int, Bit] = field(default_factory=dict)
    signed: bool = False
    errors: int = 0
    is_valid: bool = True
    raw_val: bytes = b''
    _parsed_val: Any = 0
    _offset: int = 0

    def _set_byte_order(self, byte_order: Literal['big', 'little']) -> None:
        self.byte_order = byte_order

    def _set_prefix(self) -> None:
        if 'X' in self.str_format:
            self.prefix = '0x'
            self.str_format = f'0{self.size * 2}X'
        elif 'b' in self.str_format:
            self.prefix = '0b'
            self.str_format = f'0{self.size * 8}b'


class SubFrame:
    def __init__(self, rows: list[Row], prefix: str = '',
                 postfix: str = '') -> None:
        self.prefix: str = prefix
        self.postfix: str = postfix
        self.rows: list[Row] = deepcopy(rows)
        self._index: int = 0

    def __getitem__(self, key):
        return self.rows[key]

    def __iter__(self):
        return self

    def __next__(self) -> Row:
        if self._index < len(self.rows):
            var: Row = self.rows[self._index]
            var.label = f'{self.prefix}{var.label}{self.postfix}'
            self._index += 1
            return var
        raise StopIteration

class Frame:
    def __init__(self, frame_type: str, rows: list[Row],
                 byte_order: Literal['big', 'little'] = 'big',
                 use_frame_type_as_header: bool = True) -> None:
        self.frame_type: str = frame_type
        self.rows: list[Row] = rows
        self.full_size: int = sum(row.size for row in rows)
        [row._set_byte_order(byte_order) for row in self.rows
         if not row.byte_order]
        [row._set_prefix() for row in self.rows]
        self.use_frame_type_as_header: bool = use_frame_type_as_header
        self.update_offsets()

    def update_offsets(self) -> None:
        offset = 0
        for prev_row, row in zip(self.rows[:-1], self.rows[1:]):
            offset += prev_row.size
            row._offset = offset

    def parse(self, raw_data: bytes) -> DataFrame:
        table_rows: list[tuple] = self.parse_tuple(raw_data)
        header: str = ('Name', self.frame_type)[self.use_frame_type_as_header]
        return DataFrame(table_rows, columns=[header, 'Value', 'IsOK',
                                              'ErrCnt'])

    def parse_tuple(self, raw_data: bytes) -> list[tuple[str, str, bool, int]]:
        table_rows: list[tuple[str, str, bool, int]] = []
        if self.full_size != len(raw_data):
            logger.warning(f'Frame size ({self.full_size}) and raw_data '\
                           f'({len(raw_data)}) are different!')
        for row in self.rows:
            bit_list: list[Bit] = []
            if row.size > 0:
                row.raw_val = raw_data[row._offset: row._offset + row.size]
                row._parsed_val = row.parser(row)
                row.is_valid = row.validator(row)
                if not row.is_valid:
                    row.errors += 1
                repr_data: str = row.representer(row)
                if len(row.bit_fields) > 0:
                    val = deepcopy(row)
                    bit_list = bit_fields(val)
            else:
                row.raw_val = raw_data[row._offset:]
                row._parsed_val = row.parser(row)
                repr_data = row.representer(row)
            table_rows.append((row.label, repr_data, row.is_valid, row.errors))
            if len(bit_list):
                table_rows.extend([(bit.label, bit._repr, row.is_valid,
                                    row.errors)
                                  for bit in bit_list])

        return table_rows

    def clear_errors(self) -> None:
        for row in self.rows:
            row.errors = 0

    def __str__(self) -> str:
        table_rows: list[tuple[str, int, int]] = []
        for row in self.rows:
            table_rows.append((row.label, row.size, row._offset))
        df = DataFrame(table_rows, columns=['Label', 'Size', 'Offset'])
        return df.to_string() + f'\nFull size: {self.full_size}'
