"""Marketplace API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agentarmor.marketplace.catalog import get_rule, list_rules
from agentarmor.marketplace.installer import install_rule, list_installed, uninstall_rule

router = APIRouter(prefix="/v1/marketplace", tags=["marketplace"])


class InstallRequest(BaseModel):
    rule_id: str


@router.get("/rules")
def list_marketplace_rules(category: str | None = None) -> list[dict]:
    return [r.model_dump(mode="json") for r in list_rules(category=category)]


@router.get("/installed")
def list_installed_rules() -> list[dict]:
    return [r.model_dump(mode="json") for r in list_installed()]


@router.post("/install")
def install_marketplace_rule(body: InstallRequest) -> dict:
    try:
        installed = install_rule(body.rule_id)
        return installed.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/installed/{rule_id}")
def uninstall_marketplace_rule(rule_id: str) -> dict:
    if uninstall_rule(rule_id):
        return {"status": "removed", "rule_id": rule_id}
    raise HTTPException(404, "rule not installed")


@router.get("/rules/{rule_id}")
def get_marketplace_rule(rule_id: str) -> dict:
    rule = get_rule(rule_id)
    if not rule:
        raise HTTPException(404, "rule not found")
    return rule.model_dump(mode="json")
