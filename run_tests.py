"""
Standardized test runner for all microservices.
Runs pytest with coverage reporting to /reports folder.
Usage: python run_tests.py [--html] [--verbose]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_pytest(reports_dir: Path = None, verbose: bool = False, html: bool = False) -> int:
    """Run pytest with standardized coverage and reporting.
    
    Args:
        reports_dir: Directory to store test reports (defaults to ./reports)
        verbose: Enable verbose output
        html: Generate HTML coverage report
        
    Returns:
        Exit code from pytest
    """
    if reports_dir is None:
        reports_dir = Path(__file__).parent / "reports"
    
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Paths for reports
    junit_xml = reports_dir / "junit.xml"
    coverage_xml = reports_dir / "coverage.xml"
    coverage_html = reports_dir / "htmlcov"
    
    # Base pytest command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        f"--junitxml={junit_xml}",
        "--asyncio-mode=auto",
        "--cov=app",
        "--cov=main",
        f"--cov-report=xml:{coverage_xml}",
        "--cov-report=term-missing",
    ]
    
    # Add HTML report if requested
    if html:
        cmd.append(f"--cov-report=html:{coverage_html}")
    
    # Add verbosity
    if verbose:
        cmd.extend(["-v", "-s"])
    else:
        cmd.append("-q")
    
    # Run pytest
    print(f"Running tests from: {Path(__file__).parent / 'tests'}")
    print(f"Reports directory: {reports_dir}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    if result.returncode == 0:
        print(f"\n✓ Tests passed!")
        print(f"  - JUnit report: {junit_xml}")
        print(f"  - Coverage XML: {coverage_xml}")
        if html:
            print(f"  - HTML report: {coverage_html}/index.html")
    else:
        print(f"\n✗ Tests failed with code {result.returncode}")
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run microservice tests with coverage")
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML coverage report"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=None,
        help="Custom reports directory (default: ./reports)"
    )
    
    args = parser.parse_args()
    
    return run_pytest(
        reports_dir=args.reports_dir,
        verbose=args.verbose,
        html=args.html
    )


if __name__ == "__main__":
    sys.exit(main())
