#!/usr/bin/env python3
"""
Test AI Quality Enhancement on existing output directory.

Usage:
    python -m scripts.test_ai_enhancement "outputs/2025-12-27_הוראה-והדרכה-בטכנולוגיות-ענן"
    python -m scripts.test_ai_enhancement "outputs/..." --apply-fixes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils import Settings, QualityChecker  # noqa: E402
from src.utils.ai_quality_enhancer import (  # noqa: E402
    enhance_with_ai,
)
from src.utils.quality_checker import QualityReport, CheckResult  # noqa: E402

console = Console()


def load_quality_report(run_dir: Path) -> QualityReport:
    """Load existing quality report from directory."""
    report_path = run_dir / "quality_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Quality report not found: {report_path}")

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    checker = QualityChecker(Settings.load())
    checker.report = QualityReport(
        timestamp=data.get("timestamp", ""),
        run_type=data.get("run_type", "FULL"),
        overall_status=data.get("overall_status", "PENDING"),
        recommendations=data.get("recommendations", []),
    )

    for name, check_data in data.get("postprocess", {}).items():
        checker.report.add_postprocess(
            CheckResult(
                name=name,
                status=check_data.get("status", "UNKNOWN"),
                message=check_data.get("message", ""),
                details=check_data.get("details", {}),
            )
        )

    return checker.report


def load_metadata(run_dir: Path) -> dict:
    metadata_path = run_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_dialogue(run_dir: Path) -> dict:
    dialogue_path = run_dir / "dialogue.json"
    if dialogue_path.exists():
        with open(dialogue_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test AI Quality Enhancement on existing output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory to analyze",
    )
    parser.add_argument(
        "--apply-fixes",
        action="store_true",
        help="Apply automatic fixes (default: False, only show suggestions)",
    )

    args = parser.parse_args()

    if not args.output_dir.exists():
        console.print(f"[red]ERROR: Directory not found: {args.output_dir}[/red]")
        return 1

    console.print()
    console.print(
        Panel(
            f"AI Quality Enhancement Test\n{args.output_dir.name}",
            style="bold cyan",
            box=box.DOUBLE,
        )
    )
    console.print()

    try:
        settings = Settings.load()
        settings.enable_ai_quality_enhancement = True
        settings.auto_apply_ai_fixes = args.apply_fixes
    except Exception as exc:
        console.print(f"[red]ERROR: Could not load settings: {exc}[/red]")
        return 1

    try:
        console.print("[cyan]Loading quality report...[/cyan]")
        quality_report = load_quality_report(args.output_dir)
        console.print(
            f"[green]✓[/green] Loaded quality report (status: {quality_report.overall_status})"
        )
    except Exception as exc:
        console.print(f"[red]ERROR: {exc}[/red]")
        return 1

    metadata = load_metadata(args.output_dir)
    dialogue = load_dialogue(args.output_dir)

    if metadata:
        console.print(f"[green]✓[/green] Loaded metadata")
    if dialogue:
        console.print(
            f"[green]✓[/green] Loaded dialogue ({len(dialogue.get('dialogue', []))} entries)"
        )

    console.print()
    console.print("[cyan]Running AI analysis...[/cyan]")
    console.print("[dim](This may take 10-30 seconds)[/dim]")
    console.print()

    try:
        plan = enhance_with_ai(
            quality_report=quality_report,
            run_dir=args.output_dir,
            settings=settings,
            metadata=metadata,
            dialogue=dialogue,
            apply_auto_fixes=args.apply_fixes,
        )

        console.print()
        console.print(Panel("AI Enhancement Results", style="bold green", box=box.ROUNDED))
        console.print()

        if not plan.suggestions:
            console.print("[yellow]No improvement suggestions generated.[/yellow]")
            console.print(
                "[dim]This could mean the quality report shows no issues, or AI analysis failed.[/dim]"
            )
        else:
            table = Table(
                title="Improvement Suggestions", show_header=True, header_style="bold magenta"
            )
            table.add_column("#", style="dim", width=3)
            table.add_column("Severity", width=10)
            table.add_column("Category", width=12)
            table.add_column("Issue", width=40)
            table.add_column("Action", width=50)
            table.add_column("Auto-fix", width=10)

            for i, suggestion in enumerate(plan.suggestions, 1):
                severity_color = {
                    "critical": "red",
                    "high": "yellow",
                    "medium": "cyan",
                    "low": "dim",
                }.get(suggestion.severity, "white")

                issue = suggestion.issue
                action = suggestion.action
                if len(issue) > 40:
                    issue = issue[:37] + "..."
                if len(action) > 50:
                    action = action[:47] + "..."

                table.add_row(
                    str(i),
                    f"[{severity_color}]{suggestion.severity.upper()}[/{severity_color}]",
                    suggestion.category,
                    issue,
                    action,
                    "✓" if suggestion.auto_fixable else "✗",
                )

            console.print(table)
            console.print()
            console.print("[bold]Summary:[/bold]")
            console.print(f"  • Total suggestions: {len(plan.suggestions)}")
            console.print(f"  • Auto-fixable: {len(plan.auto_fixes)}")
            console.print(f"  • Manual review needed: {len(plan.manual_review)}")

            if plan.auto_fixes:
                console.print()
                console.print("[yellow bold]Auto-fixable actions:[/yellow bold]")
                for fix in plan.auto_fixes:
                    console.print(f"  • {fix}")

            if plan.manual_review:
                console.print()
                console.print("[cyan bold]Actions requiring manual review:[/cyan bold]")
                for action in plan.manual_review:
                    console.print(f"  • {action}")

        plan_path = args.output_dir / "enhancement_plan.json"
        plan_dict = {
            "suggestions": [
                {
                    "issue": s.issue,
                    "severity": s.severity,
                    "category": s.category,
                    "action": s.action,
                    "auto_fixable": s.auto_fixable,
                    "estimated_impact": s.estimated_impact,
                    "details": s.details,
                }
                for s in plan.suggestions
            ],
            "auto_fixes": plan.auto_fixes,
            "manual_review": plan.manual_review,
            "priority_order": plan.priority_order,
        }

        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan_dict, f, ensure_ascii=False, indent=2)

        console.print()
        console.print(f"[green]✓[/green] Enhancement plan saved to: {plan_path.name}")
        return 0

    except Exception as exc:  # pragma: no cover - runtime guard
        console.print(f"[red]ERROR: AI enhancement failed: {exc}[/red]")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return 1


if __name__ == "__main__":  # pragma: no cover - manual run
    sys.exit(main())

