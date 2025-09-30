#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import urllib.request

VENDOR_ROOT = "/comma-tools/vendor/openpilot"

def inject_vendor_paths():
    """Inject vendor paths if they exist, with helpful diagnostics."""
    # The key insight: LogReader expects imports like "from openpilot.tools.lib..."
    # So we need to add the PARENT of the openpilot directory to sys.path
    vendor_parent = "/comma-tools/vendor"  # Parent containing "openpilot" subdir
    tools_dir = os.path.join(VENDOR_ROOT, "tools")
    cereal_dir = os.path.join(VENDOR_ROOT, "cereal")

    # Check if vendor dependencies exist
    vendor_exists = os.path.isdir(VENDOR_ROOT)
    if not vendor_exists:
        print(f"Warning: Vendor dependencies not found at {VENDOR_ROOT}", file=sys.stderr)
        print("OpenPilot-dependent analyzers may not work properly.", file=sys.stderr)

    # Add vendor parent FIRST so "import openpilot.X" works
    for p in (vendor_parent, VENDOR_ROOT, tools_dir, cereal_dir):
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
    
    print("🚀 Starting comma-tools API server (cts-lite)...")
    subprocess.Popen(["cts-lite"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    
    if not wait_health():
        print("❌ Server failed to start within timeout", file=sys.stderr)
        sys.exit(1)
    
    print("✅ API server is running at http://localhost:8080\n")
    
    welcome = """
╔════════════════════════════════════════════════════════════════╗
║                      COMMA-TOOLS CONTAINER                     ║
╚════════════════════════════════════════════════════════════════╝

🎉 Welcome! Your comma-tools environment is ready.

📡 API Server: Running at http://localhost:8080
🔧 CLI Tool: 'cts' command is available in your PATH

QUICK START:
  cts ping              # Test connection to API server
  cts capabilities      # List available analysis tools
  cts run cruise-control-analyzer --help  # Get help for a tool

EXAMPLES:
  cts run cruise-control-analyzer \\
    --route-name "your-dongle-id|YYYY-MM-DD--HH-MM-SS"

  comma-connect-dl "your-dongle-id|YYYY-MM-DD--HH-MM-SS"

LEGACY TOOLS (if you prefer CLI without API):
  rlog-to-csv --help
  can-bitwatch --help

📚 Documentation: https://github.com/anteew/comma-tools

═══════════════════════════════════════════════════════════════════
"""
    print(welcome)
    
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
