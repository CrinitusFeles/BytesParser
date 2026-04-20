from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from bytes_parser.bitfields import BitField, BitFlag
from bytes_parser.default_handlers import bit_fields, parse, represent, validate

if TYPE_CHECKING:
    from bytes_parser import Frame


@dataclass
class Row:
    label: str
    size: int
    str_format: str = 'd'
    parser: Callable[["Row"], int | float] = parse
    validator: Callable[["Row"], bool] = validate
    representer: Callable[["Row"], str] = represent
    args: Iterable = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    min_value: float = float('-inf')
    max_value: float = float('inf')
    byte_order: Literal['big', 'little'] = ''  # type: ignore
    bit_fields: list[BitField | BitFlag] = field(default_factory=list)
    signed: bool = False
    prefix: str | None = ''
    _errors: int = 0
    _is_valid: bool = True
    _raw_val: bytes = b''
    _parsed_val: int | float = 0
    _offset: int = 0
    _parent_frame: 'Frame | None' = None
    _repr_bit_list: Sequence[BitField | BitFlag] = field(default_factory=list)
    _repr_data: str = ''

    def _set_byte_order(self, byte_order: Literal['big', 'little']) -> None:
        self.byte_order = byte_order

    def _set_prefix(self) -> None:
        if 'X' in self.str_format:
            self.prefix = '0x' if self.prefix is not None else ''
            if self.size > 0:
                self.str_format = f'0{self.size * 2}X'
            else:
                self.str_format = 'X'
        elif 'b' in self.str_format:
            self.prefix = '0b' if self.prefix is not None else ''
            if self.size > 0:
                self.str_format = f'0{self.size * 8}b'
            else:
                self.str_format = 'b'

    def clear_errors(self) -> None:
        self._errors = 0
        for bit in self.bit_fields:
            bit.errors = 0

    def _parse(self, raw_data: bytes, all_bits: bool = False):
        if self.size > 0:
            self._raw_val = raw_data[self._offset: self._offset + self.size]
            if len(self.bit_fields) > 0:
                self._repr_bit_list = bit_fields(self, all_bits)
        else:
            self._raw_val = raw_data[self._offset:]
        if self.kwargs and self.args:
            self._parsed_val = self.parser(self, *self.args, **self.kwargs)
        elif self.args:
            self._parsed_val = self.parser(self, *self.args)
        elif self.kwargs:
            self._parsed_val = self.parser(self, **self.kwargs)
        else:
            self._parsed_val = self.parser(self)
        self._is_valid = self.validator(self)
        self._repr_data = self.representer(self)
        if not self._is_valid:
            self._errors += 1
        return (self.label, self._repr_data, self._parsed_val,
                f'0x{self._raw_val.hex().upper()}',
                self._is_valid, self._errors)
