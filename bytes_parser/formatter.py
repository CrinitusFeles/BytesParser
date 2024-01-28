from pandas import DataFrame
from bytes_parser.frame_struct import Frame


def frame_field_formatter(frame_struct: Frame, frame: bytes) -> DataFrame:
    """
    For every field in template is matched the slice from the frame bytes.
    Frame consists of continuous bytes list without separation by word.
    Resulting values are converted from bytes to integer and  multiplied by
    dimension coefficient. After all transformations data are matched with
    template keys and appended to list.
    """
    table_rows: list[tuple[str, str]] = []
    for row in frame_struct:
        data: str | list[tuple[str, str]] = ''
        if row.size > 0:
            _start: int = frame_struct.size_ptr - row.size
            data = row.parser(frame[_start: frame_struct.size_ptr],
                              *row.args, **row.kwargs)
        else:
            data = row.parser(frame[frame_struct.size_ptr:],
                              *row.args, **row.kwargs)
        if isinstance(data, str):
            table_rows.append((row.label, data))
        else:
            table_rows.extend(data)
    return DataFrame(table_rows, columns=['Name', 'Value'])
