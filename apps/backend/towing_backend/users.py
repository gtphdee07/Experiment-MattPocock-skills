"""The `AccountManager` - fastapi-users' extension point for this app's two
account-specific behaviors: Garage auto-provisioning on registration, and
the minimum-password-length policy.
"""

from __future__ import annotations

from fastapi import Request
from fastapi_users import BaseUserManager, IntegerIDMixin, exceptions, schemas
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from towing_backend import garages
from towing_backend.models import Account

MIN_PASSWORD_LENGTH = 8


class AccountManager(IntegerIDMixin, BaseUserManager[Account, int]):
    """`BaseUserManager` for `Account`.

    Takes the same `AsyncSession` the request's `SQLAlchemyUserDatabase` is
    using (rather than reaching into `user_db.session`, an implementation
    detail of that adapter) so `on_after_register`'s Garage insert commits
    in the same request/transaction as the Account row it depends on.
    """

    def __init__(
        self,
        user_db: SQLAlchemyUserDatabase[Account, int],
        session: AsyncSession,
        secret: str,
    ) -> None:
        super().__init__(user_db)
        self._session = session
        # Deferred features (ADR 0011 consequence) still require these
        # attributes to be set - ADR 0018 Story 21 keeps email
        # verification/password-reset explicitly deferred, not silently
        # dropped, so these secrets exist but no route ever sends the mail.
        self.reset_password_token_secret = secret
        self.verification_token_secret = secret

    async def validate_password(
        self, password: str, user: schemas.BaseUserCreate | Account
    ) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise exceptions.InvalidPasswordException(
                reason=(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
            )

    async def on_after_register(
        self, account: Account, request: Request | None = None
    ) -> None:
        await garages.create_garage(self._session, account_id=account.id)
        await self._session.commit()
