# ArcGIS Service/Layer Learn More and Right-Click Guide (User-Facing)

## What This Guide Covers

This guide explains user-facing actions for ArcGIS **service** and **layer** items:
- Learn More button behavior
- Service Info modal features
- Layer Info modal features
- Right-click context menu actions

Use this guide for questions like:
- "How do I open Learn More for a service or layer?"
- "What can I do in Service Info or Layer Info modal?"
- "What options appear when I right-click a service/layer?"
- "What options are in the right click menu for layer?"

---

## How to Open Learn More

### Service Learn More
You can open service details by:
1. Clicking the service row action button (three dots / info action), or
2. Right-clicking a service and selecting **Learn more**.

This opens the **Service Info** modal.

### Layer Learn More
You can open layer details by:
1. Clicking a layer link from Service Info modal, or
2. Right-clicking a layer and selecting **Learn more**.

This opens the **Layer Info** modal.

---

## Service Info Modal: What Users Can Do

When Service Info opens, users can:
1. Read service metadata (when available), such as description, item ID, copyright, and spatial reference.
2. Open layer links listed under that service.
3. Open the external ArcGIS service page.
4. Adjust **service-specific opacity** for active map layers tied to that service.
5. Apply historical filters (if supported by that service):
   - Date range mode (start/end)
   - Timeline mode (year/month)
6. Clear historical filters and return to unfiltered view.

Notes:
- Some ArcGIS services return limited metadata.
- If time filtering is available, applying filters may reload raster sources.

---

## Layer Info Modal: What Users Can Do

When Layer Info opens, users can:
1. Read layer metadata (when available), including:
   - Layer name
   - Description
   - Geometry type
   - Scale and visibility fields
   - Attachments support
   - Field summary
2. Open the external ArcGIS layer page.

Notes:
- Metadata availability depends on the ArcGIS endpoint.

---

## Right-Click Context Menu: Service and Layer Actions

### Service right-click menu
Typical actions include:
1. **Learn more** (opens Service Info modal)
2. **Pin / Unpin (Auto-load)**
3. **Save to Custom Layers** (login required)
4. **Rename** (admin-only, when available)

### Layer right-click menu
Typical actions include:
1. **Learn more** (opens Layer Info modal)
2. **Pin / Unpin (Auto-load)**

If you ask "what options are in the right click menu for layer", the answer is usually:
- Learn more
- Pin / Unpin (Auto-load)

### Sublayer right-click menu
Typical actions include:
1. **Pin / Unpin (Auto-load)**

---

## Pinning and Auto-Load

When you pin a service/layer/sublayer:
- The app can auto-restore pinned items on panel open.
- Related tree nodes may auto-expand.
- Saved pins can be synced to account preferences when logged in.

If not logged in, pin behavior may be limited or routed through local pending preferences.

---

## Login and Permission Rules

- **Save to Custom Layers** requires login.
- **Rename** actions are admin-gated and may not be visible to all users.
- Learn More and info modals are generally available for browsing metadata.

---

## FAQ

**Q: I right-clicked a service but do not see Rename. Why?**
A: Rename is admin-only and appears only when permitted by your role.

**Q: Why does Service Info show little or no metadata?**
A: Some ArcGIS endpoints provide limited metadata fields.

**Q: Why did the map refresh after I changed a time filter?**
A: Time filters rebuild raster source URLs with temporal parameters.

**Q: Why does Save to Custom Layers ask me to log in?**
A: That action is user-scoped and requires an authenticated account.

**Q: How do I quickly inspect one layer without enabling all layers in a service?**
A: Open Service Info, click the target layer link, then review Layer Info details.
