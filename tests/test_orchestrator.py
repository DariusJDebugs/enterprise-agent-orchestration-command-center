import asyncio
from pathlib import Path

import pytest


async def seed_services(services):
    for path in sorted((Path(__file__).parents[1] / "sample_docs").glob("*.md")):
        services.rag.ingest(path.name, "text/markdown", path.read_bytes(), trust_state="trusted")


@pytest.mark.asyncio
async def test_full_graph_completes_with_report_and_observability(app):
    services = app.state.services
    await seed_services(services)
    mission = services.orchestrator.create_mission(
        "Enterprise vendor risk and compliance review", "Northstar Cloud Systems",
        "Assess security, privacy, compliance, continuity, and operational resilience using source evidence.",
    )
    completed = await services.orchestrator.run_mission(mission["id"])
    assert completed["status"] == "completed"
    assert "Enterprise Vendor Risk Review" in completed["final_report"]
    assert len(services.repository.list_tasks(mission["id"])) == 11
    assert len(services.repository.list_traces(mission["id"])) == 11
    assert services.repository.verify_audit_chain(mission["id"])["valid"] is True


@pytest.mark.asyncio
async def test_pause_resume_controls_are_persistent(app):
    services = app.state.services
    services.orchestrator.step_delay_ms = 80
    await seed_services(services)
    mission = services.orchestrator.create_mission(
        "Pause proof", "Northstar Cloud Systems", "Demonstrate a persistent pause and resume command during execution."
    )
    running = asyncio.create_task(services.orchestrator.run_mission(mission["id"]))
    await asyncio.sleep(0.11)
    services.orchestrator.control(mission["id"], "pause", "risk-manager", "Pause for operator inspection")
    await asyncio.sleep(0.12)
    assert services.repository.get_mission(mission["id"])["status"] == "paused"
    services.orchestrator.control(mission["id"], "resume", "risk-manager", "Inspection complete")
    completed = await running
    assert completed["status"] == "completed"
    events = services.repository.list_events(mission["id"])
    assert {event["event_type"] for event in events} >= {"control.pause", "control.resume"}


@pytest.mark.asyncio
async def test_stop_control_prevents_completion(app):
    services = app.state.services
    services.orchestrator.step_delay_ms = 80
    await seed_services(services)
    mission = services.orchestrator.create_mission(
        "Stop proof", "Northstar Cloud Systems", "Demonstrate an authorized emergency stop during execution."
    )
    running = asyncio.create_task(services.orchestrator.run_mission(mission["id"]))
    await asyncio.sleep(0.11)
    services.orchestrator.control(mission["id"], "stop", "risk-manager", "Emergency stop proof")
    stopped = await running
    assert stopped["status"] == "stopped"
    assert any(task["status"] == "stopped" for task in services.repository.list_tasks(mission["id"]))
