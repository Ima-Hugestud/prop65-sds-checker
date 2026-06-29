# Decision Record — TAE Master List & Disposition Layer

**Status:** Accepted (design locked; implementation pending)
**Date:** 2026-06-26
**Applies to:** `prop65-sds-checker` (package `prop65_sds_checker/`)
**Scope:** Adds a durable, human-curated layer on top of the OEHHA-matching pipeline so that a reviewer's determinations persist between runs and drive proactive matching.

---

## Context

The tool batch-screens SDS PDFs against the OEHHA Proposition 65 list (CAS match, name match, and a Section 15 manufacturer-declaration pass). Both outputs — `master_summary.md` and the per-product `by_product/*.md` reports — are **regenerated from scratch on every run**. They are a snapshot of what the tool currently infers, not a record of what a human has decided.

The prompting problem: a reviewer flags an SDS (e.g., PRO-SET INF-114 Resin, where `1-Chloro-4 Trifluromethyl Bisphenol A Epoxy Resin` is declared as a Prop 65 carcinogen with a withheld/proprietary CAS), analyzes it, and concludes it belongs on a TAE-controlled in-scope list. Today there is nowhere durable for that conclusion to live — the next scan overwrites any hand-edited report.

The fix is not "edit a report" but "introduce a third layer the reports read *from*": an external read-only OEHHA list, a durable internal TAE layer holding human determinations, and ephemeral run outputs that are views onto the first two.

A foundational rule constrains every decision below: **OEHHA's determinations (California's authority) and TAE's determinations (our authority) must never blur.** The OEHHA list is never edited; TAE additions live in a separate overlay loaded alongside it, carrying their own provenance.

---

## Decisions

### D1 — Durable layer is two files, not one

**Decision:** A **master list** (`tae_master_list.json`) holding chemicals that drive Pass 1/2 matching, and a separate **disposition log** (`tae_dispositions.json`) holding per-product decisions (reviewer, date, outcome).

**Rationale:** The two artifacts have different shapes, lifespans, and audiences. The master list is a clean chemical roster an auditor could read or that could be published; the disposition log is a messy product-by-product decision trail. A single combined file would force the roster to carry dead `not_in_scope` rows and would tangle the audit trail into matching data. Two files also match TAE-EHS-DOC instincts: the list is the controlled artifact, the log is the evidence. Build cost is effectively identical. A `promote` action writes both files; a `not_in_scope` decision writes only the log.

### D2 — Validated subcommands now; pre-filled promote flow later

**Decision:** Implement `promote` and `dispose` as validated CLI subcommands now (CAS checksum, duplicate refusal, auto-stamped reviewer/date). Defer the convenience flow that pre-fills fields from the flagged report.

**Rationale:** Hand-editing the files has zero guardrails — a fat-fingered CAS or a duplicate silently corrupts matching, and nothing records attribution. Validated subcommands put guardrails exactly where correctness matters (CAS integrity, dedup, attribution) for modest build cost, and every addition becomes a reviewable git diff. The pre-filled flow is a quality-of-life affordance worth adding once the register exists; it is not worth blocking the core capability.

### D3a — Disposition key is product + chemical

**Decision:** Key each disposition on **product + chemical**, not product alone.

**Rationale:** When a new SDS revision changes the formulation and surfaces a different or additional chemical, that new chemical re-flags for review while the prior determination stands undisturbed. This pairs with TAE's SDS-versioning and retention practice: the superseded SDS is retained as the evidence behind the earlier call, and the disposition records which revision it was made against. Keying on product alone would either wrongly suppress new chemicals or wrongly invalidate settled determinations.

### D3b — Provenance upgrades are flagged, not auto-applied

**Decision:** If a chemical previously promoted under `manufacturer_adopted` or `company_precautionary` later appears on a refreshed OEHHA list, the run surfaces a one-line "provenance upgrade available" note. It does **not** mutate the existing entry.

**Rationale:** A change in provenance (TAE-asserted → California-listed) is a substantive determination, not a mechanical one. Auto-rewriting an entry's basis would erase the human judgment that produced it and could mask a meaningful regulatory change. A human confirms the upgrade.

### D3c — Staleness/expiry: field now, logic later

**Decision:** Include a `review_by` date field in the master-list schema now, but build no expiry or re-review logic yet.

**Rationale:** Periodic re-review may become desirable, but building expiry behavior before there is a curated list to re-review is premature. Reserving the field avoids a later schema migration; deferring the logic avoids speculative complexity.

---

## Schema

Both files live in `PROP65_DIR`, are git-tracked **internally**, and are **never** committed to the public repository (see "Data boundary" below).

**`tae_master_list.json`** — one entry per chemical; loaded into the same lookup as OEHHA for Pass 1/2 matching:

| Field | Notes |
|-------|-------|
| `canonical_name` | Preferred chemical name |
| `cas` | Empty if none found → name-match only (narrower coverage) |
| `synonyms` | Trade names / alternate names that should also match |
| `endpoint` | `cancer`, `developmental/reproductive toxicity`, or both |
| `basis` | `oehha_alias` \| `manufacturer_adopted` \| `company_precautionary` |
| `added_by` | Reviewer ID |
| `added_date` | Auto-stamped |
| `source_sds` | Product the determination originated from |
| `review_by` | Reserved (D3c); no logic yet |

