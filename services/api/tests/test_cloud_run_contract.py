from pathlib import Path

import yaml

API_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TEMPLATE = API_ROOT / "cloud-run.service.yaml.tmpl"
DOCKERIGNORE = API_ROOT / ".dockerignore"

PROJECT_ID = "patchamomma-2026-505415"
PROJECT_NUMBER = "859217028205"
REGION = "asia-south1"
SERVICE_NAME = "sakhicircle-api"
RUNTIME_SERVICE_ACCOUNT = (
    f"sakhi-runtime@{PROJECT_ID}.iam.gserviceaccount.com"
)
IMAGE_PREFIX = (
    f"{REGION}-docker.pkg.dev/{PROJECT_ID}/sakhi-containers/{SERVICE_NAME}@sha256:"
)


def _render_manifest() -> tuple[str, dict]:
    template = MANIFEST_TEMPLATE.read_text(encoding="utf-8")
    rendered = template.replace("${IMAGE_DIGEST}", "a" * 64).replace(
        "${FIREBASE_APP_ID}", "1:859217028205:web:test-app-id"
    )
    return template, yaml.safe_load(rendered)


def test_cloud_run_manifest_locks_the_approved_runtime_boundary() -> None:
    template, manifest = _render_manifest()

    assert manifest["apiVersion"] == "serving.knative.dev/v1"
    assert manifest["kind"] == "Service"
    assert manifest["metadata"] == {
        "name": SERVICE_NAME,
        "namespace": PROJECT_NUMBER,
        "labels": {"cloud.googleapis.com/location": REGION},
        "annotations": {"run.googleapis.com/ingress": "all"},
    }

    revision = manifest["spec"]["template"]
    assert revision["metadata"]["annotations"] == {
        "autoscaling.knative.dev/minScale": "0",
        "autoscaling.knative.dev/maxScale": "2",
    }

    runtime = revision["spec"]
    assert runtime["containerConcurrency"] == 20
    assert runtime["timeoutSeconds"] == 420
    assert runtime["serviceAccountName"] == RUNTIME_SERVICE_ACCOUNT

    assert len(runtime["containers"]) == 1
    container = runtime["containers"][0]
    assert container["image"] == f"{IMAGE_PREFIX}{'a' * 64}"
    assert container["ports"] == [{"name": "http1", "containerPort": 8080}]
    assert container["resources"]["limits"] == {"cpu": "1", "memory": "512Mi"}

    assert template.count("${IMAGE_DIGEST}") == 1
    assert template.count("${FIREBASE_APP_ID}") == 1


def test_cloud_run_manifest_is_fail_closed_and_contains_no_secret_values() -> None:
    template, manifest = _render_manifest()
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    environment = {
        item["name"]: item.get("value", item.get("valueFrom"))
        for item in container["env"]
    }

    assert environment == {
        "SAKHI_APP_ENV": "production",
        "SAKHI_DEMO_MODE": "false",
        "SAKHI_ADAPTER_MODE": "production",
        "SAKHI_JOURNEY_ADAPTER_MODE": "gemini_adk",
        "SAKHI_JOURNEY_ATTEMPT_TIMEOUT_SECONDS": "30",
        "SAKHI_PROFILE_EXTRACTION_TIMEOUT_SECONDS": "10",
        "SAKHI_PAID_API_CALLS_ENABLED": "true",
        "SAKHI_GEMINI_MODEL": "gemini-3.7-flash",
        "SAKHI_JOURNEY_GEMINI_MODEL": "gemini-2.5-flash",
        "SAKHI_GEMINI_BACKEND": "vertex_ai",
        "SAKHI_GEMINI_LOCATION": "global",
        "GOOGLE_GENAI_USE_VERTEXAI": "true",
        "GOOGLE_CLOUD_PROJECT": PROJECT_ID,
        "GOOGLE_CLOUD_LOCATION": "global",
        "SAKHI_FIREBASE_PROJECT_ID": PROJECT_ID,
        "SAKHI_FIREBASE_APP_ID": "1:859217028205:web:test-app-id",
        "SAKHI_FIRESTORE_DATABASE_ID": "(default)",
        "SAKHI_ALLOWED_ORIGINS": "${ALLOWED_ORIGINS}",
        "SAKHI_ANALYTICS_LOCATION": REGION,
        "SAKHI_ANALYTICS_PRIVATE_DATASET_ID": "sakhi_analytics",
        "SAKHI_ANALYTICS_TABLE_ID": "checkpoint_events_v1",
        "SAKHI_ANALYTICS_REPORTING_DATASET_ID": "sakhi_reporting",
        "SAKHI_ANALYTICS_REPORTING_VIEW_ID": "checkpoint_metrics_v1",
        "SAKHI_ANALYTICS_QUEUE_ID": "analytics-delivery",
        "SAKHI_ANALYTICS_TASK_SERVICE_ACCOUNT": (
            f"sakhi-task-delivery@{PROJECT_ID}.iam.gserviceaccount.com"
        ),
        "SAKHI_ANALYTICS_TASK_AUDIENCE": "${ANALYTICS_TASK_AUDIENCE}",
        "SAKHI_ANALYTICS_HMAC_SECRET_NAME": "sakhi-analytics-hmac-key",
        "SAKHI_ANALYTICS_HMAC_SECRET_VERSIONS": (
            '["${ANALYTICS_HMAC_SECRET_VERSION}"]'
        ),
        "SAKHI_ANALYTICS_CURRENT_HMAC_SECRET_VERSION": (
            "${ANALYTICS_HMAC_SECRET_VERSION}"
        ),
    }

    assert "valueFrom" not in template
    assert "SAKHI_GEMINI_API_KEY" not in template
    assert "SAKHI_ANALYTICS_HMAC_KEY" not in template
    assert "vpc-access-connector" not in template
    assert "cloudsql-instances" not in template
    assert "run.googleapis.com/cpu-throttling" not in template
    assert template.count("${ANALYTICS_TASK_AUDIENCE}") == 1
    assert template.count("${ANALYTICS_HMAC_SECRET_VERSION}") == 2
    assert template.count("${ALLOWED_ORIGINS}") == 1


def test_docker_build_context_excludes_local_and_generated_files() -> None:
    exclusions = {
        line.strip()
        for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {
        ".env",
        ".env.*",
        ".pytest_cache/",
        ".ruff_cache/",
        "**/__pycache__/",
        "**/*.py[cod]",
        "tests/",
    } <= exclusions


def test_container_dependencies_pin_the_verified_adk_vertex_runtime() -> None:
    project = (API_ROOT / "pyproject.toml").read_text()

    assert '"google-adk==2.7.1"' in project
    assert '"google-genai==2.20.0"' in project
    assert '"pydantic==2.13.4"' in project
