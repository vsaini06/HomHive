import hmac
from collections.abc import Mapping

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


def build_household_authorizer(tokens: Mapping[str, str]):
    bearer = HTTPBearer(auto_error=False)

    def authorize(
        household_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> None:
        expected = tokens.get(household_id)
        if expected is None or credentials is None or not hmac.compare_digest(
            credentials.credentials,
            expected,
        ):
            raise HTTPException(status_code=403, detail="Access denied")

    return authorize
