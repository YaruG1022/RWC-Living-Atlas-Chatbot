# ArcGIS Upload Panel: Search and Result Navigation

## What This Covers

This document explains search features inside ArcGIS Upload Panel.

Included features:
- Keyword search
- Search scope by current navigation path
- Search type behavior
- Result expansion
- Search match next/previous navigation
- Added-only filter

---

## Search Input

Users can search by keyword from panel search bar.

Search supports matching across:
- Folder names
- Service names
- Layer names

Search placeholder text changes based on current path context (root, state, or folder).

---

## Search Scope

Search is scoped to current panel navigation context:
- Root path: all states/services
- State path: only services in that state
- Folder path: only services in that folder

This keeps results relevant to current browsing context.

---

## Search Result Expansion

After search runs, panel automatically expands matching nodes:
- Relevant states
- Matching folders
- Matching services
- Matching layer groups

This allows users to see matched items without manual expansion.

---

## Async Layer Loading During Search

If layer data for candidate services is not loaded yet, panel loads them lazily during search.

While this happens, a search loading indicator is shown with remaining count.

---

## Search Result Navigation (Mini Navigator)

When search is active, panel shows mini navigation controls:
- Previous match
- Next match
- Position counter (e.g., 2 / 8)

This allows step-by-step traversal of result matches.

---

## Clear Search

Clear action resets:
- Search keyword
- Search results
- Expanded states/folders/services/layers from search
- Search navigation state

Panel returns to normal navigation mode.

---

## Added-Only Toggle

The "Show only services added to map" checkbox filters service list to entries with active selected layers.

When enabled, panel expands folders/services that currently have selected layers.

When disabled, panel expansion related to added-only mode is reset.

---

## Common Questions

**Q: Why do results increase after a moment?**
A: Additional service layers may load asynchronously and then become searchable.

**Q: Why is search result limited to one state or folder?**
A: Search scope follows your current navigation path.
