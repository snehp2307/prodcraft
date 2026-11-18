"""Minimal auth stub for the demo."""

from fastapi import Header, HTTPException


def current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401)
    token = authorization.removeprefix("Bearer ")
    return {"id": token, "name": token}
