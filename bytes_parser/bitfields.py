

from collections.abc import Callable
from typing import Literal


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
        self._raw: bytes = b''
        self._repr: str = '' # not for user!
        self.errors = 0

    def get_pos_range(self) -> list[int]:
        return [self.pos]

    def get_tuple(self) -> tuple[str, str, int, str, bool, int]:
        return (self._repr_label, self._repr, self._value,
                f'0x{self._raw.hex().upper()}',
                self.is_valid, self.errors)


class BitField:
    def __init__(self, pos: int, label: str, length: int = 1,
                 max_value: float = float('inf'),
                 min_value: float = float('-inf'),
                 show: Literal['always', 'error'] = 'error',
                 representer: Callable[[int | float], str] | None = None) -> None:
        self.label: str = label
        self.pos: int = pos
        self.length: int = length
        self.show: Literal['always', 'error'] = show
        self.errors = 0
        if self.length < 1:
            raise ValueError('BitField length must be bigger then 0')
        self.max_value: float = max_value
        self.min_value: float = min_value
        self.representer: Callable[[int | float], str] | None = representer
        self.is_valid: bool = True
        self._repr_label: str = f'    $[{self.pos}:{self.pos + self.length}]'\
                                f'{self.label}'
        self._value: int = -1  # not for user!
        self._raw: bytes = b''
        self._repr: str = '' # not for user!

    def get_pos_range(self) -> list[int]:
        return list(range(self.pos, self.pos + self.length))

    def get_tuple(self) -> tuple[str, str, int, str, bool, int]:
        return (self._repr_label, self._repr, self._value,
                f'0x{self._raw.hex().upper()}',
                self.is_valid, self.errors)
