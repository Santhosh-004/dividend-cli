import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from dividend_calculator import server


class TestServerFrontendServing(unittest.TestCase):
    def test_missing_frontend_build_returns_503(self):
        with TemporaryDirectory() as temp_dir:
            missing_dist = Path(temp_dir) / "missing-dist"

            with patch.object(server, "_FRONTEND_DIST", missing_dist):
                client = TestClient(server.app)
                response = client.get("/")

        self.assertEqual(response.status_code, 503)
        self.assertIn("Frontend build not found", response.text)

    def test_serves_spa_routes_and_frontend_assets(self):
        with TemporaryDirectory() as temp_dir:
            frontend_dist = Path(temp_dir)
            index_file = frontend_dist / "index.html"
            asset_dir = frontend_dist / "_app" / "immutable"
            asset_file = asset_dir / "app.js"
            favicon_file = frontend_dist / "favicon.svg"

            asset_dir.mkdir(parents=True)
            index_file.write_text("<html><body>Dividend CLI UI</body></html>", encoding="utf-8")
            asset_file.write_text("console.log('bundled asset');", encoding="utf-8")
            favicon_file.write_text("<svg></svg>", encoding="utf-8")

            with patch.object(server, "_FRONTEND_DIST", frontend_dist):
                client = TestClient(server.app)

                home_response = client.get("/")
                spa_response = client.get("/screener")
                asset_response = client.get("/_app/immutable/app.js")
                favicon_response = client.get("/favicon.svg")
                missing_asset_response = client.get("/missing.js")

        self.assertEqual(home_response.status_code, 200)
        self.assertIn("Dividend CLI UI", home_response.text)

        self.assertEqual(spa_response.status_code, 200)
        self.assertIn("Dividend CLI UI", spa_response.text)

        self.assertEqual(asset_response.status_code, 200)
        self.assertIn("bundled asset", asset_response.text)

        self.assertEqual(favicon_response.status_code, 200)
        self.assertIn("image/svg+xml", favicon_response.headers["content-type"])

        self.assertEqual(missing_asset_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
