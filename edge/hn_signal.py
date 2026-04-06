#!/usr/bin/env python3
"""
HN Signal Scraper — Virgin Jelly from Hacker News

The market talks in real time on HN. Builders post their pain points,
failures, breakthroughs, and needs. This scraper captures the signal
and converts it into training pair candidates for the tribunal scale.

Architecture:
  HN API → filter by keywords → extract pain points → generate pairs
  → save as JSONL → tribunal scores → deeds → micro-cook

Usage:
    # Scan top stories for AI agent signal
    python3 hn_signal.py

    # Scan with custom keywords
    python3 hn_signal.py --keywords "agent,security,fine-tune,hallucinate"

    # Deep dive a specific thread (like the Anthropic/OpenClaw thread)
    python3 hn_signal.py --thread 47616297

    # Output pairs for tribunal
    python3 hn_signal.py --output virgin_jelly_hn.jsonl

    # Continuous monitoring (check every hour)
    python3 hn_signal.py --watch
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

HN_API = "https://hacker-news.firebaseio.com/v0"

# Signal keywords — what we're mining for
DEFAULT_KEYWORDS = [
    # Agent problems (ClawHash)
    "agent", "openclaw", "hallucinate", "hallucination", "tool call",
    "function calling", "prompt injection", "rogue", "security",
    "structured output", "json output", "mcp", "tool poison",
    "privilege escalation", "sandbox", "guardrails", "kill switch",
    # Agent reliability (AgentHash — broken weights signal)
    "fake tool", "tool unreliable", "tool calling broken", "malformed",
    "lost state", "agent loop", "infinite loop", "bad retry",
    "agent drift", "orchestration", "clawbot", "kimi k2",
    # Model/training (AgentHash, general)
    "fine-tune", "fine-tuning", "qlora", "lora", "training data",
    "local model", "open source model", "self-host", "sovereignty",
    # Specific models
    "gemma", "qwen", "llama", "claude", "codex", "ollama",
    # Infrastructure
    "gpu", "inference", "rtx", "blackwell", "vram",
    # Business signal
    "subscription", "api pricing", "rate limit", "cost", "token",
]

# Domain classification based on content
DOMAIN_MAP = {
    "clawhash": ["openclaw", "prompt injection", "tool poison", "rogue agent",
                  "security", "cve", "vulnerability", "mcp attack", "malicious"],
    "agenthash": ["agent", "tool call", "function calling", "structured output",
                   "multi-step", "error recovery", "hallucinate", "json",
                   "fake tool", "tool unreliable", "agent loop", "agent drift",
                   "orchestration", "lost state", "bad retry", "kimi"],
    "granthash": ["grant", "nonprofit", "501c3", "sbir", "federal funding"],
    "medhash": ["medical", "clinical", "drug", "patient", "healthcare"],
    "crehash": ["real estate", "cre", "commercial", "lease", "cap rate"],
    "wikihash": ["fine-tune", "training data", "local model", "self-host",
                  "sovereignty", "open source", "weights"],
}


def hn_get(path, retries=3):
    """Fetch from HN API with retry."""
    url = f"{HN_API}/{path}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SwarmSignal/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt == retries - 1:
                print(f"  [warn] Failed to fetch {path}: {e}")
                return None
            time.sleep(1)


def matches_keywords(text, keywords):
    """Check if text contains any signal keywords."""
    lower = text.lower()
    matched = [kw for kw in keywords if kw.lower() in lower]
    return matched


def classify_domain(text):
    """Classify text into a domain-hash algorithm."""
    lower = text.lower()
    scores = {}
    for domain, keywords in DOMAIN_MAP.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[domain] = score
    if scores:
        return max(scores, key=scores.get)
    return "general"


def extract_comments(item_id, max_depth=3, max_comments=50):
    """Recursively extract comments from a thread."""
    comments = []

    def _extract(item_id, depth=0):
        if depth > max_depth or len(comments) >= max_comments:
            return
        item = hn_get(f"item/{item_id}.json")
        if not item or item.get("deleted") or item.get("dead"):
            return
        if item.get("type") == "comment" and item.get("text"):
            comments.append({
                "id": item["id"],
                "by": item.get("by", "anon"),
                "text": item["text"],
                "time": item.get("time", 0),
                "depth": depth,
            })
        for kid_id in (item.get("kids") or [])[:10]:
            _extract(kid_id, depth + 1)

    _extract(item_id)
    return comments


def generate_pair_from_comment(story_title, comment_text, domain):
    """Convert an HN comment into a training pair candidate."""
    # Strip HTML tags (basic)
    import re
    clean = re.sub(r'<[^>]+>', '', comment_text)
    clean = clean.replace('&gt;', '>').replace('&lt;', '<')
    clean = clean.replace('&amp;', '&').replace('&#x27;', "'")
    clean = clean.replace('&quot;', '"')

    if len(clean) < 50:
        return None

    # The pain point IS the user query
    # A good response addresses the pain
    pair = {
        "messages": [
            {
                "role": "system",
                "content": f"You are a domain expert helping builders solve real-world AI problems. The user is describing a pain point from a Hacker News discussion about '{story_title}'. Provide specific, actionable guidance."
            },
            {
                "role": "user",
                "content": clean[:2000]
            }
        ],
        "metadata": {
            "source": "hackernews",
            "source_type": "virgin_jelly",
            "domain": domain,
            "story_title": story_title[:200],
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "freshness": "today",
        }
    }
    return pair


def scan_top_stories(keywords, limit=30):
    """Scan HN top/new/best stories for signal."""
    print("═══ HN SIGNAL SCANNER — VIRGIN JELLY ═══")
    print(f"Keywords: {len(keywords)}")
    print(f"Scanning top/new/best stories...")
    print()

    all_pairs = []
    seen_stories = set()

    for feed_name, feed_path in [("top", "topstories"), ("new", "newstories"), ("best", "beststories")]:
        story_ids = hn_get(f"{feed_path}.json")
        if not story_ids:
            continue

        for story_id in story_ids[:limit]:
            if story_id in seen_stories:
                continue
            seen_stories.add(story_id)

            story = hn_get(f"item/{story_id}.json")
            if not story:
                continue

            title = story.get("title", "")
            text = story.get("text", "")
            url = story.get("url", "")
            score = story.get("score", 0)
            descendants = story.get("descendants", 0)

            # Check title + text for signal
            check_text = f"{title} {text} {url}"
            matched = matches_keywords(check_text, keywords)

            if not matched:
                continue

            domain = classify_domain(check_text)

            print(f"  [{feed_name}] {title[:70]}")
            print(f"    Score: {score} | Comments: {descendants} | Signal: {', '.join(matched[:5])} | Domain: {domain}")

            # Extract top comments for pair generation
            if descendants > 5:
                comments = extract_comments(story_id, max_depth=2, max_comments=20)
                for comment in comments:
                    comment_matched = matches_keywords(comment["text"], keywords)
                    if comment_matched and len(comment["text"]) > 100:
                        pair = generate_pair_from_comment(title, comment["text"], domain)
                        if pair:
                            all_pairs.append(pair)

            # Small delay to be nice to the API
            time.sleep(0.5)

    return all_pairs


def scan_thread(thread_id, keywords):
    """Deep dive a specific HN thread."""
    story = hn_get(f"item/{thread_id}.json")
    if not story:
        print(f"Could not fetch thread {thread_id}")
        return []

    title = story.get("title", "Untitled")
    descendants = story.get("descendants", 0)
    domain = classify_domain(f"{title} {story.get('text', '')}")

    print(f"═══ DEEP DIVE: {title[:70]} ═══")
    print(f"  Comments: {descendants} | Domain: {domain}")
    print()

    comments = extract_comments(thread_id, max_depth=4, max_comments=200)
    pairs = []

    for comment in comments:
        matched = matches_keywords(comment["text"], keywords)
        if matched and len(comment["text"]) > 100:
            pair = generate_pair_from_comment(title, comment["text"], domain)
            if pair:
                pairs.append(pair)
                if len(pairs) % 10 == 0:
                    print(f"  {len(pairs)} pairs extracted...")

    return pairs


def main():
    parser = argparse.ArgumentParser(description="HN Signal Scraper — Virgin Jelly Pipeline")
    parser.add_argument("--keywords", help="Comma-separated keywords to filter", default=None)
    parser.add_argument("--thread", type=int, help="Deep dive a specific HN thread ID")
    parser.add_argument("--output", default="hn_virgin_jelly.jsonl", help="Output JSONL file")
    parser.add_argument("--limit", type=int, default=30, help="Stories to scan per feed")
    parser.add_argument("--watch", action="store_true", help="Continuous monitoring (hourly)")
    args = parser.parse_args()

    keywords = args.keywords.split(",") if args.keywords else DEFAULT_KEYWORDS

    while True:
        if args.thread:
            pairs = scan_thread(args.thread, keywords)
        else:
            pairs = scan_top_stories(keywords, limit=args.limit)

        if pairs:
            # Classify and summarize
            domains = {}
            for p in pairs:
                d = p["metadata"]["domain"]
                domains[d] = domains.get(d, 0) + 1

            print(f"\n═══ SIGNAL SUMMARY ═══")
            print(f"  Total pairs: {len(pairs)}")
            print(f"  Domains:")
            for d, c in sorted(domains.items(), key=lambda x: -x[1]):
                print(f"    {d:15s} {c:>4} pairs")

            # Save
            mode = "a" if os.path.exists(args.output) else "w"
            with open(args.output, mode) as f:
                for p in pairs:
                    f.write(json.dumps(p) + "\n")

            existing = sum(1 for _ in open(args.output)) if os.path.exists(args.output) else 0
            print(f"\n  Saved to: {args.output} ({existing} total pairs)")
            print(f"  Next: score through tribunal → weigh → deed → micro-cook")
        else:
            print("  No signal found matching keywords.")

        if not args.watch:
            break

        print(f"\n  Sleeping 1 hour... (next scan at {datetime.now().strftime('%H:%M')}+1h)")
        time.sleep(3600)


if __name__ == "__main__":
    main()
