#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import urllib.request

VENDOR_ROOT = "/comma-tools/vendor/openpilot"

def inject_vendor_paths():
    """Inject vendor paths if they exist, with helpful diagnostics."""
    tools_dir = os.path.join(VENDOR_ROOT, "tools")
    cereal_dir = os.path.join(VENDOR_ROOT, "cereal")

    # Check if vendor dependencies exist
    vendor_exists = os.path.isdir(VENDOR_ROOT)
    if not vendor_exists:
        print(f"Warning: Vendor dependencies not found at {VENDOR_ROOT}", file=sys.stderr)
        print("OpenPilot-dependent analyzers may not work properly.", file=sys.stderr)

    for p in (VENDOR_ROOT, tools_dir, cereal_dir):
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)

def wait_health(url="http://127.0.0.1:8080/v1/health", timeout_s=30):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False

def start_interactive():
    inject_vendor_paths()
    subprocess.Popen(["cts-lite"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    if not wait_health():
        print("Server failed to start within timeout", file=sys.stderr)
        sys.exit(1)
    os.execv("/bin/bash", ["/bin/bash"])

def start_daemon():
    inject_vendor_paths()
    os.execvpe("cts-lite", ["cts-lite", "--host", "0.0.0.0"], os.environ)

def start_cli(args):
    inject_vendor_paths()
    p = subprocess.Popen(["cts-lite"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        if not wait_health():
            print("Server failed to start within timeout", file=sys.stderr)
            p.terminate()
            sys.exit(1)
        if not args:
            args = ["cts", "ping"]
        os.execvp(args[0], args)
    finally:
        pass

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "interactive"
    if mode == "interactive":
        start_interactive()
    elif mode == "daemon":
        start_daemon()
    elif mode == "cli":
        start_cli(sys.argv[2:])
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
