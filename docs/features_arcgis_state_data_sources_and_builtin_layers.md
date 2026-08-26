# State ArcGIS Data Sources and Built-in Layers

## Scope

This document explains the spatial data the Living Atlas can display on the map. It covers:

- The three state ArcGIS data sources — **Washington**, **Idaho**, and **Oregon**
- What kind of environmental data each provides and the agency behind it
- The folder/service/layer structure shown in the GIS data panel
- The map's **built-in layers** (separate from ArcGIS services and user-added layers)

It is intended as a knowledge source for the chatbot so it can answer questions like "What is the AQ folder?", "Where does Idaho data come from?", or "What are those boundary lines on the map?".

---

## How State Data Reaches the Map

The Living Atlas does **not** store these layers itself. It fetches them live from each state's public **ArcGIS REST** server. In the GIS data panel, users pick a state (WA, ID, OR), browse a **folder → service → layer** tree, and load layers onto the map as colored regions, lines, or points. Clicking a loaded feature opens an info pop-up.

Each entry in the panel has a type:
- **MapServer** — a rendered map image service (drawn as colored regions/overlays).
- **FeatureServer** — a vector feature service (individual clickable features).

---

## Washington ArcGIS — Department of Ecology

| Field | Value |
|-------|-------|
| Agency | **Washington State Department of Ecology** |
| ArcGIS server | `https://gis.ecology.wa.gov/serverext/rest/services` |
| Services in the Atlas | ~125 |
| Mission | "To protect, preserve, and enhance Washington's environment for current and future generations." |

The Department of Ecology is Washington's lead environmental agency, responsible for protecting the state's land, air, water, and climate. Its GIS server publishes environmental monitoring and regulatory datasets, organized into program folders.

### Notable Washington folders

| Folder | What it generally contains |
|--------|----------------------------|
| **AQ** | Air Quality — e.g. `AirQualityMonitoringHourlyResults` and `SmokeForecast` (wildfire smoke). |
| **WQ** | Water Quality — water body assessments and monitoring. |
| **WR** | Water Resources — water rights and availability data. |
| **EAP** | Environmental Assessment Program — environmental monitoring and study data. |
| **ADS** | Data submission / `eim*` map services tied to the Environmental Information Management (EIM) database. |
| **NHD** | National Hydrography Dataset — streams, rivers, and water bodies. |
| **TCP** | Toxics Cleanup Program — contaminated site cleanup data. |
| **SEA** | Shorelands & Environmental Assistance. |
| **SPPR** | Spill Prevention, Preparedness, and Response. |
| **WASHD** | Agency program/reference datasets. |
| **Authoritative**, **GIS**, **CustomUtilities**, **Utilities**, **MapControl** | Authoritative reference layers and supporting/utility services. |

> The **EIM (Environmental Information Management)** database is Ecology's public repository of environmental monitoring data, which several Washington map services draw from.

---

## Idaho ArcGIS — Department of Water Resources (IDWR)

| Field | Value |
|-------|-------|
| Agency | **Idaho Department of Water Resources (IDWR)** |
| ArcGIS server | `https://gis.idwr.idaho.gov/hosting/rest/services` |
| Services in the Atlas | ~267 |
| Mission | "To serve Idahoans by ensuring their water is conserved and available to sustain Idaho's economy, ecosystems, and resulting quality of life." |

Idaho's data comes from IDWR, the state agency that manages water rights, water resource planning, and well/groundwater data. Because IDWR is a water-focused agency, the Idaho layers center on water administration, allocation, and hydrology rather than general environmental monitoring.

### Notable Idaho folders

| Folder | What it generally contains |
|--------|----------------------------|
| **Administrative** | Administrative basins, adjudication boundaries, IDWR office locations. |
| **Allocation** | Water rights and water allocation data. |
| **Groundwater** | Groundwater levels, aquifers, and well data. |
| **IrrigatedLands** | Irrigated agricultural land mapping. |
| **Irrigation** | Irrigation infrastructure and entities. |
| **Regulatory** | Regulatory boundaries and compliance areas. |
| **Compliance** | Water-use compliance datasets. |
| **Modeling** | Hydrologic and groundwater model outputs. |
| **WaterPlans** | Water planning areas and basin plans. |
| **Reference**, **BasemapImagery**, **ScientificRasters** | Reference layers, imagery basemaps, and scientific raster data. |
| **Utilities**, **MapAutomation** | Supporting/utility services. |

---

## Oregon ArcGIS — Geospatial Enterprise Operations (GEO) / Navigator

| Field | Value |
|-------|-------|
| Agency | **Oregon Geospatial Enterprise Operations (GEO)**, within Enterprise Information Services |
| ArcGIS server | `https://navigator.state.or.us/arcgis/rest/services` |
| Services in the Atlas | ~20 |
| Role | Coordinates statewide GIS data, standards, and the Oregon Framework Program; hosts authoritative "Framework" data. |

