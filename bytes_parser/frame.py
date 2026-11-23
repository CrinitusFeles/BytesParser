import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from loguru import logger
from pandas import DataFrame

from bytes_parser.notification import Notification

if TYPE_CHECKING:
    from bytes_parser.row import Row


@dataclass
class Location:
    module: str
    filepath: Path


def _initialization_location() -> Location | None:
    frame = inspect.currentframe()
    while frame:
        if frame.f_code.co_name == '<module>':
            return Location(frame.f_globals['__name__'],
                            Path(frame.f_globals['__file__']))
        frame = frame.f_back


NOTIFICATION_CALLBACK = Callable[[list[Notification], list[Notification]], None]
SUBSCRIBERS = dict[tuple[tuple[str, tuple[str, ...]] | str, ...],
                   NOTIFICATION_CALLBACK]


class Frame:
    def __init__(self, frame_type: str, rows: list["Row"],
                 byte_order: Literal['big', 'little'] = 'big',
                 use_frame_type_as_header: bool = True,
                 show_bits: Literal['auto', 'always'] = 'auto') -> None:
        self._location: Location
        self.frame_type: str = frame_type
        self.rows: list[Row] = rows
        self.rows_dict: dict[str, Row] = {row.label: row for row in self.rows}
        self.full_size: int = sum(row.size for row in self.rows)
        self._byte_order = byte_order
        for row in self.rows:
            if not row.byte_order:
                row._set_byte_order(byte_order)
            row._set_prefix()
            row._parent_frame = self
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
        self.check_labels()
        self._subscribers: SUBSCRIBERS = {}
        self._parsed_count: int = 0

    def __new__(cls, *_args, **_kwargs):
        obj = super().__new__(cls)
        obj._location = _initialization_location()  # type: ignore
        return obj

    def get_location(self) -> Location:
        return self._location

    def inject_kwargs(self, kwargs: dict):
        for row in self.rows:
            row.kwargs.update(kwargs)
        return self

    def check_labels(self):
        labels: list[str] = [row.label for row in self.rows]
        dups: list[str] = list(set(filter(lambda x: labels.count(x) > 1, labels)))
        if dups:
            logger.warning(f'Frame {self.frame_type} has duplicated rows: {dups}')

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
        self._call_subscribers()
        header: str = ('Name', self.frame_type)[self.use_frame_type_as_header]
        try:
            df = DataFrame(table_rows, columns=[header, 'Value', 'Numeric', 'Hex',
                                                'IsOK', 'ErrCnt'])
            return df
        except Exception as err:
            logger.error(f'Failed to create dataframe {header}\n{table_rows}\n{err}')
            raise

    def parse_tuple(self, raw_data: bytes) -> list[tuple]:
        table_rows: list[tuple] = []
        if self.full_size != len(raw_data):
            logger.warning(f'Frame {self.frame_type} size ({self.full_size}) '\
                           f'and raw_data ({len(raw_data)}) are different!')
        for row in self.rows:
            try:
                table_rows.append(row._parse(raw_data))
                if len(row._repr_bit_list):
                    table_rows.extend([bit.get_tuple()
                                       for bit in row._repr_bit_list])
            except Exception as err:
                raise ValueError(f'Incorrect proccessing of {row.label} '\
                                 f'label: {err}') from err
        self._parsed_count += 1
        return table_rows

    def _get_table_header(self) -> list[str]:
        header: list[str] = []
        for row in self.rows:
            header.append(row.label)
            if len(row.bit_fields):
                for bit in row.bit_fields:
                    header.append(f'    {row.label}: {bit.label}')
        return header

    def parse_table(self, raw_rows: Sequence[bytes] | Sequence[str]) -> tuple[DataFrame, DataFrame]:
        header: list[str] = self._get_table_header()
        table_rows: list[list[int | float]] = []
        valid_mask: list[list[bool]] = []
        frames: list[bytes] = [bytes.fromhex(line)
                               if isinstance(line, str) else line
                               for line in raw_rows]
        for raw_data in frames:
            if self.full_size != len(raw_data):
                logger.warning(f'Frame {self.frame_type} size ({self.full_size}) '\
                               f'and raw_data ({len(raw_data)}) are different!')
            table_row: list[int | float] = []
            row_valid_list: list[bool] = []
            for row in self.rows:
                data: tuple = row._parse(raw_data, all_bits=True)
                row_valid_list.append(data[4])
                table_row.append(data[2])
                table_row.extend([bit._value for bit in row._repr_bit_list])
                row_valid_list.extend([bit.is_valid for bit in row._repr_bit_list])
            table_rows.append(table_row)
            valid_mask.append(row_valid_list)
        return (DataFrame(table_rows, columns=header),
                DataFrame(valid_mask, columns=header))

    def clear_errors(self) -> None:
        for row in self.rows:
            row.clear_errors()

    def _orig_dataframe(self, show_bits: bool) -> DataFrame:
        table_rows: list[tuple[int | str, str, int | str, int | str]] = []
        for i, row in enumerate(self.rows, start=1):
            table_rows.append((i, row.label, row.size, row._offset))
            if show_bits:
                for bit in row.bit_fields:
                    table_rows.append(('', bit._repr_label, '', ''))
        return DataFrame(table_rows, columns=['№', 'Label', 'Size', 'Offset'])

    def __repr__(self) -> str:
        df: DataFrame = self._orig_dataframe(show_bits=False)
        return df.to_string(index=False) + f'\nFull size: {self.full_size}'

    def to_markdown(self, show_bits: bool) -> str:
        df: DataFrame = self._orig_dataframe(show_bits)
        return df.to_markdown(index=False) + f'\nFull size: {self.full_size}'

    def to_string(self, show_bits: bool) -> str:
        df: DataFrame = self._orig_dataframe(show_bits)
        return df.to_string(index=True) + f'\nFull size: {self.full_size}'

    def from_frames(self, *frames: "Frame"):
        raw_data: bytes = b''
        for row in self.rows:
            frame_row: Row | None = None
            for frame in frames:
                frame_row = frame.rows_dict.get(row.label, None)
                if frame_row:
                    break
            if not frame_row:
                labels: list[str] = [frame.frame_type for frame in frames]
                logger.error(f'Row {row.label} not found in {labels}')
                return None
            raw_data += frame_row.raw_val
        if len(raw_data) != self.full_size:
            logger.error('Failed to assemble frame')
            return None
        return self.parse(raw_data)

    def subscribe(self, fields: list[str | tuple[str, list[str]]],
                  callback: NOTIFICATION_CALLBACK) -> None:
        hash_fields: tuple = tuple(field if isinstance(field, str)
                                   else (field[0], tuple(field[1]))
                                   for field in fields)
        self._subscribers[hash_fields] = callback

    def unsubscribe(self, fields: list[str | tuple[str, list[str]]]) -> None:
        hash_fields: tuple = tuple(field if isinstance(field, str)
                                   else (field[0], tuple(field[1]))
                                   for field in fields)
        self._subscribers.pop(hash_fields)

    def get_failed_params(self, fields: list[tuple[str, tuple[str, ...]] | str]):
        err_notifications: list[Notification] = []
        warn_notifications: list[Notification] = []
        for field_label in fields:
            level = 'error'
            if isinstance(field_label, str):
                row = self.rows_dict[field_label]
                if row._is_valid:
                    continue
                level = ('error', 'warning')[row._is_warn]
                notif = Notification(self.rows_dict[field_label], level=level)

            elif isinstance(field_label, tuple) and len(field_label) > 1:
                bits: list = []
                row = self.rows_dict[field_label[0]]
                for bf_label in field_label[1]:
                    bit = row._bit_fields_kwarg[bf_label]
                    if not bit.is_valid:
                        bits.append(bit)
                if not bits:
                    continue
                # if len(bits):
                #     level = 'error'
                # else:
                #     level: str = ('error', 'warning')[row._is_warn]
                notif = Notification(row, bits, level)
            else:
                logger.error(f'Incorrect subscriber format {field_label} for '\
                                f'frame {self.frame_type}')
                continue
            if level == 'error':
                err_notifications.append(notif)
            else:
                warn_notifications.append(notif)
        return err_notifications, warn_notifications

    def _call_subscribers(self) -> None:
        for subscriber, callback in self._subscribers.items():
            callback(*self.get_failed_params(list(subscriber)))
