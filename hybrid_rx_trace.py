#!/usr/bin/env python3
"""Small helper to explain why panda safety marks RX invalid.

Run this on-device while toggling ignition. It watches the pandaStates
stream and, whenever safetyRxChecksInvalid flips, prints how long it's
been since each required CAN message was last seen.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from cereal import messaging, log

EXPECTED = [
  (0, 0x119, "Steering_Torque"),
  (0, 0x139, "Brake_Pedal"),
  (0, 0x13A, "Wheel_Speeds"),
  (1, 0x168, "Throttle_Hybrid"),
  (1, 0x226, "Brake_Hybrid"),
  (2, 0x321, "ES_DashStatus"),
]

@dataclass
class PandaSnapshot:
  safety_model: int
  safety_param: int
  rx_invalid: int
  rx_checks_invalid: bool
  controls_allowed: bool


def main() -> None:
  sm = messaging.SubMaster(['pandaStates', 'can'])

  last_seen = {key: None for key in EXPECTED}  # type: ignore[assignment]
  prev_state: dict[int, PandaSnapshot] = {}

  def format_delta(ts: float | None, now: float) -> str:
    if ts is None:
      return "never"
    return f"{(now - ts):.3f}s"

  while True:
    sm.update(100)
    now = time.monotonic()

    if sm.updated['can']:
      for frame in sm['can'].can:
        key = (frame.src, frame.address)
        for bus, addr, name in EXPECTED:
          if key == (bus, addr):
            last_seen[(bus, addr, name)] = now

    if sm.updated['pandaStates']:
      for idx, ps in enumerate(sm['pandaStates']):
        current = PandaSnapshot(
          safety_model=ps.safetyModel,
          safety_param=ps.safetyParam,
          rx_invalid=ps.safetyRxInvalid,
          rx_checks_invalid=ps.safetyRxChecksInvalid,
          controls_allowed=ps.controlsAllowed,
        )

        prev = prev_state.get(idx)
        if prev is None or prev.rx_checks_invalid != current.rx_checks_invalid:
          state = log.PandaState.SafetyModel.names.get(current.safety_model, current.safety_model)
          print("--- panda", idx)
          print(f" safety: {state} param={current.safety_param} controlsAllowed={current.controls_allowed}")
          print(f" safetyRxChecksInvalid={current.rx_checks_invalid} safetyRxInvalidCount={current.rx_invalid}")
          for bus, addr, name in EXPECTED:
            delta = format_delta(last_seen[(bus, addr, name)], now)
            print(f"  last {name:<17} bus={bus} addr=0x{addr:03X} -> {delta}")
          print()

        prev_state[idx] = current


if __name__ == "__main__":
  main()
