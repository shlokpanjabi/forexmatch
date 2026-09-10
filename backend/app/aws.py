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
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

#: Refresh a little before expiry so an in-flight request cannot age out.
REFRESH_MARGIN = timedelta(minutes=5)

_lock = threading.Lock()
_cached: dict[str, Any] = {}


def _oidc_token() -> str | None:
    return os.environ.get("VERCEL_OIDC_TOKEN") or None


def _role_arn() -> str | None:
    return os.environ.get("AWS_ROLE_ARN") or None


def uses_web_identity() -> bool:
    return bool(_oidc_token() and _role_arn())


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
