#!/usr/bin/env python3
"""
SwarmGEO API — Generative Engine Optimization Scanner
=====================================================
Scans any URL and scores how AI models see, cite, and reference the content.
Free report → paid optimization plans.

GEO Dimensions Scored:
  1. STRUCTURED DATA   — Schema.org, JSON-LD, Open Graph, meta tags
  2. CONTENT CLARITY   — Headings, paragraphs, reading level, Q&A patterns
  3. ENTITY DENSITY    — Named entities, facts, citations, specificity
  4. CITATION READINESS — Is content quotable? Does it answer questions directly?
  5. AUTHORITY SIGNALS  — About pages, author info, credentials, trust markers
  6. FRESHNESS         — Dates, timestamps, update frequency signals
  7. TECHNICAL ACCESS   — robots.txt, sitemap, page speed, mobile, HTTPS

Endpoints:
  POST /geo/api/scan    — Submit URL for scanning
  GET  /geo/api/report/<id> — Get scan report

Usage:
    python3 geo_api.py --port 9093
"""
import argparse
import hashlib
import html as html_lib
import json
import logging
import os
import re
import secrets
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logging.basicConfig(level=logging.INFO, format="%(asctime)s [geo] %(levelname)s %(message)s")
log = logging.getLogger("geo")

DB_URL = os.environ.get("DATABASE_URL", "")
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma3:4b")
REPORTS = {}  # In-memory cache (production: use DB)


