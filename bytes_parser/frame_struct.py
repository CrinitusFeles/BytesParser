from dataclasses import dataclass, field
from typing import Callable, Literal


def dummy(val: bytes, str_format: str, *_, **kwargs) -> str:
    prefix = ''
    if 'X' in str_format:
        prefix = '0x'
    result: int = int.from_bytes(val, kwargs.get('byte_order', 'big'),
                                 signed=kwargs.get('signed', False))
    return prefix + f"{result:{str_format}}"


@dataclass
class Row:
    label: str
    size: int
    args: list = field(default_factory=lambda: ['d'])
    parser: Callable[[bytes, str, list, dict],
                     str | list[tuple[str, str]]] = dummy
    kwargs: dict = field(default_factory=lambda: {})

    def set_byte_order(self, byte_order: Literal['big', 'little']) -> None:
        self.kwargs.update({'byte_order': byte_order})


class Frame:
    def __init__(self, frame_type: str, rows: list[Row],
                 byte_order: Literal['big', 'little'] = 'big') -> None:
        self.frame_type: str = frame_type
        self._index = 0
        self.size_ptr = 0
        self.rows: list[Row] = rows
        self.full_size: int = sum(row.size for row in rows)
        [row.set_byte_order(byte_order) for row in self.rows]

    def __iter__(self):
        return self

    def __next__(self) -> Row:
        if self._index < len(self.rows):
            val: Row = self.rows[self._index]
            self.size_ptr += self.rows[self._index].size
            self._index += 1
            return val
        self.size_ptr = 0
        self._index = 0
        raise StopIteration