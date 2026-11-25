#!/usr/bin/env python3
"""Check repeated cancellation and native ownership before terminal settlement."""

import asyncio
import errno
from itertools import product
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


class PrimaryFailure(Exception):
    pass


def opened(descriptor):
    try:
        os.fstat(descriptor)
    except OSError as error:
        assert error.errno == errno.EBADF
        return False
    return True


async def trial(work, mode, pulses, diagnostic, protected):
    file = work / "fixture"
    file.write_bytes(b"-")
    descriptor = os.open(file, os.O_RDWR)
    body_entered = asyncio.Event()
    body_go = asyncio.Event()
    cleanup_entered = asyncio.Event()
    cleanup_go = asyncio.Event()
    events = []

    async def release():
        events.append("cleanup-entered")
        cleanup_entered.set()
        await cleanup_go.wait()
        os.close(descriptor)
        events.append("close")
        if diagnostic:
            events.append("cleanup-error")
            return "fixture-cleanup-error"
        return "clean"

    async def owner():
        primary = "returned"
        try:
            events.append("body-entered")
            body_entered.set()
            await body_go.wait()
            assert os.pwrite(descriptor, b"P", 0) == 1
            events.append("performed")
            if mode == "failed":
                raise PrimaryFailure
        except PrimaryFailure:
            primary = "body-error"
        except asyncio.CancelledError:
            primary = "cancelled"

        if protected:
            cleanup = asyncio.create_task(release())
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    events.append("cancel-during-cleanup")
            cleanup_result = cleanup.result()
        else:
            try:
                cleanup_result = await release()
            except asyncio.CancelledError:
                events.append("cleanup-interrupted")
                primary = "cancelled"
                cleanup_result = "interrupted"
        events.append("terminal")
        return {"primary": primary, "cleanup": cleanup_result, "open_at_terminal": opened(descriptor)}

    try:
        async with asyncio.TaskGroup() as scope:
            task = scope.create_task(owner())
            assert await asyncio.wait_for(body_entered.wait(), 5)
            if mode == "cancelled":
                assert task.cancel()
            else:
                body_go.set()
            assert await asyncio.wait_for(cleanup_entered.wait(), 5)
            assert opened(descriptor) and not task.done()
            for _ in range(pulses):
                task.cancel()
                # Yield twice to make cancellation delivery an actual
                # schedule boundary before the release gate opens.
                await asyncio.sleep(0)
                await asyncio.sleep(0)
            early = task.done()
            cleanup_go.set()
        terminal = task.result()
        current = file.read_bytes().decode()
        return terminal | {"early": early, "events": events, "file": current}
    finally:
        if opened(descriptor):
            os.close(descriptor)


def oracle(mode, pulses, diagnostic, protected):
    performed = mode != "cancelled"
    primary = {"returned": "returned", "failed": "body-error", "cancelled": "cancelled"}[mode]
    chronological = ["body-entered"]
    if performed:
        chronological.append("performed")
    chronological.append("cleanup-entered")
    interrupted = bool(pulses and not protected)
    if interrupted:
        primary = "cancelled"
        result = "interrupted"
        chronological.append("cleanup-interrupted")
    else:
        chronological.extend(["cancel-during-cleanup"] * pulses)
        chronological.append("close")
        if diagnostic:
            result = "fixture-cleanup-error"
            chronological.append("cleanup-error")
        else:
            result = "clean"
    return {"primary": primary, "cleanup": result, "open_at_terminal": interrupted,
            "early": interrupted, "events": chronological + ["terminal"],
            "file": "P" if performed else "-"}


async def experiment(work):
    rows = []
    choices = product(("returned", "failed", "cancelled"), (0, 1, 2), (False, True), (False, True))
    for mode, repeats, diagnostic, protection in choices:
        actual = await trial(work, mode, repeats, diagnostic, protection)
        independent = oracle(mode, repeats, diagnostic, protection)
        assert actual == independent
        rows.append({"mode": mode, "additional_cancellations": repeats, "cleanup_error": diagnostic,
                     "protected": protection, **actual})
    assert len(rows) == 36
    assert sum(row["open_at_terminal"] for row in rows) == 12
    assert any(row["primary"] == "body-error" and row["cleanup"] == "fixture-cleanup-error"
               for row in rows if row["protected"])
    return {"format": "async-terminal-settlement-01", "schedules": rows,
            "python": sys.version.split()[0]}


if __name__ == "__main__":
    with TemporaryDirectory(prefix="llmlang-terminal-settlement-") as directory:
        evidence = asyncio.run(experiment(Path(directory)))
    text = json.dumps(evidence, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