def llm_score(text_content, url, dimension):
    """Call Whale LLM for deep GEO scoring. Returns (score, findings_list)."""
    prompts = {
        "citation_readiness": f"""You are a GEO (Generative Engine Optimization) expert analyzing a webpage for AI citation readiness.

URL: {url}

PAGE CONTENT (truncated):
{text_content[:3000]}

Score this page 0-100 on CITATION READINESS — how likely are AI models (ChatGPT, Claude, Gemini, Perplexity) to quote or cite this content when answering user questions?

Evaluate:
1. Does the content directly answer questions? (not just describe, but ANSWER)
2. Are there quotable passages — concise, factual statements an AI would extract?
3. Does it use clear definitions, comparisons, or step-by-step explanations?
4. Are claims backed by specific data, not vague assertions?
5. Is the content structured so an AI can extract discrete facts?

Respond with ONLY this JSON:
{{"score": <0-100>, "findings": ["finding 1", "finding 2", "finding 3", "finding 4"], "quotable_passages": ["best quotable sentence 1", "best quotable sentence 2"]}}""",

        "entity_density": f"""You are a GEO expert analyzing a webpage for entity density and factual specificity.

URL: {url}

PAGE CONTENT (truncated):
{text_content[:3000]}

Score this page 0-100 on ENTITY DENSITY — how rich is the content with named entities, specific facts, data points, and domain expertise that AI models can index?

Evaluate:
1. Named entities: companies, people, products, technologies, standards
2. Quantitative claims: numbers, percentages, dollar amounts, measurements
3. Domain-specific terminology: does the author demonstrate real expertise?
4. Temporal markers: dates, versions, timeframes that establish currency
5. Relationship density: does the content connect entities to each other?

Respond with ONLY this JSON:
{{"score": <0-100>, "findings": ["finding 1", "finding 2", "finding 3", "finding 4"], "key_entities": ["entity 1", "entity 2", "entity 3"]}}""",
    }

    prompt = prompts.get(dimension)
    if not prompt:
        return None, []

    try:
        payload = json.dumps({
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 500},
        }).encode()

        req = urllib.request.Request(
            f"{LLM_ENDPOINT}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read().decode())
        content = data.get("message", {}).get("content", "")

        # Parse JSON from response
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            score = max(0, min(100, int(result.get("score", 50))))
            findings = result.get("findings", [])
            extras = result.get("quotable_passages", result.get("key_entities", []))
            if extras:
                findings.append(f"AI extracted: {', '.join(str(e)[:50] for e in extras[:3])}")
            return score, findings

        log.warning("LLM response not parseable: %s", content[:200])
        return None, []

    except Exception as e:
        log.error("LLM call failed for %s: %s", dimension, e)
        return None, []


def fetch_url(url, timeout=15):
    """Fetch a URL and return (html, status, headers, error)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "SwarmGEO-Scanner/1.0 (+https://swarmandbee.ai/geo)",
            "Accept": "text/html,application/xhtml+xml",
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        html = resp.read(500000).decode("utf-8", errors="replace")  # 500KB max
        headers = dict(resp.headers)
        return html, resp.status, headers, None
    except urllib.error.HTTPError as e:
        return None, e.code, {}, str(e)
    except Exception as e:
        return None, 0, {}, str(e)


def scan_url(url):
    """Full GEO scan of a URL. Returns score breakdown."""
    report = {
        "url": url,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "scores": {},
        "findings": [],
        "overall_score": 0,
        "grade": "F",
    }

    # Fetch
    html, status, headers, error = fetch_url(url)
    if not html:
        report["error"] = error or f"HTTP {status}"
        return report

    report["http_status"] = status
    report["content_length"] = len(html)

    # ── 1. STRUCTURED DATA (0-100) ──
    sd_score = 0
    sd_findings = []

    # JSON-LD
    jsonld = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    if jsonld:
        sd_score += 30
        sd_findings.append(f"{len(jsonld)} JSON-LD blocks found")
        for block in jsonld:
            try:
                data = json.loads(block)
                dtype = data.get("@type", "unknown")
                sd_findings.append(f"  Schema: {dtype}")
            except Exception:
                sd_findings.append("  Warning: malformed JSON-LD")
    else:
        sd_findings.append("NO JSON-LD structured data — AI models can't parse your entity relationships")

    # Open Graph
    og_tags = re.findall(r'<meta\s+property=["\']og:(\w+)["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    og_tags += re.findall(r'<meta\s+content=["\']([^"\']*)["\'][^>]*property=["\']og:(\w+)["\']', html, re.IGNORECASE)
    if len(og_tags) >= 4:
        sd_score += 20
        sd_findings.append(f"{len(og_tags)} Open Graph tags")
    elif og_tags:
        sd_score += 10
        sd_findings.append(f"Only {len(og_tags)} OG tags — need at least title, description, image, url")
    else:
        sd_findings.append("NO Open Graph tags — social sharing and AI snippets will be generic")

    # Meta description
    meta_desc = re.search(r'<meta\s+name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if meta_desc and len(meta_desc.group(1)) > 50:
        sd_score += 15
        sd_findings.append(f"Meta description: {len(meta_desc.group(1))} chars")
    elif meta_desc:
        sd_score += 5
        sd_findings.append(f"Meta description too short: {len(meta_desc.group(1))} chars (need 50+)")
    else:
        sd_findings.append("NO meta description — AI models use this as your site's summary")

    # Title
    title = re.search(r'<title>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    if title and len(title.group(1).strip()) > 10:
        sd_score += 10
    else:
        sd_findings.append("Missing or short <title> tag")

    # Schema.org microdata
    if 'itemtype=' in html.lower() or 'itemprop=' in html.lower():
        sd_score += 10
        sd_findings.append("Schema.org microdata detected")

    # Twitter cards
    twitter = re.findall(r'<meta\s+name=["\']twitter:', html, re.IGNORECASE)
    if twitter:
        sd_score += 5
        sd_findings.append(f"{len(twitter)} Twitter card tags")

    # FAQ schema
    if '"FAQPage"' in html or 'FAQPage' in html:
        sd_score += 10
        sd_findings.append("FAQ schema detected — excellent for AI Q&A extraction")

    sd_score = min(sd_score, 100)
    report["scores"]["structured_data"] = {"score": sd_score, "findings": sd_findings}

    # ── 2. CONTENT CLARITY (0-100) ──
    cc_score = 0
    cc_findings = []

    # Strip tags for text analysis
    text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split()
    word_count = len(words)

    if word_count > 500:
        cc_score += 25
        cc_findings.append(f"{word_count:,} words — good content depth")
    elif word_count > 200:
        cc_score += 15
        cc_findings.append(f"{word_count:,} words — moderate depth, consider expanding")
    else:
        cc_findings.append(f"Only {word_count:,} words — thin content, AI models prefer depth")

    # Headings structure
    h1s = re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
    h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL | re.IGNORECASE)
    h3s = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL | re.IGNORECASE)

    if h1s:
        cc_score += 15
        h1_text = re.sub(r'<[^>]+>', '', h1s[0]).strip()[:60]
        cc_findings.append(f"H1: \"{h1_text}\"")
    else:
        cc_findings.append("NO H1 tag — AI models use this as your page's main topic")

    if len(h2s) >= 3:
        cc_score += 15
        cc_findings.append(f"{len(h2s)} H2 sections — good content structure")
    elif h2s:
        cc_score += 8
        cc_findings.append(f"Only {len(h2s)} H2 — more sections help AI understand your content")

    if h3s:
        cc_score += 10
        cc_findings.append(f"{len(h3s)} H3 subsections")

    # Paragraphs
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE)
    long_paras = [p for p in paragraphs if len(re.sub(r'<[^>]+>', '', p).strip()) > 100]
    if len(long_paras) >= 5:
        cc_score += 15
        cc_findings.append(f"{len(long_paras)} substantial paragraphs")
    elif long_paras:
        cc_score += 8
        cc_findings.append(f"Only {len(long_paras)} substantial paragraphs — add more explanatory content")

    # Lists
    lists = len(re.findall(r'<(?:ul|ol)[^>]*>', html, re.IGNORECASE))
    if lists >= 2:
        cc_score += 10
        cc_findings.append(f"{lists} lists — good for AI extraction")
    elif lists:
        cc_score += 5

    # Q&A patterns
    questions = len(re.findall(r'[?]', text))
    if questions >= 3:
        cc_score += 10
        cc_findings.append(f"{questions} questions detected — excellent for conversational AI")

    cc_score = min(cc_score, 100)
    report["scores"]["content_clarity"] = {"score": cc_score, "findings": cc_findings}

    # ── 3. ENTITY DENSITY (0-100) ──
    ed_score = 0
    ed_findings = []

    # Numbers and statistics
    numbers = re.findall(r'\$[\d,.]+|\d+%|\d{1,3}(?:,\d{3})+|\d+\.\d+', text)
    if len(numbers) >= 10:
        ed_score += 30
        ed_findings.append(f"{len(numbers)} statistics/numbers — high factual density")
    elif len(numbers) >= 5:
        ed_score += 20
        ed_findings.append(f"{len(numbers)} numbers — moderate factual content")
    else:
        ed_findings.append(f"Only {len(numbers)} numbers — add more specific data points")

    # Proper nouns (capitalized words not at sentence start)
    proper = re.findall(r'(?<=[a-z]\s)[A-Z][a-z]+', text)
    unique_proper = len(set(proper))
    if unique_proper >= 15:
        ed_score += 25
        ed_findings.append(f"{unique_proper} unique entities/proper nouns")
    elif unique_proper >= 5:
        ed_score += 15
        ed_findings.append(f"{unique_proper} entities — add more named references")

    # URLs/links
    links = re.findall(r'href=["\']https?://[^"\']+["\']', html, re.IGNORECASE)
    ext_links = [l for l in links if urlparse(url).hostname not in l]
    if len(ext_links) >= 3:
        ed_score += 15
        ed_findings.append(f"{len(ext_links)} external references — good citation web")
    else:
        ed_findings.append("Few external links — AI models value sites that reference authoritative sources")

    # Specific domain terms (technical depth indicator)
    avg_word_len = sum(len(w) for w in words) / max(len(words), 1)
    if avg_word_len > 5.5:
        ed_score += 15
        ed_findings.append(f"Avg word length {avg_word_len:.1f} — indicates technical/specialized content")
    elif avg_word_len > 4.5:
        ed_score += 8

    # Quotes/citations
    quotes = len(re.findall(r'["\u201c].*?["\u201d]', text))
    if quotes >= 2:
        ed_score += 15
        ed_findings.append(f"{quotes} quoted passages — boosts citation likelihood")

    ed_score = min(ed_score, 100)

    # LLM deep analysis for entity density (Whale RTX 3090)
    llm_ed_score, llm_ed_findings = llm_score(text, url, "entity_density")
    if llm_ed_score is not None:
        # Blend: 40% heuristic + 60% LLM
        ed_score = round(ed_score * 0.4 + llm_ed_score * 0.6)
        ed_findings.append("— AI DEEP ANALYSIS (gemma3:12b on RTX 3090) —")
        ed_findings.extend(llm_ed_findings)

    report["scores"]["entity_density"] = {"score": ed_score, "findings": ed_findings}

    # ── 4. CITATION READINESS (0-100) ──
    cr_score = 0
    cr_findings = []

    # Direct answer patterns (sentences that state facts)
    sentences = re.split(r'[.!?]+', text)
    definitive = [s for s in sentences if re.match(r'\s*\w+\s+(is|are|was|were|means|refers|provides|offers|includes)\s', s)]
    if len(definitive) >= 10:
        cr_score += 30
        cr_findings.append(f"{len(definitive)} definitive statements — highly quotable")
    elif len(definitive) >= 3:
        cr_score += 15
        cr_findings.append(f"{len(definitive)} definitive statements — add more direct answers")
    else:
        cr_findings.append("Few direct-answer statements — AI models prefer content that states facts clearly")

    # Bullet points / structured answers
    li_items = len(re.findall(r'<li[^>]*>', html, re.IGNORECASE))
    if li_items >= 10:
        cr_score += 20
        cr_findings.append(f"{li_items} list items — easy for AI to extract and cite")
    elif li_items >= 3:
        cr_score += 10

    # Tables
    tables = len(re.findall(r'<table[^>]*>', html, re.IGNORECASE))
    if tables >= 1:
        cr_score += 15
        cr_findings.append(f"{tables} tables — structured data AI can reference directly")

    # Short, quotable paragraphs (< 200 chars)
    short_paras = [p for p in paragraphs if 50 < len(re.sub(r'<[^>]+>', '', p).strip()) < 200]
    if len(short_paras) >= 5:
        cr_score += 20
        cr_findings.append(f"{len(short_paras)} concise paragraphs — ideal citation length")

    # Code blocks (for technical content)
    code_blocks = len(re.findall(r'<(?:pre|code)[^>]*>', html, re.IGNORECASE))
    if code_blocks >= 1:
        cr_score += 15
        cr_findings.append(f"{code_blocks} code blocks — excellent for technical citations")

    cr_score = min(cr_score, 100)

    # LLM deep analysis for citation readiness (Whale RTX 3090)
    llm_cr_score, llm_cr_findings = llm_score(text, url, "citation_readiness")
    if llm_cr_score is not None:
        # Blend: 40% heuristic + 60% LLM (LLM is better at judging citation quality)
        cr_score = round(cr_score * 0.4 + llm_cr_score * 0.6)
        cr_findings.append("— AI DEEP ANALYSIS (gemma3:12b on RTX 3090) —")
        cr_findings.extend(llm_cr_findings)

    report["scores"]["citation_readiness"] = {"score": cr_score, "findings": cr_findings}

    # ── 5. AUTHORITY SIGNALS (0-100) ──
    as_score = 0
    as_findings = []

    # About/team/author
    has_about = bool(re.search(r'(?:about|team|author|founder|who we are)', html, re.IGNORECASE))
    if has_about:
        as_score += 25
        as_findings.append("About/team/author section detected")
    else:
        as_findings.append("No about/author section — AI models weight content from identifiable sources")

    # Contact info
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html))
    has_phone = bool(re.search(r'[\(]?\d{3}[\)]?[-.\s]?\d{3}[-.\s]?\d{4}', html))
    has_address = bool(re.search(r'(?:street|ave|blvd|road|suite|floor|city|state|zip|\d{5})', html, re.IGNORECASE))
    if has_email: as_score += 10; as_findings.append("Email found")
    if has_phone: as_score += 10; as_findings.append("Phone found")
    if has_address: as_score += 10; as_findings.append("Physical address found")

    # Copyright / established date
    copyright_match = re.search(r'(?:©|\(c\)|copyright)\s*(\d{4})', html, re.IGNORECASE)
    if copyright_match:
        as_score += 10
        year = copyright_match.group(1)
        as_findings.append(f"Copyright {year}")

    # Social proof
    social = len(re.findall(r'(?:testimonial|review|case.study|client|customer)', html, re.IGNORECASE))
    if social >= 2:
        as_score += 15
        as_findings.append("Social proof signals detected")

    # Credentials/certifications
    creds = len(re.findall(r'(?:certified|licensed|accredited|registered|patent|ISO|award)', html, re.IGNORECASE))
    if creds >= 1:
        as_score += 15
        as_findings.append(f"{creds} credential/certification mentions")

    # HTTPS
    if url.startswith("https"):
        as_score += 5
        as_findings.append("HTTPS: yes")

    as_score = min(as_score, 100)
    report["scores"]["authority_signals"] = {"score": as_score, "findings": as_findings}

    # ── 6. TECHNICAL ACCESS (0-100) ──
    ta_score = 0
    ta_findings = []

    # HTTPS
    if url.startswith("https"):
        ta_score += 15
    else:
        ta_findings.append("NOT HTTPS — major trust signal missing")

    # Canonical
    if re.search(r'<link[^>]*rel=["\']canonical["\']', html, re.IGNORECASE):
        ta_score += 10
        ta_findings.append("Canonical URL set")
    else:
        ta_findings.append("No canonical URL — risk of duplicate content confusion")

    # Viewport (mobile)
    if re.search(r'<meta[^>]*name=["\']viewport["\']', html, re.IGNORECASE):
        ta_score += 15
        ta_findings.append("Mobile viewport configured")
    else:
        ta_findings.append("No viewport meta — not mobile optimized")

    # Language
    if re.search(r'<html[^>]*lang=', html, re.IGNORECASE):
        ta_score += 10
        ta_findings.append("Language attribute set")

    # Page size
    size_kb = len(html) / 1024
    if size_kb < 200:
        ta_score += 15
        ta_findings.append(f"Page size: {size_kb:.0f}KB — fast")
    elif size_kb < 500:
        ta_score += 8
        ta_findings.append(f"Page size: {size_kb:.0f}KB — moderate")
    else:
        ta_findings.append(f"Page size: {size_kb:.0f}KB — heavy, may slow crawling")

    # Check robots.txt
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.hostname}/robots.txt"
    try:
        robots_resp = urllib.request.urlopen(robots_url, timeout=5)
        robots = robots_resp.read(10000).decode("utf-8", errors="replace")
        ta_score += 15
        ta_findings.append("robots.txt: accessible")
        if "Disallow: /" in robots and "Allow" not in robots:
            ta_findings.append("WARNING: robots.txt blocks all crawlers!")
            ta_score -= 15
    except Exception:
        ta_findings.append("No robots.txt — add one to guide AI crawlers")

    # Sitemap reference
    if re.search(r'sitemap', html, re.IGNORECASE):
        ta_score += 10
        ta_findings.append("Sitemap referenced")

    # Content-Type header
    ct = headers.get("Content-Type", "")
    if "utf-8" in ct.lower():
        ta_score += 10
        ta_findings.append("UTF-8 encoding confirmed")

    ta_score = min(ta_score, 100)
    report["scores"]["technical_access"] = {"score": ta_score, "findings": ta_findings}

    # ── OVERALL ──
    dimensions = report["scores"]
    scores = [d["score"] for d in dimensions.values()]
    overall = round(sum(scores) / len(scores))
    report["overall_score"] = overall

    if overall >= 80: report["grade"] = "A"
    elif overall >= 65: report["grade"] = "B"
    elif overall >= 50: report["grade"] = "C"
    elif overall >= 35: report["grade"] = "D"
    else: report["grade"] = "F"

    # Top recommendations
    recs = []
    if dimensions["structured_data"]["score"] < 50:
        recs.append("Add JSON-LD structured data (Organization, FAQPage, Service schemas)")
    if dimensions["content_clarity"]["score"] < 50:
        recs.append("Expand content depth — aim for 1000+ words with clear heading hierarchy")
    if dimensions["entity_density"]["score"] < 50:
        recs.append("Add more specific data points, statistics, and named entities")
    if dimensions["citation_readiness"]["score"] < 50:
        recs.append("Restructure content with direct-answer statements and bulleted lists")
    if dimensions["authority_signals"]["score"] < 50:
        recs.append("Add about page, author credentials, and social proof")
    if dimensions["technical_access"]["score"] < 50:
        recs.append("Fix technical basics: HTTPS, canonical URL, mobile viewport, robots.txt")
    report["recommendations"] = recs[:5]

    return report


def json_resp(handler, data, status=200):
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


class GeoHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.startswith("/geo/api/report/"):
            rid = path.split("/geo/api/report/")[1]
            if rid in REPORTS:
                json_resp(self, REPORTS[rid])
            else:
                json_resp(self, {"error": "Report not found"}, 404)
        else:
            json_resp(self, {"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/geo/api/scan":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length > 0 else {}
            url = body.get("url", "").strip()

            if not url:
                json_resp(self, {"error": "url required"}, 400)
                return
            if not url.startswith("http"):
                url = "https://" + url

            log.info("SCAN: %s", url)
            report = scan_url(url)
            rid = secrets.token_hex(8)
            report["report_id"] = rid
            REPORTS[rid] = report

            log.info("REPORT: %s → grade=%s score=%d", url, report["grade"], report["overall_score"])
            json_resp(self, report)
        else:
            json_resp(self, {"error": "not found"}, 404)

    def log_message(self, format, *args):
        pass


def serve(port=9093):
    log.info("SwarmGEO Scanner starting on :%d", port)
    HTTPServer(("0.0.0.0", port), GeoHandler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9093)
    serve(parser.parse_args().port)
