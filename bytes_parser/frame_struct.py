from dataclasses import dataclass, field
from typing import Callable, Literal
from loguru import logger
from pandas import DataFrame


def simple_check(val: bytes, field: "Row") -> str:
    result: int = int.from_bytes(val, field.byte_order, signed=field.signed)
    if field.min_value <= result <= field.max_value:
        field.is_valid = True
    else:
        field.errors += 1
        field.is_valid = False
    return field.prefix + f"{result:{field.str_format}}"


@dataclass
class Row:
    label: str
    size: int
    str_format: str = 'd'
    prefix: str = ''
    parser: Callable[[bytes, "Row"], str | list[tuple[str, str]]] = simple_check
    args: tuple = ()
    kwargs: dict | None = None
    min_value: float = float('-inf')
    max_value: float = float('inf')
    byte_order: Literal['big', 'little'] = ''  # type: ignore
    nested_fields: list[str] = field(default_factory=lambda: [])
    signed: bool = False
    errors: int = 0
    is_valid: bool = True

    def _set_byte_order(self, byte_order: Literal['big', 'little']) -> None:
        self.byte_order = byte_order

    def _set_prefix(self):
        if 'X' in self.str_format:
            self.prefix = '0x'
        elif 'b' in self.str_format:
            self.prefix = '0b'


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

    def parse(self, raw_data: bytes) -> DataFrame:
        table_rows: list[tuple[str, str, bool, int]] = []
        _size_ptr = 0
        _index = 0
        if self.full_size != len(raw_data):
            logger.warning(f'Frame size ({self.full_size}) and raw_data '\
                           f'({len(raw_data)}) are different!')
        for row in self.rows:
            _size_ptr += self.rows[_index].size
            _index += 1
            data: str | list[tuple[str, str]] = ''
            if row.size > 0:
                _start: int = _size_ptr - row.size
                data = row.parser(raw_data[_start: _size_ptr], row)
            else:
                data = row.parser(raw_data[_size_ptr:], row)
            if isinstance(data, str):
                table_rows.append((row.label, data, row.is_valid, row.errors))
            else:
                table_rows.extend([(*val, row.is_valid, row.errors)
                                   for val in data])
        header: str = ('Name', self.frame_type)[self.use_frame_type_as_header]
        return DataFrame(table_rows, columns=[header, 'Value', 'IsOK',
                                              'ErrCnt'])

    def clear_errors(self) -> None:
        for row in self.rows:
            row.errors = 0

    def __str__(self) -> str:
        table_rows: list[tuple[str, int]] = []
        for row in self.rows:
            table_rows.append((row.label, row.size))
        df = DataFrame(table_rows, columns=['Label', 'Size'])
        return df.to_string() + f'\nFull size: {self.full_size}'
