"""
Gestión de configuración y variables de entorno para PeakyMiner.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carga variables de entorno desde el archivo .env en el directorio actual o raíz
load_dotenv(dotenv_path=Path(".env"), override=False)


class ConfigurationError(Exception):
    """Excepción lanzada cuando falta una configuración obligatoria o es inválida."""
    pass


def get_github_token(cli_token: str | None = None) -> str:
    """
    Obtiene el token de GitHub para autenticar las peticiones a la API GraphQL.

    Prioridad de resolución:
        1. Token suministrado explícitamente vía CLI (`cli_token`).
        2. Variable de entorno `GITHUB_TOKEN` del sistema.
        3. Variable `GITHUB_TOKEN` en archivo `.env`.

    Args:
        cli_token: Token opcional suministrado por el usuario vía línea de comandos.

    Returns:
        str: Token de autenticación de GitHub válido.

    Raises:
        ConfigurationError: Si no se encuentra un token configurado.
    """
    token = cli_token or os.getenv("GITHUB_TOKEN")
    if not token or not token.strip():
        raise ConfigurationError(
            "No se encontró un token de GitHub configurado.\n"
            "Solución: Cree un archivo .env basado en .env.example con 'GITHUB_TOKEN=tu_token' "
            "o use la opción '--token tu_token' en el comando CLI."
        )
    return token.strip()

