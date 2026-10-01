"""Multi-Agent System Evaluation Runner.

Evaluates the LangGraph Multi-Agent Architecture across:
1. Routing & Intent Classification Precision
2. Tool Trajectory & Zero-Loop Guarantee (<= 2 tool calls per query)
3. Groundedness & Source Citation Accuracy
4. End-to-End Latency & Node Transition Profiling
"""

import sys
import os
import json
import time
import uuid
import asyncio
from pathlib import Path
from dataclasses import dataclass, asdict

# Fix Windows console UTF-8 encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Root directory setup
SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from dotenv import load_dotenv
for env_path in [SRC_DIR / ".env", SRC_DIR.parent / ".env"]:
    if env_path.exists():
        load_dotenv(env_path, override=False)

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from agent.graph import graph
from agent.tools import mcp_client


@dataclass
class TestCaseResult:
    id: str
    category: str
    query: str
    expected_route: str
    actual_route: str
    route_matched: bool
    tools_called: list[str]
    tool_count: int
    zero_loop_pass: bool
    citation_pass: bool
    content_clean: bool
    overall_pass: bool
    latency_sec: float
    total_steps: int
    step_trace: list[str]
    answer_preview: str
    failure_reasons: list[str]


async def evaluate_query(test_case: dict) -> TestCaseResult:
    case_id = test_case["id"]
    query = test_case["query"]
    expected_route = test_case["expected_route"]
    expected_tools = test_case.get("expected_tools", [])
    require_citation = test_case.get("require_citation", False)

    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["evaluation", test_case["category"]],
    }

    start_time = time.perf_counter()
    step_trace = []
    tools_called = []
    actual_route = "UNKNOWN"
    total_steps = 0
    final_answer = ""
    failure_reasons = []

    try:
        async for event in graph.astream(
            {"messages": [HumanMessage(content=query)]},
            config=config,
            stream_mode="updates",
        ):
            total_steps += 1
            for node_name, node_output in event.items():
                step_trace.append(node_name)

                # Capture supervisor routing decision
                if node_name == "supervisor" and "next_step" in node_output:
                    # Only record the initial routing decision
                    if actual_route == "UNKNOWN":
                        actual_route = node_output["next_step"]

                # Capture tool calls from specialists
                if "messages" in node_output and node_output["messages"]:
                    for msg in node_output["messages"]:
                        if isinstance(msg, AIMessage):
                            if getattr(msg, "tool_calls", None):
                                for tc in msg.tool_calls:
                                    tools_called.append(tc["name"])
                            elif msg.content:
                                final_answer = msg.content
    except Exception as e:
        failure_reasons.append(f"Execution exception: {e}")

    latency = round(time.perf_counter() - start_time, 2)

    # If supervisor never set next_step, fallback to check end state
    if actual_route == "UNKNOWN":
        if any("docs" in s for s in step_trace):
            actual_route = "docs_specialist"
        elif any("github" in s for s in step_trace):
            actual_route = "github_specialist"
        else:
            actual_route = "FINISH"

    # Evaluation Checks
    route_matched = (actual_route == expected_route)
    if not route_matched:
        failure_reasons.append(f"Routing mismatch: expected '{expected_route}', got '{actual_route}'")

    # Zero Loop Check: <= 2 tool calls and total steps <= 6
    zero_loop_pass = (len(tools_called) <= 2) and (total_steps <= 6)
    if not zero_loop_pass:
        failure_reasons.append(f"Loop/Step limit breached: tools={len(tools_called)}, steps={total_steps}")

    # Tool selection validation
    if expected_tools:
        if not any(t in tools_called for t in expected_tools):
            failure_reasons.append(f"Expected one of tools {expected_tools}, got {tools_called}")
    elif len(tools_called) > 0:
        failure_reasons.append(f"Expected 0 tools for direct query, but called {tools_called}")

    # Citation check for documentation answers
    citation_pass = True
    if require_citation:
        citation_keywords = ["[source:", "docs/", "adr", "runbook", "guide", "source:", "security.md", "specification"]
        answer_lower = final_answer.lower()
        has_citation = any(kw in answer_lower for kw in citation_keywords)
        if not has_citation:
            citation_pass = False
            failure_reasons.append("Missing required source citation in final answer")

    # Clean content check (non-empty, no raw JSON leaks)
    content_clean = (len(final_answer.strip()) >= 2) and not ('"tool_calls":' in final_answer)
    if not content_clean:
        failure_reasons.append("Final answer too short or contains raw tool JSON leaks")

    overall_pass = (len(failure_reasons) == 0)

    return TestCaseResult(
        id=case_id,
        category=test_case["category"],
        query=query,
        expected_route=expected_route,
        actual_route=actual_route,
        route_matched=route_matched,
        tools_called=tools_called,
        tool_count=len(tools_called),
        zero_loop_pass=zero_loop_pass,
        citation_pass=citation_pass,
        content_clean=content_clean,
        overall_pass=overall_pass,
        latency_sec=latency,
        total_steps=total_steps,
        step_trace=step_trace,
        answer_preview=final_answer.strip().replace("\n", " ")[:120],
        failure_reasons=failure_reasons,
    )


