#!/usr/bin/env python3
"""
Interactive Demo for Arcade.dev Examples

This script provides an interactive demonstration of the Arcade.dev integration
examples, allowing users to explore different features and capabilities.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json

# Add FACT framework to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


@dataclass
class DemoExample:
    """Represents a demo example."""

    name: str
    description: str
    script_path: str
    requirements: List[str]
    difficulty: str  # 'beginner', 'intermediate', 'advanced'


class InteractiveDemo:
    """Interactive demonstration manager."""

    def __init__(self):
        self.console = Console() if HAS_RICH else None
        self.examples = self._load_examples()
        self.logger = logging.getLogger(__name__)

    def _load_examples(self) -> List[DemoExample]:
        """Load available examples."""
        return [
            DemoExample(
                name="Basic Integration",
                description="Fundamental Arcade.dev API client integration",
                script_path="01_basic_integration/basic_arcade_client.py",
                requirements=["ARCADE_API_KEY"],
                difficulty="beginner",
            ),
            DemoExample(
                name="Code Analysis",
                description="Analyze code quality and structure",
                script_path="02_code_analysis/code_analyzer.py",
                requirements=["ARCADE_API_KEY"],
                difficulty="beginner",
            ),
            DemoExample(
                name="Test Generation",
                description="Generate comprehensive test cases using AI",
                script_path="03_automated_testing/test_generator.py",
                requirements=["ARCADE_API_KEY"],
                difficulty="intermediate",
            ),
            DemoExample(
                name="Documentation Generation",
                description="Automatically generate documentation from code",
                script_path="04_documentation/doc_generator.py",
                requirements=["ARCADE_API_KEY"],
                difficulty="intermediate",
            ),
            DemoExample(
                name="Cache Integration",
                description="Integrate Arcade.dev with FACT's caching system",
                script_path="07_cache_integration/cached_arcade_client.py",
                requirements=["ARCADE_API_KEY", "FACT_CACHE_ENABLED"],
                difficulty="advanced",
            ),
        ]

    def _print_banner(self):
        """Print welcome banner."""
        if self.console:
            self.console.print(
                Panel.fit(
                    "[bold blue]🎮 Arcade.dev Integration Examples[/bold blue]\n"
                    "[dim]Interactive demonstration of FACT + Arcade.dev integration[/dim]",
                    border_style="blue",
                )
            )
        else:
            print("=" * 60)
            print("🎮 Arcade.dev Integration Examples")
            print("Interactive demonstration of FACT + Arcade.dev integration")
            print("=" * 60)

    def _check_prerequisites(self) -> bool:
        """Check if prerequisites are met."""
        missing_vars = []
        required_vars = ["ARCADE_API_KEY"]

        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            if self.console:
                self.console.print(
                    Panel(
                        f"[red]Missing required environment variables:[/red]\n"
                        f"{', '.join(missing_vars)}\n\n"
                        f"[dim]Please copy .env.example to .env and configure your settings.[/dim]",
                        title="Prerequisites Check Failed",
                        border_style="red",
                    )
                )
            else:
                print(
                    f"❌ Missing required environment variables: {', '.join(missing_vars)}"
                )
                print("Please copy .env.example to .env and configure your settings.")
            return False

        return True

    def _display_examples_table(self):
        """Display available examples in a table."""
        if self.console:
            table = Table(title="Available Examples")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="bold")
            table.add_column("Description")
            table.add_column("Difficulty", justify="center")
            table.add_column("Status", justify="center")

            for i, example in enumerate(self.examples, 1):
                # Check if example script exists
                script_path = Path(__file__).parent / example.script_path
                status = "✅" if script_path.exists() else "🚧"

                # Color code difficulty
                if example.difficulty == "beginner":
                    difficulty = f"[green]{example.difficulty}[/green]"
                elif example.difficulty == "intermediate":
                    difficulty = f"[yellow]{example.difficulty}[/yellow]"
                else:
                    difficulty = f"[red]{example.difficulty}[/red]"

                table.add_row(
                    str(i), example.name, example.description, difficulty, status
                )

            self.console.print(table)
        else:
            print("\nAvailable Examples:")
            print("-" * 60)
            for i, example in enumerate(self.examples, 1):
                script_path = Path(__file__).parent / example.script_path
                status = "✅" if script_path.exists() else "🚧"
                print(f"{i:2d}. {example.name} ({example.difficulty}) {status}")
                print(f"    {example.description}")

    def _get_user_choice(self) -> Optional[int]:
        """Get user's example choice."""
        if self.console:
            choice = Prompt.ask(
                "\n[bold]Select an example to run[/bold]",
                choices=[str(i) for i in range(1, len(self.examples) + 1)] + ["q"],
                default="q",
            )
        else:
            choice = input(
                f"\nSelect an example (1-{len(self.examples)}) or 'q' to quit: "
            )

        if choice.lower() == "q":
            return None

        try:
            return int(choice)
        except ValueError:
            return None

    async def _run_example(self, example: DemoExample):
        """Run a selected example."""
        script_path = Path(__file__).parent / example.script_path

        if not script_path.exists():
            if self.console:
                self.console.print(
                    f"[red]❌ Example script not found: {example.script_path}[/red]"
                )
            else:
                print(f"❌ Example script not found: {example.script_path}")
            return

        # Check example-specific requirements
        missing_reqs = []
        for req in example.requirements:
            if not os.getenv(req):
                missing_reqs.append(req)

        if missing_reqs:
            if self.console:
                self.console.print(
                    f"[yellow]⚠️  Missing requirements for this example: {', '.join(missing_reqs)}[/yellow]"
                )
                if not Confirm.ask("Continue anyway?"):
                    return
            else:
                print(f"⚠️  Missing requirements: {', '.join(missing_reqs)}")
                response = input("Continue anyway? (y/N): ")
                if response.lower() != "y":
                    return

        # Display example info
        if self.console:
            self.console.print(
                Panel(
                    f"[bold]{example.name}[/bold]\n"
                    f"{example.description}\n\n"
                    f"[dim]Script: {example.script_path}[/dim]\n"
                    f"[dim]Difficulty: {example.difficulty}[/dim]",
                    title="Running Example",
                    border_style="green",
                )
            )
        else:
            print(f"\n🚀 Running: {example.name}")
            print(f"Description: {example.description}")
            print(f"Script: {example.script_path}")

        # Run the example
        try:
            if self.console:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console,
                ) as progress:
                    task = progress.add_task("Executing example...", total=None)

                    # Execute the script
                    process = await asyncio.create_subprocess_exec(
                        sys.executable,
                        str(script_path),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    stdout, stderr = await process.communicate()

                    progress.remove_task(task)

            else:
                print("Executing example...")
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(script_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

            # Display results
            if process.returncode == 0:
                if self.console:
                    self.console.print(
                        "[green]✅ Example completed successfully![/green]"
                    )
                    if stdout:
                        self.console.print(
                            Panel(stdout.decode(), title="Output", border_style="green")
                        )
                else:
                    print("✅ Example completed successfully!")
                    if stdout:
                        print("\nOutput:")
                        print("-" * 40)
                        print(stdout.decode())
            else:
                if self.console:
                    self.console.print("[red]❌ Example failed![/red]")
                    if stderr:
                        self.console.print(
                            Panel(
                                stderr.decode(),
                                title="Error Output",
                                border_style="red",
                            )
                        )
                else:
                    print("❌ Example failed!")
                    if stderr:
                        print("\nError Output:")
                        print("-" * 40)
                        print(stderr.decode())

        except Exception as e:
            if self.console:
                self.console.print(f"[red]❌ Error running example: {e}[/red]")
            else:
                print(f"❌ Error running example: {e}")

    async def run(self):
        """Run the interactive demo."""
        self._print_banner()

        if not self._check_prerequisites():
            return 1

        while True:
            self._display_examples_table()
            choice = self._get_user_choice()

            if choice is None:
                if self.console:
                    self.console.print(
                        "\n[blue]👋 Thanks for exploring Arcade.dev examples![/blue]"
                    )
                else:
                    print("\n👋 Thanks for exploring Arcade.dev examples!")
                break

            if 1 <= choice <= len(self.examples):
                example = self.examples[choice - 1]
                await self._run_example(example)

                if self.console:
                    if not Confirm.ask("\nRun another example?"):
                        break
                else:
                    response = input("\nRun another example? (y/N): ")
                    if response.lower() != "y":
                        break
            else:
                if self.console:
                    self.console.print("[red]Invalid choice. Please try again.[/red]")
                else:
                    print("Invalid choice. Please try again.")

        return 0


async def main():
    """Main function."""
    # Setup basic logging
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise in interactive mode
        format="%(levelname)s: %(message)s",
    )

    # Check for rich dependency
    if not HAS_RICH:
        print("⚠️  For the best experience, install 'rich': pip install rich")
        print("Continuing with basic text interface...\n")

    demo = InteractiveDemo()
    return await demo.run()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
        sys.exit(0)
