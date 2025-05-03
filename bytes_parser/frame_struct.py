from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Literal, Sequence
from loguru import logger
from pandas import DataFrame


class BitFlag:
    def __init__(self, pos: int, label: str, ok_condition: bool,
                 show: Literal['always', 'error'] = 'error') -> None:
        self.pos: int = pos
        self.label: str = label
        self.ok_condition: bool = ok_condition
        self.is_valid: bool = True
        self.show: Literal['always', 'error'] = show
        self._repr_label: str = f'    $[{self.pos}]{self.label}'
        self._value: int = -1  # not for user!
        self._repr: str = '' # not for user!
        self.errors = 0

    def get_pos_range(self) -> list[int]:
        return [self.pos]


class BitField:
    def __init__(self, pos: int, label: str, length: int = 1,
                 max_value: float = float('inf'),
                 min_value: float = float('-inf'),
                 show: Literal['always', 'error'] = 'error',
                 parser: Callable | None = None) -> None:
        self.label: str = label
        self.pos: int = pos
        self.length: int = length
        self.show: Literal['always', 'error'] = show
        self.errors = 0
        if self.length < 1:
            raise ValueError('BitField length must be bigger then 0')
        self.max_value: float = max_value
        self.min_value: float = min_value
        self.parser: Callable | None = parser
        self.is_valid: bool = True
        self._repr_label: str = f'    $[{self.pos}:{self.pos + self.length}]'\
                                f'{self.label}'
        self._value: int = -1  # not for user!
        self._repr: str = '' # not for user!

    def get_pos_range(self) -> list[int]:
        return list(range(self.pos, self.pos + self.length))


def bit_fields(row: "Row") -> list[BitField | BitFlag]:
    repr_list: list[BitField | BitFlag] = []
    for bit in row.bit_fields:
        val: int = int.from_bytes(row.raw_val, byteorder=row.byte_order)
        if isinstance(bit, BitFlag):
            bit._value = ((val & (0x01 << bit.pos)) >> bit.pos)
            bit.is_valid = bit.ok_condition == bit._value
            if not bit.is_valid:
                bit.errors += 1
            if bit.is_valid and bit.show != 'always':
                continue
            bit._repr = f'{bit._value}'
            repr_list.append(bit)
        else:
            mask: int = 0
            mask = [mask := mask | (1 << i) for i in range(bit.length)][-1]
            bit._value = (val >> bit.pos) & mask
            bit.is_valid = bit.min_value < bit._value < bit.max_value
            if not bit.is_valid:
                bit.errors += 1
            if bit.parser:
                bit._repr = f'{bit.parser(bit._value)}'
            else:
                bit._repr = f'{bit._value}'
            repr_list.append(bit)
    return repr_list


def parse(row: "Row") -> Any:
    result: int = int.from_bytes(row.raw_val, row.byte_order,
                                 signed=row.signed)
    return result


def represent(row: "Row") -> str:
    if isinstance(row._parsed_val, float) and row.str_format == 'd':
        row.str_format = 'f'
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
    bit_fields: list[BitField | BitFlag] = field(default_factory=list)
    signed: bool = False
    errors: int = 0
    is_valid: bool = True
    raw_val: bytes = b''
    _parsed_val: Any = 0
    _offset: int = 0
    parent_frame: 'Frame | None' = None
    _repr_bit_list: list[BitField | BitFlag] = field(default_factory=list)
    _repr_data: str = ''

    def _set_byte_order(self, byte_order: Literal['big', 'little']) -> None:
        self.byte_order = byte_order

    def _set_prefix(self) -> None:
        if 'X' in self.str_format:
            self.prefix = '0x'
            self.str_format = f'0{self.size * 2}X'
        elif 'b' in self.str_format:
            self.prefix = '0b'
            self.str_format = f'0{self.size * 8}b'

    def clear_errors(self) -> None:
        self.errors = 0
        for bit in self.bit_fields:
            bit.errors = 0


