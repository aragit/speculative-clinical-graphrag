import logging
import json
import re
from typing import Dict, Optional
import os

logger = logging.getLogger(__name__)


class TelemetryManager:
    def __init__(self, jaeger_host: str = None, service_name: str = "speculative-graphrag"):
        self.jaeger_host = jaeger_host or os.getenv("JAEGER_HOST", "jaeger:6831")
        self.service_name = service_name
        self._tracer = None

    def get_tracer(self, name: Optional[str] = None):
        if self._tracer is None:
            try:
                from opentelemetry import trace
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                provider = TracerProvider()
                exporter = OTLPSpanExporter(endpoint=f"http://{self.jaeger_host}:4317", insecure=True)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                trace.set_tracer_provider(provider)
                self._tracer = trace.get_tracer(self.service_name)
            except Exception as e:
                logger.warning(f"OpenTelemetry init failed ({e}), using fallback tracer")
                self._tracer = logging.getLogger(f"trace.{self.service_name}")
        return self._tracer if name is None else self._tracer

    async def llm_as_judge(self, execution_graph: Dict, llm_backend=None) -> Dict:
        scores = {"factual_accuracy": 0.0, "tone": 0.0, "logic": 0.0}
        if llm_backend is None:
            return {**scores, "status": "stub"}
        text = execution_graph.get("final_output", "")
        prompt = f"""Evaluate the following clinical reasoning output on three axes (0.0-1.0).
Return valid JSON only: {{"factual_accuracy": float, "tone": float, "logic": float}}

Output:
{text[:2000]}"""
        try:
            resp = await llm_backend._call_llm(prompt, system="You are a clinical quality evaluator. Return JSON.")
            match = re.search(r'\{.*\}', resp, re.DOTALL)
            if match:
                scores = json.loads(match.group())
            return {**scores, "status": "ok"}
        except Exception as e:
            logger.warning(f"LLM-as-judge failed: {e}")
            return {**scores, "status": "error"}
