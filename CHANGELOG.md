# Changelog

All notable changes to this project are documented in this file. The format
loosely follows Keep a Changelog. This changelog was introduced at version
0.2.0; commit history predates it.

## [0.2.0] - 2026-06-29

### Fixed
- Section splitter no longer mis-parses page-footer dates or digit-leading
  chemical names as SDS section headers, which had been carving the Prop 65
  block out of Section 15 and producing silent false negatives.
- Section headers wrapped in decoration (e.g. "==== SECTION 15 ===="), common in
  older ANSI-style SDSs, are now recognized instead of falling back to full-text.

### Added
- Chemicals named in the Section 15 safe-harbor warning or a "(>0.0%)" list are
  flagged even when the CAS is withheld or proprietary (previously passed clean).
- Bold red FLAG banner in the master summary and per-product reports, stating the
  endpoint, the named chemical, and a "where to look" SDS locator.
- docs/decisions.md - decision record for the planned master-list and disposition
  layer (design only; implementation tracked separately).

### Changed
- Strengthened negation handling so "no chemicals ... require reporting"
  boilerplate no longer produces spurious review items.