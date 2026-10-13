"""No API route lets a request choose which configuration file to load.

The rule this turns on: **a request-controlled config path lets the request supply
the limits that are then enforced against it.**

It was a complete bypass on the swarm route, where the file supplies `max_agents`,
`max_concurrent`, `max_swarms_per_day`, `max_concurrent_swarms` and the budget
ceiling, all of which `apply_swarm_options` and `_enforce_swarm_limits` read back.
It was a smaller one on the scan route, where the file supplies
`detection.agentic.max_tokens_per_scan` and `max_cost_usd_per_scan`, which
`enforce_plan_budget` checks the request against.

Both are fixed. This test covers every route module rather than those two, because
the next request model to grow a config field would reintroduce the same bug
somewhere nobody is looking.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import pytest
from pydantic import BaseModel

import agentarmor.api.routes as routes_pkg

# Names that would hand a request control over which file is loaded.
FORBIDDEN = {
    "config_path",
    "config_file",
    "configpath",
    "settings_path",
    "settings_file",
    "toml_path",
    "config",
}


def _route_modules():
    for info in pkgutil.iter_modules(routes_pkg.__path__):
        yield importlib.import_module(f"{routes_pkg.__name__}.{info.name}")


def _request_models():
    """Every Pydantic model defined in a route module."""
    seen: set[int] = set()
    for module in _route_modules():
        for name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseModel)
                and obj is not BaseModel
                and obj.__module__ == module.__name__
                and id(obj) not in seen
            ):
                seen.add(id(obj))
                yield module.__name__, name, obj


def test_there_are_route_models_to_check():
    """Guards the guard: a broken discovery would make every assertion vacuous."""
    models = list(_request_models())
    assert len(models) >= 3, models
    names = {name for _mod, name, _obj in models}
    assert "ScanCreateRequest" in names
    assert "SwarmCreateRequest" in names


@pytest.mark.parametrize(
    "module_name,model_name,model",
    [(m, n, o) for m, n, o in _request_models()],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_no_request_model_accepts_a_config_path(module_name, model_name, model):
    offending = FORBIDDEN & set(model.model_fields)
    assert not offending, (
        f"{module_name}.{model_name} accepts {sorted(offending)}. "
        "A request-controlled config path supplies the limits enforced against it."
    )


def test_every_route_module_loads_its_config_from_the_environment():
    """`_config_path` comes from AGENTARMOR_CONFIG, never from a request."""
    for module in _route_modules():
        source = inspect.getsource(module)
        if "load_config(" not in source:
            continue
        assert "body.config_path" not in source, (
            f"{module.__name__} still loads a config path off the request body"
        )
