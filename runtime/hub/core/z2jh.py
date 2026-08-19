# Modifications Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Portions of this file consist of AI-generated content.
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


"""
Utility methods for use in jupyterhub_config.py and dynamic subconfigs.

Methods here can be imported by extraConfig in values.yaml
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from typing import Any, TypeVar

import yaml

T = TypeVar("T")


# memorize so we only load config once
@lru_cache
def _load_config() -> dict[str, Any]:
    """Load the Helm chart configuration used to render the Helm templates of
    the chart from a mounted k8s Secret, and merge in values from an optionally
    mounted secret (hub.existingSecret)."""

    cfg: dict[str, Any] = {}
    for source in ("secret/values.yaml", "existing-secret/values.yaml"):
        path = f"/usr/local/etc/jupyterhub/{source}"
        if os.path.exists(path):
            print(f"Loading {path}")
            with open(path) as f:
                values = yaml.safe_load(f)
            cfg = _merge_dictionaries(cfg, values)
        else:
            print(f"No config at {path}")
    return cfg


@lru_cache
def _get_config_value(key: str) -> str:
    """Load value from the k8s ConfigMap given a key."""

    path = f"/usr/local/etc/jupyterhub/config/{key}"
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    else:
        raise Exception(f"{path} not found!")


@lru_cache
def get_secret_value(key: str, default: str | None = "never-explicitly-set") -> str | None:
    """Load value from the user managed k8s Secret or the default k8s Secret
    given a key."""

    for source in ("existing-secret", "secret"):
        path = f"/usr/local/etc/jupyterhub/{source}/{key}"
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
    if default != "never-explicitly-set":
        return default
    raise Exception(f"{key} not found in either k8s Secret!")


def get_name(name: str) -> str:
    """Returns the fullname of a resource given its short name"""
    return _get_config_value(name)


def get_name_env(name: str, suffix: str = "") -> str:
    """Returns the fullname of a resource given its short name along with a
    suffix, converted to uppercase with dashes replaced with underscores. This
    is useful to reference named services associated environment variables, such
    as PROXY_PUBLIC_SERVICE_PORT."""
    env_key = _get_config_value(name) + suffix
    env_key = env_key.upper().replace("-", "_")
    return os.environ[env_key]


def _merge_dictionaries(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Merge two dictionaries recursively.

    Simplified From https://stackoverflow.com/a/7205107
    """
    merged = a.copy()
    for key in b:
        if key in a:
            if isinstance(a[key], Mapping) and isinstance(b[key], Mapping):
                merged[key] = _merge_dictionaries(a[key], b[key])
            else:
                merged[key] = b[key]
        else:
            merged[key] = b[key]
    return merged


def get_config(key: str, default: T | None = None) -> T | Any:
    """
    Find a config item of a given name & return it

    Parses everything as YAML, so lists and dicts are available too

    get_config("a.b.c") returns config['a']['b']['c']
    """
    value: Any = _load_config()
    # resolve path in yaml
    for level in key.split("."):
        if not isinstance(value, dict):
            # a parent is a scalar or null,
            # can't resolve full path
            return default
        if level not in value:
            return default
        else:
            value = value[level]
    return value


def get_config_list(key: str, default: list[Any] | None = None) -> list[Any]:
    """Get list configuration value."""
    result = get_config(key, default)
    return result if isinstance(result, list) else (default or [])


def get_config_dict(key: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Get dict configuration value."""
    result = get_config(key, default)
    return result if isinstance(result, dict) else (default or {})


def set_config_if_not_none(cparent: Any, name: str, key: str) -> None:
    """
    Find a config item of a given name, set the corresponding Jupyter
    configuration item if not None
    """
    data = get_config(key)
    if data is not None:
        setattr(cparent, name, data)
