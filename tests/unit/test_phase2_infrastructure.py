"""
SignalStream — Phase 2 Infrastructure Validation Tests
======================================================
Verifies repository structure, infrastructure configurations, and service manifests.
Compatible with standard unittest and pytest.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPhase2Infrastructure(unittest.TestCase):

    def test_dockerfiles_exist(self):
        """Verify all required Dockerfiles are present."""
        expected_dockerfiles = [
            REPO_ROOT / "infrastructure" / "docker" / "api" / "Dockerfile",
            REPO_ROOT / "infrastructure" / "docker" / "worker" / "Dockerfile",
            REPO_ROOT / "infrastructure" / "docker" / "inference" / "Dockerfile",
            REPO_ROOT / "infrastructure" / "docker" / "frontend" / "Dockerfile",
        ]
        for df in expected_dockerfiles:
            self.assertTrue(df.exists(), f"Missing Dockerfile: {df}")
            self.assertGreater(df.stat().st_size, 0, f"Empty Dockerfile: {df}")

    def test_database_init_script(self):
        """Verify postgres init script contains pgvector and uuid extensions."""
        init_sql = REPO_ROOT / "scripts" / "init_db.sql"
        self.assertTrue(init_sql.exists(), "scripts/init_db.sql missing")
        content = init_sql.read_text(encoding="utf-8")
        self.assertIn("vector", content, "Missing vector extension in init_db.sql")
        self.assertTrue(
            "uuid-ossp" in content or "pgcrypto" in content,
            "Missing uuid extension",
        )

    def test_monitoring_configurations(self):
        """Verify Prometheus, Grafana, and Nginx configurations exist."""
        prom_yml = REPO_ROOT / "infrastructure" / "monitoring" / "prometheus" / "prometheus.yml"
        self.assertTrue(prom_yml.exists(), "prometheus.yml missing")

        gf_ds = REPO_ROOT / "infrastructure" / "monitoring" / "grafana" / "datasources" / "datasource.yml"
        self.assertTrue(gf_ds.exists(), "Grafana datasource.yml missing")

        gf_prov = REPO_ROOT / "infrastructure" / "monitoring" / "grafana" / "dashboards" / "dashboard_provider.yml"
        self.assertTrue(gf_prov.exists(), "Grafana dashboard_provider.yml missing")

        gf_dash = REPO_ROOT / "infrastructure" / "monitoring" / "grafana" / "dashboards" / "signalstream_overview.json"
        self.assertTrue(gf_dash.exists(), "Grafana overview dashboard missing")

        nginx_conf = REPO_ROOT / "infrastructure" / "nginx" / "conf.d" / "default.conf"
        self.assertTrue(nginx_conf.exists(), "Nginx default.conf missing")

    def test_kubernetes_manifests_exist(self):
        """Verify base and overlay Kubernetes manifests exist."""
        base_kust = REPO_ROOT / "infrastructure" / "kubernetes" / "base" / "kustomization.yaml"
        self.assertTrue(base_kust.exists(), "Base kustomization.yaml missing")

        staging_kust = REPO_ROOT / "infrastructure" / "kubernetes" / "overlays" / "staging" / "kustomization.yaml"
        self.assertTrue(staging_kust.exists(), "Staging kustomization.yaml missing")

        prod_kust = REPO_ROOT / "infrastructure" / "kubernetes" / "overlays" / "production" / "kustomization.yaml"
        self.assertTrue(prod_kust.exists(), "Production kustomization.yaml missing")

    def test_worker_entrypoints_exist(self):
        """Verify all 13 worker main entry points exist."""
        workers = [
            "normalization",
            "sentiment",
            "complaint",
            "trend",
            "crisis",
            "rootcause",
            "demand",
            "product",
            "support",
            "churn",
            "recommendation",
            "ticket_routing",
            "auto_resolver",
        ]
        for w in workers:
            main_file = REPO_ROOT / "workers" / w / "main.py"
            self.assertTrue(main_file.exists(), f"Worker {w} main.py missing")

    def test_services_entrypoints_exist(self):
        """Verify auxiliary service entrypoints exist."""
        self.assertTrue((REPO_ROOT / "services" / "inference" / "main.py").exists())
        self.assertTrue((REPO_ROOT / "services" / "mcp_server" / "main.py").exists())

    def test_kafka_topics_configuration(self):
        """Verify all 23 Kafka topics are defined."""
        from scripts.init_kafka_topics import TOPICS_CONFIG

        self.assertEqual(len(TOPICS_CONFIG), 23)
        topic_names = {t[0] for t in TOPICS_CONFIG}
        self.assertIn("feedback.raw", topic_names)
        self.assertIn("feedback.normalized", topic_names)
        self.assertIn("feedback.enriched", topic_names)
        self.assertIn("dlq.feedback.raw", topic_names)
        self.assertIn("retry.feedback.normalized", topic_names)


if __name__ == "__main__":
    unittest.main()