def generate_markdown_report(results: list[TestCaseResult], total_time: float) -> str:
    total_cases = len(results)
    passed_cases = sum(1 for r in results if r.overall_pass)
    route_accuracy = (sum(1 for r in results if r.route_matched) / total_cases) * 100
    zero_loop_rate = (sum(1 for r in results if r.zero_loop_pass) / total_cases) * 100
    citation_cases = [r for r in results if r.category == "docs_architecture"]
    citation_accuracy = (sum(1 for r in citation_cases if r.citation_pass) / max(len(citation_cases), 1)) * 100
    avg_latency = sum(r.latency_sec for r in results) / total_cases

    report = []
    report.append("# Multi-Agent System Evaluation Benchmark Report\n")
    report.append(f"**Execution Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Total Benchmark Latency**: {total_time:.2f}s | **Test Cases**: {total_cases}\n")

    report.append("## Executive Summary Scorecard\n")
    report.append("| Metric | Target | Result | Status |")
    report.append("| :--- | :---: | :---: | :---: |")
    report.append(f"| **Overall Benchmark Pass Rate** | >= 90.0% | **{(passed_cases/total_cases)*100:.1f}%** ({passed_cases}/{total_cases}) | {'✅ PASS' if passed_cases/total_cases >= 0.9 else '❌ FAIL'} |")
    report.append(f"| **Routing Precision & Accuracy** | >= 95.0% | **{route_accuracy:.1f}%** | {'✅ PASS' if route_accuracy >= 95.0 else '⚠️ WARN'} |")
    report.append(f"| **Zero-Loop Guarantee** | 100.0% | **{zero_loop_rate:.1f}%** | {'✅ PASS' if zero_loop_rate == 100.0 else '❌ FAIL'} |")
    report.append(f"| **Documentation Citation Rate** | >= 90.0% | **{citation_accuracy:.1f}%** | {'✅ PASS' if citation_accuracy >= 90.0 else '⚠️ WARN'} |")
    report.append(f"| **Average End-to-End Latency** | <= 7.0s | **{avg_latency:.2f}s** | {'✅ PASS' if avg_latency <= 7.0 else '⚠️ WARN'} |\n")

    report.append("## Detailed Evaluation Case Breakdown\n")
    report.append("| Test ID | Category | Expected -> Actual Route | Tools Called | Latency | Zero-Loop | Result |")
    report.append("| :--- | :--- | :--- | :--- | :---: | :---: | :---: |")

    for r in results:
        status_badge = "✅ PASS" if r.overall_pass else "❌ FAIL"
        loop_badge = "✅" if r.zero_loop_pass else "❌"
        tools_str = ", ".join(r.tools_called) if r.tools_called else "*(none)*"
        report.append(
            f"| `{r.id}` | {r.category} | `{r.expected_route}` -> `{r.actual_route}` | `{tools_str}` | {r.latency_sec}s | {loop_badge} | {status_badge} |"
        )

    report.append("\n## Trajectory Traces & Diagnostics\n")
    for r in results:
        report.append(f"### Case: `{r.id}`")
        report.append(f"- **Query**: *\"{r.query}\"*")
        report.append(f"- **Step Sequence**: `{' -> '.join(r.step_trace)}`")
        report.append(f"- **Tools Executed ({r.tool_count})**: `{r.tools_called}`")
        report.append(f"- **Answer Preview**: {r.answer_preview}...")
        if r.failure_reasons:
            report.append(f"- **Failure Reasons**: `{'; '.join(r.failure_reasons)}`")
        report.append("")

    return "\n".join(report)


async def main():
    print("\n" + "=" * 75)
    print("      MULTI-AGENT SYSTEM EVALUATION HARNESS BENCHMARK")
    print("=" * 75)

    dataset_path = Path(__file__).resolve().parent / "eval_dataset.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"\n[Setup] Loaded {len(cases)} test cases from {dataset_path.name}")
    print("[Setup] Connecting MCP Client...")
    await mcp_client.connect()
    print("[Setup] MCP Client connected successfully.\n")

    bench_start = time.perf_counter()
    results: list[TestCaseResult] = []

    try:
        for idx, case in enumerate(cases, 1):
            print(f"[{idx:02d}/{len(cases):02d}] Running `{case['id']}` ... ", end="", flush=True)
            res = await evaluate_query(case)
            results.append(res)
            status_text = "PASS" if res.overall_pass else "FAIL"
            print(f"[{status_text}] ({res.latency_sec}s, tools={res.tool_count}, route={res.actual_route})")
            if not res.overall_pass:
                for fr in res.failure_reasons:
                    print(f"     -> [FAILURE] {fr}")

            # Small delay between calls to respect API rate limits
            await asyncio.sleep(1.0)
    finally:
        await mcp_client.close()
        print("\n[Teardown] MCP Client disconnected.")

    total_bench_time = time.perf_counter() - bench_start

    # Output Markdown Report
    report_md = generate_markdown_report(results, total_bench_time)
    report_path = Path(__file__).resolve().parent / "eval_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"\n[Export] Detailed Markdown report written to: {report_path.name}")

    # Output JSON Results
    json_path = Path(__file__).resolve().parent / "eval_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"[Export] Machine-readable metrics written to: {json_path.name}")

    # Print Summary Table
    total_cases = len(results)
    passed_cases = sum(1 for r in results if r.overall_pass)
    route_accuracy = (sum(1 for r in results if r.route_matched) / total_cases) * 100
    zero_loop_rate = (sum(1 for r in results if r.zero_loop_pass) / total_cases) * 100
    avg_latency = sum(r.latency_sec for r in results) / total_cases

    print("\n" + "=" * 75)
    print("                    EVALUATION BENCHMARK SCORECARD")
    print("=" * 75)
    print(f"  • Total Test Cases      : {total_cases}")
    print(f"  • Overall Passed        : {passed_cases}/{total_cases} ({(passed_cases/total_cases)*100:.1f}%)")
    print(f"  • Routing Accuracy      : {route_accuracy:.1f}%")
    print(f"  • Zero-Loop Rate        : {zero_loop_rate:.1f}%")
    print(f"  • Average Latency       : {avg_latency:.2f}s")
    print(f"  • Total Benchmark Time  : {total_bench_time:.2f}s")
    print("=" * 75 + "\n")

    return 0 if (passed_cases == total_cases) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
