"""
Modelos Pydantic para representación y validación de repositorios de GitHub.
"""

import re

from pydantic import BaseModel, Field, field_validator


class RepoTarget(BaseModel):
    """
    Representa un repositorio objetivo de GitHub con su propietario y nombre.

    Permite instanciar y validar a partir de cadenas en formato 'owner/repo'
    o URLs completas de GitHub (ej. 'https://github.com/owner/repo').
    """

    owner: str = Field(..., description="Propietario u organización del repositorio")
    name: str = Field(..., description="Nombre del repositorio")

    @property
    def full_name(self) -> str:
        """Retorna el identificador canónico 'owner/name'."""
        return f"{self.owner}/{self.name}"

    @property
    def url(self) -> str:
        """Retorna la URL canónica del repositorio en GitHub."""
        return f"https://github.com/{self.owner}/{self.name}"

    @field_validator("owner", "name")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El identificador del repositorio no puede estar vacío.")
        if "/" in cleaned or "\\" in cleaned:
            raise ValueError(f"El identificador '{value}' no debe contener separadores de ruta.")
        return cleaned

    @classmethod
    def from_raw(cls, raw: str | object) -> "RepoTarget":
        """
        Construye una instancia de RepoTarget a partir de una cadena con formato
        'owner/repo' o una URL de GitHub completa.

        Formatos soportados:
            - 'torvalds/linux'
            - 'https://github.com/owner/repo'
            - 'http://github.com/owner/repo.git'
            - 'git@github.com:owner/repo.git'
            - 'https://github.com/owner/repo/tree/main'

        Args:
            raw: Cadena de texto a procesar.

        Returns:
            RepoTarget: Instancia validada con owner y name.

        Raises:
            ValueError: Si la cadena no puede ser analizada como un repositorio de GitHub válido.
        """
        if not isinstance(raw, str):
            raise ValueError(f"Se esperaba una cadena de texto, recibido: {type(raw).__name__}")

        text = raw.strip()
        if not text:
            raise ValueError("El texto del repositorio no puede estar vacío.")

        # Manejo de formato SSH: git@github.com:owner/repo.git
        ssh_match = re.match(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", text)
        if ssh_match:
            return cls(owner=ssh_match.group(1), name=ssh_match.group(2))

        # Si es una URL http/https, validar que pertenezca a github.com
        if re.match(r"^https?://", text):
            if not re.match(r"^https?://(?:www\.)?github\.com/", text):
                raise ValueError(f"Dominio no soportado en URL: '{raw}'. Solo se admite github.com.")
            text = re.sub(r"^https?://(?:www\.)?github\.com/", "", text)
        else:
            # Remover github.com/ si viene sin protocolo
            text = re.sub(r"^(?:www\.)?github\.com/", "", text)

        # Eliminar sufijo .git
        text = re.sub(r"\.git$", "", text)

        # Separar partes por /
        parts = [part for part in text.strip("/").split("/") if part]
        if len(parts) < 2:
            raise ValueError(
                f"Formato de repositorio inválido: '{raw}'. "
                "Se esperaba 'owner/repo' o una URL de GitHub."
            )

        owner = parts[0]
        name = parts[1]

        # Eliminar .git si persiste en el nombre
        if name.endswith(".git"):
            name = name[:-4]

        return cls(owner=owner, name=name)

    def __hash__(self) -> int:
        return hash((self.owner.lower(), self.name.lower()))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RepoTarget):
            return (
                self.owner.lower() == other.owner.lower()
                and self.name.lower() == other.name.lower()
            )
        return False

    def __str__(self) -> str:
        return self.full_name
