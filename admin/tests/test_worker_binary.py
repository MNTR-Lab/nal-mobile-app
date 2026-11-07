import base64
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('worker_modules', ROOT / 'scripts/read-worker-modules.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def multipart(name, data):
    # Cloudflare downloads omit filename=; generic FormData readers treat it as text.
    return b'--worker-boundary\r\nContent-Disposition: form-data; name="' + name.encode() + b'"\r\n\r\n' + data + b'\r\n--worker-boundary--\r\n'


class WorkerBinaryTests(unittest.TestCase):
    def test_binary_guides_preserve_exact_bytes_without_filename_header(self):
        for name in ['weekly.webp', 'six-week.webp']:
            data = (ROOT / 'guides' / name).read_bytes()
            part = reader.read_modules(multipart('guides/' + name, data))[0]
            self.assertEqual(base64.b64decode(part['content']), data)
            self.assertEqual(part['content_type'], 'application/octet-stream')
            self.assertEqual(part['byte_length'], len(data))

    def test_text_decoding_damage_is_rejected_before_upload(self):
        data = (ROOT / 'guides/weekly.webp').read_bytes().decode('utf-8', errors='replace').encode('utf-8')
        with self.assertRaisesRegex(ValueError, 'Corrupt WebP'):
            reader.read_modules(multipart('guides/weekly.webp', data))

    def test_worker_entrypoint_retains_es_module_type(self):
        part = reader.read_modules(multipart('worker.js', b'export default {};'))[0]
        self.assertEqual(part['content_type'], 'application/javascript+module')


if __name__ == '__main__':
    unittest.main()
