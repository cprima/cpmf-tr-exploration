"""Renderer — pleasant UPnP AVTransport + RenderingControl API."""

from cprima_raumtube.devices import AVT_SVC, RC_SVC
from cprima_raumtube.model.ids import RendererUdn
from cprima_raumtube.soap import soap_call


class Renderer:
    def __init__(
        self,
        avt_control: str,
        rc_control: str | None = None,
        udn: RendererUdn = RendererUdn(""),
    ) -> None:
        self._avt = avt_control
        self._rc = rc_control
        self.udn = udn

    @classmethod
    def from_zone(cls, zone: dict) -> "Renderer":
        return cls(zone["avt_control"], zone.get("rc_control"), RendererUdn(zone.get("udn", "")))

    # ── Transport ────────────────────────────────────────────────────────────

    def set_uri(self, url: str, metadata: str = "") -> None:
        soap_call(
            self._avt,
            AVT_SVC,
            "SetAVTransportURI",
            {
                "InstanceID": "0",
                "CurrentURI": url,
                "CurrentURIMetaData": metadata,
            },
        )

    def play(self, speed: str = "1") -> None:
        soap_call(self._avt, AVT_SVC, "Play", {"InstanceID": "0", "Speed": speed})

    def stop(self) -> None:
        soap_call(self._avt, AVT_SVC, "Stop", {"InstanceID": "0"})

    def pause(self) -> None:
        soap_call(self._avt, AVT_SVC, "Pause", {"InstanceID": "0"})

    def seek(self, target: str, unit: str = "ABS_TIME") -> None:
        soap_call(
            self._avt,
            AVT_SVC,
            "Seek",
            {
                "InstanceID": "0",
                "Unit": unit,
                "Target": target,
            },
        )

    # ── State ────────────────────────────────────────────────────────────────

    def get_state(self) -> str:
        result = soap_call(self._avt, AVT_SVC, "GetTransportInfo", {"InstanceID": "0"})
        return result.get("CurrentTransportState", "")

    def get_position(self) -> dict:
        return soap_call(self._avt, AVT_SVC, "GetPositionInfo", {"InstanceID": "0"})

    def get_media_info(self) -> dict:
        return soap_call(self._avt, AVT_SVC, "GetMediaInfo", {"InstanceID": "0"})

    # ── Volume (requires rc_control) ─────────────────────────────────────────

    def _require_rc(self) -> str:
        if not self._rc:
            raise RuntimeError("No RenderingControl URL available for this renderer")
        return self._rc

    def get_volume(self) -> int:
        rc = self._require_rc()
        result = soap_call(rc, RC_SVC, "GetVolume", {"InstanceID": "0", "Channel": "Master"})
        return int(result.get("CurrentVolume", "0"))

    def set_volume(self, level: int) -> None:
        rc = self._require_rc()
        soap_call(
            rc,
            RC_SVC,
            "SetVolume",
            {
                "InstanceID": "0",
                "Channel": "Master",
                "DesiredVolume": str(level),
            },
        )
