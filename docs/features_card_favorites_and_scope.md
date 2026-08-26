# Card Toolbar: Favorites and Scope Controls

## What This Covers

This document covers top-toolbar controls for list scope and favorite-only filtering.

Included controls:
- Favorites toggle
- Scope toggle (All Cards / In View)

---

## Favorites Toggle

### Purpose
Show only cards the current user has favorited.

### How to Use
1. Click the **Favorites** button.
2. When active, only favorited cards remain in the list.
3. Click again to return to normal card listing.

### Login Requirement
- User must be logged in to use favorites filter.
- If not logged in, a login prompt appears.

### Notes
- This is a filter only; it does not add/remove favorites itself.
- Favoriting/unfavoriting individual cards is done from card actions.

---

## Scope Toggle (All Cards / In View)

### Purpose
Switch between showing all cards and only cards inside current map viewport.

### Modes
- **All Cards**: no viewport clipping
- **In View**: only cards currently inside map bounds

### How to Use
1. Click the scope button in the toolbar.
2. Button label changes between **All Cards** and **In View**.
3. Card list updates immediately.

### Notes
- Viewport scope is most useful when exploring a specific map area.
- During active search workflows, viewport clipping behavior can be relaxed.

---

## Common Questions

**Q: Why does card count change while I pan the map?**
A: If scope is set to In View, map bounds directly affect visible card count.

**Q: Can favorites filter and in-view scope be used together?**
A: Yes. Both constraints apply to the final displayed list.
