"""AWS credentials.

Two environments, one rule: no long-lived access key ever exists.

Locally, boto3's standard chain handles it — `aws login`, `~/.aws`, SSO, or an
instance role. On Vercel we use OIDC federation: the platform injects a
short-lived `VERCEL_OIDC_TOKEN` identifying the deployment, and we exchange it
for temporary AWS credentials through AssumeRoleWithWebIdentity. Nothing secret
is stored in the project's environment variables, so there is no key to leak or
rotate (BUILD.md section 66).
"""

from __future__ import annotations

import os
import threading
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

#: Refresh a little before expiry so an in-flight request cannot age out.
REFRESH_MARGIN = timedelta(minutes=5)

#: Vercel delivers the OIDC token differently depending on where the code runs:
#: an environment variable during builds and local development, but a
#: per-request `x-vercel-oidc-token` header inside a Function. Middleware puts
#: the header value here for the life of the request.
OIDC_HEADER = "x-vercel-oidc-token"
_request_token: ContextVar[str | None] = ContextVar("vercel_oidc_token", default=None)

_lock = threading.Lock()
_cached: dict[str, Any] = {}


def set_request_oidc_token(token: str | None) -> object:
    """Bind the token for the current request. Returns a reset handle."""
    return _request_token.set(token or None)


def reset_request_oidc_token(handle: object) -> None:
    _request_token.reset(handle)  # type: ignore[arg-type]


def _oidc_token() -> str | None:
    return _request_token.get() or os.environ.get("VERCEL_OIDC_TOKEN") or None


def _role_arn() -> str | None:
    return os.environ.get("AWS_ROLE_ARN") or None


def uses_web_identity() -> bool:
    return bool(_oidc_token() and _role_arn())


def credential_diagnostics() -> dict[str, Any]:
    """Which pieces of the OIDC setup are present. Values are never included."""
    import os as _os

    return {
        "has_oidc_token": bool(_oidc_token()),
        "token_source": (
            "request_header" if _request_token.get() else ("env" if os.environ.get("VERCEL_OIDC_TOKEN") else None)
        ),
        "has_role_arn": bool(_role_arn()),
        "on_vercel": bool(_os.environ.get("VERCEL")),
        # Names only, so a missing token is diagnosable without exposing one.
        "vercel_oidc_env_names": sorted(
            k for k in _os.environ if "OIDC" in k.upper() or k.startswith("VERCEL_")
        )[:12],
    }


def _assume_role(region: str) -> dict[str, Any]:
    import boto3

    sts = boto3.client("sts", region_name=region)
    response = sts.assume_role_with_web_identity(
        RoleArn=_role_arn(),
        RoleSessionName=os.environ.get("VERCEL_DEPLOYMENT_ID", "forexmatch")[:64],
        WebIdentityToken=_oidc_token(),
        DurationSeconds=3600,
    )
    credentials = response["Credentials"]
    logger.info("aws.assumed_web_identity_role", expires=credentials["Expiration"].isoformat())
    return credentials


def build_session(region: str | None = None):
    """A boto3 Session with credentials appropriate to this environment."""
    import boto3

    region = region or os.environ.get("AWS_REGION") or "us-east-1"

    if not uses_web_identity():
        return boto3.Session(region_name=region)

    with _lock:
        expiry = _cached.get("expiration")
        if expiry is None or datetime.now(UTC) >= expiry - REFRESH_MARGIN:
            try:
                credentials = _assume_role(region)
            except Exception as exc:  # noqa: BLE001
                # Fall back rather than hard-fail: a misconfigured role should
                # surface as "the model is unavailable", not a 500 on every route.
                logger.warning("aws.web_identity_failed", error=str(exc))
                return boto3.Session(region_name=region)
            _cached.update(
                access_key=credentials["AccessKeyId"],
                secret_key=credentials["SecretAccessKey"],
                token=credentials["SessionToken"],
                expiration=credentials["Expiration"],
            )

        return boto3.Session(
            aws_access_key_id=_cached["access_key"],
            aws_secret_access_key=_cached["secret_key"],
            aws_session_token=_cached["token"],
            region_name=region,
        )