class SubFrame:
    def __init__(self, rows: list[Row], prefix: str = '',
                 byte_order: Literal['big', 'little'] | None = None,
                 postfix: str = '') -> None:
        self.prefix: str = prefix
        self.postfix: str = postfix
        self.rows: list[Row] = deepcopy(rows)
        if byte_order is not None:
            for row in self.rows:
                if not row.byte_order:
                    row.byte_order = byte_order
        self._index: int = 0

    def __getitem__(self, key) -> Row:
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
                 use_frame_type_as_header: bool = True,
                 show_bits: Literal['auto', 'always'] = 'auto') -> None:
        self.frame_type: str = frame_type
        self.rows: list[Row] = rows
        self.rows_dict: dict[str, Row] = {row.label: row for row in self.rows}
        self.full_size: int = sum(row.size for row in self.rows)
        for row in self.rows:
            if not row.byte_order:
                row._set_byte_order(byte_order)
            row._set_prefix()
            row.parent_frame = self
            bits: list[int] = []
            for bit in row.bit_fields:
                bits.extend(bit.get_pos_range())
                if show_bits == 'always':
                    bit.show = 'always'
            if len(bits) != len(set(bits)):
                raise ValueError(f'Invalid BitField positions for {row.label}')
            if bits and  max(bits) > row.size * 8 - 1:
                raise ValueError(f'BitField overflow position '\
                                 f'value {max(bits)}')

        self.use_frame_type_as_header: bool = use_frame_type_as_header
        self.update_offsets()

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self.rows[key]._parsed_val
        else:
            return self.rows_dict[key]._parsed_val

    def update_offsets(self) -> None:
        offset = 0
        for prev_row, row in zip(self.rows[:-1], self.rows[1:]):
            offset += prev_row.size
            row._offset = offset

    def parse(self, raw_data: bytes | str) -> DataFrame:
        if isinstance(raw_data, str):
            raw_data = bytes.fromhex(raw_data)
        table_rows: list[tuple] = self.parse_tuple(raw_data)
        header: str = ('Name', self.frame_type)[self.use_frame_type_as_header]
        return DataFrame(table_rows, columns=[header, 'Value', 'IsOK',
                                              'ErrCnt'])

    def _parse_fields(self, raw_data: bytes) -> None:
        for row in self.rows:
            try:
                if row.size > 0:
                    row.raw_val = raw_data[row._offset: row._offset + row.size]
                    if len(row.bit_fields) > 0:
                        row._repr_bit_list = bit_fields(row)
                else:
                    row.raw_val = raw_data[row._offset:]
                row._parsed_val = row.parser(row)
            except Exception as err:
                raise ValueError(f'Incorrect proccessing of {row.label} '\
                                 f'label: {err}') from err

    def parse_tuple(self, raw_data: bytes) -> list[tuple[str, str, bool, int]]:
        table_rows: list[tuple[str, str, bool, int]] = []
        if self.full_size != len(raw_data):
            logger.warning(f'Frame size ({self.full_size}) and raw_data '\
                           f'({len(raw_data)}) are different!')
        self._parse_fields(raw_data)
        for row in self.rows:
            row.is_valid = row.validator(row)
            row._repr_data = row.representer(row)
            if not row.is_valid:
                row.errors += 1
            table_rows.append((row.label, row._repr_data, row.is_valid,
                               row.errors))
            if len(row._repr_bit_list):
                table_rows.extend([(bit._repr_label, bit._repr, bit.is_valid,
                                    bit.errors) for bit in row._repr_bit_list])
        return table_rows

    def parse_table(self, raw_rows: Sequence[bytes] | Sequence[str],
                    drop_columns: Iterable[str] = []) -> tuple[DataFrame,
                                                           DataFrame]:
        header: list[str] = [row.label for row in self.rows
                             if row.label not in drop_columns]
        table_rows: list[list[str]] = []
        valid_mask: list[list[bool]] = []
        bytes_rows: list[bytes] = [bytes.fromhex(line) if isinstance(line, str) else line
                                   for line in raw_rows]
        for raw_data in bytes_rows:
            if self.full_size != len(raw_data):
                logger.warning(f'Frame size ({self.full_size}) and raw_data '\
                            f'({len(raw_data)}) are different!')
            table_row: list[str] = []
            row_valid_list: list[bool] = []
            for row in self.rows:
                if row.label in drop_columns:
                    continue
                if row.size > 0:
                    row.raw_val = raw_data[row._offset: row._offset + row.size]
                else:
                    row.raw_val = raw_data[row._offset:]
                row._parsed_val = row.parser(row)
                repr_data: str = row.representer(row)
                row_valid_list.append(row.validator(row))
                table_row.append(repr_data)
            table_rows.append(table_row)
            valid_mask.append(row_valid_list)
        return (DataFrame(table_rows, columns=header),
                DataFrame(valid_mask, columns=header))

    def clear_errors(self) -> None:
        for row in self.rows:
            row.clear_errors()

    def __str__(self) -> str:
        table_rows: list[tuple[str, int, int]] = []
        for row in self.rows:
            table_rows.append((row.label, row.size, row._offset))
        df = DataFrame(table_rows, columns=['Label', 'Size', 'Offset'])
        return df.to_string() + f'\nFull size: {self.full_size}'
