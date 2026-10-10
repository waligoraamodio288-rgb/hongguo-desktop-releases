from pathlib import Path
import subprocess
import tempfile
import unittest

class PatchTests(unittest.TestCase):
    def test_minimal_patch_applies_to_encoder_contract(self):
        patch = Path(__file__).resolve().parents[1] / "enable-auto.patch"
        text = patch.read_text(encoding="utf-8")
        # Build only the patch's context; no private encoder source is needed.
        hunk = text.split("@@", 2)[2].splitlines()[1:]
        before = "\n".join(line[1:] for line in hunk if line.startswith((" ", "-"))) + "\n"
        after = "\n".join(line[1:] for line in hunk if line.startswith((" ", "+"))) + "\n"
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "backend/desktop_hls.py"
            file.parent.mkdir()
            for autocrlf in ("false", "true"):
                with self.subTest(autocrlf=autocrlf):
                    file.write_bytes(before.encode("utf-8"))
                    git = ["git", "-c", "core.autocrlf=" + autocrlf, "apply"]
                    subprocess.run([*git, "--check", str(patch)], cwd=root, check=True, capture_output=True)
                    subprocess.run([*git, str(patch)], cwd=root, check=True, capture_output=True)
                    self.assertEqual(file.read_text(encoding="utf-8"), after)

    def test_actual_pyav_decoder_accepts_auto(self):
        import av
        import io
        stream = io.BytesIO()
        with av.open(stream, mode="w", format="mp4") as output:
            video = output.add_stream("libx264", rate=24)
            video.width, video.height, video.pix_fmt = 64, 64, "yuv420p"
            for _ in range(12):
                frame = av.VideoFrame(64, 64, "yuv420p")
                for plane in frame.planes:
                    plane.update(bytes(plane.buffer_size))
                for packet in video.encode(frame):
                    output.mux(packet)
            for packet in video.encode():
                output.mux(packet)
        stream.seek(0)
        with av.open(stream) as reader:
            reader.streams.video[0].thread_type = "AUTO"
            self.assertEqual(reader.streams.video[0].thread_type.name, "AUTO")
            self.assertEqual(len(list(reader.decode(video=0))), 12)

if __name__ == "__main__":
    unittest.main(verbosity=2)
