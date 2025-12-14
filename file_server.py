import logging
import threading
from pathlib import Path
from typing import Optional
from flask import Flask, send_from_directory, abort, Response, request

MIME_TYPES = {
    '.mp4': 'video/mp4',
    '.mp3': 'audio/mpeg',
    '.webm': 'video/webm',
}


class FileServer:
    def __init__(self, upload_dir: str = "./uploads", port: int = 3000, domain: str = "http://localhost:3000"):
        self.upload_dir = Path(upload_dir).resolve()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.port = port
        self.domain = domain.rstrip('/')
        self.app = Flask(__name__)
        self.app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
        self._server_thread: Optional[threading.Thread] = None
        self._register_routes()

    def _find_file(self, file_id: str) -> Optional[Path]:
        file_id_clean = file_id.split('.')[0]
        for file in self.upload_dir.iterdir():
            if file.name.startswith(file_id_clean) and not file.name.startswith('.'):
                return file
        return None

    def _register_routes(self):
        @self.app.route('/files/<path:file_id>')
        def serve_file(file_id: str):
            file = self._find_file(file_id)
            if not file:
                abort(404)

            mimetype = MIME_TYPES.get(file.suffix.lower(), 'application/octet-stream')
            file_size = file.stat().st_size
            range_header = request.headers.get('Range')

            if range_header:
                return self._serve_range(file, file_size, mimetype, range_header)

            response = send_from_directory(self.upload_dir, file.name, mimetype=mimetype, as_attachment=False)
            response.headers.update({
                'Accept-Ranges': 'bytes',
                'X-Content-Type-Options': 'nosniff',
                'Content-Disposition': f'inline; filename="{file.name}"'
            })
            return response

        @self.app.route('/download/<path:file_id>')
        def download_file(file_id: str):
            file = self._find_file(file_id)
            if not file:
                abort(404)
            return send_from_directory(self.upload_dir, file.name, as_attachment=True)

        @self.app.route('/health')
        def health_check():
            return {"status": "ok", "upload_dir": str(self.upload_dir)}

        @self.app.errorhandler(404)
        def not_found(e):
            return {"error": "File not found or expired"}, 404

    def _serve_range(self, file: Path, file_size: int, mimetype: str, range_header: str) -> Response:
        byte_range = range_header.replace('bytes=', '').split('-')
        start = int(byte_range[0]) if byte_range[0] else 0
        end = int(byte_range[1]) if byte_range[1] else file_size - 1

        if start >= file_size:
            return Response("Requested range not satisfiable", status=416)

        end = min(end, file_size - 1)
        length = end - start + 1

        with open(file, 'rb') as f:
            f.seek(start)
            data = f.read(length)

        response = Response(data, status=206, mimetype=mimetype)
        response.headers.update({
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Content-Length': length,
            'Accept-Ranges': 'bytes',
            'X-Content-Type-Options': 'nosniff',
            'Content-Disposition': f'inline; filename="{file.name}"'
        })
        return response

    def get_file_url(self, file_uuid: str, download: bool = False, extension: str = ".mp4") -> str:
        endpoint = "download" if download else "files"
        return f"{self.domain}/{endpoint}/{file_uuid}{extension}"

    def start(self, threaded: bool = True):
        if threaded:
            self._server_thread = threading.Thread(target=self._run_server, daemon=True)
            self._server_thread.start()
            print(f" File server started at {self.domain}")
        else:
            self._run_server()

    def _run_server(self):
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        self.app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)