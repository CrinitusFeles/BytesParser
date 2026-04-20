


from copy import deepcopy
from typing import Literal

from bytes_parser.row import Row


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
