"""QA automation: API scans, concurrency, benchmarks."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8787"
QA = Path(r"C:\AgentArmorQA")


async def wait_scan(client: httpx.AsyncClient, scan_id: str, timeout: float = 120) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        r = await client.get(f"{API}/v1/scans/{scan_id}")
        r.raise_for_status()
        data = r.json()
        if data.get("status") in ("completed", "failed", "cancelled"):
            return data
        await asyncio.sleep(0.5)
    raise TimeoutError(f"scan {scan_id} did not finish")


async def create_scan(client: httpx.AsyncClient, body: dict) -> str:
    r = await client.post(f"{API}/v1/scans", json=body)
    r.raise_for_status()
    return r.json()["scan_id"]


async def run_concurrent() -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        agent_id = await create_scan(
            client,
            {
                "target_type": "agent",
                "agent": "crewai",
                "agent_config": str(QA / "agent.toml"),
                "analysis_mode": "offline",
                "formats": ["json"],
            },
        )
        rag_id = await create_scan(
            client,
            {
                "target_type": "rag",
                "rag": str(QA / "rag_corpus"),
                "embedder": "bge",
                "analysis_mode": "offline",
                "formats": ["json"],
            },
        )
        agent, rag = await asyncio.gather(wait_scan(client, agent_id), wait_scan(client, rag_id))
        return {
            "agent_id": agent_id,
            "rag_id": rag_id,
            "agent_status": agent["status"],
            "rag_status": rag["status"],
            "agent_findings": agent["finding_count"],
            "rag_findings": rag["finding_count"],
            "distinct_ids": agent_id != rag_id,
        }


async def run_benchmarks() -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{API}/v1/benchmarks",
            json={"providers": ["openai"], "suite": "owasp", "model": "gpt-4o-mini"},
        )
        r.raise_for_status()
        bench_id = r.json()["benchmark_id"]
        start = time.time()
        model_scores = []
        while time.time() - start < 300:
            br = await client.get(f"{API}/v1/benchmarks/{bench_id}")
            br.raise_for_status()
            data = br.json()
            if data.get("status") in ("completed", "failed"):
                model_scores = data.get("model_scores", [])
                return {
                    "benchmark_id": bench_id,
                    "status": data.get("status"),
                    "error": data.get("error"),
                    "model_scores": model_scores,
                }
            await asyncio.sleep(2)
        return {"benchmark_id": bench_id, "status": "timeout"}

        r2 = await client.post(
            f"{API}/v1/benchmarks/tools",
            json={"suite": "owasp-llm01", "targets": ["corpus"]},
        )


async def run_tools_benchmark() -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{API}/v1/benchmarks/tools",
            json={"suite": "owasp-llm01", "targets": ["corpus"]},
        )
        r.raise_for_status()
        bench_id = r.json()["benchmark_id"]
        start = time.time()
        while time.time() - start < 120:
            br = await client.get(f"{API}/v1/benchmarks/tools/{bench_id}")
            br.raise_for_status()
            data = br.json()
            if data.get("status") in ("completed", "failed"):
                scores = data.get("tool_scores", [])
                return {
                    "benchmark_id": bench_id,
                    "status": data.get("status"),
                    "tool_count": len(scores),
                    "tools": [
                        {
                            "tool": s.get("tool"),
                            "status": s.get("status"),
                            "detection_rate": s.get("detection_rate"),
                            "true_positives": s.get("true_positives"),
                        }
                        for s in scores
                    ],
                }
            await asyncio.sleep(2)
        return {"benchmark_id": bench_id, "status": "timeout"}


async def run_provider_scan() -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        scan_id = await create_scan(
            client,
            {
                "target_type": "provider",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "analysis_mode": "offline",
                "formats": ["json", "sarif"],
            },
        )
        result = await wait_scan(client, scan_id, timeout=300)
        return {
            "scan_id": scan_id,
            "status": result["status"],
            "finding_count": result["finding_count"],
            "probe_count": result["probe_count"],
        }


async def main() -> None:
    results = {}
    print("=== Concurrent agent + RAG scans ===")
    results["concurrent"] = await run_concurrent()
    print(json.dumps(results["concurrent"], indent=2))

    print("\n=== Provider scan (OpenAI gpt-4o-mini) ===")
    results["provider"] = await run_provider_scan()
    print(json.dumps(results["provider"], indent=2))

    print("\n=== Model benchmark ===")
    results["benchmark_models"] = await run_benchmarks()
    print(json.dumps(results["benchmark_models"], indent=2))

    print("\n=== Tools benchmark ===")
    results["benchmark_tools"] = await run_tools_benchmark()
    print(json.dumps(results["benchmark_tools"], indent=2))

    out = QA / "qa_api_results.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
