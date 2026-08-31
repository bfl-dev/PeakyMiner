"""
Punto de entrada de la interfaz de línea de comandos (CLI) para PeakyMiner.
"""

import asyncio
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from src import __version__
from src.config import ConfigurationError, get_github_token
from src.csv_processor import load_repositories_from_csv, save_results_to_csv
from src.github_client import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubRateLimitError,
    check_repositories_ghaw,
)

app = typer.Typer(
    name="pkminer",
    help="⛏️ PeakyMiner: Detector automatizado de GitHub Agentic Workflows (GH-AW) en repositorios.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


async def _run_miner_async(
    input_csv: Path,
    output_csv: Path,
    batch_size: int,
    concurrency: int,
    filter_positive: bool,
    token_str: str,
) -> int:
    """Función interna asíncrona que orquesta la lectura, escaneo y guardado."""
    # 1. Cargar repositorios desde el CSV
    try:
        df, repo_col, valid_targets = load_repositories_from_csv(input_csv)
    except Exception as e:
        console.print(f"[bold red]Error al leer CSV:[/bold red] {e}")
        return 1

    unique_repos = list({t for _, t in valid_targets})
    total_valid = len(valid_targets)
    total_unique = len(unique_repos)

    console.print(
        f"[cyan]ℹ️ Archivo cargado:[/cyan] {input_csv} "
        f"([bold]{total_valid}[/bold] filas analizadas, [bold]{total_unique}[/bold] repositorios únicos)"
    )

    # 2. Configurar barra de progreso Rich
    start_time = time.time()
    results: dict[str, bool] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[green]Analizando repositorios con GraphQL...", total=total_unique)

        def on_batch_progress(completed: int, total: int) -> None:
            progress.update(task, completed=completed)

        try:
            results = await check_repositories_ghaw(
                repos=unique_repos,
                token=token_str,
                batch_size=batch_size,
                max_concurrency=concurrency,
                on_batch_complete=on_batch_progress,
            )
        except GitHubAuthError as e:
            console.print(f"\n[bold red]Error de Autenticación:[/bold red] {e}")
            return 1
        except GitHubRateLimitError as e:
            console.print(f"\n[bold red]Límite de Tasa Alcanzado:[/bold red] {e}")
            return 1
        except GitHubAPIError as e:
            console.print(f"\n[bold red]Error de API de GitHub:[/bold red] {e}")
            return 1

    elapsed = time.time() - start_time

    # 3. Guardar resultados
    saved_count = save_results_to_csv(
        df=df,
        repo_col=repo_col,
        results=results,
        output_path=output_csv,
        filter_positive_only=filter_positive,
    )

    # 4. Resumen de resultados en tabla
    positive_count = sum(1 for res in results.values() if res)
    negative_count = total_unique - positive_count

    table = Table(title="📊 Resumen de Ejecución PeakyMiner", show_header=True, header_style="bold magenta")
    table.add_column("Métrica", style="dim", width=30)
    table.add_column("Valor", justify="right")

    table.add_row("Total repositorios únicos", str(total_unique))
    table.add_row("GH-AW Detectados ✅", f"[bold green]{positive_count}[/bold green]")
    table.add_row("GH-AW No detectados ❌", str(negative_count))
    table.add_row("Registros exportados", f"[bold]{saved_count}[/bold]")
    table.add_row("Archivo de salida", f"[cyan]{output_csv.resolve()}[/cyan]")
    table.add_row("Tiempo de ejecución", f"{elapsed:.2f} s")

    console.print()
    console.print(table)
    console.print("\n[bold green]✨ Proceso finalizado con éxito.[/bold green]\n")
    return 0


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold cyan]PeakyMiner (pkminer)[/bold cyan] versión [bold]{__version__}[/bold]")
        raise typer.Exit(code=0)


@app.command()
def main(
    input_csv: Path = typer.Argument(
        ...,
        help="Ruta al archivo CSV de entrada con la lista de repositorios.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output: Path = typer.Option(
        Path("output.csv"),
        "--output",
        "-o",
        help="Ruta donde se guardará el archivo CSV resultante.",
    ),
    batch_size: int = typer.Option(
        25,
        "--batch-size",
        "-b",
        help="Cantidad de repositorios por consulta GraphQL (lote).",
        min=1,
        max=50,
    ),
    concurrency: int = typer.Option(
        5,
        "--concurrency",
        "-c",
        help="Número máximo de consultas concurrentes simultáneas.",
        min=1,
        max=20,
    ),
    filter_positive: bool = typer.Option(
        False,
        "--filter-positive",
        "-f",
        help="Exportar únicamente los repositorios donde se detectó GH-AW.",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        "-t",
        help="Token de acceso personal de GitHub (anula el valor en .env).",
        envvar="GITHUB_TOKEN",
    ),
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Muestra la versión instalada de PeakyMiner.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """
    ⛏️ PeakyMiner CLI: Analiza repositorios de GitHub para identificar si utilizan GitHub Agentic Workflows.
    """

    # Validar token
    try:
        token_str = get_github_token(token)
    except ConfigurationError as e:
        console.print(Panel(f"[bold red]{e}[/bold red]", title="❌ Configuración Requerida", border_style="red"))
        raise typer.Exit(code=1) from e

    exit_code = asyncio.run(
        _run_miner_async(
            input_csv=input_csv,
            output_csv=output,
            batch_size=batch_size,
            concurrency=concurrency,
            filter_positive=filter_positive,
            token_str=token_str,
        )
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


if __name__ == "__main__":
    app()
