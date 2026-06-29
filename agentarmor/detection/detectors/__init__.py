"""Detector plugin integration."""

from agentarmor.detection.detectors.registry import (
    discover_detector_plugins,
    reset_detector_discovery,
    run_detector_plugins,
)

__all__ = ["discover_detector_plugins", "reset_detector_discovery", "run_detector_plugins"]
