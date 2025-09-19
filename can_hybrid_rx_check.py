#!/usr/bin/env python3
"""Count the Subaru hybrid safety signals per bus."""

from __future__ import annotations

import collections
import time

from cereal import messaging

IDS = {
  0x119: "Steering_Torque",
  0x139: "Brake_Pedal",
  0x13A: "Wheel_Speeds",
  0x168: "Throttle_Hybrid",
  0x226: "Brake_Hybrid",
  0x321: "ES_DashStatus",
}

SAMPLE_SECONDS = 5.0

def main() -> None:
  counts: collections.Counter[tuple[int, int]] = collections.Counter()
  sock = messaging.sub_sock("can")
  start = time.monotonic()

  while time.monotonic() - start < SAMPLE_SECONDS:
    msg = messaging.recv_sock(sock, wait=True)
    if msg is None:
      continue
    for frame in msg.can:
      if frame.address in IDS:
        counts[(frame.address, frame.src)] += 1

  if not counts:
    print("No matching frames observed.")
    return

  for (addr, bus), cnt in sorted(counts.items()):
    print(f"addr=0x{addr:X} bus={bus} count={cnt} -> {IDS[addr]}")


if __name__ == "__main__":
  main()
