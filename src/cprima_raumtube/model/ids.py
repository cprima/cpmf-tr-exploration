"""Typed ID aliases — prevents passing the wrong string kind across boundaries.

NewType has zero runtime cost; it guides mypy and makes call sites self-documenting.
"""

from __future__ import annotations

from typing import NewType

ZoneId = NewType("ZoneId", str)
RendererUdn = NewType("RendererUdn", str)
MediaItemId = NewType("MediaItemId", str)
QueueId = NewType("QueueId", str)
StreamSessionId = NewType("StreamSessionId", str)
InstallationId = NewType("InstallationId", str)
RoomId = NewType("RoomId", str)
GroupId = NewType("GroupId", str)
PhysicalDeviceUdn = NewType("PhysicalDeviceUdn", str)
ServiceType = NewType("ServiceType", str)
