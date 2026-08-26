# Card Item Interactions

## What This Covers

This document covers interactions available directly on each card item in the Card Container (before opening the full Learn More modal).

Included interactions:
- Open Learn More
- Favorite / Unfavorite
- Locate on map
- Thumbnail image preview and image navigation

---

## Open Learn More

### Purpose
Open the full card detail modal.

### How to Use
1. Click the card body.
2. The Learn More modal opens with card details.

### Notes
- The card also supports keyboard open with Enter/Space.
- When opened, linked ArcGIS items and image data are refreshed.

---

## Favorite / Unfavorite (Heart Icon)

### Purpose
Add or remove a card from the current user's favorites.

### How to Use
1. Click the heart icon on the card.
2. If not favorited, it becomes favorited.
3. If already favorited, it is removed from favorites.

### Requirements
- User must be logged in.
- Card must have a valid card ID.

### Notes
- If not logged in, a login prompt appears.
- Favorites are tied to user account state.

---

## Locate on Map (Magnifier Button)

### Purpose
Center/focus map interaction on the selected card location.

### How to Use
1. Click the magnifier icon on the card metadata row.
2. The parent map handler is called to zoom/focus.

### Notes
- This action does not edit card data.

---

## Card Thumbnail and Image Navigation

### Purpose
Preview card images directly from the card tile.

### Behavior
- Clicking thumbnail opens image preview.
- If the card has multiple images:
  - Previous/Next arrows are shown.
  - Dot indicators show current position.
- If no image exists, a default CEREO thumbnail is used.

### Notes
- Image cards can display card representation imagery.
- Broken image URLs fall back to default logo.

---

## Common Questions

**Q: Why can I not favorite a card?**
A: You may not be logged in, or the card has missing ID data.

**Q: Why does clicking the card open a modal instead of zooming map?**
A: Card body click opens Learn More. Use magnifier button for map locate.
