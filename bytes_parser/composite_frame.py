from typing import Literal

from loguru import logger
from pandas import DataFrame

from bytes_parser.frame import Frame
from bytes_parser.row import Row


class CompositeFrame:
    def __init__(self, frame_type: str, rules: dict[str, list[Row]],
                 byte_order: Literal['big', 'little'] = 'big') -> None:
        self.frame_type: str = frame_type
        self.rules: dict[str, list[Row]] = rules
        self.rows: list[Row] = []
        for frame_label, rows in rules.items():
            for row in rows:
                row.label = f'{frame_label} {row.label}'
                self.rows.append(row)
        self.frame = Frame(frame_type, self.rows, byte_order)

    def from_frames(self, *frames: Frame) -> None | DataFrame:
        raw_data: bytes = b''
        for frame_type, rows in self.rules.items():
            filtered: list = [f for f in frames if f.frame_type == frame_type]
            if not filtered:
                logger.error(f'Frame {frame_type} not found in incoming '\
                             f'frames: {[f.frame_type for f in frames]}')
                return None
            frame: Frame = filtered[0]
            for row in rows:
                label: str = row.label[len(frame.frame_type + " "):]
                frame_row: Row | None = frame.rows_dict.get(label, None)
                if not frame_row:
                    labels: list[str] = [frame.frame_type for frame in frames]
                    logger.error(f'Row {row.label} not found in {labels} '\
                                 f'for {frame_type}')
                    return None
                raw_data += frame_row.raw_val
        if len(raw_data) != self.frame.full_size:
            logger.error(f'Failed to assemble frame. Incorrect size '\
                         f'{len(raw_data)} != {self.frame.full_size}')
            return None
        return self.frame.parse(raw_data)
