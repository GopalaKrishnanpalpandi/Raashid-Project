"""Quick smoke test for the v3 comparison engine."""
import asyncio
from compare import check_description_consistency


async def main():
    print("=" * 60)
    print("TEST 1: B09XYZ1234 — Water Bottle (LOW risk expected)")
    print("=" * 60)
    r = await check_description_consistency("B09XYZ1234")
    print(f"Risk: {r['risk_level']}   Avg Similarity: {r['average_similarity']:.3f}")
    print(f"Issue counts: {r['issue_counts']}")
    c = r["comparisons"][0]
    for k in ["ngram_dice", "sentence_alignment", "spec_match", "feature_overlap",
              "word_jaccard", "bigram_jaccard", "sequence_score", "structural_score", "tfidf_score"]:
        print(f"  {k}: {c.get(k)}")
    specs = r.get("spec_analysis", {})
    print(f"Specs extracted: {len(specs)}")
    for k, v in list(specs.items())[:5]:
        print(f"  {k}: consistent={v['consistent']}, values={v['values']}")
    for iss in r["issues"][:3]:
        print(f"  [{iss['severity']}] {iss['title']}: {iss['description'][:60]}")

    print()
    print("=" * 60)
    print("TEST 2: B00DIFFER1 — Mixed products (HIGH risk expected)")
    print("=" * 60)
    r2 = await check_description_consistency("B00DIFFER1")
    print(f"Risk: {r2['risk_level']}   Avg Similarity: {r2['average_similarity']:.3f}")
    print(f"Issue counts: {r2['issue_counts']}")
    for iss in r2["issues"][:5]:
        print(f"  [{iss['severity']}] {iss['title']}: {iss['description'][:60]}")

    print()
    print("=" * 60)
    print("TEST 3: B00TEST123 — Earbuds (MEDIUM risk expected)")
    print("=" * 60)
    r3 = await check_description_consistency("B00TEST123")
    print(f"Risk: {r3['risk_level']}   Avg Similarity: {r3['average_similarity']:.3f}")
    print(f"Issue counts: {r3['issue_counts']}")
    for iss in r3["issues"][:5]:
        print(f"  [{iss['severity']}] {iss['title']}: {iss['description'][:60]}")

    print()
    print("=" * 60)
    print("TEST 4: Page-data phone (scraped content)")
    print("=" * 60)
    r4 = await check_description_consistency(
        "B0DPHONE99",
        page_title="OnePlus Nord 5 5G (12GB RAM, 256GB)",
        page_description=(
            "OnePlus Nord 5 features a 6.72 inch FHD+ AMOLED display with 120Hz refresh rate. "
            "Powered by Snapdragon 8 Gen 3 processor. 50MP flagship dual camera with Sony IMX890. "
            "5000mAh battery with 80W SUPERVOOC fast charging. Supports 5G, WiFi 6, NFC."
        ),
        page_region="IN",
    )
    print(f"Risk: {r4['risk_level']}   Avg Similarity: {r4['average_similarity']:.3f}")
    print(f"Issue counts: {r4['issue_counts']}")
    for iss in r4["issues"][:5]:
        print(f"  [{iss['severity']}] {iss['title']}: {iss['description'][:60]}")

    print("\n✅ All tests passed!")


asyncio.run(main())
