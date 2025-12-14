import os
import threading
from pathlib import Path
from flask import Flask, send_from_directory, abort, Response, request
from typing import Optional


class FileServer:
    def __init__(self, upload_dir: str = "./uploads", port: int = 3000, domain: str = "http://localhost:3000"):
        self.upload_dir = Path(upload_dir).resolve()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.port = port
        self.domain = domain.rstrip('/')

        self.app = Flask(__name__)
        self.app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

        self._register_routes()

        self._server_thread: Optional[threading.Thread] = None

    def _register_routes(self):
        @self.app.route('/files/<path:file_id>')
        def serve_file(file_id: str):
            file_id_clean = file_id.split('.')[0]
            for file in self.upload_dir.iterdir():
                if file.name.startswith(file_id_clean) and not file.name.startswith('.'):
                    ext = file.suffix.lower()
                    if ext == '.mp4':
                        mimetype = 'video/mp4'
                    elif ext == '.mp3':
                        mimetype = 'audio/mpeg'
                    elif ext == '.webm':
                        mimetype = 'video/webm'
                    else:
                        mimetype = 'application/octet-stream'

                    file_path = self.upload_dir / file.name
                    file_size = file_path.stat().st_size
                    
                    range_header = request.headers.get('Range')
                    if range_header:
                        byte_range = range_header.replace('bytes=', '').split('-')
                        start = int(byte_range[0]) if byte_range[0] else 0
                        end = int(byte_range[1]) if byte_range[1] else file_size - 1
                        
                        if start >= file_size:
                            return Response("Requested range not satisfiable", status=416)
                        
                        end = min(end, file_size - 1)
                        length = end - start + 1
                        
                        with open(file_path, 'rb') as f:
                            f.seek(start)
                            data = f.read(length)
                        
                        response = Response(
                            data,
                            status=206,
                            mimetype=mimetype
                        )
                        response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                        response.headers['Content-Length'] = length
                        response.headers['Accept-Ranges'] = 'bytes'
                        response.headers['X-Content-Type-Options'] = 'nosniff'
                        response.headers['Content-Disposition'] = f'inline; filename="{file.name}"'
                        return response
                    
                    response = send_from_directory(
                        self.upload_dir,
                        file.name,
                        mimetype=mimetype,
                        as_attachment=False
                    )
                    response.headers['Accept-Ranges'] = 'bytes'
                    response.headers['X-Content-Type-Options'] = 'nosniff'
                    response.headers['Content-Disposition'] = f'inline; filename="{file.name}"'
                    return response

            abort(404)

        @self.app.route('/download/<path:file_id>')
        def download_file(file_id: str):
            file_id_clean = file_id.split('.')[0]
            for file in self.upload_dir.iterdir():
                if file.name.startswith(file_id_clean) and not file.name.startswith('.'):
                    return send_from_directory(
                        self.upload_dir,
                        file.name,
                        as_attachment=True
                    )

            abort(404)

        @self.app.route('/health')
        def health_check():
            return {"status": "ok", "upload_dir": str(self.upload_dir)}

        @self.app.errorhandler(404)
        def not_found(e):
            return {"error": "File not found or expired"}, 404

    def get_file_url(self, file_uuid: str, download: bool = False, extension: str = ".mp4") -> str:
        endpoint = "download" if download else "files"
        return f"{self.domain}/{endpoint}/{file_uuid}{extension}"

    def start(self, threaded: bool = True):
        if threaded:
            self._server_thread = threading.Thread(
                target=self._run_server,
                daemon=True
            )
            self._server_thread.start()
            print(f" File server started at {self.domain}")
        else:
            self._run_server()

    def _run_server(self):
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.WARNING)

        self.app.run(
            host='0.0.0.0',
            port=self.port,
            debug=False,
            use_reloader=False
        )