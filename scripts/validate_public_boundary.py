#!/usr/bin/env python3
"""Validate the public Learning Support Navigator boundary using only stdlib."""

from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_REPO = "EduLinked-coder/learning-support-navigator-private"
PUBLIC_APPROVED = "public_approved"
FORBIDDEN_CLASSIFICATIONS = {"private", "company_confidential", "restricted"}
WORKFLOW_AUTHORITY = "general_navigation_only"
WORKFLOW_OUTCOME = "not_established"
PUBLIC_SOURCE_TYPE = "approved_public_source"
PRIVATE_PROJECTION_TYPE = "paired_private_projection"
LEARNING_CAPABILITY_PROJECTION = "edulinked_learning_capability_projection_v1"


def load_json(path: str) -> dict:
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def approved_public_sources(repo_contract: dict) -> set[str]:
    values = (
        repo_contract.get("spec", {})
        .get("informationClassification", {})
        .get("approvedPublicSourceRepositories", [])
    )
    return {str(value) for value in values if str(value).strip()}


def validate_projection(obj: dict, repo_contract: dict) -> list[str]:
    errors: list[str] = []
    required = {
        "sourceRepository",
        "sourceRevision",
        "sourceType",
        "projectionVersion",
        "classification",
        "approvalEvidence",
        "preparedAt",
        "minimisationStatement",
        "payload",
    }
    missing = sorted(required - set(obj))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    source_repo = obj.get("sourceRepository")
    source_type = obj.get("sourceType")
    public_sources = approved_public_sources(repo_contract)

    if source_type == PRIVATE_PROJECTION_TYPE:
        if source_repo != PRIVATE_REPO:
            errors.append("paired_private_projection must come from the paired private repository")
    elif source_type == PUBLIC_SOURCE_TYPE:
        if source_repo not in public_sources:
            errors.append("approved_public_source must be explicitly allowlisted by the repository contract")
        if not str(obj.get("sourcePath", "")).strip():
            errors.append("approved_public_source requires sourcePath")
    else:
        errors.append("sourceType must be paired_private_projection or approved_public_source")

    if obj.get("classification") != PUBLIC_APPROVED:
        errors.append("classification must be public_approved")
    if obj.get("classification") in FORBIDDEN_CLASSIFICATIONS:
        errors.append("forbidden private classification")
    if not str(obj.get("sourceRevision", "")).strip():
        errors.append("sourceRevision is required")
    if not str(obj.get("approvalEvidence", "")).strip():
        errors.append("approvalEvidence is required")
    if not str(obj.get("minimisationStatement", "")).strip():
        errors.append("minimisationStatement is required")
    if not isinstance(obj.get("payload"), dict):
        errors.append("payload must be an object")
    return errors


