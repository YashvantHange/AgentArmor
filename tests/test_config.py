"""Config loading tests."""

import pytest
from pathlib import Path

from agentarmor.core.config import load_config, merge_cli_target
from agentarmor.core.models import TargetType


def test_load_default_config():
    cfg = load_config(Path("nonexistent.toml"))
    assert cfg.target.type.value == "endpoint"


def test_merge_cli_url():
    cfg = load_config()
    cfg = merge_cli_target(cfg, url="http://localhost:9999/v1/chat/completions")
    assert cfg.target.url == "http://localhost:9999/v1/chat/completions"
    assert cfg.target.type == TargetType.ENDPOINT


def test_merge_cli_provider():
    cfg = load_config()
    cfg = merge_cli_target(cfg, provider="anthropic")
    assert cfg.target.provider == "anthropic"
    assert cfg.target.type == TargetType.PROVIDER


def test_merge_cli_model():
    cfg = load_config()
    cfg = merge_cli_target(cfg, model="./models/llama.gguf")
    assert cfg.target.model == "./models/llama.gguf"
    assert cfg.target.type == TargetType.LOCAL


def test_merge_cli_mutually_exclusive():
    cfg = load_config()
    with pytest.raises(ValueError, match="Only one"):
        merge_cli_target(cfg, url="http://x", provider="openai")


def test_merge_cli_agent():
    cfg = load_config()
    cfg = merge_cli_target(cfg, agent="crewai", agent_config="agent.toml")
    assert cfg.target.agent_framework == "crewai"
    assert cfg.target.type == TargetType.AGENT


def test_merge_cli_mcp():
    cfg = load_config()
    cfg = merge_cli_target(cfg, mcp="./filesystem-mcp")
    assert cfg.target.mcp_target == "./filesystem-mcp"
    assert cfg.target.type == TargetType.MCP


def test_merge_cli_rag():
    cfg = load_config()
    cfg = merge_cli_target(cfg, rag="./corpus", embedder="bge")
    assert cfg.target.rag_corpus == "./corpus"
    assert cfg.target.type == TargetType.RAG
    assert cfg.module_rag.embedder == "bge"
