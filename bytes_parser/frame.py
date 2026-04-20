from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal

from loguru import logger
from pandas import DataFrame

if TYPE_CHECKING:
    from bytes_parser.row import Row


class Frame:
    def __init__(self, frame_type: str, rows: list["Row"],
                 byte_order: Literal['big', 'little'] = 'big',
                 use_frame_type_as_header: bool = True,
                 show_bits: Literal['auto', 'always'] = 'auto') -> None:
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
        header: str = ('Name', self.frame_type)[self.use_frame_type_as_header]
        return DataFrame(table_rows, columns=[header, 'Value', 'Numeric', 'Hex',
                                              'IsOK', 'ErrCnt'])

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

    def __repr__(self) -> str:
        table_rows: list[tuple[str, int, int]] = []
        for row in self.rows:
            table_rows.append((row.label, row.size, row._offset))
        df = DataFrame(table_rows, columns=['Label', 'Size', 'Offset'])
        return df.to_string() + f'\nFull size: {self.full_size}'

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
            raw_data += frame_row._raw_val
        if len(raw_data) != self.full_size:
            logger.error('Failed to assemble frame')
            return None
        return self.parse(raw_data)
