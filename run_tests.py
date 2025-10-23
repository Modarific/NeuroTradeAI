#!/usr/bin/env python3
"""
Test runner for the NeuroTradeAI test suite.
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path

def run_tests(test_type="all", verbose=False, coverage=False):
    """Run the test suite."""
    
    # Add the app directory to the path
    app_dir = Path(__file__).parent / "app"
    sys.path.insert(0, str(app_dir))
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add test directory
    cmd.append("tests/")
    
    # Add verbosity
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    # Add coverage if requested
    if coverage:
        cmd.extend(["--cov=app", "--cov-report=html", "--cov-report=term"])
    
    # Filter by test type
    if test_type == "unit":
        cmd.extend(["tests/test_storage.py", "tests/test_rate_limiter.py", "tests/test_adapters.py"])
    elif test_type == "integration":
        cmd.append("tests/test_integration.py")
    elif test_type == "load":
        cmd.append("tests/test_load.py")
    elif test_type == "security":
        cmd.append("tests/test_security.py")
    elif test_type == "all":
        pass  # Run all tests
    else:
        print(f"Unknown test type: {test_type}")
        return False
    
    # Run the tests
    print(f"Running {test_type} tests...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n✅ {test_type.title()} tests passed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {test_type.title()} tests failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print("❌ pytest not found. Please install pytest: pip install pytest")
        return False

def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run NeuroTradeAI test suite")
    parser.add_argument(
        "--type", 
        choices=["all", "unit", "integration", "load", "security"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Generate coverage report"
    )
    
    args = parser.parse_args()
    
    print("🧪 NeuroTradeAI Test Suite")
    print("=" * 50)
    
    success = run_tests(
        test_type=args.type,
        verbose=args.verbose,
        coverage=args.coverage
    )
    
    if success:
        print("\n🎉 All tests completed successfully!")
        if args.coverage:
            print("📊 Coverage report generated in htmlcov/index.html")
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
