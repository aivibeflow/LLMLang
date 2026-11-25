"""Compare native vector reads with a typed progress and continuation contract."""

from itertools import product
import errno
import json
import os
import platform


FILL = b"_"
SHAPES = ((3, 4), (0, 3, 0, 4), (0, 0), (), (1, 1, 1), (4,))


def new_buffers(shape):
    return [bytearray(FILL * length) for length in shape]


def one_read(reader, buffers):
    try:
        return os.readv(reader, buffers), None
    except BlockingIOError as error:
        assert error.errno == errno.EAGAIN
        return None, "EAGAIN"


def typed_status(requested, count, error):
    if requested == 0:
        assert count == 0 and error is None
        return "zero-request"
    if error:
        return "would-block"
    return "eof" if count == 0 else "progress"


def expected_buffers(shape, payload):
    cursor = 0
    result = []
    for length in shape:
        part = payload[cursor:cursor + length]
        result.append(bytes(part) + FILL * (length - len(part)))
        cursor += length
    return result


def run_case(shape, payload, closed):
    reader, writer = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if payload:
            assert os.write(writer, payload) == len(payload)
        if closed:
            os.close(writer)
            writer = None
        buffers = new_buffers(shape)
        count, error = one_read(reader, buffers)
        requested = sum(shape)
        expected_count = min(requested, len(payload))
        assert buffers == expected_buffers(shape, payload[:expected_count])
        if requested > 0 and not payload and not closed:
            assert count is None and error == "EAGAIN"
        else:
            assert count == expected_count and error is None

        try:
            remaining = os.read(reader, 32)
        except BlockingIOError as exc:
            assert exc.errno == errno.EAGAIN and not closed
            remaining = b""
        assert remaining == payload[expected_count:]
        return {
            "shape": shape, "payload": payload.decode(), "writer_closed": closed, "raw_count": count,
            "raw_error": error, "typed": typed_status(requested, count, error),
            "buffers": [value.decode() for value in buffers], "remaining": remaining.decode(),
        }
    finally:
        os.close(reader)
        if writer is not None:
            os.close(writer)


def remaining_views(buffers, completed):
    result = []
    for buffer in buffers:
        if completed >= len(buffer):
            completed -= len(buffer)
        else:
            result.append(memoryview(buffer)[completed:])
            completed = 0
    assert completed == 0
    return result


def resume(retain_progress):
    reader, writer = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    buffers = new_buffers((2, 3, 2))
    try:
        assert os.write(writer, b"abc") == 3
        first, error = one_read(reader, buffers)
        assert (first, error) == (3, None)
        snapshot = [buffer.decode() for buffer in buffers]
        assert os.write(writer, b"defg") == 4
        destination = remaining_views(buffers, first) if retain_progress else buffers
        count, error = one_read(reader, destination)
        assert (count, error) == (4, None)
        third, last_error = one_read(reader, [bytearray(1)])
        assert (third, last_error) == (None, "EAGAIN")
        return {"first_count": first, "before_resume": snapshot, "second_count": count,
                "after_resume": [buffer.decode() for buffer in buffers], "pipe_empty": True}
    finally:
        os.close(reader)
        os.close(writer)


def study():
    cases = [run_case(shape, b"ABCDEFGH"[:count], closed)
             for shape, count, closed in product(SHAPES, range(9), (False, True))]
    observations = {
        "tracked_cursor": resume(retain_progress=True),
        "whole_vector_retry": resume(retain_progress=False),
    }
    assert observations["tracked_cursor"]["after_resume"] == ["ab", "cde", "fg"]
    assert observations["whole_vector_retry"]["after_resume"] == ["de", "fg_", "__"]
    counts = {status: sum(row["typed"] == status for row in cases)
              for status in ("zero-request", "would-block", "eof", "progress")}
    assert counts == {"zero-request": 36, "would-block": 4, "eof": 4, "progress": 64}
    return {
        "python": platform.python_version(),
        "kernel": platform.release(),
        "cases": cases,
        "typed_counts": counts,
        "resume": observations,
    }


if __name__ == "__main__":
    print(json.dumps(study(), indent=2, sort_keys=True))
