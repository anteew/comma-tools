#!/usr/bin/env python3
"""Quick utility to tally selected CAN IDs by bus.

Run on-device while the car is on. It prints how many times each
interesting message appeared on each bus during a short sample window.
"""

from __future__ import annotations

import collections
import time

from cereal import messaging

INTERESTING = {
    0x40: "Throttle",
    0x168: "Throttle_Hybrid",
    0x13C: "Brake_Status",
    0x240: "CruiseControl",
    0x321: "ES_DashStatus",
}

SAMPLE_SECONDS = 5.0


def main() -> None:
    counts: collections.Counter[tuple[int, int]] = collections.Counter()
    start = time.monotonic()
    sock = messaging.sub_sock("can")

    while time.monotonic() - start < SAMPLE_SECONDS:
        msg = messaging.recv_sock(sock, wait=True)
        if msg is None:
            continue

        for frame in msg.can:
            key = (frame.address, frame.src)
            if frame.address in INTERESTING:
                counts[key] += 1

    if not counts:
        print("No matching CAN frames observed.")
        return

    for (addr, bus), cnt in sorted(counts.items()):
        name = INTERESTING.get(addr, "")
        print(f"addr=0x{addr:X} bus={bus} count={cnt} -> {name}")


if __name__ == "__main__":
    main()
