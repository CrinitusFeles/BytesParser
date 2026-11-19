from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any, Literal, Protocol

from bytes_parser.bitfields import BitField, BitFlag
from bytes_parser.default_handlers import (
    bit_fields,
    check_warning,
    parse,
    represent,
    validate,
)

if TYPE_CHECKING:
    from bytes_parser import Frame


class Parser(Protocol):
    def __call__(self, field: "Row", *args: Any, **kwds: Any) -> int | float:
        ...

class Representer(Protocol):
    def __call__(self, field: "Row", *args: Any, **kwds: Any) -> str:
        ...

class Validator(Protocol):
    def __call__(self, field: "Row", *args: Any, **kwds: Any) -> bool:
        ...


class Row:
    def __init__(self, label: str, size: int, str_format: str = 'd',
                parser: Parser | None = None,
                validator: Validator | None = None,
                warn_checker: Validator | None = None,
                representer: Representer | None = None,
                args: Iterable | None = None,
                kwargs: dict | None = None,
                min_value: float = float('-inf'),
                max_value: float = float('inf'),
                warn_min_value: float = float('-inf'),
                warn_max_value: float = float('inf'),
                byte_order: Literal['big', 'little'] | None = None,
                bit_fields: list[BitField | BitFlag] | None = None,
                signed: bool = False,
                prefix: str | None = ''
        ) -> None:
        self.label: str = label
        self.size: int = size
        self.str_format: str = str_format
        self.parser: Parser = parser or parse
        self.validator: Validator = validator or validate
        self.warn_checker: Validator = warn_checker or check_warning
        self.representer: Representer = representer or represent
        self.args: Iterable = args or []
        self.kwargs: dict = kwargs or {}
        self.min_value: float = min_value
        self.max_value: float = max_value
        self.warn_min_value: float = warn_min_value
        self.warn_max_value: float = warn_max_value
        self.byte_order: Literal['big', 'little'] = byte_order or ''  # type: ignore
        self.bit_fields: list[BitField | BitFlag] = bit_fields or []
        self.signed: bool = signed
        self.prefix: str | None = prefix

        self._bit_fields_kwarg: dict[str, BitField | BitFlag] = {
            bf.label: bf for bf in self.bit_fields
        }
        self._errors: int = 0
        self._warnings: int = 0
        self._is_valid: bool = True
        self._is_warn: bool = False
        self.raw_val: bytes = b''
        self._parsed_val: int | float = 0
        self._offset: int = 0
        self._parent_frame: Frame | None = None
        self._repr_bit_list: Sequence[BitField | BitFlag] = []
        self._repr_data: str = ''

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
        self._warnings = 0
        for bit in self.bit_fields:
            bit.errors = 0

    def _parse(self, raw_data: bytes, all_bits: bool = False):
        if self.size > 0:
            self.raw_val = raw_data[self._offset: self._offset + self.size]
            if len(self.bit_fields) > 0:
                self._repr_bit_list = bit_fields(self, all_bits)
        else:
            self.raw_val = raw_data[self._offset:]
        if self.kwargs and self.args:
            self._parsed_val = self.parser(self, *self.args, **self.kwargs)
            self._is_valid = self.validator(self, *self.args, **self.kwargs)
            if self._is_valid:
                self._is_warn = self.warn_checker(self, *self.args, **self.kwargs)
            self._repr_data = self.representer(self, *self.args, **self.kwargs)
        elif self.args:
            self._parsed_val = self.parser(self, *self.args)
            self._is_valid = self.validator(self, *self.args)
            if self._is_valid:
                self._is_warn = self.warn_checker(self, *self.args)
            self._repr_data = self.representer(self, *self.args)
        elif self.kwargs:
            self._parsed_val = self.parser(self, **self.kwargs)
            self._is_valid = self.validator(self, **self.kwargs)
            if self._is_valid:
                self._is_warn = self.warn_checker(self, **self.kwargs)
            self._repr_data = self.representer(self, **self.kwargs)
        else:
            self._parsed_val = self.parser(self)
            self._is_valid = self.validator(self)
            if self._is_valid:
                self._is_warn = self.warn_checker(self)
            self._repr_data = self.representer(self)
        if not self._is_valid:
            self._errors += 1
        elif not all(bit.is_valid for bit in self.bit_fields) and not self._is_warn:
            self._is_warn = True
        if self._is_warn:
            self._warnings += 1

        return (self.label, self._repr_data, self._parsed_val,
                f'0x{self.raw_val.hex().upper()}',
                self._is_valid, self._errors)
