#!/usr/bin/env python3
"""Read a downloaded Worker multipart body without decoding binary parts as text.

Usage: python read-worker-modules.py worker-download.multipart > modules.json
The output contains base64 payloads for binary-safe multipart re-upload.
"""
import base64
from email import policy
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import struct
import sys


def read_modules(raw):
    first = raw.split(b'\r\n', 1)[0]
    if not first.startswith(b'--'):
        raise ValueError('Expected a Worker multipart response')
    header = b'Content-Type: multipart/form-data; boundary="' + first[2:] + b'"\r\nMIME-Version: 1.0\r\n\r\n'
    message = BytesParser(policy=policy.default).parsebytes(header + raw)
    if not message.is_multipart():
        raise ValueError('Could not parse Worker modules')
    modules = []
    for part in message.iter_parts():
        name = part.get_param('name', header='content-disposition')
        if not name:
            raise ValueError('Worker module has no name')
        data = part.get_payload(decode=True)
        if data is None:
            raise ValueError('Could not read module bytes: ' + name)
        if name.endswith('.webp'):
            if len(data) < 12 or data[:4] != b'RIFF' or data[8:12] != b'WEBP' or struct.unpack('<I', data[4:8])[0] + 8 != len(data):
                raise ValueError('Corrupt WebP module: ' + name)
        mime = 'application/javascript+module' if name == 'worker.js' else 'application/octet-stream' if name.endswith('.webp') else 'text/plain'
        modules.append({'name': name, 'content_type': mime, 'encoding': 'base64', 'content': base64.b64encode(data).decode('ascii'), 'byte_length': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    return modules


if __name__ == '__main__':
    json.dump(read_modules(Path(sys.argv[1]).read_bytes()), sys.stdout)
    sys.stdout.write('\n')
