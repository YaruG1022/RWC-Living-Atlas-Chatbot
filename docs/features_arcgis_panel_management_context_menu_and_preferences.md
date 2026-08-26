# ArcGIS Upload Panel: Management, Context Menu, and Preferences

## What This Covers

This document explains management actions, right-click context menu, pinning, update workflow, and preference persistence.

Included features:
- Context menu actions by item type
- Pin / unpin auto-load
- Rename folder/service
- Remove service
- Save to Custom Layers
- Update services from ArcGIS endpoints
- Preference loading/sync logic
- Login-gated actions

---

## Context Menu

Right-click context menu supports different actions by target type.

### Folder target
- Rename (admin flow)

### Service target
- Rename (admin flow)
- Learn more
- Save to Custom Layers
- Pin/Unpin (Auto-load)

### Layer target
- Learn more
- Pin/Unpin (Auto-load)

If you ask "what options are in right click menu for layer", the typical options are:
- Learn more
- Pin/Unpin (Auto-load)

### Sublayer target
- Pin/Unpin (Auto-load)

---

## Pin / Unpin (Auto-load)

Pinned items are stored as tuples:
- serviceKey
- optional layerId
- optional sublayerIndex

On panel open, pinned selections can auto-expand relevant tree nodes and auto-apply checked states.

If user is not logged in, pin action triggers login prompt.

---

## Rename Actions

### Rename Folder
Calls backend rename-folder API and refreshes service map after success.

### Rename Service
Calls backend rename-service API and refreshes service map after success.

Validation includes non-empty names.

---

## Remove Service

Removing a service:
1. Prompts for confirmation.
2. Calls backend remove service API.
3. Removes relevant map layers/sources if active.
4. Cleans panel state for that service.
5. Refreshes service list from backend.

Error handling includes conflict/duplicate and table initialization edge cases.

---

## Save to Custom Layers

From service context menu, service can be saved to Custom Layers.

Requirements:
- User must be logged in.

On success:
- A completion message is shown.
- Optional callback notifies other panel(s) to refresh.

---

## Update Services

Update button runs state-specific service refresh from ArcGIS REST.

UI includes:
- Running spinner state
- Progress text
- Result summary (found/existing/new)

After successful update with new services, panel refreshes services from backend.

---

## Preferences and Persistence

### Pinned items persistence
- Logged-in users: cloud preferences API
- Anonymous users: local pending preferences cache
- Legacy local pinned storage is migrated to pending preferences

### Selection persistence notes
Layer selection DB persistence exists in code comments but is currently disabled.

---

## Onboarding

ArcGIS panel onboarding highlights guided steps for:
- Panel overview
- State folders
- Service checkboxes
- Search area
- Service info button
- Layer tree
- Opacity slider

Onboarding supports previous/next, keyboard navigation, and escape close.

---

## Common Questions

**Q: Why can I see rename options only sometimes?**
A: Rename is gated by admin capability and context-menu target type.

**Q: Why are pinned items restored on open?**
A: Auto-load pin behavior expands tree and reapplies saved pinned selections.

**Q: Why does save to custom layers ask me to log in?**
A: That action is user-scoped and requires authenticated identity.
