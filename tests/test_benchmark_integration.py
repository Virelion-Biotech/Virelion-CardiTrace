from cardi_trace.integration import trace_benchmark_discovery, trace_benchmark_result

class Recorder:
    def __init__(self): self.calls=[]
    def record(self,event,payload,run_id=None,component=None):
        item={"event":event,"payload":payload,"run_id":run_id,"component":component}
        self.calls.append(item)
        return item

def test_benchmark_trace_helpers_preserve_ids():
    r=Recorder()
    a=trace_benchmark_discovery(r,observation={"observation_id":"o1","source":"geo","source_record_id":"GSE1","content_sha256":"a"*64},run_id="run")
    b=trace_benchmark_result(r,result={"result_id":"r1","benchmark_id":"b","benchmark_version":"1","benchmark_provenance_sha256":"b"*64,"comparability_key":"k"},run_id="run")
    assert a["component"]=="CardiBench" and a["payload"]["observation_id"]=="o1"
    assert b["event"]=="benchmark.result" and b["payload"]["comparability_key"]=="k"
