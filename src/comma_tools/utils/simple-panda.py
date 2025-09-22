from panda import Panda

p = Panda()
print("=== PANDA STATUS ===")
print(f"Health: {p.health()}")
print(f"Safety Mode: {p.get_safety_mode()}")
print(f"Controls Allowed: {p.get_controls_allowed()}")
