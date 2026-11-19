
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from bytes_parser.bitfields import BitField, BitFlag
    from bytes_parser.row import Row


class Notification:
    def __init__(self, row: "Row",
                 bitfield: "list[BitFlag | BitField] | None" = None,
                 level: Literal['error', 'warning'] = 'error') -> None:
        self.row: Row = row
        self.bitfield: list[BitFlag | BitField] = bitfield or []
        self.level: Literal['error', 'warning'] = level
