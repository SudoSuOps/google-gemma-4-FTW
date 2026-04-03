#!/usr/bin/env python3
"""
Offering Memorandum Generator
=============================
Generates a property-grade OM for a domain's deeded inventory.
Like a CRE OM: property description, financials, legal description, verification.

Usage:
    python generate_om.py --domain grants --output docs/OM_grants_v1.md
    python generate_om.py --domain medical --output docs/OM_medical_v1.md
"""
import argparse
import json
import os
import time
from pathlib import Path
from collections import Counter

DB_URL = os.environ.get("DATABASE_URL", "postgresql://swarm:swarmandbee2026@192.168.0.102:5433/swarmgraph")

DOMAIN_DESCRIPTIONS = {
    "grants": """This offering contains **federal grants intelligence** — SBIR/STTR proposals, NSF/NIH
reviewer responses, resubmission strategies, SAM.gov registration guidance, and compliance frameworks.
Each pair features a domain-expert system prompt, a realistic client query, and a comprehensive
response with specific regulatory citations, budget justifications, and reviewer feedback analysis.

Target buyers: Grant writing firms, university research offices, federal contractors,
SBA-funded businesses, defense contractors with SBIR portfolios.""",

    "medical": """This offering contains **clinical intelligence across 61 medical specialties** —
internal medicine (98K pairs), surgery (43K), neurology (38K), obstetrics (28K), pharmacology (22K),
and 56 additional specialties. Pairs include MRI/imaging interpretation, differential diagnosis,
drug interaction analysis, surgical planning, and evidence-based treatment recommendations.

Target buyers: Health tech companies, clinical decision support systems, medical education platforms,
telemedicine providers, pharmaceutical R&D, hospital IT departments.""",

    "aviation": """This offering contains **aviation maintenance engineering intelligence** —
A&P/IA-level airworthiness evaluation, inspection procedures, maintenance planning, and
regulatory compliance. Each pair follows a 5-step trajectory analysis methodology: identify
core issue, calculate key metrics, evaluate operational impact, recommend actions, cite regulations.

Target buyers: Aviation MRO providers, airline operations, aerospace manufacturers,
FAA compliance teams, flight school curricula developers.""",

    "cre": """This offering contains **commercial real estate intelligence** — underwriting analysis,
NOI calculations, cap rate analysis, rent roll evaluation, 1031 exchange strategies,
debt service coverage ratios, and market comparable analysis. Includes multifamily, industrial,
retail, office, cold storage, and medical office specialties.

Target buyers: CRE brokerages, investment firms, REIT operators, lenders,
appraisal firms, property management companies.""",
}


def get_domain_stats(domain):
    """Pull real stats from PostgreSQL."""
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM pairs WHERE domain_id = %s", (domain,))
        total_pairs = cur.fetchone()[0]

        # Get metadata breakdown
        cur.execute("""
            SELECT metadata->>'specialty', COUNT(*)
            FROM pairs WHERE domain_id = %s AND metadata->>'specialty' IS NOT NULL
            GROUP BY metadata->>'specialty' ORDER BY COUNT(*) DESC LIMIT 15
        """, (domain,))
        specialties = cur.fetchall()

        # Sample pair
        cur.execute("""
            SELECT messages FROM pairs WHERE domain_id = %s LIMIT 1
        """, (domain,))
        sample = cur.fetchone()

        conn.close()
        return {
            "total_pairs": total_pairs,
            "specialties": specialties,
            "sample": sample[0] if sample else None,
        }
    except Exception as e:
        return {"total_pairs": 0, "error": str(e)}


def generate_om(domain, output_path):
    """Generate a full Offering Memorandum for a domain."""

    template_path = Path(__file__).parent.parent / "docs" / "om_template.md"
    with open(template_path) as f:
        template = f.read()

    stats = get_domain_stats(domain)
    total = stats["total_pairs"]

    # Placeholder tier stats (will be real after tribunal runs)
    rj_est = int(total * 0.55)
    honey_est = int(total * 0.30)
    propolis_est = total - rj_est - honey_est

    # Build specialty breakdown
    spec_text = ""
    if stats.get("specialties"):
        spec_text = "| Specialty | Pairs |\n|-----------|-------|\n"
        for spec, count in stats["specialties"]:
            spec_text += f"| {spec} | {count:,} |\n"

    # Build sample pair
    sample_text = ""
    if stats.get("sample"):
        msgs = stats["sample"]
        for m in msgs[:3]:
            role = m.get("role", "?").upper()
            content = m.get("content", "")[:300]
            sample_text += f"**[{role}]**\n```\n{content}...\n```\n\n"

    # Fill template
    om = template.replace("{DOMAIN}", domain.upper())
    om = om.replace("{DOMAIN_NAME}", domain.replace("_", " ").title())
    om = om.replace("{DATE}", time.strftime("%B %d, %Y"))
    om = om.replace("{TOTAL_PAIRS}", f"{total:,}")
    om = om.replace("{RJ_COUNT}", f"{rj_est:,}")
    om = om.replace("{RJ_PCT}", f"{rj_est/max(total,1)*100:.0f}")
    om = om.replace("{HONEY_COUNT}", f"{honey_est:,}")
    om = om.replace("{HONEY_PCT}", f"{honey_est/max(total,1)*100:.0f}")
    om = om.replace("{PROPOLIS_COUNT}", f"{propolis_est:,}")
    om = om.replace("{PROPOLIS_PCT}", f"{propolis_est/max(total,1)*100:.0f}")
    om = om.replace("{MEAN_SCORE}", "0.72 (estimated, pre-tribunal)")
    om = om.replace("{DOMAIN_DESCRIPTION}", DOMAIN_DESCRIPTIONS.get(domain, "Domain description pending."))
    om = om.replace("{SPECIALTY_BREAKDOWN}", spec_text or "Specialty breakdown will be populated after tribunal scoring.")
    om = om.replace("{SAMPLE_PAIR}", sample_text or "Sample pair will be included after tribunal scoring.")
    om = om.replace("{JUDGE_A_MODEL}", "google/gemma-3-12b (base, unmodified)")
    om = om.replace("{JUDGE_B_MODEL}", "Qwen/Qwen2.5-7B-Instruct (base, unmodified)")
    om = om.replace("{SCORE_HISTOGRAM}", "Score distribution chart will be generated after tribunal scoring.")
    om = om.replace("{COST_PER_DEED}", "0.005")
    om = om.replace("{ENERGY_PER_DEED}", "1,260")
    om = om.replace("{TOTAL_COST}", f"{total * 0.005:,.2f}")
    om = om.replace("{CONVERGENCE_TREND}", "Will be measured during tribunal run.")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(om)

    print(f"[om] Generated: {output_path}")
    print(f"  Domain: {domain}")
    print(f"  Pairs: {total:,}")
    print(f"  Est. RJ: {rj_est:,} ({rj_est/max(total,1)*100:.0f}%)")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OM Generator")
    parser.add_argument("--domain", required=True, help="Domain: grants, medical, aviation, cre, all")
    parser.add_argument("--output", help="Output path")
    args = parser.parse_args()

    if args.domain == "all":
        for domain in ["grants", "medical", "aviation", "cre"]:
            output = f"docs/OM_{domain}_v1.md"
            generate_om(domain, output)
            print()
    else:
        output = args.output or f"docs/OM_{args.domain}_v1.md"
        generate_om(args.domain, output)
