# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added
- **Declarations to Review bucket.** A generic manufacturer Prop 65 warning that
  names no chemical/CAS no longer flags the product. It is routed to a separate
  `review` tier and a dedicated "Declarations to Review" section in the master
  summary (with a short explanation of why it landed there and the SDS snippet),
  so unconfirmed statements don't imply a chemical match. Declarations that *do*
  name a chemical/CAS remain `declared` findings and still flag the product.
  `CheckResult` gains `substantive_hits`, `review_hits`, and `needs_review`;
  `flagged`, `carcinogens`, and `reproductive_hazards` now count substantive hits only.
- **Pass 3 — Manufacturer-declared Prop 65 detection.** The checker now captures
  chemicals that a manufacturer explicitly flags under Proposition 65 in the SDS
  (typically a "California Proposition 65" subsection in Section 15, or a "known to
  the State of California to cause..." warning), **even when the substance is not on
  the OEHHA list**. Two sub-cases are handled:
  - Declaration names a chemical/CAS → that CAS is recorded (deduplicated against
    Pass 1/2 so an OEHHA-list hit is never double-reported).
  - Declaration is generic (no CAS) → routed to the Declarations to Review bucket
    (see above); does not flag the product.
- New confidence tier `declared` and match method `manufacturer_declared`, kept
  distinct from OEHHA list matches throughout the reports.
- Product reports now include a **"Manufacturer-Declared Prop 65 (Not an OEHHA List
  Match)"** section, and the master summary confidence column shows a `declared` count.
- Recommended-action checklist items for declared findings.

### Design notes / guardrails
- The trigger is an explicit **Proposition 65 declaration**, not a generic
  carcinogenicity statement (IARC/NTP/GHS H350). Generic carcinogenicity does not
  trigger Pass 3, avoiding mass over-flagging.
- **Negation detection** suppresses the common "this product does not contain a
  chemical known to the State of California..." boilerplate. The pass errs toward
  suppression when negation language is near a declaration — a deliberate tradeoff
  that may miss a rare real positive surrounded by negation wording.
- Section text is whitespace-normalized before phrase matching so that PDF line
  wrapping does not defeat multi-word patterns (e.g. "known to the\nState of
  California").

### Tested
- Five synthetic SDS scenarios validated: declaration with named CAS (not on list),
  generic declaration (no CAS), "does not contain" negation boilerplate, chemical
  on the OEHHA list also declared (dedup, no spurious generic hit), and a
  carcinogenicity statement with no Prop 65 reference (correctly ignored).
