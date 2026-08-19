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

"""
Spawner Package

Provides spawner implementations for different deployment platforms.
Currently supports Kubernetes (KubeSpawner), with extensibility for
future standalone deployment.
"""

from core.spawner.kubernetes import RemoteLabKubeSpawner

__all__ = [
    "RemoteLabKubeSpawner",
]


def create_spawner(platform: str = "kubernetes"):
    """
    Factory function to create the appropriate spawner class.

    Args:
        platform: Deployment platform ("kubernetes" or "standalone")

    Returns:
        Spawner class (not instance)
    """
    if platform == "kubernetes":
        return RemoteLabKubeSpawner
    elif platform == "standalone":
        # Future: from core.spawner.standalone import RemoteLabLocalSpawner
        raise NotImplementedError("Standalone spawner not yet implemented")
    else:
        raise ValueError(f"Unknown platform: {platform}")
