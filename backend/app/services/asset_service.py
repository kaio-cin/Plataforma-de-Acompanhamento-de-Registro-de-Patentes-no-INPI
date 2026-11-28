"""Regras de negócio da carteira de ativos, independentes da camada HTTP."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, AssetType, Dispatch, User, UserRole
from app.services.auth_service import get_user_by_email
from app.services.process_number import normalize_process_number


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


@dataclass(frozen=True)
class AssetChanges:
    """Dados da edição de um ativo (US05): substituem todos os campos.

    author_email não tem valor padrão: quem chama precisa dizer se mantém, troca ou remove o
    autor (None remove o vínculo).
    """

    title: str
    asset_type: AssetType
    process_number: str
    deposit_date: date
    status: str
    authors: str
    author_email: str | None


class AssetServiceError(Exception):
    """Erro de regra de negócio, com mensagem pronta para o usuário."""


class DuplicateProcessError(AssetServiceError):
    pass


class AuthorNotFoundError(AssetServiceError):
    pass


class AssetNotFoundError(AssetServiceError):
    """Ativo inexistente ou fora do alcance do usuário: os dois casos são tratados igual, para não revelar ids."""


class ProcessNumberLockedError(AssetServiceError):
    """O ativo já tem despachos da RPI ligados ao número atual, então o número não pode ser trocado."""


def list_assets_for(db: Session, user: User) -> Sequence[Asset]:
    """NIT vê a carteira inteira; AUTOR vê apenas os ativos vinculados a ele (US03, US06)."""
    query = select(Asset).options(selectinload(Asset.author_user)).order_by(Asset.deposit_date.desc(), Asset.id.desc())
    if user.role != UserRole.NIT:
        query = query.where(Asset.author_user_id == user.id)
    return db.scalars(query).all()


def get_asset_for(db: Session, user: User, asset_id: int) -> Asset:
    """Detalhe de um ativo (US05): NIT vê qualquer um; AUTOR só os vinculados a ele.

    Levanta AssetNotFoundError se o ativo não existe ou não é visível ao usuário.
    """
    query = select(Asset).options(selectinload(Asset.author_user)).where(Asset.id == asset_id)
    if user.role != UserRole.NIT:
        query = query.where(Asset.author_user_id == user.id)
    asset = db.scalar(query)
    if asset is None:
        raise AssetNotFoundError("Ativo não encontrado.")
    return asset


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


def update_asset(db: Session, asset_id: int, changes: AssetChanges) -> Asset:
    """Edita um ativo (US05), inclusive trocando ou removendo o autor vinculado.

    Todas as checagens vêm antes de alterar o objeto: em qualquer erro, o ativo fica como estava.
    - O número é comparado já normalizado, como no cruzamento da RPI ("BR10.2023.000001-1" é o
      mesmo processo que "BR 10 2023 000001-1"). Só há checagem quando o número normalizado muda:
      mudar só a formatação é sempre permitido.
    - Com despachos da RPI já ligados ao ativo, o número normalizado não pode mudar.
    - A natureza pode mudar mesmo com despachos: o glossário de um despacho vem da seção da RPI.

    Levanta AssetNotFoundError, DuplicateProcessError, ProcessNumberLockedError ou AuthorNotFoundError.
    """
    asset = db.scalar(select(Asset).options(selectinload(Asset.author_user)).where(Asset.id == asset_id))
    if asset is None:
        raise AssetNotFoundError("Ativo não encontrado.")

    new_key = normalize_process_number(changes.process_number)
    if new_key != normalize_process_number(asset.process_number):
        others = db.scalars(select(Asset.process_number).where(Asset.id != asset_id))
        if any(normalize_process_number(number) == new_key for number in others):
            raise DuplicateProcessError(_duplicate_message(changes.process_number))
        if db.scalar(select(Dispatch.id).where(Dispatch.asset_id == asset_id).limit(1)) is not None:
            raise ProcessNumberLockedError(
                f"Este ativo já tem despachos da RPI ligados ao processo {asset.process_number}; "
                "o número não pode ser trocado."
            )

    author_user = _resolve_author(db, changes.author_email)

    asset.title = changes.title
    asset.asset_type = changes.asset_type
    asset.process_number = changes.process_number
    asset.deposit_date = changes.deposit_date
    asset.status = changes.status
    asset.authors = changes.authors
    asset.author_user = author_user
    try:
        db.commit()
    except IntegrityError as exc:
        # Cobre a corrida com outro cadastro ou edição e o número igual, só com outra formatação,
        # a um ativo antigo "gêmeo" (a checagem acima não roda quando o número normalizado não muda).
        db.rollback()
        raise DuplicateProcessError(_duplicate_message(changes.process_number)) from exc
    db.refresh(asset)
    return asset
