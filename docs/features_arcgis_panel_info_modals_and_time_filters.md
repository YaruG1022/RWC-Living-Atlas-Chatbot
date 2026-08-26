# ArcGIS Upload Panel: Info Modals, Opacity, and Historical Filters

## What This Covers

This document explains service/layer info modals and advanced controls inside service info modal.

Included features:
- Service info modal
- Layer info modal
- Global opacity and per-service opacity
- Historical view filters (date range and timeline)
- Service/layer external links

---

## Service Info Modal

### Open
Click service row action button (ellipsis / Learn more).

### Quick User Answer
If you ask "what can I do in service info modal", the main actions are:
- Read service metadata
- Open linked layers
- Open external ArcGIS service page
- Adjust per-service opacity
- Apply/clear historical time filters

### Data Source
Service metadata is fetched from ArcGIS REST and cached by service key.

### Displayed Fields (when available)
- Service description
- Service item ID
- Copyright text
- Spatial reference
- Layer and sublayer links

### External Link
Modal provides link to ArcGIS service page.

---

## Layer Info Modal

### Open
From service info modal layer links, open a specific layer.

### Quick User Answer
If you ask "what can I do in layer info modal", the main actions are:
- Read layer metadata (name, description, geometry, scale/visibility)
- Review field/attachment support info (when available)
- Open external ArcGIS layer page

### Data Source
Layer metadata is fetched from ArcGIS REST and cached by service-layer key.

### Displayed Fields (when available)
- Description
- Layer name
- Geometry type
- Copyright
- Min/max scale
- Default visibility
- Attachments support
- Field summary

### External Link
Modal provides direct link to ArcGIS layer page.

---

## Opacity Controls

### Global Opacity
Main toolbar slider updates opacity for all ArcGIS raster/vector layers.

### Per-Service Opacity
Service info modal includes service-specific opacity slider.

This updates all active map layers that belong to the selected service key.

---

## Historical View Filters

Service info modal includes two historical modes:

### Date Range Mode
- Start date input
- End date input
- Apply and Clear actions

### Timeline Mode
- Year slider
- Month slider
- Clear action

Both modes build time range and re-apply raster tile URLs with time parameters.

### Active Indicator
If a service has active time filter, modal shows active filter date interval.

---

## Common Questions

**Q: Why does applying time filter redraw layers?**
A: Time filter updates tile source URLs, so raster sources are rebuilt with new temporal parameters.

**Q: Why no info appears in modal for some services/layers?**
A: Some ArcGIS endpoints provide limited metadata or return empty fields.
