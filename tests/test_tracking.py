from cardi_trace import TraceRecorder, TraceQuery

def test_metrics_tags_and_best_run(tmp_path):
    recorder=TraceRecorder(tmp_path)
    first=recorder.start_run("model","fit",tags={"split":"validation"})
    recorder.log_metrics(first.run_id,{"accuracy":0.81,"loss":0.4})
    recorder.finish_run(first.run_id)
    second=recorder.start_run("model","fit",tags={"split":"validation"})
    recorder.log_metric(second.run_id,"accuracy",0.93)
    recorder.set_tag(second.run_id,"model","baseline-v2")
    recorder.finish_run(second.run_id)
    query=TraceQuery(recorder)
    assert len(query.runs(tag="split",tag_value="validation")) == 2
    assert query.best_run("accuracy").run_id == second.run_id
    assert query.latest_run(component="model",operation="fit").run_id == second.run_id
    assert query.metric_history("accuracy")[-1][2] == 0.93
