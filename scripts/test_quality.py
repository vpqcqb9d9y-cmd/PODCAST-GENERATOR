#!/usr/bin/env python3
"""
M.B.S Studio - Quality Verification Test Script
==============================================

Standalone script to run quality checks without executing the full pipeline.

Usage:
    python -m scripts.test_quality --check-quota
    python -m scripts.test_quality --check-voices
    python -m scripts.test_quality --check-output outputs/2025-12-03_test10
    python -m scripts.test_quality --full
    python -m scripts.test_quality --full --output-dir outputs/2025-12-03_test10

Author: M.B.S Studio
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.utils import Settings, QualityChecker, check_elevenlabs_quota_quick


console = Console()


def print_header(title: str) -> None:
    """Print a styled header."""
    console.print()
    console.print(Panel(title, style="bold cyan", box=box.DOUBLE))
    console.print()


def print_check_result(name: str, status: str, message: str, details: dict = None) -> None:
    """Print a single check result with styling."""
    icons = {
        "PASS": "[green]✅ PASS[/green]",
        "FAIL": "[red]❌ FAIL[/red]",
        "WARNING": "[yellow]⚠️  WARN[/yellow]",
        "SKIP": "[dim]⏭️  SKIP[/dim]",
    }
    icon = icons.get(status, status)
    console.print(f"  {icon} [bold]{name}[/bold]: {message}")
    
    if details and status != "PASS":
        for key, value in details.items():
            if isinstance(value, dict):
                console.print(f"       [dim]{key}:[/dim]")
                for k, v in value.items():
                    console.print(f"         [dim]{k}: {v}[/dim]")
            elif isinstance(value, list) and value:
                console.print(f"       [dim]{key}: {', '.join(str(v) for v in value[:5])}[/dim]")
            else:
                console.print(f"       [dim]{key}: {value}[/dim]")


def check_quota_only(api_key: str) -> bool:
    """Quick quota check."""
    print_header("ElevenLabs Quota Check")
    
    has_quota, remaining, limit, tier = check_elevenlabs_quota_quick(api_key)
    
    table = Table(title="ElevenLabs Account Status", box=box.ROUNDED)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green" if has_quota else "red")
    
    table.add_row("Tier", str(tier))
    table.add_row("Character Limit", f"{limit:,}")
    table.add_row("Characters Remaining", f"{remaining:,}")
    table.add_row("Has Quota", "✅ Yes" if has_quota else "❌ No")
    
    console.print(table)
    
    if not has_quota:
        console.print("\n[red bold]⚠️  WARNING: Low or no quota remaining![/red bold]")
        console.print("[yellow]Consider waiting for quota reset or upgrading your plan.[/yellow]")
        return False
    
    console.print(f"\n[green]✅ Quota OK: {remaining:,} characters available[/green]")
    return True


def check_voices_only(settings: Settings) -> bool:
    """Check voice configuration."""
    print_header("Voice Configuration Check")
    
    checker = QualityChecker(settings)
    report = checker.run_preflight_checks(skip_quota_check=True)
    
    console.print("[bold]Pre-flight Voice Checks:[/bold]")
    all_pass = True
    
    for check in report.preflight_checks:
        print_check_result(check.name, check.status, check.message, check.details)
        if check.status == "FAIL":
            all_pass = False
    
    if report.recommendations:
        console.print("\n[yellow bold]Recommendations:[/yellow bold]")
        for rec in report.recommendations:
            console.print(f"  • {rec}")
    
    console.print()
    if all_pass:
        console.print("[green bold]✅ Voice configuration is valid![/green bold]")
    else:
        console.print("[red bold]❌ Voice configuration has issues.[/red bold]")
    
    return all_pass


def check_output_only(settings: Settings, output_dir: Path) -> bool:
    """Check existing output directory."""
    print_header(f"Output Quality Check: {output_dir.name}")
    
    if not output_dir.exists():
        console.print(f"[red]ERROR: Directory not found: {output_dir}[/red]")
        return False
    
    checker = QualityChecker(settings)
    report = checker.run_postprocess_checks(run_dir=output_dir)
    
    console.print("[bold]Post-Processing Checks:[/bold]")
    all_pass = True
    
    for check in report.postprocess_checks:
        print_check_result(check.name, check.status, check.message, check.details)
        if check.status == "FAIL":
            all_pass = False
    
    if report.recommendations:
        console.print("\n[yellow bold]Recommendations:[/yellow bold]")
        for rec in report.recommendations:
            console.print(f"  • {rec}")
    
    console.print()
    if all_pass:
        console.print("[green bold]✅ Output quality check passed![/green bold]")
    else:
        console.print("[red bold]❌ Output has quality issues.[/red bold]")
    
    # Save report to output directory
    report_path = report.save(output_dir)
    console.print(f"\n[dim]Report saved to: {report_path}[/dim]")
    
    return all_pass


def run_full_check(settings: Settings, output_dir: Path = None) -> bool:
    """Run all quality checks."""
    print_header("Full Quality Verification")
    
    checker = QualityChecker(settings)
    
    # Run preflight checks
    console.print("[bold cyan]1. Running Pre-flight Checks...[/bold cyan]")
    preflight_report = checker.run_preflight_checks(
        estimated_characters=0,
        skip_quota_check=False,
    )
    
    all_pass = True
    for check in preflight_report.preflight_checks:
        print_check_result(check.name, check.status, check.message, check.details)
        if check.status == "FAIL":
            all_pass = False
    
    # Run postprocess checks if output_dir provided
    if output_dir and output_dir.exists():
        console.print()
        console.print("[bold cyan]2. Running Post-Processing Checks...[/bold cyan]")
        postprocess_report = checker.run_postprocess_checks(run_dir=output_dir)
        
        for check in postprocess_report.postprocess_checks:
            print_check_result(check.name, check.status, check.message, check.details)
            if check.status == "FAIL":
                all_pass = False
        
        # Save report
        report_path = checker.report.save(output_dir)
        console.print(f"\n[dim]Report saved to: {report_path}[/dim]")
    elif output_dir:
        console.print(f"\n[yellow]Output directory not found: {output_dir}[/yellow]")
    
    # Print recommendations
    if checker.report.recommendations:
        console.print("\n[yellow bold]Recommendations:[/yellow bold]")
        for rec in checker.report.recommendations:
            console.print(f"  • {rec}")
    
    # Print summary
    console.print()
    console.print("=" * 50)
    status = checker.report.overall_status
    if status == "PASS":
        console.print("[green bold]✅ OVERALL: ALL CHECKS PASSED[/green bold]")
    elif status == "WARNING":
        console.print("[yellow bold]⚠️  OVERALL: PASSED WITH WARNINGS[/yellow bold]")
    else:
        console.print("[red bold]❌ OVERALL: CHECKS FAILED[/red bold]")
    console.print("=" * 50)
    
    # Print summary as text
    console.print()
    console.print("[dim]" + checker.get_summary() + "[/dim]")
    
    return all_pass


def main():
    parser = argparse.ArgumentParser(
        description="M.B.S Studio Quality Verification Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.test_quality --check-quota
  python -m scripts.test_quality --check-voices  
  python -m scripts.test_quality --check-output outputs/2025-12-03_test10
  python -m scripts.test_quality --full
  python -m scripts.test_quality --full --output-dir outputs/2025-12-03_test10
        """
    )
    
    parser.add_argument(
        "--check-quota",
        action="store_true",
        help="Check ElevenLabs quota only"
    )
    parser.add_argument(
        "--check-voices",
        action="store_true",
        help="Validate voice configuration"
    )
    parser.add_argument(
        "--check-output",
        type=Path,
        metavar="DIR",
        help="Validate existing output directory"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run all checks"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        metavar="DIR",
        help="Output directory to check (with --full)"
    )
    
    args = parser.parse_args()
    
    # Require at least one check type
    if not any([args.check_quota, args.check_voices, args.check_output, args.full]):
        parser.print_help()
        console.print("\n[yellow]Please specify at least one check type.[/yellow]")
        return 1
    
    # Load settings
    try:
        settings = Settings.load()
    except Exception as e:
        console.print(f"[red]ERROR: Could not load settings: {e}[/red]")
        console.print("[yellow]Make sure .env file is configured correctly.[/yellow]")
        return 1
    
    success = True
    
    # Run requested checks
    if args.check_quota:
        if not settings.elevenlabs_api_key:
            console.print("[red]ERROR: ELEVENLABS_API_KEY not configured[/red]")
            return 1
        success &= check_quota_only(settings.elevenlabs_api_key)
    
    if args.check_voices:
        success &= check_voices_only(settings)
    
    if args.check_output:
        success &= check_output_only(settings, args.check_output)
    
    if args.full:
        success &= run_full_check(settings, args.output_dir)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

