#!/usr/bin/env python3
"""
Script to run tests with various options.
"""
import subprocess
import sys


def run_tests(verbose=False, coverage=False):
    """Run pytest with optional flags."""
    
    # Build command
    cmd = ["pytest", "tests/", "-v"]
    
    if verbose:
        cmd.extend(["-s", "--tb=short"])
    
    if coverage:
        cmd.extend([
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html"
        ])
    
    print("=" * 60)
    print("Running tests for Mansão Fefael")
    print("=" * 60)
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    print()
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=False,
            text=True
        )
        
        if coverage and result.returncode == 0:
            print("\n" + "=" * 60)
            print("Tests completed successfully!")
            print("=" * 60)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run tests for Mansão Fefael")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    args = parser.parse_args()
    
    success = run_tests(verbose=args.verbose, coverage=args.coverage)
    sys.exit(0 if success else 1)
