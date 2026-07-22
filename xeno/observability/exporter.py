from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from xeno.observability.tracer import TraceSpan

logger = logging.getLogger(__name__)


class SpanExporter:
    def export(self, span: TraceSpan):
        raise NotImplementedError


class ConsoleExporter(SpanExporter):
    def __init__(self, verbose: bool = False):
        self._verbose = verbose

    def export(self, span: TraceSpan):
        if self._verbose:
            logger.info(
                f"TRACE {span.name}: {span.duration_ms:.1f}ms "
                f"[{span.status}]{' ERR:' + span.error[:100] if span.error else ''}"
            )


class FileExporter(SpanExporter):
    def __init__(self, path: str | Path, max_entries: int = 10000):
        self._path = Path(path)
        self._max_entries = max_entries
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict] = []
        self._load_existing()

    def _load_existing(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                if isinstance(data, list):
                    self._entries = data[-self._max_entries:]
            except Exception:
                self._entries = []

    def export(self, span: TraceSpan):
        self._entries.append(span.to_dict())
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        try:
            self._path.write_text(json.dumps(self._entries, indent=2))
        except Exception as e:
            logger.warning(f"Trace file export failed: {e}")


class CompositeExporter(SpanExporter):
    def __init__(self, exporters: list[SpanExporter]):
        self._exporters = exporters

    def add(self, exporter: SpanExporter):
        self._exporters.append(exporter)

    def export(self, span: TraceSpan):
        for exporter in self._exporters:
            try:
                exporter.export(span)
            except Exception as e:
                logger.warning(f"Exporter failed: {e}")
