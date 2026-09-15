"""Stdlib SQLite index for scalable read/query access without replacing the canonical ledger."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path

class SQLiteTraceIndex:
    """Rebuildable secondary index; JSONL remains the canonical append-only source."""
    def __init__(self, path: str|Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._db=sqlite3.connect(self.path)
        self._db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, component TEXT, operation TEXT, started_at REAL, finished_at REAL, status TEXT, code_identity TEXT, parameters_json TEXT, environment_json TEXT, metrics_json TEXT, tags_json TEXT, metadata_json TEXT);
        CREATE TABLE IF NOT EXISTS artifacts(artifact_id TEXT PRIMARY KEY, digest TEXT, kind TEXT, media_type TEXT, name TEXT, size_bytes INTEGER, uri TEXT, metadata_json TEXT);
        CREATE TABLE IF NOT EXISTS lineage(source_id TEXT, target_id TEXT, relation TEXT, run_id TEXT, metadata_json TEXT, PRIMARY KEY(source_id,target_id,relation));
        CREATE INDEX IF NOT EXISTS idx_runs_component_operation ON runs(component,operation);
        CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
        CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind);
        CREATE INDEX IF NOT EXISTS idx_lineage_source ON lineage(source_id);
        CREATE INDEX IF NOT EXISTS idx_lineage_target ON lineage(target_id);
        """); self._db.commit()
    def close(self): self._db.close()
    def rebuild(self, recorder):
        with self._db:
            self._db.execute("DELETE FROM runs"); self._db.execute("DELETE FROM artifacts"); self._db.execute("DELETE FROM lineage")
            self._db.executemany("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",[(r.run_id,r.component,r.operation,r.started_at,r.finished_at,str(r.status),r.code_identity,json.dumps(r.parameters,sort_keys=True,default=str),json.dumps(r.environment,sort_keys=True,default=str),json.dumps(r.metrics,sort_keys=True),json.dumps(r.tags,sort_keys=True),json.dumps(r.metadata,sort_keys=True,default=str)) for r in recorder.runs])
            self._db.executemany("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?)",[(a.artifact_id,a.digest,str(a.kind),a.media_type,a.name,a.size_bytes,a.uri,json.dumps(a.metadata,sort_keys=True,default=str)) for a in recorder.artifacts])
            self._db.executemany("INSERT INTO lineage VALUES(?,?,?,?,?)",[(e.source_id,e.target_id,e.relation,e.run_id,json.dumps(e.metadata,sort_keys=True,default=str)) for e in recorder.lineage])
        return self
    def runs(self, *, component=None, operation=None, status=None, tag=None, metric=None, metric_min=None):
        sql="SELECT * FROM runs WHERE 1=1"; args=[]
        if component is not None: sql+=" AND component=?"; args.append(component)
        if operation is not None: sql+=" AND operation=?"; args.append(operation)
        if status is not None: sql+=" AND status=?"; args.append(status)
        rows=self._db.execute(sql,args).fetchall(); out=[]
        for row in rows:
            metrics=json.loads(row[9]); tags=json.loads(row[10])
            if tag is not None and tag not in tags: continue
            if metric is not None and (metric not in metrics or (metric_min is not None and metrics[metric] < metric_min)): continue
            out.append({"run_id":row[0],"component":row[1],"operation":row[2],"started_at":row[3],"finished_at":row[4],"status":row[5],"code_identity":row[6],"parameters":json.loads(row[7]),"environment":json.loads(row[8]),"metrics":metrics,"tags":tags,"metadata":json.loads(row[11])})
        return tuple(out)
    def artifacts(self, *, kind=None):
        if kind is None: rows=self._db.execute("SELECT * FROM artifacts ORDER BY artifact_id").fetchall()
        else: rows=self._db.execute("SELECT * FROM artifacts WHERE kind=? ORDER BY artifact_id",(str(kind),)).fetchall()
        return tuple({"artifact_id":r[0],"digest":r[1],"kind":r[2],"media_type":r[3],"name":r[4],"size_bytes":r[5],"uri":r[6],"metadata":json.loads(r[7])} for r in rows)
    def upstream(self, artifact_id):
        seen={artifact_id}; changed=True
        while changed:
            changed=False
            for source,target in self._db.execute("SELECT source_id,target_id FROM lineage"):
                if target in seen and source not in seen: seen.add(source); changed=True
        return seen
    def downstream(self, artifact_id):
        seen={artifact_id}; changed=True
        while changed:
            changed=False
            for source,target in self._db.execute("SELECT source_id,target_id FROM lineage"):
                if source in seen and target not in seen: seen.add(target); changed=True
        return seen
