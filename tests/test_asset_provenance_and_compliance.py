"""Tests for asset provenance, font integrity, and compliance invariants.

Verifies:
1. Cryptographic SHA-256 checksums of all self-hosted font binaries against FONTS_PROVENANCE.md.
2. Complete absence of external remote stylesheet/font URLs in frontend CSS (offline privacy / default-deny).
3. Existence and validity of SIL Open Font License (OFL.txt).
4. Synchrony between requirements.txt runtime packages and THIRD_PARTY_NOTICES.md.
5. Strict edge-tts 7.x version pinning in requirements.txt.
"""

import hashlib
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FRONTEND = RAIZ / "frontend"
FONTS_DIR = FRONTEND / "src" / "assets" / "fonts"
FONTS_PROVENANCE = FONTS_DIR / "FONTS_PROVENANCE.md"
FONTS_CSS = FRONTEND / "src" / "fonts.css"
INDEX_CSS = FRONTEND / "src" / "index.css"
OFL_TXT = FONTS_DIR / "OFL.txt"
REQUIREMENTS_TXT = RAIZ / "requirements.txt"
THIRD_PARTY_NOTICES = RAIZ / "THIRD_PARTY_NOTICES.md"
COMPLIANCE_REVIEW = RAIZ / "docs" / "legal" / "COMPLIANCE-REVIEW.md"


