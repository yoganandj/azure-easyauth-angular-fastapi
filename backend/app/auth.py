import base64
import json
import os
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status

ALLOW_DEV_AUTH = os.getenv("ALLOW_DEV_AUTH", "false").lower() in ("1", "true", "yes")


def build_mock_easy_auth_header(
    user_id: str,
    name: str,
    username: str,
    roles: list[str] | None = None,
) -> str:
    """Helper to generate a valid base64-encoded x-ms-client-principal header for testing."""
    roles = roles or ["Reader"]
    payload = {
        "auth_typ": "aad",
        "claims": [
            {"typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier", "val": user_id},
            {"typ": "name", "val": name},
            {"typ": "preferred_username", "val": username},
            *[{"typ": "roles", "val": role} for role in roles],
        ],
        "name_typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        "role_typ": "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
        "userId": user_id,
        "userRoles": ["authenticated", *roles],
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def _decode_easy_auth_principal(encoded: str) -> dict[str, Any]:
    """Decode the x-ms-client-principal JSON payload supplied by App Service Easy Auth."""
    padded = encoded + "=" * (-len(encoded) % 4)
    raw = base64.b64decode(padded)
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Invalid Easy Auth principal")
    return value


def get_principal(request: Request) -> dict[str, Any]:
    """
    Return a principal populated by Azure App Service Easy Auth.

    The x-ms-client-principal header must only be trusted when the request passes
    through the App Service authentication module. Never accept an arbitrary user-created
    identity header in production.
    """
    encoded = request.headers.get("x-ms-client-principal")
    if not encoded:
        # Dev fallback when ALLOW_DEV_AUTH is explicitly enabled for local development
        if ALLOW_DEV_AUTH:
            return {
                "auth_typ": "aad-local-dev",
                "userId": "dev-user-001",
                "claims": [
                    {"typ": "name", "val": "Local Dev User"},
                    {"typ": "preferred_username", "val": "dev-user@example.com"},
                    {"typ": "roles", "val": "Admin"},
                    {"typ": "roles", "val": "Reader"},
                ],
                "userRoles": ["authenticated", "Admin", "Reader"],
            }

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        principal = _decode_easy_auth_principal(encoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, base64.binascii.Error):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication principal",
        )

    # A principal should contain at least an identity provider and claims or userId.
    if not principal.get("claims") and not principal.get("userId"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication principal",
        )
    return principal


def _claim_values(principal: dict[str, Any], *claim_types: str) -> list[str]:
    wanted = {item.lower() for item in claim_types}
    values: list[str] = []
    for claim in principal.get("claims", []):
        if not isinstance(claim, dict):
            continue
        claim_type = str(claim.get("typ", "")).lower()
        if claim_type in wanted or any(claim_type.endswith("/" + item) for item in wanted):
            value = claim.get("val")
            if isinstance(value, str):
                values.extend(part for part in value.split(",") if part)
    return values


def get_roles(principal: dict[str, Any]) -> set[str]:
    role_claims = _claim_values(
        principal,
        "roles",
        "role",
        "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
    )
    direct = principal.get("roles", [])
    if isinstance(direct, str):
        role_claims.extend(direct.split(","))
    elif isinstance(direct, list):
        role_claims.extend(str(role) for role in direct)
    return {role.strip() for role in role_claims if role.strip()}


def require_role(required_role: str) -> Callable:
    def dependency(principal: dict[str, Any] = Depends(get_principal)) -> dict[str, Any]:
        if required_role not in get_roles(principal):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' is required",
            )
        return principal
    return dependency


def safe_user_summary(principal: dict[str, Any]) -> dict[str, Any]:
    """Return a deliberately small identity summary; avoid returning all claims by default."""
    def first_claim(*types: str) -> str | None:
        vals = _claim_values(principal, *types)
        return vals[0] if vals else None

    user_id = principal.get("userId") or first_claim(
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
        "sub",
        "oid",
    )
    name = first_claim("name", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name")
    username = first_claim(
        "preferred_username",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    )

    return {
        "authenticated": True,
        "user_id": user_id or "unknown-user",
        "provider": principal.get("auth_typ") or principal.get("identityProvider"),
        "name": name or username or "Authenticated User",
        "username": username or name or user_id or "unknown",
        "roles": sorted(get_roles(principal)),
    }


def get_current_user(principal: dict[str, Any] = Depends(get_principal)) -> dict[str, Any]:
    """Dependency to retrieve the authenticated user profile derived solely from Easy Auth."""
    return safe_user_summary(principal)
