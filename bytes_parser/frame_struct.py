from dataclasses import field, dataclass
from typing import Any, Callable, Iterable, Literal
from loguru import logger
from pandas import DataFrame


def calc_bit(data: bytes, pos: int) -> int:
    return ((int.from_bytes(data) & (0x01 << pos)) >> pos)


def bit_fields(row: "Row") -> list[str]:
    repr_list: list[str] = []
    for pos, label in row.bit_fields.items():
        bit: int = calc_bit(data=row.raw_val, pos=pos)
        if bit == 0 and row.show_bits == '1':
            continue
        elif bit == 1 and row.show_bits == '0':
            continue
        else:
            repr_list.append(f"{label}: {bit}")
    return repr_list


def parse(row: "Row") -> Any:
    result: int = int.from_bytes(row.raw_val, row.byte_order,
                                 signed=row.signed)
    return result


def represent(parsed_val: Any, row: "Row") -> str:
    result: str = f"{row.prefix}{parsed_val:{row.str_format}}"

    if len(row.bit_fields) > 0 and row.show_bits != 'none':
        bit_list: list[str] = bit_fields(row)
        result = '\n'.join([result, *bit_list])
    return result


def validate(parsed_val: int | float, row: "Row") -> bool:
    try:
        return row.min_value <= parsed_val <= row.max_value
    except Exception:
        return True


@dataclass
class Row:
    label: str
    size: int
    str_format: str = 'd'
    prefix: str = ''
    parser: Callable[["Row"], Any] = parse
    validator: Callable[[Any, "Row"], bool] = validate
    representer: Callable[[Any, "Row"], str] = represent
    args: Iterable = ()
    kwargs: dict = field(default_factory=dict)
    min_value: float = float('-inf')
    max_value: float = float('inf')
    byte_order: Literal['big', 'little'] = 'big'
    bit_fields: dict[int, str] = field(default_factory=dict)
    show_bits: Literal['all', '1', '0', 'none'] = '1'
    signed: bool = False
    errors: int = 0
    is_valid: bool = True
    raw_val: bytes = b''
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

    def _set_bits_repr(self, mode: Literal['all', '1', '0', 'none']):
        self.show_bits = mode


class Frame:
    def __init__(self, frame_type: str, rows: list[Row],
                 byte_order: Literal['big', 'little'] = 'big',
                 bits_repr_mode: Literal['all', '1', '0', 'none'] | None = None,
                 use_frame_type_as_header: bool = True) -> None:
        self.frame_type: str = frame_type
        self.rows: list[Row] = rows
        self.full_size: int = sum(row.size for row in rows)
        [row._set_byte_order(byte_order) for row in self.rows
         if not row.byte_order]
        if bits_repr_mode:
            [row._set_bits_repr(bits_repr_mode) for row in self.rows]
        [row._set_prefix() for row in self.rows]
        self.use_frame_type_as_header: bool = use_frame_type_as_header
        self.update_offsets()

    def update_offsets(self):
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
            if row.size > 0:
                row.raw_val = raw_data[row._offset: row._offset + row.size]
                data: Any = row.parser(row)
                row.is_valid = row.validator(data, row)
                if not row.is_valid:
                    row.errors += 1
                repr_data: str = row.representer(data, row)
            else:
                row.raw_val = raw_data[row._offset:]
                data = row.parser(row)
                repr_data = row.representer(data, row)
            table_rows.append((row.label, repr_data, row.is_valid, row.errors))
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
