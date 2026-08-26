# ArcGIS Upload Panel: Layer Selection and Map Updates

## What This Covers

This document explains how service/layer/sublayer selections affect map rendering.

Included features:
- Service-level select all / add-remove behavior
- Layer checkbox logic
- Group layer checkbox logic
- Sublayer checkbox logic
- Clear All behavior
- Loading messages and map spinner

---

## Selection Levels

The panel supports multiple selection levels:
1. Service-level checkbox (all leaf layers)
2. Layer-level checkbox
3. Group layer toggle for descendant leaf layers
4. Sublayer-level checkbox (legend-driven)

---

## Service-Level Selection

Service row checkbox can select/unselect all feature layers under a service.

Effects include:
- checkedLayerIds update
- serviceLayerAdded state update
- sublayer selection initialization when legends provide multiple entries
- loading message updates

---

## Layer-Level Selection

When a layer checkbox is checked:
- Layer ID is added to checked set
- Loading message for that layer is shown
- All sublayers can be auto-selected when legend supports sublayer entries

When unchecked:
- Layer ID is removed
- Loading message is removed
- Sublayer selections are cleared

---

## Group Layer Selection

Group layer checkbox toggles all descendant leaf layers.

Supported behavior:
- Bulk check descendant layers
- Bulk uncheck descendant layers
- Synchronize sublayer selections
- Synchronize service added status

---

## Sublayer Selection

For layers with multi-legend entries, sublayer checkboxes are supported.

Behavior:
- If at least one sublayer is checked, parent layer remains checked.
- If all sublayers are unchecked, parent layer is unchecked.

---

## Map Rendering Logic

The panel updates map layers by diffing previous and current checked selections.

For each service/layer it can:
- Add or remove vector layers
- Add or remove raster layers
- Rebuild raster sublayer sources for selected sublayers

IDs follow service/layer naming patterns for deterministic cleanup.

---

## Direct External Layer Toggle Events

The panel listens for `arcgis-layer-toggle` events from outside components (e.g., learn-more workflows).

If target service layers are not loaded yet, panel loads them first, then applies toggle.

---

## Clear All Layers

Clear All action resets map-related panel state:
- checked layer IDs
- service added flags
- checked sublayer IDs
- loading state cache
- loading message list

---

## Loading UX

The panel uses two loading channels:
- Per-layer/service loading messages
- Map-centered spinner overlay while map layers are loading

Loaded completion messages appear when map sources become ready.

---

## Common Questions

**Q: How do I add ArcGIS layers to the map?**
A: In ArcGIS Upload Panel, expand a state and service, then check either the service checkbox (adds all leaf layers) or specific layer checkboxes. Wait for loading to complete; checked layers are rendered on the map.

**Q: Why does selecting one sublayer still keep parent layer checked?**
A: Parent layer remains active while any sublayer is selected.

**Q: Why does map still show loading after selection?**
A: Tile/source readiness is tracked asynchronously and clears when source load completes.