def _strip_css_comments(css: str) -> str:
    """Removes CSS block comments to evaluate executable rules only."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def test_fonts_provenance_markdown_exists_and_matches_binary_hashes():
    """Validates that all font files declared in FONTS_PROVENANCE.md match their SHA-256 checksums on disk."""
    assert FONTS_PROVENANCE.exists(), f"Missing font provenance file: {FONTS_PROVENANCE}"
    content = FONTS_PROVENANCE.read_text(encoding="utf-8")

    row_pattern = re.compile(r"\|\s*`([^`]+\.woff2)`\s*\|[^|]*\|[^|]*\|[^|]*\|\s*`([a-f0-9]{64})`\s*\|", re.IGNORECASE)
    matches = row_pattern.findall(content)

    assert len(matches) >= 6, f"Expected at least 6 font declarations in FONTS_PROVENANCE.md, found {len(matches)}"

    declared_files = set()
    for filename, expected_hash in matches:
        font_path = FONTS_DIR / filename
        assert font_path.exists(), (
            f"Font file '{filename}' declared in FONTS_PROVENANCE.md does not exist on disk at {font_path}"
        )

        actual_hash = hashlib.sha256(font_path.read_bytes()).hexdigest().lower()
        assert actual_hash == expected_hash.lower(), (
            f"Cryptographic hash mismatch for font '{filename}':\n"
            f"  Expected (FONTS_PROVENANCE.md): {expected_hash}\n"
            f"  Actual (disk):                 {actual_hash}"
        )
        declared_files.add(filename)

    disk_woff2_files = {p.name for p in FONTS_DIR.glob("*.woff2")}
    assert disk_woff2_files == declared_files, (
        f"Mismatch between disk woff2 files and FONTS_PROVENANCE.md:\n"
        f"  On disk only: {disk_woff2_files - declared_files}\n"
        f"  In doc only:  {declared_files - disk_woff2_files}"
    )


def test_fonts_css_local_resolution_and_zero_remote_urls():
    """Verifies that all CSS files under frontend have zero remote external URL imports and all local fonts resolve."""
    css_files = list((FRONTEND / "src").glob("**/*.css"))
    assert len(css_files) >= 2, f"Expected at least 2 CSS files under frontend/src, found {len(css_files)}"

    remote_url_pattern = re.compile(r"""url\(\s*['"]?(?:https?:)?//""", re.IGNORECASE)
    remote_import_pattern = re.compile(r"""@import\s+['"]?(?:https?:)?//""", re.IGNORECASE)
    local_url_pattern = re.compile(r"""url\(\s*['"]?(\./assets/fonts/[^'")]+)['"]?\s*\)""", re.IGNORECASE)

    for css_file in css_files:
        css_clean = _strip_css_comments(css_file.read_text(encoding="utf-8"))

        # 1. Assert zero remote URLs or protocol-relative URLs in url(...)
        assert not remote_url_pattern.search(css_clean), (
            f"{css_file.name} contains remote http/https/protocol-relative URL references"
        )

        # 2. Assert zero remote @import statements
        assert not remote_import_pattern.search(css_clean), f"{css_file.name} contains remote @import statement"

        # 3. Assert no remote Google Fonts domain references
        assert "fonts.googleapis.com" not in css_clean, f"{css_file.name} references fonts.googleapis.com"
        assert "fonts.gstatic.com" not in css_clean, f"{css_file.name} references fonts.gstatic.com"

        # 4. Assert all local font url() references resolve to actual files
        for rel_path in local_url_pattern.findall(css_clean):
            resolved_path = (css_file.parent / rel_path).resolve()
            assert resolved_path.exists(), (
                f"Referenced font path '{rel_path}' in {css_file.name} does not exist on disk: {resolved_path}"
            )


def test_ofl_license_file_exists():
    """Verifies that the SIL Open Font License 1.1 file exists with complete canonical clauses."""
    assert OFL_TXT.exists(), f"Missing OFL.txt license file at {OFL_TXT}"
    content = OFL_TXT.read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in content
    assert "PREAMBLE" in content
    assert "PERMISSION & CONDITIONS" in content
    assert "TERMINATION" in content
    assert "DISCLAIMER" in content


def test_requirements_pins_edge_tts_7x():
    """Verifies that requirements.txt pins edge-tts to the LGPL-3.0 7.x line."""
    assert REQUIREMENTS_TXT.exists()
    reqs = REQUIREMENTS_TXT.read_text(encoding="utf-8")
    match = re.search(r"^edge-tts([>=<0-9., ]+)", reqs, re.MULTILINE)
    assert match is not None, "edge-tts dependency not found in requirements.txt"
    version_spec = match.group(1).replace(" ", "")
    assert ">=7.0.0" in version_spec
    assert "<8.0.0" in version_spec


def test_third_party_notices_and_compliance_review_exist():
    """Verifies existence and structural completeness of legal documentation and package inventory."""
    assert THIRD_PARTY_NOTICES.exists(), f"Missing {THIRD_PARTY_NOTICES}"
    assert COMPLIANCE_REVIEW.exists(), f"Missing {COMPLIANCE_REVIEW}"

    notices_text = THIRD_PARTY_NOTICES.read_text(encoding="utf-8")
    compliance_text = COMPLIANCE_REVIEW.read_text(encoding="utf-8")

    # Verify all backend runtime dependencies are documented in notices
    dev_test_tools = {"pytest", "pytest-asyncio", "pytest-cov", "ruff"}
    backend_reqs = REQUIREMENTS_TXT.read_text(encoding="utf-8").splitlines()
    for line in backend_reqs:
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        pkg_name = re.split(r"[><=~;\[]", clean)[0].strip()
        if pkg_name.lower() in dev_test_tools:
            continue
        # Verify package is documented in notices
        pattern = re.compile(rf"\b{re.escape(pkg_name)}\b", re.IGNORECASE)
        assert pattern.search(notices_text), (
            f"Backend runtime package '{pkg_name}' not documented in THIRD_PARTY_NOTICES.md"
        )

    # Verify core frontend dependencies
    for dep in ["React", "react-dom", "Vite"]:
        assert dep in notices_text, f"Expected frontend dependency '{dep}' to be listed in THIRD_PARTY_NOTICES.md"

    # Verify compliance taxonomy markers
    for rating in ["VERIFIED", "CONTRACTUAL RISK", "REQUIRES LEGAL REVIEW"]:
        assert rating in compliance_text, f"Expected compliance taxonomy rating '{rating}' in COMPLIANCE-REVIEW.md"


def test_frontend_site_config_and_seo_plugin_structure():
    """Verifies that site.config.js and vite.config.js define canonical URLs, metadata, and JSON-LD schema generator."""
    site_config_js = FRONTEND / "site.config.js"
    vite_config_js = FRONTEND / "vite.config.js"
    index_html = FRONTEND / "index.html"

    assert site_config_js.exists(), f"Missing site.config.js at {site_config_js}"
    assert vite_config_js.exists(), f"Missing vite.config.js at {vite_config_js}"
    assert index_html.exists(), f"Missing index.html at {index_html}"

    site_content = site_config_js.read_text(encoding="utf-8")
    assert "defaultSiteUrl" in site_content
    assert "getBasePath" in site_content
    assert "generateSoftwareApplicationSchema" in site_content
    assert "siteConfig" in site_content

    vite_content = vite_config_js.read_text(encoding="utf-8")
    assert "seoPlugin" in vite_content
    assert "robots.txt" in vite_content
    assert "sitemap.xml" in vite_content
    assert "application/ld+json" in vite_content

    html_content = index_html.read_text(encoding="utf-8")
    assert "<!-- %SEO_METADATA% -->" in html_content or "<!-- SEO_PLACEHOLDER -->" in html_content
    assert "<noscript>" in html_content
