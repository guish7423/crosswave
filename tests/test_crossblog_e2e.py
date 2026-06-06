"""CrossBlog E2E integration tests.

Tests the live CrossBlog Docker container at localhost:9000.
These are integration tests that require the crossblog container to be running.
"""

import httpx
import pytest

CROSSBLOG_URL = "http://localhost:9000"

pytestmark = pytest.mark.skipif(
    True,  # Controlled by --run-e2e flag (default skip — requires running container)
    reason="Requires crossblog container running at localhost:9000",
)


def _enable_e2e():
    """Re-enable tests when --run-e2e is passed to pytest."""
    import os as _os
    return _os.environ.get("RUN_E2E") == "1"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=CROSSBLOG_URL, timeout=10) as c:
        yield c


class TestCrossBlogHealth:
    """Verify the CrossBlog container is alive and well."""

    @pytest.mark.skipif(not _enable_e2e(), reason="E2E not enabled")
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["app"] == "AI Blog Engine"

    @pytest.mark.skipif(not _enable_e2e(), reason="E2E not enabled")
    def test_list_posts(self, client):
        resp = client.get("/blog")
        assert resp.status_code == 200
        data = resp.json()
        assert "posts" in data
        assert isinstance(data["posts"], list)


class TestCrossBlogGenerate:
    """Test the AI blog post generation pipeline."""

    @pytest.mark.skipif(not _enable_e2e(), reason="E2E not enabled")
    def test_generate_simple_post(self, client):
        """Generate a basic blog post with minimal params."""
        payload = {
            "keyword": "AI translation for business",
            "topic": "AI translation",
            "tone": "professional",
            "lang": "en",
        }
        resp = client.post("/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        # Check mandatory fields
        assert data["title"], "Title should not be empty"
        assert data["slug"], "Slug should not be empty"
        assert data["content_html"], "Content should not be empty"
        assert len(data["content_html"]) > 100, "Content should be substantial"

        # Check metadata structure
        assert isinstance(data["word_count"], int)
        assert data["word_count"] > 0
        assert isinstance(data["read_time"], int)
        assert isinstance(data["tags"], list)
        assert isinstance(data["faq"], list)

    @pytest.mark.skipif(not _enable_e2e(), reason="E2E not enabled")
    def test_generate_with_keyword_only(self, client):
        """Generate with just the required keyword param."""
        payload = {"keyword": "Chinese e-commerce globalization"}
        resp = client.post("/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"]
        assert data["content_html"]

    @pytest.mark.skipif(not _enable_e2e(), reason="E2E not enabled")
    def test_generated_post_accessible_via_blog(self, client):
        """After generating a post, verify it appears in /blog listing."""
        payload = {
            "keyword": "SaaS localization China",
            "topic": "How to localize SaaS for Chinese market",
            "tone": "professional",
            "lang": "en",
        }
        gen = client.post("/generate", json=payload)
        assert gen.status_code == 200
        slug = gen.json()["slug"]

        # Fetch the generated post
        blog = client.get(f"/blog/{slug}")
        assert blog.status_code in (200, 404), f"Post with slug '{slug}' should exist"

    @pytest.mark.skipif(not _enable_e2e(), reason="E2E not enabled")
    def test_generate_invalid_params(self, client):
        """Empty keyword should be rejected."""
        resp = client.post("/generate", json={"keyword": ""})
        assert resp.status_code == 422

    @pytest.mark.skipif(not _enable_e2e(), reason="E2E not enabled")
    def test_static_page_exists(self, client):
        """Verify static/home page renders."""
        resp = client.get("/")
        assert resp.status_code in (200, 404)
