"""Engineering regression checks; run `python -m unittest discover -s tests -v`."""
import json
import unittest
from dataclasses import replace
import numpy as np

import engine as e


def satellite(lat,lon):
    return e.ground_xyz(lat,lon)*(e.R_EARTH+550)/e.R_EARTH


class GeometryAndRouting(unittest.TestCase):
    def setUp(self):
        self.config=e.Config(duration_min=90)

    def test_overhead_range_and_elevation(self):
        ground=e.ground_xyz(56.35,3.55)
        el,r=e.look_angles(np.array([satellite(56.35,3.55)]),ground)
        self.assertAlmostEqual(el[0],90,places=5)
        self.assertAlmostEqual(r[0],550,places=7)

    def test_circular_radius_and_physical_slant_range(self):
        xyz,_=e.circular_positions(self.config,np.arange(0,5400,30))
        np.testing.assert_allclose(np.linalg.norm(xyz,axis=-1),e.R_EARTH+550,rtol=1e-12)
        el,r=e.look_angles(xyz,e.ground_xyz(56.35,3.55))
        self.assertTrue((r>=550-1e-7).all())

    def test_earth_blocks_isl(self):
        c=replace(self.config,max_isl_range_km=20000)
        self.assertFalse(e.clear_isl(satellite(0,0),satellite(0,180),c))

    def test_bent_pipe_uses_alternative_authorized_gateway(self):
        c=replace(self.config,architecture="bent_pipe",local_enabled=False,alternative_enabled=True)
        s=e.snapshot(c,np.array([satellite(56.35,3.55)]),np.array([1]))
        result=e.decide_alarm(c,s)
        self.assertTrue(result['route_available'])
        self.assertEqual(result['gateway'],'Alternative GW (LU)')
        self.assertEqual(result['route_kind'],'Direct feeder')

    def test_valid_isl_route_only_when_each_hop_exists(self):
        # Source sees the terminal but not LU; relay sees LU but not the terminal.
        xyz=np.array([satellite(68,3.55),satellite(40,6.13)])
        planes=np.array([1,2])
        c=replace(self.config,isl_topology="optical_cross_plane")
        s=e.snapshot(c,xyz,planes)
        route=e.decide_alarm(c,s)
        self.assertTrue(route['route_available'])
        self.assertEqual([x['kind'] for x in json.loads(route['route_edges'])],['Service','Optical ISL','Feeder'])
        self.assertFalse(e.decide_alarm(replace(c,architecture="bent_pipe"),s)['route_available'])
        blocked=replace(c,max_isl_range_km=1000)
        self.assertFalse(e.decide_alarm(blocked,e.snapshot(blocked,xyz,planes))['route_available'])

    def test_both_gateways_disabled_means_no_latency_or_route(self):
        c=replace(self.config,local_enabled=False,alternative_enabled=False)
        for a in e.ARCHITECTURES:
            ca=replace(c,architecture=a)
            s=e.snapshot(ca,np.array([satellite(56.35,3.55)]),np.array([1]))
            r=e.decide_alarm(ca,s)
            self.assertFalse(r['route_available'])
            self.assertIsNone(r['latency_ms'])
            self.assertEqual(json.loads(r['route_edges']),[])

    def test_visible_satellite_does_not_guarantee_deadline(self):
        c=replace(self.config,alarm_deadline_ms=10)
        r=e.decide_alarm(c,e.snapshot(c,np.array([satellite(56.35,3.55)]),np.array([1])))
        self.assertTrue(r['route_available'])
        self.assertFalse(r['alarm_deadline_met'])
        self.assertEqual(r['alarm_status'],'deadline_missed')


class QueuesAndComparisons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=e.Config(duration_min=90)
        cls.runs={a:e.simulate(replace(cls.base,architecture=a)) for a in e.ARCHITECTURES}

    def test_packet_conservation_at_every_sample(self):
        for r,p,_,_ in self.runs.values():
            accounted=r.delivered_mb+r.expired_mb+r.overflow_mb+r.ground_queue_mb+r.onboard_queue_mb
            np.testing.assert_allclose(r.generated_mb,accounted,atol=1e-8)
            self.assertTrue((r.largest_sat_buffer_mb<=self.base.onboard_buffer_mb_per_sat+1e-8).all())
            self.assertTrue((r.ground_queue_mb<=self.base.ground_buffer_mb+1e-8).all())
            d=p[p.status=='delivered']
            self.assertTrue((d.delivered_s<=d.deadline_s).all())

    def test_transparent_and_split_do_not_store_autonomously_onboard(self):
        for a in ('bent_pipe','functional_split'):
            r,p,_,_=self.runs[a]
            self.assertTrue((r.onboard_queue_mb==0).all())
            self.assertFalse(r.telemetry_state.eq('queued_onboard').any())
            self.assertTrue(p.location.eq('ground').all())

    def test_architectures_use_identical_orbits(self):
        tr=self.runs['regenerative'][2]
        for a in ('bent_pipe','functional_split'):
            self.assertTrue(tr.equals(self.runs[a][2]))

    def test_overflow_expiry_and_real_uploads(self):
        c=replace(self.base,alternative_enabled=False,telemetry_mb_per_min=.2,service_rate_mbps=.256,ground_buffer_mb=.15,onboard_buffer_mb_per_sat=.1,telemetry_deadline_min=5,forecast_storage_guard=False)
        r,p,_,_=e.simulate(c)
        self.assertTrue(p.status.str.startswith('overflow').any())
        self.assertTrue(p.status.eq('expired').any())
        self.assertTrue(p.uploaded_s.notna().any())
        self.assertTrue((r.largest_sat_buffer_mb<=.1+1e-9).all())
        uploaded=p[p.uploaded_s.notna()]
        self.assertTrue(uploaded.location.str.startswith('LYNQ-').all())
        self.assertTrue((uploaded.uploaded_s>=uploaded.born_s).all())
        np.testing.assert_allclose(r.generated_mb,r.delivered_mb+r.expired_mb+r.overflow_mb+r.ground_queue_mb+r.onboard_queue_mb,atol=1e-8)

    def test_48_satellites_do_not_force_continuous_access(self):
        c=replace(self.base,fleet_size=48)
        r,_,_,_=e.simulate(c)
        self.assertTrue((~r.terminal_visible).any())
        self.assertTrue(r.terminal_visible.any())
        self.assertTrue(r.loc[~r.route_available,'latency_ms'].isna().all())

    def test_queues_remain_on_the_upload_satellite(self):
        c=replace(self.base,alternative_enabled=False,telemetry_deadline_min=180,forecast_storage_guard=False)
        r,p,_,_=e.simulate(c)
        previous={}
        for row in r.itertuples():
            now=json.loads(row.onboard_queue_by_sat)
            for sat,mb in previous.items():
                self.assertGreaterEqual(now.get(sat,0)+1e-6,mb)
            previous=now
        self.assertFalse(p.status.eq('delivered').any())

    def test_forecast_guard_does_not_upload_without_any_future_egress(self):
        c=replace(self.base,alternative_enabled=False,forecast_storage_guard=True)
        r,p,_,_=e.simulate(c)
        self.assertFalse(p.uploaded_s.notna().any())
        self.assertTrue((r.onboard_queue_mb==0).all())


if __name__=='__main__':
    unittest.main()
