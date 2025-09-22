#!/usr/bin/env python3
from cereal import messaging, log

try:
    model_name = log.PandaState.SafetyModel.Name  # may not exist on every build
except AttributeError:
    model_name = None


def resolve(val):
    try:
        return model_name(val) if model_name is not None else str(val)
    except Exception:
        return str(val)


sm = messaging.SubMaster(["pandaStates", "selfdriveState"])

while True:
    sm.update(100)
    if sm.updated["pandaStates"]:
        for i, ps in enumerate(sm["pandaStates"]):
            print(
                f"panda{i}: model={resolve(ps.safetyModel)} "
                f"param={ps.safetyParam} altExp={ps.alternativeExperience} "
                f"controlsAllowed={ps.controlsAllowed} rxInvalid={ps.safetyRxChecksInvalid}"
            )
        print(f"selfdrive enabled={sm['selfdriveState'].enabled}")
        print("---")
