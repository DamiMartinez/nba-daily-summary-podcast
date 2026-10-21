"""Validate published artwork without third-party imaging dependencies."""

from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
COVER = ROOT / "podcast/NBA_daily_summary_cover_v2.png"
URL = "https://damimartinez.github.io/nba-daily-summary-podcast/podcast/NBA_daily_summary_cover_v2.png"


class ArtworkTests(unittest.TestCase):
    def test_cover_is_square_rgb_png_at_podcast_resolution(self):
        header = COVER.read_bytes()[:33]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(header[12:16], b"IHDR")
        width, height, depth, color_type = struct.unpack(">IIBB", header[16:26])
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 1400)
        self.assertLessEqual(width, 3000)
        self.assertEqual(depth, 8)
        self.assertEqual(color_type, 2)  # RGB, no transparency

    def test_feed_and_publisher_use_same_versioned_artwork_url(self):
        channel = ET.parse(ROOT / "podcast/rss.xml").getroot().find("channel")
        image = channel.find("{http://www.itunes.com/dtds/podcast-1.0.dtd}image")
        self.assertEqual(image.get("href"), URL)
        workflow = (ROOT / ".github/workflows/publish_podcast.yml").read_text()
        self.assertIn(f'podcast_image = "{URL}"', workflow)


if __name__ == "__main__":
    unittest.main()
