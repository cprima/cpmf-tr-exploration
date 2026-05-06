"""cprima_raumtube.services — service layer for single-zone playback.

QueueManager    queue state, item resolution, navigation
PlaybackManager SOAP playback control, autoplay loop
StreamManager   HTTP streaming session lifecycle
cache_service   persistent MediaItem / CacheEntry index
"""

from cprima_raumtube.services.cache_service import load_index, save_index
from cprima_raumtube.services.playback_manager import PlaybackManager, StopReason
from cprima_raumtube.services.queue_manager import QueueManager
from cprima_raumtube.services.stream_manager import StreamManager

__all__ = [
    "QueueManager",
    "PlaybackManager",
    "StopReason",
    "StreamManager",
    "load_index",
    "save_index",
]
