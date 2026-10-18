"""CAAIF Core SDK v0.2 — Three distinct HTTP agent worker processes.

This is a loopback-only developer demonstration. One trusted process owns the
LocalController and calls its recipient workers through HTTPTransport.
"""
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from caaif_core import LocalController
from caaif_core.http_transport import ContextRelay, HTTPTransport

PROFILE = ROOT / "examples" / "three-agent"
IDS = {"conversational": "demo.agent.conversational",
       "reasoning": "demo.agent.reasoning", "task": "demo.agent.task"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def await_health(proc, port):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("worker_process_exited")
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=0.25) as response:
                if json.load(response).get("status") == "ok":
                    return
        except Exception:
            time.sleep(0.05)
    raise TimeoutError("worker_not_ready")


def demo():
    contracts = [read(p) for p in sorted((PROFILE / "contracts").glob("*.json"))]
    core = LocalController(profile=read(PROFILE / "profile.json"), contracts=contracts,
                           policy=lambda req, c: req["correlation_id"].startswith("demo-"),
                           effect_policy=lambda req, c: req["input"].get("operation") == "create_outline")
    processes = []
    try:
        with ContextRelay() as relay:
            agents = {}
            for role, agent_id in IDS.items():
                port = free_port()
                secret = secrets.token_urlsafe(32)
                env = os.environ.copy()
                env["CAAIF_WORKER_SECRET"] = secret
                proc = subprocess.Popen([sys.executable, str(ROOT / "examples" / "http_agent_worker.py"),
                                         role, str(port)], env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(proc)
                await_health(proc, port)
                agents[role] = core.attach(agent_id,
                    HTTPTransport(url=f"http://127.0.0.1:{port}", recipient_id=agent_id,
                                  auth_token=secret, relay=relay))

            conversational, reasoning, task = (agents["conversational"],
                                               agents["reasoning"], agents["task"])
            corr = "demo-outline-http-001"
            intent = core.put_context(conversational, ref="ctx:http/session/1", version="v1",
                                      scope="session.intent", value={"topic": "agent collaboration"},
                                      readers={reasoning.agent_id}, correlation_id=corr)
            result1 = core.dispatch(conversational, core.new_request(
                conversational, contract_id="demo.three-agent.intent.v1", correlation_id=corr,
                context_refs=[intent], data={"intent": "Make an outline"}))

            instruction = core.put_context(reasoning, ref="ctx:http/instructions/1", version="v1",
                                            scope="workspace.instructions",
                                            value={"topic": result1["output"]["source_topic"]},
                                            readers={task.agent_id}, correlation_id=corr)
            decision = core.issue_decision(reasoning, correlation_id=corr,
                        contract_id="demo.three-agent.execute.v1", recipient_id=task.agent_id,
                        capability="task.execute",
                        authorized=result1["output"].get("authorizes_outline") is True)
            result2 = core.dispatch(reasoning, core.new_request(
                reasoning, contract_id="demo.three-agent.execute.v1", correlation_id=corr,
                context_refs=[instruction], decision_ref=decision,
                idempotency_key="outline-http-001", data={"operation": "create_outline"}))

            receipt = core.put_context(task, ref="ctx:http/task/1", version="v1",
                                       scope="task.receipt", value=result2["output"],
                                       readers={reasoning.agent_id}, correlation_id=corr)
            result3 = core.dispatch(task, core.new_request(
                task, contract_id="demo.three-agent.report.v1", correlation_id=corr,
                context_refs=[receipt], data={"receipt_id": "receipt-http-001"}))
            summary = core.put_context(reasoning, ref="ctx:http/summary/1", version="v1",
                                       scope="workspace.summary",
                                       value={"points": result3["output"]["summary_points"]},
                                       readers={conversational.agent_id}, correlation_id=corr)
            result4 = core.dispatch(reasoning, core.new_request(
                reasoning, contract_id="demo.three-agent.response.v1", correlation_id=corr,
                context_refs=[summary], data={"style": "concise"}))

            completed = sum(e["event"] == "completed" for e in core.events)
            reads = sum(e["event"] == "context_resolved" for e in core.events)
            assert completed == 4 and reads == 4, "unexpected_interaction_result"
            print("CAAIF Core SDK v0.2 — Three independent HTTP agent processes")
            print("Conversational → Reasoning → Task → Reasoning → Conversational")
            print(result4["output"]["message"])
            print("Interactions completed:", completed)
            print("Authorized remote context reads:", reads)
            print("Worker processes:", len(processes))
            return core
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for p in processes:
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=3)


if __name__ == "__main__":
    demo()