Oregon's data comes from the state's central geospatial office (GEO), not a single environmental agency. GEO publishes **Framework data** — the authoritative statewide base layers used across Oregon government — through the Oregon Navigator server and GEOHub.

### Notable Oregon folders

| Folder | What it generally contains |
|--------|----------------------------|
| **Framework** | Authoritative statewide base layers: administrative boundaries (`Admin_Bounds`), hydrography (`Hydro_GeneralMap`), wetlands/biota (`Bio_Wetlands`), hazards (`Haz_GeneralMap`), and cadastral/PLSS survey grids (`Cadastral_PLSS`). |
| **Locators** | Address/geocoding locator services. |
| **Projects** | Project-specific map services. |
| **Utilities**, **Root** | Supporting and utility services. |

> Many Framework services have both a standard and a `_WM` (Web Mercator) version of the same data, intended for web map display.

---

## Quick Comparison

| State | Source Agency | Server Host | Data Focus |
|-------|---------------|-------------|------------|
| Washington | Dept. of Ecology | `gis.ecology.wa.gov` | Broad environmental: air, water quality, cleanup, hydrography |
| Idaho | Dept. of Water Resources (IDWR) | `gis.idwr.idaho.gov` | Water rights, allocation, groundwater, irrigation |
| Oregon | Geospatial Enterprise Operations (GEO) | `navigator.state.or.us` | Authoritative statewide framework base layers |

---

## Built-in Map Layers

Separate from the state ArcGIS services and from user-added custom layers, the Living Atlas map includes a small set of **built-in informational layers** that can be toggled on or off:

- **Hydrological Boundaries** — watershed and hydrological boundary areas.
- **City Limits** — urban area and city boundary outlines.

### Interacting with built-in layers
1. Make sure the relevant built-in layer is visible on the map.
2. Click a hydrological boundary or city area on the map.
3. A popup shows details about that area:
   - Hydrological areas: name, length, and ID.
   - City/urban areas: city name, county, and area type.

These built-in layers are always part of the app and do not need to be loaded from a state server.

---

## Frequently Asked Questions

**Q: Which states' data does the Living Atlas include?**
A: Washington, Idaho, and Oregon. Switch between them using the state menu (WA, ID, OR) at the upper-right of the GIS data panel.

**Q: Where does the Washington data come from?**
A: The Washington State Department of Ecology's public ArcGIS server (`gis.ecology.wa.gov`). It includes environmental data such as air quality, water quality, water resources, and hydrography.

**Q: Where does the Idaho data come from?**
A: The Idaho Department of Water Resources (IDWR) ArcGIS server (`gis.idwr.idaho.gov`). Idaho's layers focus on water — water rights/allocation, groundwater, irrigation, and water administration.

**Q: Where does the Oregon data come from?**
A: Oregon's Geospatial Enterprise Operations (GEO) via the Oregon Navigator server (`navigator.state.or.us`). It provides authoritative statewide "Framework" base layers like boundaries, hydrography, wetlands, and hazards.

**Q: What is the "AQ" folder?**
A: AQ is Washington's Air Quality folder. It includes services like hourly air quality monitoring results and a wildfire smoke forecast.

**Q: What's the difference between a MapServer and a FeatureServer?**
A: A MapServer delivers a pre-rendered map image (drawn as colored regions). A FeatureServer delivers individual vector features you can click and query directly.

**Q: Why do some layers take a while to appear?**
A: State layers are fetched live from each agency's ArcGIS server and rendered as colored regions. Dense or large datasets can take a moment to load.

**Q: What are those boundary lines on the map that I never loaded?**
A: Those are the built-in layers — hydrological boundaries and city limits. Click them to see details. They are part of the app, not state ArcGIS services.

**Q: Is this data stored in the Living Atlas?**
A: No. The state ArcGIS layers are streamed live from each state's public server, so they reflect the agencies' current published data.

---

## Glossary

| Term | Meaning |
|------|---------|
| ArcGIS REST server | A web service that publishes map layers; the Atlas fetches state data from these. |
| MapServer | A rendered map image service (colored overlays). |
| FeatureServer | A vector feature service with clickable, queryable features. |
| Folder | Top-level grouping in the panel (usually a program or theme, e.g. AQ, Groundwater, Framework). |
| Service | A dataset under a folder (e.g. `SmokeForecast`). |
| Layer | A specific sublayer within a service, shown with a legend. |
| Framework data | Oregon's authoritative statewide base GIS layers. |
| EIM | Washington Ecology's Environmental Information Management database. |
| Built-in layer | A layer that ships with the Atlas (hydrological boundaries, city limits), not loaded from a state server. |
