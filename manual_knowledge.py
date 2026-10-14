"""Versioned knowledge from the exact chapter content rendered by the app manual.

No legacy docs are consulted. A validated new namespace is published by updating
one durable Pinecone control record; older namespaces are retained for recovery.
"""
import hashlib
import json
import re
import time
from urllib.parse import urlparse

CONTROL_NAMESPACE = "manual-control"
ACTIVE_ID = "active-manual"
VERSION_RE = re.compile(r"^[a-f0-9]{40}-[a-f0-9]{12}$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
MAX_PACKAGE_BYTES = 5 * 1024 * 1024


def response_dict(response):
    if isinstance(response, dict):
        return response
    if hasattr(response, 'to_dict'):
        return response.to_dict()
    if hasattr(response, 'model_dump'):
        return response.model_dump()
    return dict(response)


def namespace_for(version):
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise ValueError("Invalid manual version")
    return f"manual-{version}"


def validate_manifest(manifest):
    namespace_for(manifest.get("version"))
    revision = manifest.get("revision", "")
    if manifest.get("schemaVersion") != 1 or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Invalid manifest schema/revision")
    if not manifest["version"].startswith(revision + "-"):
        raise ValueError("Manifest revision/version mismatch")
    ids = manifest.get("sectionIds", [])
    if not ids or len(ids) != len(set(ids)) or any(not ID_RE.fullmatch(i) for i in ids):
        raise ValueError("Missing/duplicate chapter IDs")
    if manifest.get("sectionCount") != len(ids):
        raise ValueError("Chapter count mismatch")
    files = manifest.get("files", [])
    if len(files) != 1 or files[0].get("path") != "manual.json":
        raise ValueError("Only the manual bundle is allowed")
    checksum = files[0].get("sha256", "")
    if not re.fullmatch(r"[a-f0-9]{64}", checksum) or not manifest["version"].endswith(checksum[:12]):
        raise ValueError("Invalid checksum/version")
    if not isinstance(files[0].get("bytes"), int) or not 0 < files[0]["bytes"] <= MAX_PACKAGE_BYTES:
        raise ValueError("Invalid bundle size")
    for field, filename in [("bundlePath", "manual.json"), ("manifestPath", "manifest.json")]:
        if manifest.get(field) != f"/manual/releases/{manifest['version']}/{filename}":
            raise ValueError("Invalid release path")
    if 'visuals' in manifest:
        from manual_visuals import validate_visual_descriptor
        validate_visual_descriptor(manifest['visuals'])


def text_content(nodes, ordered=False):
    result, step = [], 0
    for node in nodes:
        kind = node.get("type")
        if kind == "text":
            if not isinstance(node.get("text"), str):
                raise ValueError("Invalid manual text")
            result.append(node["text"])
        elif kind == "break":
            result.append("\n")
        elif kind == "li":
            step += 1
            result.append(f"\n{str(step) + '.' if ordered else '-'} {text_content(node['content'])}")
        elif kind in {"strong", "em", "code", "span", "link", "chapter-link", "ul", "ol", "kbd"}:
            result.append(text_content(node["content"], kind == "ol"))
        else:
            raise ValueError("Unknown manual content type")
    return "".join(result)


def validate_bundle(manifest, raw):
    validate_manifest(manifest)
    expected = manifest["files"][0]
    if len(raw) != expected["bytes"] or hashlib.sha256(raw).hexdigest() != expected["sha256"]:
        raise ValueError("Bundle checksum/size mismatch")
    bundle = json.loads(raw)
    if bundle.get("schemaVersion") != 1 or bundle.get("revision") != manifest["revision"]:
        raise ValueError("Bundle version mismatch")
    sections = bundle.get("sections", [])
    if [s.get("id") for s in sections] != manifest["sectionIds"]:
        raise ValueError("Bundle chapters do not match manifest")
    seen = set()
    for section in sections:
        if not section.get("title") or section.get("manualPath") != f"/user-manual?section={section['id']}":
            raise ValueError("Missing title or invalid manual link")
        if not section.get("blocks"):
            raise ValueError("Empty chapter")
        for block in section["blocks"]:
            if not ID_RE.fullmatch(block.get("id", "")) or block["id"] in seen:
                raise ValueError("Duplicate/invalid block ID")
            seen.add(block["id"])
            if block.get("text") != text_content(block["content"], block.get("ordered", False)):
                raise ValueError("Exported prose does not match rendered content")
    if len(seen) != manifest.get("blockCount"):
        raise ValueError("Bundle block count mismatch")
    return bundle


def validate_base_url(base):
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("MANUAL_BASE_URL must be an HTTPS app origin")
    return base.rstrip("/")


def fetch_json_bytes(session, url):
    # Redirects are disabled: configured origin, not a dispatch payload, selects the host.
    response = session.get(url, timeout=20, allow_redirects=False, stream=True, headers={"Cache-Control": "no-cache"})
    response.raise_for_status()
    if response.status_code != 200 or "json" not in response.headers.get("Content-Type", "").lower():
        raise ValueError("Manual content is not a published JSON resource")
    chunks, size = [], 0
    try:
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_PACKAGE_BYTES:
                raise ValueError("Manual response exceeds limit")
            chunks.append(chunk)
    finally:
        response.close()
    return b"".join(chunks)


def fetch_published_bundle(session, base, expected_revision=None):
    base = validate_base_url(base)
    current = json.loads(fetch_json_bytes(session, base + "/manual/current.json"))
    validate_manifest(current)
    if expected_revision and current["revision"] != expected_revision:
        raise ValueError("Requested app version is not yet published")
    manifest = json.loads(fetch_json_bytes(session, base + current["manifestPath"]))
    if manifest != current:
        raise ValueError("Published release marker and manifest disagree")
    bundle = validate_bundle(manifest, fetch_json_bytes(session, base + manifest["bundlePath"]))
    if manifest.get('visuals'):
        from manual_visuals import fetch_catalog
        bundle['_visual_catalog'] = fetch_catalog(session, base, manifest['visuals'], manifest['version'], manifest['revision'], bundle)
    # A marker generated by a build is only accepted with an accessible manual page.
    page = session.get(base + "/user-manual?section=home", timeout=20, allow_redirects=False)
    try:
        page.raise_for_status()
        if page.status_code != 200 or "html" not in page.headers.get("Content-Type", "").lower():
            raise ValueError("Published user manual page is not accessible")
    finally:
        page.close()
    return manifest, bundle


def build_records(manifest, bundle):
    """Keep each heading/feature and its complete paragraphs, steps and notes together."""
    records = []
    for section in bundle["sections"]:
        operations, current = [], []
        for block in section["blocks"]:
            if current and (block["type"] == "heading" or block.get("role") == "feature-title"):
                operations.append(current)
                current = []
            current.append(block)
        if current:
            operations.append(current)
        for position, blocks in enumerate(operations):
            visual_ids = [entry['id'] for entry in bundle.get('_visual_catalog', {}).get('entries', [])
                if entry['sectionId'] == section['id'] and (entry['state'] == 'chapter-overview'
                or set(entry['blockIds']).intersection(block['id'] for block in blocks))]
            records.append({"_id": f"{section['id']}-{position:03d}",
                "content": f"{section['title']}\n{section['summary']}\n\n" + "\n\n".join(b["text"] for b in blocks),
                "section_id": section["id"], "title": section["title"], "manual_path": section["manualPath"],
                "version": manifest["version"], "revision": manifest["revision"],
                "block_ids": [b["id"] for b in blocks],
                "step_ids": [step for b in blocks for step in b.get("stepIds", [])],
                "image_ids": visual_ids or [i["id"] for i in section["images"]],
                "example_ids": [i["id"] for i in section["examples"]]})
    return records


def fetched_metadata(index, namespace, ids):
    result = response_dict(index.fetch(ids=ids, namespace=namespace))
    return {key: value.get("metadata", {}) for key, value in result.get("vectors", {}).items()}


def read_active(index):
    metadata = fetched_metadata(index, CONTROL_NAMESPACE, [ACTIVE_ID]).get(ACTIVE_ID)
    pointer = dict(metadata) if metadata else None
    if not pointer:
        return None
    namespace = namespace_for(pointer.get("version"))
    if pointer.get("namespace") != namespace:
        raise ValueError("Invalid active manual pointer")
    pointer["base_url"] = validate_base_url(pointer["base_url"])
    if pointer.get('visuals_json'):
        from manual_visuals import validate_visual_descriptor
        pointer['visuals'] = json.loads(pointer['visuals_json'])
        validate_visual_descriptor(pointer['visuals'])
    return pointer


def verify_records(index, namespace, records, attempts=30, delay=2, sleep=time.sleep):
    for attempt in range(attempts):
        complete = True
        for start in range(0, len(records), 100):
            batch = records[start:start + 100]
            found = fetched_metadata(index, namespace, [record["_id"] for record in batch])
            if any(found.get(r["_id"], {}).get("content") != r["content"] or found.get(r["_id"], {}).get("version") != r["version"] for r in batch):
                complete = False
                break
        stats = response_dict(index.describe_index_stats())
        count = stats.get("namespaces", {}).get(namespace, {}).get("vector_count", 0)
        if complete and count == len(records):
            # Probe each chapter so a correct count cannot hide an unsearchable chapter.
            sections = {r["section_id"]: r for r in records}
            for section, record in sections.items():
                hits = response_dict(index.search(namespace=namespace, query={"inputs": {"text": record["title"]}, "top_k": 1,
                    "filter": {"section_id": {"$eq": section}}}, fields=["section_id", "version", "content"]))["result"]["hits"]
                if not hits or hits[0].get("fields", {}).get("section_id") != section or hits[0].get("fields", {}).get("version") != record["version"]:
                    complete = False
                    break
            if complete:
                return
        if attempt + 1 < attempts:
            sleep(delay)
    raise RuntimeError("Staged manual records/count/search validation failed; active version unchanged")


def publish_bundle(index, manifest, bundle, base, activate=False, attempts=30, sleep=time.sleep, before_activate=None):
    base = validate_base_url(base)
    namespace = namespace_for(manifest["version"])
    records = build_records(manifest, bundle)
    existing = read_active(index)
    visuals = manifest.get('visuals')
    visuals_json = json.dumps(visuals, sort_keys=True) if visuals else ''
    if existing and existing["version"] == manifest["version"] and existing["base_url"] == base and existing.get('visuals_json', '') == visuals_json:
        return {"status": "already-active", "version": manifest["version"], "records": len(records)}
    # Upsert is idempotent; a failed partial write is resumed without deleting anything.
    for start in range(0, len(records), 90):
        index.upsert_records(namespace=namespace, records=records[start:start + 90])
    verify_records(index, namespace, records, attempts=attempts, sleep=sleep)
    if activate:
        if before_activate:
            before_activate()
        previous = existing.get("version", "") if existing else ""
        pointer = {"_id": ACTIVE_ID, "content": "Validated active Living Atlas manual release",
            "namespace": namespace, "version": manifest["version"], "revision": manifest["revision"],
            "base_url": base, "previous_version": previous, "record_count": len(records)}
        if visuals:
            pointer['visuals_json'] = visuals_json
        # Store the validated release before the active pointer so rollback has a durable target.
        index.upsert_records(namespace=CONTROL_NAMESPACE, records=[{**pointer, "_id": f"release-{manifest['version']}",
            "record_ids": [record["_id"] for record in records]}])
        index.upsert_records(namespace=CONTROL_NAMESPACE, records=[pointer])
        # Pinecone fetch/search is eventually consistent; each reader can continue its old pointer during propagation.
    return {"status": "activated" if activate else "validated", "version": manifest["version"], "records": len(records)}


def rollback(index, version):
    """Explicit operator recovery; never run as automatic cleanup or on every restart."""
    namespace = namespace_for(version)
    release = fetched_metadata(index, CONTROL_NAMESPACE, [f"release-{version}"]).get(f"release-{version}")
    if not release or release.get("namespace") != namespace:
        raise ValueError("No validated rollback release")
    validate_base_url(release["base_url"])
    ids = release.get("record_ids", [])
    if not ids or len(ids) != release.get("record_count"):
        raise ValueError("Invalid rollback record inventory")
    records = []
    for start in range(0, len(ids), 100):
        found = fetched_metadata(index, namespace, ids[start:start + 100])
        for record_id in ids[start:start + 100]:
            metadata = found.get(record_id, {})
            if metadata.get("version") != version or not metadata.get("content"):
                raise ValueError("Rollback namespace is incomplete")
            records.append({"_id": record_id, **metadata})
    verify_records(index, namespace, records)
    pointer = {
        "_id": ACTIVE_ID, "content": "Validated active Living Atlas manual release (rollback)",
        "namespace": namespace, "version": version, "revision": release["revision"],
        "base_url": release["base_url"], "record_count": len(records),
        "previous_version": (read_active(index) or {}).get("version", "")}
    if release.get('visuals_json'):
        pointer['visuals_json'] = release['visuals_json']
    index.upsert_records(namespace=CONTROL_NAMESPACE, records=[pointer])
    return {"status": "rolled-back", "version": version}


def search_manual(index, query, pointer, top_k=3):
    result = response_dict(index.search(namespace=pointer["namespace"], query={"inputs": {"text": query}, "top_k": top_k},
        fields=["content", "section_id", "title", "manual_path", "version", "revision", "block_ids", "step_ids", "image_ids"]))
    passages, sources = [], []
    for hit in result.get("result", {}).get("hits", []):
        fields = hit.get("fields", {})
        section = fields.get("section_id", "")
        if not ID_RE.fullmatch(section) or fields.get("version") != pointer["version"] or not fields.get("content"):
            continue
        # URLs come from the trusted pointer + validated IDs, never from model output or stored arbitrary URLs.
        url = pointer["base_url"] + f"/user-manual?section={section}"
        passages.append(f"[{section}] {fields['content']}")
        sources.append({"section_id": section, "title": fields.get("title", section), "url": url,
            "version": pointer["version"], "revision": pointer["revision"], "block_ids": fields.get("block_ids", []),
            "step_ids": fields.get("step_ids", []), "image_ids": fields.get("image_ids", [])})
    return passages, sources