**`tae_dispositions.json`** — one entry per product + chemical determination:

| Field | Notes |
|-------|-------|
| `key` | `"<product> :: <chemical>"` (D3a) |
| `disposition` | `promoted` \| `not_in_scope` |
| `reason` | Required for `not_in_scope` |
| `reviewer` | Reviewer ID |
| `date` | Auto-stamped |
| `sds_revision` | Pulled from the parsed SDS; ties the call to the retained revision |

**`basis` enum meanings:**
- `oehha_alias` — the trade name resolves to a chemical already on the OEHHA list (e.g., a synonym of an OEHHA-listed substance); strongest, fully defensible as a California listing.
- `manufacturer_adopted` — not on OEHHA under any identity, but TAE adopts the manufacturer's Prop 65 assertion.
- `company_precautionary` — not on OEHHA; TAE elects in-scope as a policy/precautionary call. With no CAS and a trade-name-only chemical, this matches only future SDSs using that exact trade name — correct, but narrow reach.

---

## Subcommand interface

```
prop65-checker promote <product> --chemical "<name>" --basis <enum> \
    [--cas <n>] --endpoint <e> --reviewer <id> [--reason "<text>"]

prop65-checker dispose <product> --chemical "<name>" --not-in-scope \
    --reason "<text>" --reviewer <id>
```

**Validation:** CAS mod-11 check-digit validation; refuse duplicate disposition keys; refuse a master-list entry whose CAS already exists; auto-stamp date; auto-pull `sds_revision` from the product's parsed SDS. `promote` writes both files; `dispose` writes only the log.

**Open guardrail (recommended, approved):** the chemical name is a string and must join exactly between the flag and the command. To prevent silent key mismatches, `promote`/`dispose` should fuzzy-match the supplied `--chemical` against the product's current findings and ask the reviewer to confirm, rather than trusting an exactly-typed name. (The deferred D2 pre-fill flow largely supersedes this by copying the exact string.)

---

## Three cross-cutting behaviors

1. **Provenance and confidence are orthogonal.** A hit carries both independently: *confidence* = how strong the string match is (CAS > name); *provenance* = who asserts in-scope (OEHHA vs. TAE master list). A promoted chemical renders as, e.g., "high-confidence CAS match · source: TAE master list (oehha_alias)" — **never** as a California listing. This threads through `ChemicalHit` and every render path.

2. **List match wins; declaration collapses.** Once a chemical is on the master list and matches in Pass 1/2, that hit suppresses the Pass 3 `declared` finding for the same product + chemical, so it shows once (at the higher authority), not twice. This extends the existing Pass 1/2 → Pass 3 dedup mechanism.

3. **3b reconciliation is flag-only** (see D3b).

---

## Build sequence

1. **Flag patch (ready):** repairs the section splitter and flags declared-but-CAS-withheld Prop 65 chemicals with a bold red banner. Independent; ship first.
2. **Durable layer:** master list + disposition log, `promote`/`dispose` subcommands writing to them, master list loading into matching, list-match-wins dedup. **No reporter changes.** Independently testable; delivers the proactive-matching win.
3. **Dashboard + worksheet rendering:** the summary's "Awaiting Determination" / "Recently Determined" sections and the per-product "Determination" block.

**Gate before step 2 touches the pipeline:** a characterization-test suite pinning current Pass 1/2/3 behavior. State management is past the point where eyeballing report output is sufficient validation.

---

## Test strategy (summary)

- **Group A — invariant:** with no master list present, output is byte-identical to pre-change baseline. **Golden-master snapshots** (strictest check; the contract).
- **Groups B/C/D — behavior:** Pass 1/2/3 outcomes, existing dedup, parser regression net, bucketing, UTF-8 banner round-trip. **Assertion-based** (survives cosmetic rewording).
- Plus the new-behavior assertions step 2 introduces (proactive match, list-match-wins suppression, TAE-provenance rendering, subcommand validation).

Two implementation notes: the `Generated:` timestamp line must be clock-frozen (mandatory for the A snapshots specifically); and a golden-master test "passes" trivially on first write — real validation is that it then catches a deliberately injected change.

---

## Data boundary (regulatory posture)

The two JSON files are **TAE compliance data, not open-source tooling.** They live in `PROP65_DIR`, are version-controlled internally, and are never in the public repository. The published tool stays generic: the README documents that it loads a TAE overlay from `PROP65_DIR` *if present*. A reader of the public repo never sees TAE determinations; an auditor of TAE's internal records finds them fully attributed. Internally, the master list is treated as a controlled artifact under the same provenance discipline as other TAE-EHS-DOC documents.

---

## Documentation as a merge gate

Every build PR's definition of done is **code + tests + changelog entry + interface/schema doc, in one diff.** A PR that changes the command surface or the schema does not merge until its docs are in the same diff. `CHANGELOG.md` and a README "Updating the Tool" section are added as a small first PR (may bundle with the flag patch) to establish the habit before the larger work lands.
