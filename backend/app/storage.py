"""Chiffrement Fernet + lecture/ecriture des documents sur le filesystem."""
import hashlib
import uuid
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class StorageError(Exception):
    pass


def _fernet() -> Fernet:
    return Fernet(get_settings().file_encryption_key.encode())


def _root() -> Path:
    root = Path(get_settings().documents_storage_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def encrypt_and_store(plaintext: bytes) -> tuple[str, str, int]:
    """Chiffre et persiste un fichier. Retourne (path_relatif, sha256, taille_octets)."""
    sha256 = hashlib.sha256(plaintext).hexdigest()
    size = len(plaintext)
    encrypted = _fernet().encrypt(plaintext)
    name = f"{uuid.uuid4()}.enc"
    abs_path = _root() / name
    abs_path.write_bytes(encrypted)
    return name, sha256, size


def delete_file(relative_path: str) -> bool:
    """Efface le fichier chiffre d'une version supprimee. Renvoie True si efface.

    Un fichier deja absent n'est pas une erreur : on veut que la ligne parte de
    la base meme si le fichier a disparu du disque, sinon la fiche resterait
    bloquee sur un document impossible a retirer.
    """
    abs_path = _root() / relative_path
    if not abs_path.is_file():
        return False
    abs_path.unlink()
    return True


def decrypt_and_read(relative_path: str) -> bytes:
    abs_path = _root() / relative_path
    if not abs_path.is_file():
        raise StorageError(f"Fichier introuvable : {relative_path}")
    try:
        return _fernet().decrypt(abs_path.read_bytes())
    except InvalidToken as exc:
        raise StorageError("Echec du dechiffrement (cle incorrecte ou fichier corrompu)") from exc
