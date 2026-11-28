"""Regras de negócio da carteira de ativos, independentes da camada HTTP."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, AssetType, User, UserRole
from app.services.auth_service import get_user_by_email


@dataclass(frozen=True)
class NewAsset:
    """Dados de um novo ativo, como a regra de negócio os entende (US04, US07).

    O service define o que precisa receber; quem chama (a rota HTTP hoje, o coletor da RPI
    amanhã) converte o próprio formato para este. Assim o service não depende do schema da API.
    """

    title: str
    asset_type: AssetType
    process_number: str
    deposit_date: date
    status: str
    authors: str
    author_email: str | None = None


class AssetServiceError(Exception):
    """Erro de regra de negócio, com mensagem pronta para o usuário."""


class DuplicateProcessError(AssetServiceError):
    pass


class AuthorNotFoundError(AssetServiceError):
    pass


def list_assets_for(db: Session, user: User) -> Sequence[Asset]:
    """NIT vê a carteira inteira; AUTOR vê apenas os ativos vinculados a ele (US03, US06)."""
    query = select(Asset).options(selectinload(Asset.author_user)).order_by(Asset.deposit_date.desc(), Asset.id.desc())
    if user.role != UserRole.NIT:
        query = query.where(Asset.author_user_id == user.id)
    return db.scalars(query).all()


def _duplicate_message(process_number: str) -> str:
    """Mensagem de processo já cadastrado, igual no cadastro e na corrida do commit."""
    return f"Já existe um ativo cadastrado com o processo {process_number}."


def _resolve_author(db: Session, author_email: str | None) -> User | None:
    """Busca o usuário AUTOR a vincular (US07). Sem e-mail, não há vínculo.

    Levanta AuthorNotFoundError se o e-mail não existe ou é de um usuário que não é AUTOR.
    """
    if not author_email:
        return None
    author_user = get_user_by_email(db, author_email)
    if author_user is None or author_user.role != UserRole.AUTOR:
        raise AuthorNotFoundError(f"Nenhum usuário com perfil AUTOR encontrado com o e-mail {author_email}.")
    return author_user


def create_asset(db: Session, data: NewAsset) -> Asset:
    """Cadastra um novo ativo (US04), opcionalmente vinculando um autor (US07)."""
    if db.scalar(select(Asset.id).where(Asset.process_number == data.process_number)) is not None:
        raise DuplicateProcessError(_duplicate_message(data.process_number))

    author_user = _resolve_author(db, data.author_email)

    asset = Asset(
        title=data.title,
        asset_type=data.asset_type,
        process_number=data.process_number,
        deposit_date=data.deposit_date,
        status=data.status,
        authors=data.authors,
        author_user=author_user,
    )
    db.add(asset)
    try:
        db.commit()
    except IntegrityError as exc:
        # Cobre a corrida entre a checagem acima e o INSERT (duas requisições simultâneas).
        db.rollback()
        raise DuplicateProcessError(_duplicate_message(data.process_number)) from exc
    db.refresh(asset)
    return asset
