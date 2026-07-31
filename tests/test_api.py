from pathlib import Path


def seed(client):
    response = client.post("/api/demo/seed")
    assert response.status_code == 200
    return response.json()


def test_health_architecture_frontend_and_requirements(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["phase"] == 3
    assert health.json()["governance"] == "enforced"
    architecture = client.get("/api/architecture").json()
    assert len(architecture["nodes"]) == 11
    assert "red_team" in {node["name"] for node in architecture["nodes"]}
    assert client.get("/").status_code == 200
    requirements = client.get("/api/requirements").json()["requirements"]
    assert len(requirements) >= 10


def test_standard_end_to_end_mission_has_phase2_evidence(client):
    seed(client)
    create = client.post("/api/missions", json={
        "title": "Governed vendor review",
        "vendor_name": "Northstar Cloud Systems",
        "objective": "Assess security, privacy, compliance, continuity, and operational resilience using source evidence.",
        "auto_run": True,
    })
    assert create.status_code == 201
    detail = client.get(f"/api/missions/{create.json()['id']}").json()
    assert detail["mission"]["status"] == "completed"
    assert len(detail["tasks"]) == 11
    assert all(task["status"] == "completed" for task in detail["tasks"])
    assert detail["traces"] and detail["metrics"]
    assert detail["audit_verification"]["valid"] is True
    assert "Human authorization" in detail["mission"]["final_report"]
    report_task = next(task for task in detail["tasks"] if task["agent_name"] == "report")
    assert report_task["output"]["data"]["quality"]["passed"] is True


def test_role_based_access_denies_viewer_mutations(client):
    headers = {"X-Role": "viewer", "X-Actor": "read-only-user"}
    denied = client.post("/api/missions", headers=headers, json={
        "title": "Denied mission",
        "vendor_name": "Vendor",
        "objective": "This write should be rejected by role policy.",
    })
    assert denied.status_code == 403
    upload = client.post("/api/documents/upload", headers=headers, files=[("files", ("x.txt", b"A long enough policy document for testing access control.", "text/plain"))])
    assert upload.status_code == 403


def test_unauthorized_tool_access_is_blocked_and_audited(client):
    mission = client.post("/api/missions", json={
        "title": "Permission proof", "vendor_name": "Northstar Cloud Systems",
        "objective": "Create a mission used to prove unauthorized tool denial.", "auto_run": False,
    }).json()
    denied = client.post(
        "/api/tools/lookup_vendor/call",
        headers={"X-Role": "viewer", "X-Actor": "viewer-test"},
        json={"mission_id": mission["id"], "arguments": {"vendor_name": "Northstar Cloud Systems"}},
    )
    assert denied.status_code == 403
    detail = client.get(f"/api/missions/{mission['id']}").json()
    assert any(call["permission_decision"] == "denied" for call in detail["tool_calls"])
    assert any(item["incident_type"] == "unauthorized_tool_access" for item in detail["security_incidents"])


def test_high_risk_mission_pauses_for_human_approval_then_resumes(client):
    seed(client)
    created = client.post("/api/missions", json={
        "title": "High risk approval proof", "vendor_name": "Northstar Cloud Systems",
        "objective": "Demonstrate a high-risk decision pausing for authorized human approval.",
        "auto_run": True, "proof_scenario": "high_risk_approval",
    }).json()
    waiting = client.get(f"/api/missions/{created['id']}").json()
    assert waiting["mission"]["status"] == "awaiting_approval"
    approval = waiting["approvals"][-1]
    assert approval["status"] == "pending"
    decided = client.post(
        f"/api/missions/{created['id']}/approvals/{approval['id']}/decide",
        headers={"X-Role": "risk_manager", "X-Actor": "human-risk-manager"},
        json={"decision": "approved", "note": "Risk accepted for proof scenario."},
    )
    assert decided.status_code == 200
    completed = client.get(f"/api/missions/{created['id']}").json()
    assert completed["mission"]["status"] == "completed"
    assert completed["approvals"][-1]["status"] == "approved"
    assert any(event["event_type"] == "approval.consumed" for event in completed["events"])


def test_approval_rejection_stops_mission(client):
    seed(client)
    created = client.post("/api/missions", json={
        "title": "Rejected approval proof", "vendor_name": "Northstar Cloud Systems",
        "objective": "Demonstrate human rejection of a high-risk decision.",
        "auto_run": True, "proof_scenario": "high_risk_approval",
    }).json()
    waiting = client.get(f"/api/missions/{created['id']}").json()
    approval = waiting["approvals"][-1]
    client.post(
        f"/api/missions/{created['id']}/approvals/{approval['id']}/decide",
        headers={"X-Role": "risk_manager", "X-Actor": "human-risk-manager"},
        json={"decision": "rejected", "note": "Evidence is insufficient."},
    )
    stopped = client.get(f"/api/missions/{created['id']}").json()
    assert stopped["mission"]["status"] == "stopped"
    assert stopped["approvals"][-1]["status"] == "rejected"


def test_budget_limit_stops_execution(client):
    seed(client)
    created = client.post("/api/missions", json={
        "title": "Budget proof", "vendor_name": "Northstar Cloud Systems",
        "objective": "Demonstrate that the budget governor stops execution.",
        "auto_run": True, "proof_scenario": "budget_limit",
    }).json()
    detail = client.get(f"/api/missions/{created['id']}").json()
    assert detail["mission"]["status"] == "budget_exceeded"
    assert any(event["event_type"] == "budget.exceeded" for event in detail["events"])


def test_retry_recovery_and_weak_report_repair(client):
    seed(client)
    retry = client.post("/api/missions", json={
        "title": "Recovery proof", "vendor_name": "Northstar Cloud Systems",
        "objective": "Demonstrate checkpointed recovery from a transient agent failure.",
        "auto_run": True, "proof_scenario": "retry_recovery",
    }).json()
    retry_detail = client.get(f"/api/missions/{retry['id']}").json()
    assert retry_detail["mission"]["status"] == "completed"
    operations = next(task for task in retry_detail["tasks"] if task["agent_name"] == "operations")
    assert operations["attempts"] == 2
    assert any(event["event_type"] == "agent.retry_scheduled" for event in retry_detail["events"])

    weak = client.post("/api/missions", json={
        "title": "Repair proof", "vendor_name": "Northstar Cloud Systems",
        "objective": "Demonstrate rejection and repair of a weak report.",
        "auto_run": True, "proof_scenario": "weak_report_repair",
    }).json()
    weak_detail = client.get(f"/api/missions/{weak['id']}").json()
    assert weak_detail["mission"]["status"] == "completed"
    red_team = next(task for task in weak_detail["tasks"] if task["agent_name"] == "red_team")
    report = next(task for task in weak_detail["tasks"] if task["agent_name"] == "report")
    assert red_team["output"]["data"]["rejected"] is True
    assert report["output"]["data"]["repaired"] is True


def test_mission_creation_idempotency(client):
    payload = {
        "title": "Idempotent mission", "vendor_name": "Northstar Cloud Systems",
        "objective": "Prove duplicate mission requests do not create duplicate missions.",
        "auto_run": False, "idempotency_key": "mission-key-123",
    }
    first = client.post("/api/missions", json=payload).json()
    second = client.post("/api/missions", json=payload).json()
    assert first["id"] == second["id"]
    assert len(client.get("/api/missions").json()["missions"]) == 1


def test_audit_export_and_chain_verification(client):
    seed(client)
    created = client.post("/api/missions", json={
        "title": "Audit proof", "vendor_name": "Northstar Cloud Systems",
        "objective": "Produce a complete, verifiable mission decision history.", "auto_run": True,
    }).json()
    audit = client.get(f"/api/missions/{created['id']}/audit").json()
    assert audit["verification"]["valid"] is True
    assert audit["verification"]["records"] >= 20
    exported = client.get(f"/api/missions/{created['id']}/audit/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
