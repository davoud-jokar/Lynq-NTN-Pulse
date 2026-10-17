from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from streamlit.testing.v1 import AppTest
at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
assert not at.exception,[e.message for e in at.exception]
for label in ["Find a direct path","Find an onboard queue"]:
    button=next(b for b in at.button if b.label==label)
    assert not button.disabled
    button.click().run()
    assert not at.exception,[e.message for e in at.exception]
assert at.radio(key="traffic").value=="Routine telemetry"
states=[]
for arch in ['regenerative','functional_split','bent_pipe']:
    for local,alternative in [(False,True),(True,False),(False,False),(True,True)]:
        for traffic in ['Critical alarm','Routine telemetry']:
            at.selectbox(key='architecture').set_value(arch)
            at.toggle(key='local').set_value(local)
            at.toggle(key='alternative').set_value(alternative)
            at.radio(key='traffic').set_value(traffic)
            at.run()
            assert not at.exception,[e.message for e in at.exception]
            if not local and not alternative:
                assert at.metric[0].value=='—'
                assert at.metric[3].value=='0.0%'
            if arch!='regenerative':
                assert at.metric[2].value=='0.00 MB'
            states.append([arch,local,alternative,traffic])
for fleet in [48,96]:
    at.selectbox(key='fleet').set_value(fleet)
    at.toggle(key='alternative').set_value(True)
    for topology in ['rf_intra_plane','optical_cross_plane','hybrid']:
        at.selectbox(key='topology').set_value(topology).run()
        assert not at.exception,[e.message for e in at.exception]
for mode in ['3D globe','Global map','North Sea map']:
    at.radio(key='view').set_value(mode).run()
    assert not at.exception,[e.message for e in at.exception]
at.button(key='compare').click().run()
assert not at.exception,[e.message for e in at.exception]
assert len(at.dataframe)>=1
print(json.dumps({'passed_core_ui_states':len(states),'additional_topology_fleet_states':6,'map_projections':3,'comparison_rows':len(at.dataframe[0].value)},indent=2))
