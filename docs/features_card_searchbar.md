# Card Panel Search Bar

## What This Covers

This document covers the top search bar area in the Card Container.

Included controls:
- Search input
- Search button
- Clear search button

---

## Search Cards by Title

### Purpose
Find cards quickly using title keyword matching.

### How to Use
1. Enter text in the **Search cards...** input.
2. Press **Enter** or click the **Search** button.
3. The card list refreshes to matching results.

### Notes
- Search text is normalized before request.
- Search is designed for card title matching.
- Search results can still be affected by active sort/filter conditions.

---

## Clear Search

### Purpose
Reset search input and return to non-search listing state.

### How to Use
1. Click the **Clear (X)** button in the search bar.
2. Search term is removed.
3. Search-related list constraints are cleared.

### Notes
- Clear also resets category selection from the search bar workflow.
- After clear, cards reload according to active non-search criteria.

---

## Common Questions

**Q: Pressing Enter does nothing. Why?**
A: Ensure the input is focused and text is entered before pressing Enter.

**Q: Why are fewer cards shown than expected?**
A: Check whether favorites-only, viewport scope, category, or tag filters are still active.
