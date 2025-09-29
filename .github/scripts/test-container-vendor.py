#!/usr/bin/env python3
"""
Test script to verify OpenPilot vendor dependencies are properly
included in the Docker container build.

This script is designed to run inside the container and verify that:
1. The vendor directories exist
2. LogReader can be imported
3. The cereal module is available

Exit codes:
  0 - All tests passed
  1 - Import or verification failure
"""

import sys
from pathlib import Path


def main():
    """
    Run vendor dependency verification tests.

    Returns:
        int: 0 if all tests pass (success), 1 if any test fails (failure).
    """
    print("=" * 60)
    print("Container Vendor Dependencies Test")
    print("=" * 60)

    # Check vendor directory structure
    vendor_root = Path("/comma-tools/vendor/openpilot")
    print(f"\n1. Checking vendor directory: {vendor_root}")

    if not vendor_root.exists():
        print(f"   ✗ Vendor root does not exist: {vendor_root}")
        return 1
    print(f"   ✓ Vendor root exists")

    # Check for expected subdirectories
    expected_dirs = {
        "tools/lib": "OpenPilot tools library",
        "cereal": "OpenPilot cereal messaging"
    }

    for subdir, description in expected_dirs.items():
        dir_path = vendor_root / subdir
        if not dir_path.exists():
            print(f"   ✗ Missing: {subdir} ({description})")
            return 1
        print(f"   ✓ Found: {subdir} ({description})")

    # Add vendor paths to Python path (mimics startup.py behavior)
    print("\n2. Adding vendor paths to Python path:")
    vendor_paths = [
        str(vendor_root),
        str(vendor_root / "tools"),
        str(vendor_root / "cereal")
    ]

    for path in vendor_paths:
        if path not in sys.path:
            sys.path.insert(0, path)
            print(f"   + {path}")

    # Test imports
    print("\n3. Testing module imports:")

    # Test LogReader import
    try:
        from tools.lib.logreader import LogReader
        print("   ✓ LogReader import successful")
    except ImportError as e:
        print(f"   ✗ LogReader import failed: {e}")
        return 1

    # Test cereal import
    try:
        import cereal
        print("   ✓ cereal import successful")
    except ImportError as e:
        print(f"   ✗ cereal import failed: {e}")
        return 1

    # Optional: Check for specific expected files
    print("\n4. Verifying key files:")
    key_files = [
        (vendor_root / "tools/lib/logreader.py", "LogReader implementation"),
        (vendor_root / "cereal/__init__.py", "cereal package")
    ]

    for file_path, description in key_files:
        if file_path.exists():
            print(f"   ✓ {file_path.name}: {description}")
        else:
            print(f"   ✗ Missing {file_path.name}: {description}")
            return 1

    print("\n" + "=" * 60)
    print("✓ All vendor dependency tests passed!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())