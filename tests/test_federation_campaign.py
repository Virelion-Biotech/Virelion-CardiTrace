from cardi_trace import TraceRecorder, compare_runs, create_envelope, summarize_campaign, verify_envelope

def test_authenticated_federation_and_campaign(tmp_path):
    recorder=TraceRecorder(tmp_path)
    a=recorder.start_run("model","fit",parameters={"lr":0.1})
    recorder.log_metric(a.run_id,"accuracy",0.8)
    recorder.finish_run(a.run_id)
    b=recorder.start_run("model","fit",parameters={"lr":0.01},parent_run_id=a.run_id)
    recorder.log_metric(b.run_id,"accuracy",0.9)
    recorder.finish_run(b.run_id)
    envelope=create_envelope(recorder,source="HeartTwin",target="CardiLearn",secret=b"secret")
    assert verify_envelope(envelope,recorder,secret=b"secret",require_signature=True)==()
    assert "invalid_signature" in verify_envelope(envelope,recorder,secret=b"wrong")
    report=summarize_campaign(recorder,metric="accuracy")
    assert report["run_count"]==2
    assert report["metric"]["best"][0]==b.run_id
    diff=compare_runs(recorder,a.run_id,b.run_id)
    assert abs(diff["metric_delta"]["accuracy"]-0.1)<1e-12
