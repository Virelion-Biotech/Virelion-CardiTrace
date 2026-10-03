from pathlib import Path
from cardi_trace import ArtifactStore
from cardi_trace.cli import main

def test_directory_store_and_gc(tmp_path):
    source=tmp_path/"dataset"; source.mkdir(); (source/"a.txt").write_text("A"); (source/"b.txt").write_text("B")
    store=ArtifactStore(tmp_path/"store")
    directory_digest=store.put_directory(source)
    manifest=store.get_json(directory_digest)
    assert manifest["schema"]=="carditrace.directory.v1"
    assert len(manifest["entries"])==2
    assert directory_digest in store.list_digests()
    removed=store.gc({directory_digest},dry_run=True)
    assert directory_digest not in removed

def test_cli_demo_and_exports(tmp_path):
    root=tmp_path/"trace"
    assert main(["demo",str(root)])==0
    assert main(["verify",str(root)])==0
    assert main(["provenance",str(root),str(tmp_path/"prov.json"),"--format","prov-json"])==0
    assert main(["card",str(root),str(tmp_path/"card.md")])==0
    assert main(["openlineage",str(root),str(tmp_path/"lineage.jsonl")])==0
    assert Path(tmp_path/"prov.json").exists()
    assert Path(tmp_path/"card.md").exists()
    assert Path(tmp_path/"lineage.jsonl").exists()
