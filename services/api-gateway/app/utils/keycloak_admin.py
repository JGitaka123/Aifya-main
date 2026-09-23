"""Keycloak Admin API client for user provisioning.

Used by the onboarding service to create facility-admin and staff users in
Keycloak (with the ``facility_id`` attribute + realm roles) and to trigger
Keycloak's built-in "set your password" / verify-email invite. Authenticates
with a confidential service-account client (``keycloak_admin_client_id`` /
``keycloak_admin_client_secret``) that holds the ``realm-management`` roles
``manage-users`` and ``manage-realm``.

External I/O is isolated here so the onboarding service stays unit-testable
(tests inject a fake client). When admin credentials are not configured,
``is_configured`` is False and the caller returns a clear 503.
"""

from __future__ import annotations

import contextlib

import httpx

from app.config import settings


class KeycloakAdminError(RuntimeError):
    """Raised when a Keycloak Admin API call fails."""


class KeycloakAdminClient:
    """Thin async wrapper over the Keycloak Admin REST API."""

    def __init__(
        self,
        base_url: str | None = None,
        realm: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.keycloak_url).rstrip("/")
        self.realm = realm or settings.keycloak_realm
        self.client_id = client_id or settings.keycloak_admin_client_id
        self.client_secret = (
            client_secret
            if client_secret is not None
            else settings.keycloak_admin_client_secret
        )

    @property
    def is_configured(self) -> bool:
        """True when an admin service-account secret is available."""
        return bool(self.client_secret)

    async def _token(self, client: httpx.AsyncClient) -> str:
        """Fetch an admin access token via client-credentials grant."""
        resp = await client.post(
            f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        if resp.status_code != 200:
            raise KeycloakAdminError(
                f"Keycloak admin token request failed: {resp.status_code}"
            )
        return str(resp.json()["access_token"])

    async def create_user(
        self,
        *,
        email: str,
        first_name: str,
        last_name: str,
        facility_id: str,
        roles: list[str],
        temporary_password: str | None = None,
        send_invite_email: bool = True,
    ) -> str:
        """
        Create a Keycloak user carrying the facility_id attribute + realm roles.

        @param email: User email (also the username)
        @param first_name: Given name
        @param last_name: Family name
        @param facility_id: Facility UUID string set as the facility_id attribute
        @param roles: Realm role names to assign
        @param temporary_password: Optional initial password (must be changed)
        @param send_invite_email: Trigger Keycloak UPDATE_PASSWORD + VERIFY_EMAIL email
        @returns The created Keycloak user id (sub)
        @raises KeycloakAdminError on any failure
        """
        if not self.is_configured:
            raise KeycloakAdminError("Keycloak admin client is not configured")

        admin = f"{self.base_url}/admin/realms/{self.realm}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            token = await self._token(client)
            headers = {"Authorization": f"Bearer {token}"}

            payload: dict = {
                "username": email,
                "email": email,
                "firstName": first_name,
                "lastName": last_name,
                "enabled": True,
                "emailVerified": False,
                "attributes": {"facility_id": [facility_id]},
            }
            resp = await client.post(
                f"{admin}/users", json=payload, headers=headers
            )
            if resp.status_code == 409:
                raise KeycloakAdminError(f"A user with email {email} already exists")
            if resp.status_code not in (201, 204):
                raise KeycloakAdminError(
                    f"Keycloak user create failed: {resp.status_code} {resp.text}"
                )
            # New user id is in the Location header; fall back to a lookup.
            user_id = resp.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
            if not user_id:
                lookup = await client.get(
                    f"{admin}/users",
                    params={"email": email, "exact": "true"},
                    headers=headers,
                )
                rows = lookup.json() if lookup.status_code == 200 else []
                if not rows:
                    raise KeycloakAdminError("Created user could not be located")
                user_id = rows[0]["id"]

            await self._assign_realm_roles(client, admin, headers, user_id, roles)

            if temporary_password:
                await client.put(
                    f"{admin}/users/{user_id}/reset-password",
                    json={
                        "type": "password",
                        "value": temporary_password,
                        "temporary": True,
                    },
                    headers=headers,
                )

            if send_invite_email:
                # Non-fatal: user is created even if the SMTP send fails.
                with contextlib.suppress(httpx.HTTPError):
                    await client.put(
                        f"{admin}/users/{user_id}/execute-actions-email",
                        params={"client_id": settings.keycloak_client_id},
                        json=["UPDATE_PASSWORD", "VERIFY_EMAIL"],
                        headers=headers,
                    )

            return user_id

    async def _assign_realm_roles(
        self,
        client: httpx.AsyncClient,
        admin: str,
        headers: dict,
        user_id: str,
        roles: list[str],
    ) -> None:
        """Resolve realm role representations and assign them to a user."""
        reps: list[dict] = []
        for role in roles:
            r = await client.get(f"{admin}/roles/{role}", headers=headers)
            if r.status_code == 200:
                reps.append(r.json())
        if reps:
            await client.post(
                f"{admin}/users/{user_id}/role-mappings/realm",
                json=reps,
                headers=headers,
            )


def get_keycloak_admin_client() -> KeycloakAdminClient:
    """FastAPI dependency: the configured Keycloak Admin client."""
    return KeycloakAdminClient()
