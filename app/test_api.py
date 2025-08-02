# (c) 2018-2023 Tim Molteno (tim@elec.ac.nz)

import datetime
import json
import unittest

import requests


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.server = "http://object_position_server:8876"

    def request(self, dt):
        payload = {"date": dt.isoformat(), "lat": -45.87, "lon": 170.6, "elevation": 45}

        r = requests.get(f"{self.server}/catalog", params=payload, timeout=30)
        return json.loads(r.text)

    def test_basic_request(self):
        ans = self.request(datetime.datetime.now(datetime.UTC))
        print(ans)
        for sv in ans:
            assert "r" in sv
            assert "el" in sv
            assert "az" in sv
            assert "jy" in sv

    def test_future_date(self):
        t = datetime.datetime.now(datetime.UTC)
        dt = datetime.timedelta(days=2)

        # Future dates should work fine, no exception expected
        ans = self.request(t + dt)
        assert ans is not None

    def test_speed(self):
        t = datetime.datetime.now(datetime.UTC)

        dt = datetime.timedelta(minutes=1)
        for _i in range(10):
            ans = self.request(t)
            t += dt

            for sv in ans:
                assert "r" in sv
                assert "el" in sv
                assert "az" in sv


if __name__ == "__main__":
    unittest.main()
