"""Import the published app manual, stage a version, verify it, then optionally activate.

Legacy docs/*.md are deliberately never read. Default execution validates/stages;
--activate switches only after every record and chapter search is ready.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from manual_knowledge import fetch_published_bundle, publish_bundle, validate_bundle


def get_index():
    from pinecone import Pinecone
    key = os.environ.get("PINECONE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PINECONE_API_KEY is not configured")
    pc = Pinecone(api_key=key)
    host = os.environ.get("PINECONE_INDEX_HOST", "").strip()
    if host:
        return pc.Index(host=host)
    name = (os.environ.get("PINECONE_INDEX") or "living-atlas-docs-hosted")
    if name not in [item.name for item in pc.list_indexes()]:
        pc.create_index_for_model(name=name, cloud="aws", region="us-east-1",
            embed={"model": (os.environ.get("PINECONE_EMBED_MODEL") or "multilingual-e5-large"), "field_map": {"text": "content"}})
    return pc.Index(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, help="Local generated release directory (staging only)")
    parser.add_argument("--revision", help="Require this published app commit")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument('--rollback', help='Explicitly restore a previously validated version')
    args = parser.parse_args()
    if args.rollback:
        from manual_knowledge import rollback
        if args.activate or args.bundle_dir or args.revision:
            parser.error('Rollback cannot be combined with import options')
        print(json.dumps(rollback(get_index(), args.rollback)))
        return 0
    args.revision = args.revision or os.environ.get('EXPECTED_REVISION') or None
    if args.revision and not __import__('re').fullmatch(r'[a-f0-9]{40}', args.revision):
        parser.error('Expected revision must be a full commit SHA')
    base = os.environ.get("MANUAL_BASE_URL", "").strip()
    if args.bundle_dir and args.activate:
        parser.error("Activation requires the published app bundle, not local files")
    if args.bundle_dir:
        manifest = json.loads((args.bundle_dir / "manifest.json").read_bytes())
        bundle = validate_bundle(manifest, (args.bundle_dir / "manual.json").read_bytes())
    else:
        import requests
        session = requests.Session()
        manifest, bundle = fetch_published_bundle(session, base, args.revision)
    if os.environ.get('EXPECTED_VERSION') and manifest['version'] != os.environ['EXPECTED_VERSION']:
        raise ValueError('Published version differs from dispatch')
    if os.environ.get('EXPECTED_CHECKSUM') and manifest['files'][0]['sha256'] != os.environ['EXPECTED_CHECKSUM']:
        raise ValueError('Published checksum differs from dispatch')
    index = get_index()
    # Check the production marker again immediately before switching: a queued old
    # event cannot reactivate an outdated manual after a newer deployment.
    def activation_check():
        latest, _ = fetch_published_bundle(session, base, manifest["revision"])
        if latest != manifest:
            raise RuntimeError("Published app advanced during indexing; staged version not activated")
    result = publish_bundle(index, manifest, bundle, base, activate=args.activate,
        before_activate=activation_check if args.activate else None)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Manual sync failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
