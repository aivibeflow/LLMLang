"""A synchronous MCP stdio client for llmlang-server (Python 3.10+)."""

import argparse
from contextlib import contextmanager
import json
import math
import os
import selectors
import subprocess
import sys
import time


SUPPORTED_VERSIONS = ("2025-11-25", "2025-06-18")
DEFAULT_TIMEOUT = 180


class RpcError(RuntimeError):
    """A JSON-RPC error, with the original code, message, and optional data."""

    def __init__(self, error):
        super().__init__(error["message"])
        self.error = error


class Client:
    def __init__(self, process, selector, timeout):
        self._process = process
        self._selector = selector
        self._timeout = timeout
        self._pending = bytearray()
        self._next_id = 1
        self.server = self.request(
            "initialize", protocolVersion=SUPPORTED_VERSIONS[0], capabilities={},
            clientInfo={"name": "llmlang-python", "version": "1.0.0"},
        )
        version = self.server.get("protocolVersion")
        if version not in SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported MCP protocol version: {version!r}")
        self._send({"method": "notifications/initialized"})

    def _send(self, message):
        line = json.dumps({"jsonrpc": "2.0", **message}, allow_nan=False)
        self._process.stdin.write(line.encode("utf-8") + b"\n")
        self._process.stdin.flush()

    def _receive(self, deadline):
        while b"\n" not in self._pending:
            wait = deadline - time.monotonic()
            if wait <= 0 or not self._selector.select(wait):
                raise TimeoutError("MCP server did not respond before the deadline")
            data = os.read(self._process.stdout.fileno(), 8192)
            if not data:
                raise EOFError("MCP server closed stdout")
            self._pending.extend(data)
        line, _, self._pending = self._pending.partition(b"\n")
        return json.loads(line.decode("utf-8"))

    def request(self, method, /, **params):
        """Send an MCP request and return its complete result object."""
        request_id = self._next_id
        self._next_id += 1
        self._send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self._timeout
        while True:
            response = self._receive(deadline)
            if not isinstance(response, dict) or response.get("jsonrpc") != "2.0":
                raise ValueError("Invalid MCP response")
            if "method" in response and "id" not in response:
                continue
            if response.get("id") != request_id:
                raise ValueError(f"Unexpected MCP response ID: {response.get('id')!r}")
            if "error" in response:
                raise RpcError(response["error"])
            if "result" not in response:
                raise ValueError("Missing MCP response result")
            return response["result"]

    def call_tool(self, name, arguments):
        """Call a tool by its advertised name, retaining MCP content and errors."""
        return self.request("tools/call", name=name, arguments=arguments)


@contextmanager
def connect(command, *, timeout=DEFAULT_TIMEOUT):
    """Launch the server and open an initialized MCP session for sequential requests."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Response timeout must be a positive, finite number")
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                yield Client(process, selector, timeout)
        finally:
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("method", help="MCP method, e.g. tools/list or tools/call")
    parser.add_argument("params", nargs="?", default="{}", help="JSON object or - for stdin")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="response timeout in seconds")
    parser.add_argument("--server", required=True, nargs=argparse.REMAINDER,
                        help="server executable and all its arguments (must come last)")
    args = parser.parse_args()
    if not args.server:
        parser.error("--server requires an executable")
    try:
        params = json.load(sys.stdin) if args.params == "-" else json.loads(args.params)
        if not isinstance(params, dict):
            raise ValueError("MCP params must be a JSON object")
        if args.method == "initialize" and params:
            raise ValueError("initialize is automatic and takes no CLI params")
        with connect(args.server, timeout=args.timeout) as client:
            result = client.server if args.method == "initialize" else client.request(args.method, **params)
        print(json.dumps(result, indent=2))
        return int(args.method == "tools/call" and result.get("isError", False))
    except RpcError as error:
        print(json.dumps(error.error), file=sys.stderr)
    except (EOFError, OSError, ValueError) as error:
        print(f"mcp_client: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
