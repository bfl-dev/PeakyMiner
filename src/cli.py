"""
Punto de entrada de la interfaz de línea de comandos (CLI) para PeakyMiner.
Incluye persistencia ante fallos, reanudación desde checkpoints y menú interactivo de terminación.
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
from src.state import StateManager

app = typer.Typer(
    name="pkminer",
    help="⛏️ PeakyMiner: Detector automatizado de GitHub Agentic Workflows (GH-AW) en repositorios.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


def show_interruption_menu(completed: int, total: int) -> str:
    """
    Despliega un menú interactivo para que el usuario decida qué acción tomar al pausar/interrumpir.
    """
    console.print()
    console.print(
        Panel(
            f"[bold yellow]Se ha solicitado la interrupción del escaneo.[/bold yellow]\n\n"
            f"📊 Progreso actual: [bold]{completed}/{total}[/bold] repositorios analizados.\n"
            f"💾 El estado actual se encuentra guardado en el checkpoint.\n\n"
            f"[bold]Seleccione una acción:[/bold]\n"
            f"  [cyan][1][/cyan] [bold]Guardar resultados parciales y salir[/bold] (Exporta CSV parcial y conserva checkpoint)\n"
            f"  [cyan][2][/cyan] [bold]Reanudar escaneo[/bold] (Continúa el proceso desde el punto actual)\n"
            f"  [cyan][3][/cyan] [bold]Cancelar y descartar salida[/bold] (Finaliza sin modificar el CSV de salida)",
            title="⏸️ Menú de Terminación / Pausa",
            border_style="yellow",
        )
    )
    try:
        choice = typer.prompt("Opción", default="1", show_default=True)
        return choice.strip()
    except (EOFError, KeyboardInterrupt):
        return "1"


def print_summary_table(
    total_unique: int,
    results: dict[str, bool],
    saved_count: int,
    output_csv: Path,
    elapsed: float,
    is_partial: bool = False,
) -> None:
    """Imprime una tabla formateada con el resumen de la ejecución."""
    positive_count = sum(1 for res in results.values() if res)
    evaluated_count = len(results)
    negative_count = evaluated_count - positive_count
    pending_count = total_unique - evaluated_count

    title_suffix = " (Parcial)" if is_partial else ""
    table = Table(
        title=f"📊 Resumen de Ejecución PeakyMiner{title_suffix}",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Métrica", style="dim", width=30)
    table.add_column("Valor", justify="right")

    table.add_row("Total repositorios en entrada", str(total_unique))
    table.add_row("Repositorios evaluados", str(evaluated_count))
    if pending_count > 0:
        table.add_row("Pendientes por evaluar", f"[yellow]{pending_count}[/yellow]")
    table.add_row("GH-AW Detectados ✅", f"[bold green]{positive_count}[/bold green]")
    table.add_row("GH-AW No detectados ❌", str(negative_count))
    table.add_row("Registros exportados", f"[bold]{saved_count}[/bold]")
    table.add_row("Archivo de salida", f"[cyan]{output_csv.resolve()}[/cyan]")
    table.add_row("Tiempo transcurrido", f"{elapsed:.2f} s")

    console.print()
    console.print(table)


async def _run_miner_async(
    input_csv: Path,
    output_csv: Path,
    batch_size: int,
    concurrency: int,
    filter_positive: bool,
    token_str: str,
    resume: bool,
    checkpoint_path: Path | None,
) -> int:
    """Función interna asíncrona que orquesta la lectura, escaneo, persistencia y guardado."""
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

    # 2. Inicializar StateManager para persistencia
    state_mgr = StateManager(input_file=input_csv, custom_checkpoint_path=checkpoint_path)
    accumulated_results: dict[str, bool] = {}

    if resume and state_mgr.has_checkpoint():
        accumulated_results = state_mgr.load_checkpoint()
        console.print(
            f"[bold cyan]🔄 Checkpoint detectado:[/bold cyan] Reanudando con "
            f"[bold green]{len(accumulated_results)}/{total_unique}[/bold green] repositorios ya analizados."
        )
    elif not resume and state_mgr.has_checkpoint():
        state_mgr.delete_checkpoint()
        console.print("[dim]Se descartó el checkpoint previo debido a la opción --no-resume.[/dim]")

    start_time = time.time()

    # 3. Bucle de ejecución con soporte para pausas/interrupciones
    while True:
        cancel_event = asyncio.Event()

        def on_batch_success(current_state: dict[str, bool]) -> None:
            state_mgr.save_checkpoint(
                results=current_state,
                total_repos=total_unique,
            )

        interrupted = False

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "[green]Analizando repositorios con GraphQL...",
                total=total_unique,
                completed=len(accumulated_results),
            )

            def on_batch_progress(completed: int, total: int, current_task=task) -> None:
                progress.update(current_task, completed=completed)

            try:
                accumulated_results = await check_repositories_ghaw(
                    repos=unique_repos,
                    token=token_str,
                    batch_size=batch_size,
                    max_concurrency=concurrency,
                    on_batch_complete=on_batch_progress,
                    initial_results=accumulated_results,
                    on_batch_success=on_batch_success,
                    cancel_event=cancel_event,
                )
            except KeyboardInterrupt:
                cancel_event.set()
                interrupted = True
            except GitHubAuthError as e:
                console.print(f"\n[bold red]Error de Autenticación:[/bold red] {e}")
                _persist_emergency_state(df, repo_col, accumulated_results, output_csv, filter_positive, state_mgr, total_unique, input_csv)
                return 1
            except GitHubRateLimitError as e:
                console.print(f"\n[bold red]Límite de Tasa Alcanzado:[/bold red] {e}")
                _persist_emergency_state(df, repo_col, accumulated_results, output_csv, filter_positive, state_mgr, total_unique, input_csv)
                return 1
            except GitHubAPIError as e:
                console.print(f"\n[bold red]Error de API de GitHub:[/bold red] {e}")
                _persist_emergency_state(df, repo_col, accumulated_results, output_csv, filter_positive, state_mgr, total_unique, input_csv)
                return 1
            except Exception as e:
                console.print(f"\n[bold red]Error inesperado durante el escaneo:[/bold red] {e}")
                _persist_emergency_state(df, repo_col, accumulated_results, output_csv, filter_positive, state_mgr, total_unique, input_csv)
                return 1

        if interrupted:
            # Asegurar persistencia del estado actual
            state_mgr.save_checkpoint(accumulated_results, total_unique)
            choice = show_interruption_menu(completed=len(accumulated_results), total=total_unique)

            if choice == "1":
                # Guardar resultados parciales y salir
                saved_count = save_results_to_csv(
                    df=df,
                    repo_col=repo_col,
                    results=accumulated_results,
                    output_path=output_csv,
                    filter_positive_only=filter_positive,
                )
                elapsed = time.time() - start_time
                print_summary_table(
                    total_unique=total_unique,
                    results=accumulated_results,
                    saved_count=saved_count,
                    output_csv=output_csv,
                    elapsed=elapsed,
                    is_partial=True,
                )
                console.print(
                    f"\n[bold yellow]💾 Resultados parciales guardados en '{output_csv.resolve()}'.[/bold yellow]\n"
                    f"[dim]Para reanudar más tarde ejecute: pkminer {input_csv} -o {output_csv} --resume[/dim]\n"
                )
                return 0

            elif choice == "2":
                # Reanudar escaneo en el siguiente ciclo del while
                console.print("[bold green]▶️ Reanudando escaneo...[/bold green]")
                continue

            else:
                # Cancelar y descartar salida
                console.print(
                    "\n[yellow]⚠️ Operación cancelada por el usuario. No se generó el archivo de salida final.[/yellow]\n"
                    f"[dim]El checkpoint se conserva en '{state_mgr.checkpoint_path}' por si desea reanudar luego.[/dim]\n"
                )
                return 130

        # Si no hubo interrupción, salimos del bucle
        break

    elapsed = time.time() - start_time

    # 4. Guardar resultados finales y limpiar checkpoint
    saved_count = save_results_to_csv(
        df=df,
        repo_col=repo_col,
        results=accumulated_results,
        output_path=output_csv,
        filter_positive_only=filter_positive,
    )
    state_mgr.delete_checkpoint()

    # 5. Resumen de resultados
    print_summary_table(
        total_unique=total_unique,
        results=accumulated_results,
        saved_count=saved_count,
        output_csv=output_csv,
        elapsed=elapsed,
        is_partial=False,
    )
    console.print("\n[bold green]✨ Proceso finalizado con éxito al 100%.[/bold green]\n")
    return 0


def _persist_emergency_state(
    df: object,
    repo_col: str,
    results: dict[str, bool],
    output_csv: Path,
    filter_positive: bool,
    state_mgr: StateManager,
    total_unique: int,
    input_csv: Path,
) -> None:
    """Guarda de emergencia el estado en checkpoint y en CSV si hay datos recolectados."""
    if results:
        state_mgr.save_checkpoint(results, total_unique)
        save_results_to_csv(
            df=df,  # type: ignore[arg-type]
            repo_col=repo_col,
            results=results,
            output_path=output_csv,
            filter_positive_only=filter_positive,
        )
        console.print(
            f"[yellow]💾 Se preservaron {len(results)}/{total_unique} resultados parciales en '{output_csv}'.[/yellow]\n"
            f"[cyan]💡 Para reanudar cuando se resuelva el inconveniente, ejecute:[/cyan]\n"
            f"   [bold]pkminer {input_csv} -o {output_csv} --resume[/bold]\n"
        )


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
    resume: bool = typer.Option(
        True,
        "--resume/--no-resume",
        help="Reanudar automáticamente desde el último checkpoint disponible.",
    ),
    checkpoint: Path | None = typer.Option(
        None,
        "--checkpoint",
        "-k",
        help="Ruta personalizada para el archivo de checkpoint de estado.",
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
            resume=resume,
            checkpoint_path=checkpoint,
        )
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


if __name__ == "__main__":
    app()