def validate_learning_capability_projection(obj: dict) -> list[str]:
    errors: list[str] = []
    payload = obj.get("payload")
    if not isinstance(payload, dict):
        return ["learning capability projection payload must be an object"]
    if payload.get("projectionKind") != LEARNING_CAPABILITY_PROJECTION:
        return ["learning capability projection kind mismatch"]
    if payload.get("consumerRepository") != "EduLinked-coder/learning-support-navigator":
        errors.append("learning capability projection consumer identity drift")
    if payload.get("sourceAuthorityTransferred") is not False:
        errors.append("learning capability projection must not transfer source authority")
    if payload.get("learningSystemImplementationVersion") != "UNVERIFIED":
        errors.append("Learning System implementation version must remain UNVERIFIED until source evidence establishes it")

    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        return errors + ["learning capability projection must contain capabilities"]

    required_fields = {"id", "canonicalOwner", "version", "evidenceState", "sourceRef", "claimCeiling"}
    ids: list[str] = []
    by_id: dict[str, dict] = {}
    for index, capability in enumerate(capabilities):
        if not isinstance(capability, dict):
            errors.append(f"capabilities[{index}] must be an object")
            continue
        missing = sorted(required_fields - set(capability))
        if missing:
            errors.append(f"capabilities[{index}] missing fields: {', '.join(missing)}")
            continue
        cid = str(capability.get("id", "")).strip()
        ids.append(cid)
        by_id[cid] = capability
        if any(not str(capability.get(field, "")).strip() for field in required_fields):
            errors.append(f"capability {cid or index} contains blank required values")

    if len(ids) != len(set(ids)):
        errors.append("learning capability projection must not contain duplicate capability ids")

    required_ids = {
        "inclusive-learning-builder",
        "accessflow",
        "evidencepath",
        "universal-learning-design",
        "global-learning-package-portability-profile",
        "individual-contribution-evidence-profile",
    }
    missing_ids = sorted(required_ids - set(ids))
    if missing_ids:
        errors.append(f"learning capability projection missing expected reusable capabilities: {', '.join(missing_ids)}")

    accessflow = by_id.get("accessflow", {})
    if accessflow:
        if accessflow.get("version") != "1.2.0":
            errors.append("AccessFlow public projection must use current evidenced version 1.2.0")
        if accessflow.get("evidenceState") != "RUNTIME_PROVEN_BOUNDED":
            errors.append("AccessFlow evidence state must remain bounded runtime-proven")
        if "not established" not in str(accessflow.get("claimCeiling", "")).lower():
            errors.append("AccessFlow claim ceiling must preserve explicit non-conformance limitation")

    ilb = by_id.get("inclusive-learning-builder", {})
    if ilb and ilb.get("version") != "1.5.0":
        errors.append("Inclusive Learning Builder public projection must use current evidenced version 1.5.0")

    evidencepath = by_id.get("evidencepath", {})
    if evidencepath and evidencepath.get("version") != "1.2.0":
        errors.append("EvidencePath public projection must use current evidenced version 1.2.0")

    uld = by_id.get("universal-learning-design", {})
    if uld:
        if uld.get("version") != "0.2.0":
            errors.append("Universal Learning Design public projection must use current evidenced version 0.2.0")
        if "operational learner runtime" not in str(uld.get("claimCeiling", "")).lower():
            errors.append("Universal Learning Design claim ceiling must preserve no-operational-runtime limitation")

    glpp = by_id.get("global-learning-package-portability-profile", {})
    if glpp and glpp.get("version") != "1.0.0":
        errors.append("Global Learning Package Portability Profile must remain at evidenced version 1.0.0")

    icep = by_id.get("individual-contribution-evidence-profile", {})
    if icep and icep.get("version") != "1.1.0":
        errors.append("Individual Contribution Evidence Profile must remain at evidenced version 1.1.0")

    return errors


def validate_navigation_workflow(example: dict) -> list[str]:
    errors: list[str] = []
    workflow = example.get("workflow")
    if not isinstance(workflow, dict):
        return ["synthetic navigation example must include a workflow object"]

    for field in ("barrierOrConcern", "responsibleActor", "reviewOrNextAction"):
        if not str(workflow.get(field, "")).strip():
            errors.append(f"workflow.{field} is required")

    options = workflow.get("boundedSupportOptions")
    if not isinstance(options, list) or not options or any(not str(option).strip() for option in options):
        errors.append("workflow.boundedSupportOptions must contain at least one bounded support option")
    if workflow.get("authorityClass") != WORKFLOW_AUTHORITY:
        errors.append("workflow authority must remain general_navigation_only")
    if workflow.get("personSpecificDecision") is not False:
        errors.append("synthetic workflow must not make a person-specific decision")
    if workflow.get("outcomeClaim") != WORKFLOW_OUTCOME:
        errors.append("synthetic workflow must keep outcome claim not_established")
    return errors


