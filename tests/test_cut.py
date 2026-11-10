"""Tests für Creative Cut: Zeitleiste, Projektformat und FFmpeg-Export.

python3 -m unittest tests/test_cut.py
Der Render-Test läuft nur, wenn ffmpeg/ffprobe installiert sind.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cut"))

from cut_project import (  # noqa: E402
    Clip, Media, Music, Title, _atempo, finish_args, layout, needs_finish, probe, project_data,
    read_project, segment_args, transition_lengths,
)

A = Media("/tmp/a.mp4", 6000, True)
B = Media("/tmp/b.mp4", 5000, False)
M = Media("/tmp/m.m4a", 20000, True, False)


class Timeline(unittest.TestCase):
    def test_magnetic_layout_with_transitions(self):
        clips = [Clip(A, 0, 4000), Clip(B, 0, 2000, transition="fade", transition_ms=500),
                 Clip(A, 0, 3000, speed=200)]
        starts, total = layout(clips)
        self.assertEqual(starts, [0, 3500, 5500])
        self.assertEqual(total, 7000)

    def test_transition_is_at_most_half_a_clip(self):
        clips = [Clip(A, 0, 1000), Clip(A, 0, 4000, transition="fade", transition_ms=3000)]
        self.assertEqual(transition_lengths(clips), [0, 500])

    def test_speed_changes_length(self):
        self.assertEqual(Clip(A, 0, 4000, speed=50).length, 8000)
        self.assertEqual(Clip(A, 0, 4000, speed=400).length, 1000)

    def test_atempo_chain_stays_in_range(self):
        for factor in (4.0, 0.25, 3.0, 0.3):
            parts = [float(p.split("=")[1]) for p in _atempo(factor)]
            self.assertTrue(all(0.5 <= p <= 2.0 for p in parts))
            product = 1.0
            for p in parts:
                product *= p
            self.assertAlmostEqual(product, factor, places=3)
        self.assertEqual(_atempo(1.0), [])

    def test_finish_only_when_needed(self):
        self.assertFalse(needs_finish([Clip(A, 0, 1000), Clip(B, 0, 1000)], [], []))
        self.assertTrue(needs_finish([Clip(A, 0, 1000), Clip(B, 0, 1000, transition="fade")], [], []))
        self.assertTrue(needs_finish([Clip(A, 0, 1000)], [Title("x", 0)], []))


class ProjectFile(unittest.TestCase):
    def roundtrip(self, data):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "p.creativecut"
            p.write_text(json.dumps(data), encoding="utf-8")
            return read_project(p)

    def test_v2_roundtrip(self):
        clips = [Clip(A, 100, 4000, look="kino", kenburns="in", speed=150, reverse=True,
                      transition="wipeleft", transition_ms=700)]
        titles = [Title("Hallo", 500, 2000, "bauchbinde")]
        music = [Music(M, at=1000, start=0, end=9000, volume=60)]
        self.assertEqual(self.roundtrip(project_data([A, M], clips, titles, music)),
                         ([A, M], clips, titles, music))

    def test_reads_version_1(self):
        data = {"version": 1, "media": [{"path": A.path, "duration": A.duration, "audio": True}],
                "timeline": [{"path": A.path, "start": 0, "end": 2000, "volume": 80, "title": "Alt"}]}
        media, clips, titles, music = self.roundtrip(data)
        self.assertEqual(clips, [Clip(A, 0, 2000, volume=80, title="Alt")])
        self.assertEqual((titles, music), ([], []))

    def test_rejects_unknown_effect(self):
        data = project_data([A], [Clip(A, 0, 1000)], [], [])
        data["timeline"][0]["look"] = "rm -rf"
        with self.assertRaises(ValueError):
            self.roundtrip(data)


class Filters(unittest.TestCase):
    def test_segment_uses_effective_length_and_effects(self):
        args = segment_args(Clip(A, 0, 4000, speed=50, reverse=True, look="sw", kenburns="out"),
                            "out.mp4", 1280, 720, 30)
        vf = args[args.index("-vf") + 1]
        self.assertEqual(args[args.index("-t", args.index("-map")) + 1], "8.000")
        for part in ("reverse", "setpts=PTS*2.00000", "hue=s=0", "eval=frame", "crop=1280:720"):
            self.assertIn(part, vf)
        self.assertIn("areverse", args[args.index("-af") + 1])

    def test_finish_graph(self):
        clips = [Clip(A, 0, 3000), Clip(B, 0, 3000, transition="fadeblack"), Clip(A, 0, 1000)]
        args = finish_args(["s0", "s1", "s2"], clips, [Title("T", 0)], [Music(M, at=500, end=5000)],
                           1280, 720, 30, ["t0.txt"], "out.mp4")
        graph = args[args.index("-filter_complex") + 1]
        self.assertIn("xfade=transition=fadeblack:duration=1.000:offset=2.000", graph)
        self.assertIn("concat=n=2:v=1:a=0", graph)
        self.assertIn("textfile=t0.txt", graph)
        self.assertIn("adelay=500:all=1", graph)
        self.assertEqual(args[args.index("-t", args.index("-filter_complex")) + 1], "6.000")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg fehlt")
class Render(unittest.TestCase):
    def test_full_export(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)

            def run(*args):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], cwd=d, check=True)
            run("-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=3", "-f", "lavfi", "-i", "sine=d=3",
                "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "a.mp4")
            run("-f", "lavfi", "-i", "sine=f=300:d=6", "m.m4a")
            a, m = probe(d / "a.mp4"), probe(d / "m.m4a")
            self.assertFalse(m.video)
            clips = [Clip(a, 0, 3000, look="kino", kenburns="in"),
                     Clip(a, 0, 2000, speed=200, reverse=True, transition="fade", transition_ms=400)]
            segs = []
            for i, clip in enumerate(clips):
                segs.append(d / f"s{i}.mp4")
                run(*segment_args(clip, segs[-1], 320, 240, 25))
            (d / "t.txt").write_text("Titel")
            run(*finish_args(segs, clips, [Title("Titel", 200, 1000)], [Music(m, end=4000)],
                             320, 240, 25, ["t.txt"], d / "out.mp4"))
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", str(d / "out.mp4")], capture_output=True, text=True)
            self.assertAlmostEqual(float(out.stdout), layout(clips)[1] / 1000, delta=0.1)


if __name__ == "__main__":
    unittest.main()
