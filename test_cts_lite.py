#!/usr/bin/env python3
"""Test script for CTS-Lite service."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        import cts_lite
        print(f"✓ cts_lite imported successfully (version: {cts_lite.__version__})")
    except ImportError as e:
        print(f"✗ Failed to import cts_lite: {e}")
        return False
    
    try:
        from cts_lite.main import app
        print("✓ FastAPI app created successfully")
    except ImportError as e:
        print(f"✗ Failed to import FastAPI app: {e}")
        return False
    
    try:
        from cts_lite.registry import registry
        caps = registry.get_capabilities()
        print(f"✓ Tool registry loaded with {len(caps)} tools:")
        for cap in caps:
            print(f"  - {cap.tool_id} ({cap.kind})")
    except Exception as e:
        print(f"✗ Failed to load tool registry: {e}")
        return False
    
    return True

def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    
    try:
        from cts_lite.config import CTSLiteConfig
        config = CTSLiteConfig()
        print(f"✓ Configuration loaded:")
        print(f"  - Data root: {config.data_root}")
        print(f"  - Host: {config.host}:{config.port}")
        print(f"  - Max workers: {config.max_workers}")
        config.ensure_directories()
        print("✓ Directories created successfully")
        return True
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_database():
    """Test database initialization."""
    print("\nTesting database...")
    
    try:
        from cts_lite.config import CTSLiteConfig
        from cts_lite.db import DatabaseManager
        
        config = CTSLiteConfig()
        db = DatabaseManager(config)
        db.initialize_schema()
        print("✓ Database schema initialized successfully")
        
        test_run = {
            "id": "test-run-123",
            "tool_id": "test-tool",
            "status": "queued",
            "params_json": "{}",
            "inputs_json": "[]",
            "log_path": "/tmp/test.log",
            "work_dir": "/tmp/work",
            "submitted_at": "2025-09-24T22:49:00Z"
        }
        
        db.create_run(test_run)
        retrieved = db.get_run("test-run-123")
        if retrieved and retrieved["tool_id"] == "test-tool":
            print("✓ Database CRUD operations working")
        else:
            print("✗ Database CRUD operations failed")
            return False
            
        return True
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

if __name__ == "__main__":
    print("CTS-Lite Service Test")
    print("=" * 50)
    
    success = True
    success &= test_imports()
    success &= test_config()
    success &= test_database()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ All tests passed! CTS-Lite service is ready.")
        sys.exit(0)
    else:
        print("✗ Some tests failed. Check the output above.")
        sys.exit(1)