def main() -> int:
    repo = load_json(".repository/repo.json")
    schema = load_json("contracts/public-projection-intake.schema.json")
    example = load_json("examples/public-navigation-example.json")
    learning_projection = load_json("examples/accessible-rto-learning-capability-projection.json")

    errors: list[str] = []

    spec = repo.get("spec", {})
    if spec.get("visibility") != "public":
        errors.append("repository contract must declare public visibility")
    if spec.get("pairedPrivateRepository") != PRIVATE_REPO:
        errors.append("paired private repository identity drift")
    if spec.get("informationClassification", {}).get("acceptedProjectionClassification") != PUBLIC_APPROVED:
        errors.append("repository contract must accept only public_approved projections")
    if "EduLinked-Pty-Ltd/accessible-RTO" not in approved_public_sources(repo):
        errors.append("accessible-RTO public source binding is not allowlisted")
    if spec.get("accessibility", {}).get("conformanceClaim") != "not_established":
        errors.append("bootstrap must not claim accessibility conformance")

    props = schema.get("properties", {})
    source_type_values = set(props.get("sourceType", {}).get("enum", []))
    if source_type_values != {PRIVATE_PROJECTION_TYPE, PUBLIC_SOURCE_TYPE}:
        errors.append("projection schema sourceType values drift")
    if props.get("classification", {}).get("const") != PUBLIC_APPROVED:
        errors.append("projection schema must fail closed to public_approved only")

    if example.get("synthetic") is not True:
        errors.append("public navigation example must be explicitly synthetic")
    boundaries = " ".join(example.get("boundaries", [])).lower()
    if "no real learner" not in boundaries:
        errors.append("synthetic example must state that no real learner data is present")
    if "legal entitlement" not in boundaries:
        errors.append("synthetic example must not imply legal determination")
    errors.extend(validate_navigation_workflow(example))

    errors.extend(validate_projection(learning_projection, repo))
    errors.extend(validate_learning_capability_projection(learning_projection))

    synthetic_valid = {
        "sourceRepository": PRIVATE_REPO,
        "sourceRevision": "0000000-synthetic-test",
        "sourceType": PRIVATE_PROJECTION_TYPE,
        "projectionVersion": "0.0-test",
        "classification": PUBLIC_APPROVED,
        "approvalEvidence": "synthetic-test-only",
        "preparedAt": "2026-08-17T00:00:00Z",
        "minimisationStatement": "Synthetic validator fixture; contains no private source content.",
        "payload": {"synthetic": True},
    }
    if validate_projection(synthetic_valid, repo):
        errors.append("known-valid synthetic private projection was rejected")

    public_valid = copy.deepcopy(learning_projection)
    if validate_projection(public_valid, repo):
        errors.append("known-valid allowlisted public-source projection was rejected")

    for bad_class in sorted(FORBIDDEN_CLASSIFICATIONS):
        invalid = copy.deepcopy(synthetic_valid)
        invalid["classification"] = bad_class
        if not validate_projection(invalid, repo):
            errors.append(f"negative test failed: classification {bad_class} was accepted")

    missing_approval = copy.deepcopy(synthetic_valid)
    missing_approval["approvalEvidence"] = ""
    if not validate_projection(missing_approval, repo):
        errors.append("negative test failed: missing approval evidence was accepted")

    unauthorised_source = copy.deepcopy(public_valid)
    unauthorised_source["sourceRepository"] = "Example/Unapproved-Public-Repo"
    if not validate_projection(unauthorised_source, repo):
        errors.append("negative test failed: unapproved public source repository was accepted")

    missing_public_path = copy.deepcopy(public_valid)
    missing_public_path.pop("sourcePath", None)
    if not validate_projection(missing_public_path, repo):
        errors.append("negative test failed: approved public source without sourcePath was accepted")

    invented_learning_system = copy.deepcopy(public_valid)
    invented_learning_system["payload"]["learningSystemImplementationVersion"] = "1.0.0"
    if not validate_learning_capability_projection(invented_learning_system):
        errors.append("negative test failed: invented Learning System version was accepted")

    transferred_authority = copy.deepcopy(public_valid)
    transferred_authority["payload"]["sourceAuthorityTransferred"] = True
    if not validate_learning_capability_projection(transferred_authority):
        errors.append("negative test failed: source authority transfer was accepted")

    accessflow_overclaim = copy.deepcopy(public_valid)
    for capability in accessflow_overclaim["payload"]["capabilities"]:
        if capability.get("id") == "accessflow":
            capability["claimCeiling"] = "Accessibility conformance established."
    if not validate_learning_capability_projection(accessflow_overclaim):
        errors.append("negative test failed: AccessFlow accessibility-conformance overclaim was accepted")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("PASS: public/private boundary, paired-private and approved-public projection intake, learning capability binding, and bounded synthetic navigation checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
