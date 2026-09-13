# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import importlib.util
import sys
import types
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"

if "core" not in sys.modules:
    core_module = types.ModuleType("core")
    core_module.__path__ = [str(CORE)]
    sys.modules["core"] = core_module


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


config = load_module("core.config", CORE / "config.py")
ParsedConfig = config.ParsedConfig
ResourceMetadata = config.ResourceMetadata
HubConfig = config.HubConfig


def test_resource_metadata_default_path_omitted_or_null_stays_none():
    assert ResourceMetadata().defaultPath is None
    assert ResourceMetadata(defaultPath=None).defaultPath is None


@pytest.mark.parametrize(
    ("default_path", "expected_message"),
    [
        ("", "defaultPath cannot be empty"),
        ("   ", "defaultPath cannot be empty"),
        ("workspace/CV", "defaultPath must be an absolute container path"),
        ("/opt/../secret", "defaultPath cannot contain '..' segments"),
        ("/opt/\x00secret", "defaultPath cannot contain NUL bytes"),
    ],
)
def test_resource_metadata_default_path_rejects_invalid_syntax(default_path: str, expected_message: str):
    with pytest.raises(ValidationError, match=expected_message):
        ResourceMetadata(defaultPath=default_path)


@pytest.mark.parametrize(
    ("default_path", "expected_path"),
    [
        ("/", "/"),
        ("/opt/workspace/CV", "/opt/workspace/CV"),
        ("/home/jovyan/", "/home/jovyan"),
        ("//opt/./workspace//CV/", "/opt/workspace/CV"),
        ("  /home/jovyan/  ", "/home/jovyan"),
    ],
)
def test_resource_metadata_default_path_normalizes_valid_paths(default_path: str, expected_path: str):
    metadata = ResourceMetadata(defaultPath=default_path)

    assert metadata.defaultPath == expected_path


def test_code_server_extra_trusted_domains_default_to_empty_list():
    parsed_config = ParsedConfig()

    assert parsed_config.codeServer.extraTrustedDomains == []


def test_code_server_extra_trusted_domains_parse_from_config():
    parsed_config = ParsedConfig.model_validate(
        {"codeServer": {"extraTrustedDomains": ["docs.example.edu", "git.example.edu"]}}
    )

    assert parsed_config.codeServer.extraTrustedDomains == ["docs.example.edu", "git.example.edu"]


def _valid_routing_config() -> HubConfig:
    instance = HubConfig()
    instance._config = ParsedConfig.model_validate(
        {
            "accelerators": {
                "nvidia": {
                    "displayName": "NVIDIA",
                    "nodeSelector": {"gpu-vendor": "nvidia"},
                },
                "amd": {
                    "displayName": "AMD",
                    "nodeSelector": {"gpu-vendor": "amd"},
                },
            },
            "acceleratorRouting": {
                "nvidia": {"vendor": "nvidia", "scheduler_name": "hami-scheduler", "runtime_class_name": "nvidia"},
                "amd": {"vendor": "amd", "scheduler_name": "default-scheduler", "runtime_class_name": ""},
            },
            "resources": {
                "metadata": {
                    "gpu": {
                        "acceleratorKeys": ["nvidia", "amd"],
                        "acceleratorOverrides": {"amd": {"image": "rocm/image:v1"}},
                    }
                }
            },
        }
    )
    return instance


def test_accelerator_contract_accepts_explicit_vendor_routing():
    _valid_routing_config()._validate_accelerator_contract()


@pytest.mark.parametrize(
    "field_override",
    [
        {"vendor": "intel"},
        {"scheduler_name": "default-scheduler"},
        {"runtime_class_name": "nvidia", "vendor": "amd"},
    ],
)
def test_accelerator_contract_rejects_invalid_routing(field_override):
    instance = _valid_routing_config()
    raw = {
        "displayName": "NVIDIA",
        "nodeSelector": {"gpu-vendor": "nvidia"},
    }
    raw.update(field_override)
    instance._config = ParsedConfig.model_validate(
        {"accelerators": {"nvidia": raw}, "acceleratorRouting": {"nvidia": {**field_override, "vendor": field_override.get("vendor", "nvidia"), "scheduler_name": field_override.get("scheduler_name", "hami-scheduler"), "runtime_class_name": field_override.get("runtime_class_name", "nvidia")}}}
    )
    with pytest.raises(ValueError):
        instance._validate_accelerator_contract()


def test_accelerator_contract_rejects_unknown_resource_reference():
    instance = _valid_routing_config()
    instance._config = ParsedConfig.model_validate(
        {
            "accelerators": {
                "nvidia": {
                    "displayName": "NVIDIA",
                    "vendor": "nvidia",
                    "scheduler_name": "hami-scheduler",
                    "runtime_class_name": "nvidia",
                    "nodeSelector": {"gpu-vendor": "nvidia"},
                }
            },
            "resources": {"metadata": {"gpu": {"acceleratorKeys": ["missing"]}}},
        }
    )
    with pytest.raises(ValueError, match="unknown accelerator"):
        instance._validate_accelerator_contract()
