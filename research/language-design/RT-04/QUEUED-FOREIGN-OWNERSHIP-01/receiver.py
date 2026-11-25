"""Independent CPython receiver for the exact descriptor-transfer protocol."""

import os
import socket
import struct
import sys


def main():
    with socket.socket(fileno=int(sys.argv[1])) as channel:
        owned = {}
        print("ready", flush=True)
        for command in sys.stdin:
            command = command.strip()
            if command == "receive":
                payload, ancillary, flags, _ = channel.recvmsg(
                    1, socket.CMSG_SPACE(struct.calcsize("i")), socket.MSG_CMSG_CLOEXEC
                )
                assert len(ancillary) == 1 and not flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC)
                level, kind, descriptor = ancillary[0]
                assert (level, kind) == (socket.SOL_SOCKET, socket.SCM_RIGHTS)
                tag = payload.decode("ascii")
                assert tag in {"0", "1"} and tag not in owned
                fd, = struct.unpack("i", descriptor)
                assert not os.get_inheritable(fd)
                owned[tag] = fd
                stat = os.fstat(fd)
                print(f"received {tag} {stat.st_dev} {stat.st_ino}", flush=True)
            elif command in {"close 0", "close 1"}:
                tag = command[-1]
                os.close(owned.pop(tag))
                print(f"closed {tag}", flush=True)
            elif command == "exit":
                return
            else:
                raise ValueError(command)
    raise RuntimeError("Control channel closed before exit")


if __name__ == "__main__":
    main()
