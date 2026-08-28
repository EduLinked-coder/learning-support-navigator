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


def load_json(path: str) -> dict:
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_projection(obj: dict) -> list[str]:
    errors: list[str] = []
    required = {
        "sourceRepository",
        "sourceRevision",
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

    if obj.get("sourceRepository") != PRIVATE_REPO:
        errors.append("sourceRepository must be the paired private repository")
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

    errors: list[str] = []

    spec = repo.get("spec", {})
    if spec.get("visibility") != "public":
        errors.append("repository contract must declare public visibility")
    if spec.get("pairedPrivateRepository") != PRIVATE_REPO:
        errors.append("paired private repository identity drift")
    if spec.get("informationClassification", {}).get("acceptedProjectionClassification") != PUBLIC_APPROVED:
        errors.append("repository contract must accept only public_approved projections")
    if spec.get("accessibility", {}).get("conformanceClaim") != "not_established":
        errors.append("bootstrap must not claim accessibility conformance")

    props = schema.get("properties", {})
    if props.get("sourceRepository", {}).get("const") != PRIVATE_REPO:
        errors.append("projection schema private source identity drift")
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

    synthetic_valid = {
        "sourceRepository": PRIVATE_REPO,
        "sourceRevision": "0000000-synthetic-test",
        "projectionVersion": "0.0-test",
        "classification": PUBLIC_APPROVED,
        "approvalEvidence": "synthetic-test-only",
        "preparedAt": "2026-08-17T00:00:00Z",
        "minimisationStatement": "Synthetic validator fixture; contains no private source content.",
        "payload": {"synthetic": True},
    }
    if validate_projection(synthetic_valid):
        errors.append("known-valid synthetic projection was rejected")

    for bad_class in sorted(FORBIDDEN_CLASSIFICATIONS):
        invalid = copy.deepcopy(synthetic_valid)
        invalid["classification"] = bad_class
        if not validate_projection(invalid):
            errors.append(f"negative test failed: classification {bad_class} was accepted")

    missing_approval = copy.deepcopy(synthetic_valid)
    missing_approval["approvalEvidence"] = ""
    if not validate_projection(missing_approval):
        errors.append("negative test failed: missing approval evidence was accepted")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("PASS: public/private boundary, projection intake and bounded synthetic navigation workflow checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
