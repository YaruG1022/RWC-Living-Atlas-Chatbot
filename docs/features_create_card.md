# Create Card Feature

## What is a Card?

A card is the core data unit of the Living Atlas. Each card represents a geographically located resource — such as a water quality monitoring station, a watershed research area, or an environmental dataset. Cards can include a description, tags, external links, file attachments, and images. On the map, a card appears as a point marker, a polygon area, or an image overlay depending on the location type chosen at creation.

---

## Who Can Create a Card?

Any logged-in user can create a card — no special permissions are required. Users can only edit and delete cards they created. Administrators can edit and delete any card.

---

## How to Create a Card

### Step 1 — Open the Creation Form

Click the **"Create Card"** or **"Add Card"** button on the page. A card creation form will appear.

---

### Step 2 — Fill in the Basic Information

| Field | Required | Description |
|-------|----------|-------------|
| **Title** | ✅ Yes | The card name. Maximum 255 characters. |
| **Category** | ✅ Yes | Choose from the dropdown: River, Watershed, Places, Other, or None. |
| **Description** | Optional | A detailed explanation of the card's content. Maximum 2000 characters. |
| **Organization** | Optional | The institution or organization that produced the data. |
| **Funding** | Optional | The funding source for this resource. |
| **Tags** | Optional | Comma-separated keywords to make the card easier to search and filter. |
| **Links** | Optional | One or more external URLs. Each link can have optional display text. |

---

### Step 3 — Choose a Location Type

Cards support three location types. Select one when creating the card.

#### 1. Point — Default
- Use this for a single geographic coordinate, such as a monitoring station.
- Enter **Latitude** (−90 to 90) and **Longitude** (−180 to 180), with up to 8 decimal places.
- Alternatively, click **"Select a Location"** to pick a point directly on the map.

#### 2. Polygon
- Use this for a resource that covers an area, such as a watershed boundary.
- Draw a polygon on the map. **At least 3 vertices are required.**
- You can set a fill color (default: blue `#0077c0`) and a line style (solid or dashed).

#### 3. Image Overlay
- Use this to pin an image (such as a map screenshot or heatmap) over a specific area on the map.
- Upload a PNG image and place **exactly 4 corner points** on the map to define its position.

---

### Step 4 — Upload Files and Images (Optional)

#### Attachments
- Any file format is accepted.
- Maximum size per file: **5 MB**.
- Files are automatically compressed into a `.zip` archive before being stored. Users download a zip file.

#### Image Gallery
- Accepted formats: PNG, JPG, GIF, WebP.
- Maximum size per image: **5 MB**.
- You can upload multiple images. The first image automatically becomes the card's thumbnail.
- Images are displayed as a gallery in the card detail view.

#### Thumbnail
- You can upload a separate thumbnail image, which is shown in the card list.
- If no thumbnail is provided, the default CEREO thumbnail is used.

---

### Step 5 — Submit

Click **"Submit"** to create the card.

- The card appears on the map immediately after submission.
- A success notification is shown on the page.
- Other users can see and click your card on the map.

---

## Frequently Asked Questions

**Q: How do I create cards?**
A: Click **Create Card** (or **Add Card**), fill required fields (at minimum title, category, and location), then click **Submit**. For polygons and image overlays, complete the required map geometry before submitting.

**Q: I see a "Title too long" error when submitting. What do I do?**
A: The title exceeds the 255-character limit. Shorten the title and try again.

**Q: I selected the Polygon type but cannot submit. Why?**
A: A polygon requires at least 3 vertices. Make sure you have fully drawn the shape on the map before submitting.

**Q: I selected Image Overlay but cannot submit. Why?**
A: An image overlay requires exactly 4 corner points — no more, no fewer. Place all four corners on the map and try again.

**Q: My file upload failed. What should I check?**
A: Verify that each file is under 5 MB. There are no format restrictions for attachments, but very large files will be rejected.

**Q: Can I edit a card after it has been created?**
A: Yes. Open the card detail view and click the edit button to modify any field, including the location, images, and files. Only the card's creator and administrators can edit a card.

**Q: Can I delete a card?**
A: Yes. Only the card's creator and administrators have permission to delete a card. Deleting a card permanently removes all associated files, images, and tags.

---

## Field Limits Quick Reference

| Field | Limit |
|-------|-------|
| Title | 255 characters max |
| Description | 2000 characters max |
| Organization | 255 characters max |
| Funding | 255 characters max |
| Latitude | −90 to 90, up to 8 decimal places |
| Longitude | −180 to 180, up to 8 decimal places |
| File size (per file) | 5 MB max |
| Image size (per image) | 5 MB max |
| Image formats | PNG, JPG, GIF, WebP |
| Polygon vertices | Minimum 3 |
| Image Overlay vertices | Exactly 4 |
