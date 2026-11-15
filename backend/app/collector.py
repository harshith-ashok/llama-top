"""Cross-platform host metrics. Every optional metric is capability-detected."""

from __future__ import annotations

import platform
import socket
import time
from typing import Any

import psutil

try:  # NVIDIA only; absent on macOS and on hosts without drivers.
    import pynvml  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001
    pynvml = None


class Collector:
    def __init__(self) -> None:
        self._last_t = time.monotonic()
        self._disk_io = psutil.disk_io_counters()
        self._net_io = psutil.net_io_counters()
        self._nvml = False
        if pynvml is not None:
            try:
                pynvml.nvmlInit()
                self._nvml = True
            except Exception:  # noqa: BLE001
                self._nvml = False
        psutil.cpu_percent(percpu=True)  # prime the counters

    # -- static ---------------------------------------------------------------
    def info(self) -> dict[str, Any]:
        gpus = self._gpu_inventory()
        mem = psutil.virtual_memory()
        return {
            "hostname": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()}",
            "platform": platform.platform(),
            "arch": platform.machine(),
            "cpu_model": platform.processor() or platform.machine(),
            "cpu_cores_physical": psutil.cpu_count(logical=False),
            "cpu_cores_logical": psutil.cpu_count(logical=True),
            "ram_total": mem.total,
            "boot_time": psutil.boot_time(),
            "gpus": gpus,
            "capabilities": {
                "gpu": self._nvml,
                "temperatures": hasattr(psutil, "sensors_temperatures"),
                "load_average": True,
            },
        }

    def _gpu_inventory(self) -> list[dict[str, Any]]:
        if not self._nvml:
            return []
        out = []
        try:
            for i in range(pynvml.nvmlDeviceGetCount()):
                h = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(h)
                out.append({"index": i, "name": name.decode() if isinstance(name, bytes) else name})
        except Exception:  # noqa: BLE001
            pass
        return out

    # -- dynamic --------------------------------------------------------------
    def sample(self, with_processes: bool = True) -> dict[str, Any]:
        now = time.monotonic()
        dt = max(now - self._last_t, 1e-6)
        self._last_t = now
        mem, swap = psutil.virtual_memory(), psutil.swap_memory()
        try:
            freq = psutil.cpu_freq()
        except (AttributeError, NotImplementedError, OSError):
            freq = None  # unsupported on some platforms (e.g. Apple Silicon)
        try:
            load = list(psutil.getloadavg())
        except (OSError, AttributeError):
            load = None
        data: dict[str, Any] = {
            "ts": time.time(),
            "cpu": {
                "percent": psutil.cpu_percent(),
                "per_core": psutil.cpu_percent(percpu=True),
                "freq_mhz": freq.current if freq else None,
                "load_avg": load,
            },
            "memory": {
                "total": mem.total,
                "used": mem.total - mem.available,
                "available": mem.available,
                "percent": mem.percent,
                "swap_used": swap.used,
                "swap_total": swap.total,
            },
            "disks": self._disks(),
            "disk_io": self._disk_rates(dt),
            "network": self._net_rates(dt),
            "temperatures": self._temps(),
            "gpus": self._gpus(),
        }
        if with_processes:
            data["processes"] = self._processes()
        return data

    def _disks(self) -> list[dict[str, Any]]:
        out, seen = [], set()
        for p in psutil.disk_partitions(all=False):
            if p.device in seen:
                continue
            seen.add(p.device)
            try:
                u = psutil.disk_usage(p.mountpoint)
            except (PermissionError, OSError):
                continue
            out.append(
                {
                    "mount": p.mountpoint,
                    "fs": p.fstype,
                    "total": u.total,
                    "used": u.used,
                    "percent": u.percent,
                }
            )
        return out

    def _disk_rates(self, dt: float) -> dict[str, float] | None:
        cur = psutil.disk_io_counters()
        prev, self._disk_io = self._disk_io, cur
        if not cur or not prev:
            return None
        return {
            "read_bps": (cur.read_bytes - prev.read_bytes) / dt,
            "write_bps": (cur.write_bytes - prev.write_bytes) / dt,
            "read_iops": (cur.read_count - prev.read_count) / dt,
            "write_iops": (cur.write_count - prev.write_count) / dt,
        }

    def _net_rates(self, dt: float) -> dict[str, float] | None:
        cur = psutil.net_io_counters()
        prev, self._net_io = self._net_io, cur
        if not cur or not prev:
            return None
        return {
            "rx_bps": (cur.bytes_recv - prev.bytes_recv) / dt,
            "tx_bps": (cur.bytes_sent - prev.bytes_sent) / dt,
        }

    def _temps(self) -> dict[str, float] | None:
        fn = getattr(psutil, "sensors_temperatures", None)
        if fn is None:
            return None
        try:
            temps = fn()
        except Exception:  # noqa: BLE001
            return None
        out = {k: v[0].current for k, v in temps.items() if v}
        return out or None

    def _gpus(self) -> list[dict[str, Any]]:
        if not self._nvml:
            return []
        out = []
        try:
            for i in range(pynvml.nvmlDeviceGetCount()):
                h = pynvml.nvmlDeviceGetHandleByIndex(i)
                util = pynvml.nvmlDeviceGetUtilizationRates(h)
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                g: dict[str, Any] = {
                    "index": i,
                    "util": util.gpu,
                    "vram_used": mem.used,
                    "vram_total": mem.total,
                }
                for key, fn in (
                    ("temp_c", lambda h=h: pynvml.nvmlDeviceGetTemperature(h, 0)),
                    ("power_w", lambda h=h: pynvml.nvmlDeviceGetPowerUsage(h) / 1000),
                    ("clock_mhz", lambda h=h: pynvml.nvmlDeviceGetClockInfo(h, 0)),
                ):
                    try:
                        g[key] = fn()
                    except Exception:  # noqa: BLE001
                        g[key] = None
                out.append(g)
        except Exception:  # noqa: BLE001
            pass
        return out

    def _processes(self, n: int = 10) -> list[dict[str, Any]]:
        rows = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            i = p.info
            if i.get("memory_info") is None:
                continue
            rows.append(
                {
                    "pid": i["pid"],
                    "name": i["name"],
                    "cpu": i["cpu_percent"] or 0.0,
                    "rss": i["memory_info"].rss,
                }
            )
        rows.sort(key=lambda r: (r["cpu"], r["rss"]), reverse=True)
        return rows[:n]
