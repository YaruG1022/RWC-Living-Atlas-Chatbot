# ArcGIS Upload Panel: Overview and Navigation

## What This Covers

This document explains core structure and navigation behavior of the ArcGIS Upload Panel.

Scope includes:
- Data source loading and fallback
- Panel header actions
- State -> Folder -> Service -> Layer navigation
- Built-in layers section
- Breadcrumb navigation

---

## Panel Purpose

The ArcGIS Upload Panel lets users browse ArcGIS MapServer services and add selected layers to the map.

Primary supported states:
- Washington (WA)
- Idaho (ID)
- Oregon (OR)

The panel also includes a Built-in Layers folder for non-ArcGIS hardcoded map layers.

---

## How to Add ArcGIS Layers to the Map (Quick Steps)

If you are asking "how to add ArcGIS layers to map", use this flow:

1. Open the **ArcGIS Upload Panel** from the sidebar/tools.
2. Choose a state folder (**WA**, **ID**, or **OR**) or use search.
3. Expand folders and open a service.
4. Check a service checkbox to add all leaf layers, or check individual layer checkboxes.
5. Wait for loading messages/spinner to finish; selected layers appear on the map.
6. Uncheck the same checkbox to remove the layer/service from the map.

Notes:
- Built-in Layers can also be toggled from the Built-in section.
- "Clear All" removes all ArcGIS selections currently added from this panel.

---

## Data Source Behavior

### Preferred Source
The panel attempts to load services from backend database endpoints.

### Fallback Source
If backend data is unavailable, the panel falls back to local JSON files.

### User-visible Status
A status message indicates whether data is loaded from:
- Backend database
- Local fallback data

---

## Header Controls

Top header includes:
- Help button (opens ArcGIS panel manual section)
- Tutorial button (opens ArcGIS panel onboarding)
- Close button (closes panel)

---

## Tree Navigation Model

The folder area supports hierarchical browsing:
1. State folder
2. Sub-folder
3. Service row
4. Layer tree (including group layers and sublayers)

### Navigation Mode
Users can click through state and folder levels.

### Search Mode
When search is active, matching tree segments are shown in filtered form.

---

## Built-in Layers

Built-in Layers appear as a dedicated folder and are not fetched from ArcGIS service APIs.

Current built-in entries include examples like:
- Hydrological Boundaries
- City Limits

These are controlled by simple checkboxes and map visibility toggles.

---

## Breadcrumb and Back Navigation

When drilling into a state/folder path, breadcrumb is shown with:
- Back button
- Current path text

Back behavior:
- Folder level -> state level
- State level -> root

---

## Expansion Behavior

The panel tracks expansion states for:
- State folders
- Service folders
- Services
- Group layers

These states are updated by direct user clicks, search expansion logic, and onboarding steps.

---

## Common Questions

**Q: Why do I still see data when backend is down?**
A: The panel automatically switches to local JSON fallback.

**Q: Why is Built-in Layers separate from state services?**
A: Built-in layers are local predefined map layers, not ArcGIS service records.
