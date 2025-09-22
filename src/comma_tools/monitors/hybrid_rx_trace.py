#!/usr/bin/env python3
"""Trace which CAN signals cause panda safety to flag RX invalid."""

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

# Some builds don't expose PandaState.SafetyModel. Gracefully fall back to numbers.
_SAFETY_NAME_FN = getattr(getattr(log.PandaState, "SafetyModel", None), "Name", None)


def safety_name(value: int) -> str:
    if _SAFETY_NAME_FN is not None:
        try:
            return _SAFETY_NAME_FN(value)
        except Exception:
            pass
    return str(value)


@dataclass
class PandaSnapshot:
    safety_model: int
    safety_param: int
    rx_invalid: int
    rx_checks_invalid: bool
    controls_allowed: bool


def main() -> None:
    sm = messaging.SubMaster(["pandaStates"])
    can_sock = messaging.sub_sock("can")

    last_seen = {key: None for key in EXPECTED}  # type: ignore[assignment]
    prev_state: dict[int, PandaSnapshot] = {}

    def format_delta(ts: float | None, now: float) -> str:
        if ts is None:
            return "never"
        return f"{(now - ts):.3f}s"

    while True:
        sm.update(100)
        now = time.monotonic()

        can_msg = messaging.recv_sock(can_sock, wait=False)
        if can_msg is not None:
            for frame in can_msg.can:
                key = (frame.src, frame.address)
                for bus, addr, name in EXPECTED:
                    if key == (bus, addr):
                        last_seen[(bus, addr, name)] = now

        if sm.updated["pandaStates"]:
            for idx, ps in enumerate(sm["pandaStates"]):
                current = PandaSnapshot(
                    safety_model=ps.safetyModel,
                    safety_param=ps.safetyParam,
                    rx_invalid=ps.safetyRxInvalid,
                    rx_checks_invalid=ps.safetyRxChecksInvalid,
                    controls_allowed=ps.controlsAllowed,
                )

                prev = prev_state.get(idx)
                if prev is None or prev.rx_checks_invalid != current.rx_checks_invalid:
                    print("--- panda", idx)
                    print(
                        f" safety: {safety_name(current.safety_model)} param={current.safety_param} controlsAllowed={current.controls_allowed}"
                    )
                    print(
                        f" safetyRxChecksInvalid={current.rx_checks_invalid} safetyRxInvalidCount={current.rx_invalid}"
                    )
                    for bus, addr, name in EXPECTED:
                        delta = format_delta(last_seen[(bus, addr, name)], now)
                        print(f"  last {name:<17} bus={bus} addr=0x{addr:03X} -> {delta}")
                    print()

                prev_state[idx] = current


if __name__ == "__main__":
    main()
