"""Regression coverage for channel metadata shown in the guide."""

import json
import os
import tempfile
import unittest
from dataclasses import asdict
from unittest.mock import patch

import app
import database as db
from channels import ChannelConfig


class GuideChannelTests(unittest.TestCase):
    def test_guide_uses_saved_names_and_respects_channel_visibility(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(db, "DB_PATH", os.path.join(tmpdir, "guide.db")):
                db.init_db()
                db.save_custom_channel(
                    999, json.dumps(asdict(ChannelConfig(999, "Custom Channel")))
                )
                db.save_custom_channel(
                    998, json.dumps(asdict(ChannelConfig(998, "Hidden Custom")))
                )
                db.set_channel_visibility(1002, False)
                with db.get_db() as conn:
                    conn.execute(
                        "INSERT INTO programs (channel_id, title, start_time, end_time) "
                        "VALUES (?, ?, ?, ?)",
                        ("1001", "Test Show", 1000, 2000),
                    )

                client = app.app.test_client()
                with patch.object(app, "get_matching_content", return_value=[]):
                    response = client.put(
                        "/api/channels/1001",
                        json={"name": "Renamed Channel", "type": "series"},
                    )
                self.assertEqual(response.status_code, 200)

                guide = client.get("/api/guide?start=1&hours=1")
                self.assertEqual(guide.status_code, 200)
                channels = guide.get_json()["channels"]
                by_number = {channel["number"]: channel for channel in channels}
                self.assertEqual(by_number[1001]["name"], "Renamed Channel")
                self.assertEqual(by_number[1001]["type"], "series")
                self.assertEqual(by_number[1001]["programs"][0]["title"], "Test Show")
                self.assertEqual(by_number[999]["name"], "Custom Channel")
                self.assertNotIn(1002, by_number)
                self.assertEqual(list(by_number), sorted(by_number))

                hidden = client.post("/api/channels/998/hide")
                self.assertEqual(hidden.status_code, 200)
                self.assertTrue(hidden.get_json()["ok"])
                self.assertNotIn(998, {c.number for c in app._all_channel_configs()})
                channels = client.get("/api/channels").get_json()["channels"]
                self.assertTrue(next(c for c in channels if c["number"] == 998)["is_hidden"])
                guide = client.get("/api/guide?start=1&hours=1").get_json()
                self.assertNotIn(998, {c["number"] for c in guide["channels"]})

                shown = client.post("/api/channels/998/show")
                self.assertEqual(shown.status_code, 200)
                guide = client.get("/api/guide?start=1&hours=1").get_json()
                self.assertIn(998, {c["number"] for c in guide["channels"]})

                client.post("/api/channels/998/hide")
                self.assertEqual(client.delete("/api/channels/998").status_code, 200)
                with patch.object(app, "get_matching_content", return_value=[]):
                    recreated = client.post(
                        "/api/channels/custom",
                        json={"number": 998, "name": "Recreated Custom"},
                    )
                self.assertEqual(recreated.status_code, 200)
                guide = client.get("/api/guide?start=1&hours=1").get_json()
                self.assertIn(998, {c["number"] for c in guide["channels"]})


if __name__ == "__main__":
    unittest.main()
