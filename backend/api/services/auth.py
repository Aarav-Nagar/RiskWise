from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from ..settings import settings
from .store import store


@dataclass(frozen=True)
class AuthIdentity:
    clerk_user_id: str
    claims: dict[str, Any]
    mode: str = "clerk"


_jwks_clients: dict[str, PyJWKClient] = {}


def auth_config_status() -> dict[str, Any]:
    production = settings.environment == "production"
    jwks_url = clerk_jwks_url()
    return {
        "required": production,
        "configured": bool(jwks_url),
        "issuer_configured": bool(settings.clerk_issuer),
        "jwks_configured": bool(jwks_url),
        "audience_configured": bool(settings.clerk_audience),
        "authorized_parties_configured": bool(settings.clerk_authorized_parties),
        "mode": "clerk_jwt" if production else "dev_or_clerk_jwt",
    }


def clerk_jwks_url() -> str:
    if settings.clerk_jwks_url:
        return settings.clerk_jwks_url
    if settings.clerk_issuer:
        return f"{settings.clerk_issuer}/.well-known/jwks.json"
    return ""


def require_request_user(user_id: str | None, request: Request | None = None) -> AuthIdentity | None:
    clean_user_id = require_user_id(user_id)
    identity = authenticate_request(request)
    if identity is None:
        return None
    assert_profile_owner(clean_user_id, identity)
    return identity


def require_clerk_subject(clerk_id: str | None, request: Request | None = None) -> AuthIdentity | None:
    clean_clerk_id = require_user_id(clerk_id)
    identity = authenticate_request(request)
    if identity is None:
        return None
    if identity.clerk_user_id != clean_clerk_id:
        raise HTTPException(status_code=403, detail="Authenticated Clerk session does not match this profile.")
    return identity


def require_profile_lookup_owner(user: dict[str, Any], request: Request | None = None) -> AuthIdentity | None:
    identity = authenticate_request(request)
    if identity is None:
        return None
    clerk_id = str(user.get("clerkId") or "").strip()
    if clerk_id:
        if clerk_id != identity.clerk_user_id:
            raise HTTPException(status_code=403, detail="Authenticated user does not match this profile.")
        return identity
    token_email = str(identity.claims.get("email") or identity.claims.get("primary_email") or "").lower()
    profile_email = str(user.get("email") or "").lower()
    if token_email and token_email == profile_email:
        return identity
    raise HTTPException(status_code=403, detail="Authenticated user does not match this profile.")


def authenticate_request(request: Request | None) -> AuthIdentity | None:
    if settings.environment != "production" and not bearer_token_from_request(request):
        return None
    token = bearer_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authorization bearer token is required.")
    return verify_clerk_session_token(token)


def verify_clerk_session_token(token: str) -> AuthIdentity:
    jwks_url = clerk_jwks_url()
    if not jwks_url:
        raise HTTPException(status_code=401, detail="Clerk JWT verification is not configured.")
    try:
        signing_key = jwks_client(jwks_url).get_signing_key_from_jwt(token)
        decode_kwargs: dict[str, Any] = {
            "key": signing_key.key,
            "algorithms": ["RS256"],
            "leeway": settings.clerk_jwt_leeway_seconds,
            "options": {"require": ["exp", "iat", "sub"]},
        }
        if settings.clerk_issuer:
            decode_kwargs["issuer"] = settings.clerk_issuer
        if settings.clerk_audience:
            decode_kwargs["audience"] = settings.clerk_audience
        else:
            decode_kwargs["options"]["verify_aud"] = False
        claims = jwt.decode(token, **decode_kwargs)
    except (InvalidTokenError, PyJWKClientError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired Clerk session token.") from exc

    subject = str(claims.get("sub") or "").strip()
    if not subject:
        raise HTTPException(status_code=401, detail="Invalid Clerk session token.")
    authorized_party = str(claims.get("azp") or "").strip()
    if settings.clerk_authorized_parties and authorized_party not in settings.clerk_authorized_parties:
        raise HTTPException(status_code=401, detail="Clerk token authorized party is not allowed.")
    return AuthIdentity(clerk_user_id=subject, claims=claims)


def assert_profile_owner(user_id: str, identity: AuthIdentity) -> None:
    user = store.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="RiskWise profile was not found.")
    clerk_id = str(user.get("clerkId") or "").strip()
    if not clerk_id:
        raise HTTPException(status_code=403, detail="RiskWise profile is not linked to Clerk.")
    if clerk_id != identity.clerk_user_id:
        raise HTTPException(status_code=403, detail="Authenticated user does not match this profile.")


def bearer_token_from_request(request: Request | None) -> str:
    if request is None:
        return ""
    value = (request.headers.get("Authorization") or "").strip()
    if not value:
        return ""
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authorization bearer token is required.")
    return token.strip()


def require_user_id(user_id: str | None) -> str:
    clean_user_id = str(user_id or "").strip()
    if len(clean_user_id) < 3:
        raise HTTPException(status_code=401, detail="A signed-in RiskWise profile is required for this action.")
    return clean_user_id


def jwks_client(jwks_url: str) -> PyJWKClient:
    client = _jwks_clients.get(jwks_url)
    if not client:
        client = PyJWKClient(jwks_url)
        _jwks_clients[jwks_url] = client
    return client
