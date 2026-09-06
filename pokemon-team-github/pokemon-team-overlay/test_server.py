"""Run with python -m unittest -v. Tests use a temporary team file."""
import concurrent.futures
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
import pokemon_team as server

class ServerTest(unittest.TestCase):
    def test_shiny_validation_and_legacy_saves(self):
        old = {'dex': 1, 'form': '', 'name': 'Bulbasaur'}
        self.assertFalse(server.validate_slot(old)['shiny'])
        self.assertTrue(server.validate_slot(dict(old, shiny=True))['shiny'])
        with self.assertRaises(ValueError):
            server.validate_slot(dict(old, shiny='true'))

    def test_independent_clients_persistence_and_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            server.STATE_FILE = Path(temp) / 'team.json'
            server.STATE = {'slots': [None] * 6, 'layout': 'vertical'}
            httpd = server.LocalServer(('127.0.0.1', 0), server.Handler)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            port = httpd.server_port

            def request(method, path, value=None, extra=None):
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                headers = {'Content-Type': 'application/json'}
                headers.update(extra or {})
                connection.request(method, path, json.dumps(value) if value is not None else None, headers)
                response = connection.getresponse()
                status, raw = response.status, response.read()
                connection.close()
                return status, raw

            streams = []
            try:
                for route in ['/', '/settings.html', '/overlay.html', '/app.js', '/styles.css']:
                    self.assertEqual(request('GET', route)[0], 200)
                self.assertEqual(request('GET', '/server.py')[0], 404)
                self.assertEqual(request('GET', '/api/state', extra={'Host': 'foreign.example'})[0], 403)
                # Two entirely independent consumers represent browser and OBS.
                for _ in range(2):
                    c = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                    c.request('GET', '/api/events')
                    r = c.getresponse()
                    self.assertEqual(r.status, 200)
                    self.assertEqual(json.loads(r.readline().decode()[6:])['slots'], [None] * 6)
                    self.assertEqual(r.readline(), b'\n')
                    streams.append((c, r))
                meowth = {'dex': 52, 'form': '0001', 'name': 'Shiny Meowth · Alola', 'shiny': True}
                status, _ = request('POST', '/api/state', {'slot': 0, 'value': meowth})
                self.assertEqual(status, 200)
                for _, r in streams:
                    self.assertEqual(json.loads(r.readline().decode()[6:])['slots'][0], meowth)
                    r.readline()
                # Concurrent updates patch slots, so unrelated changes survive.
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    results = list(pool.map(lambda i: request('POST', '/api/state', {'slot': i, 'value': {'dex': i+1, 'form': '', 'name': 'Test'}}), range(1,6)))
                self.assertTrue(all(status == 200 for status, _ in results))
                current = json.loads(request('GET', '/api/state')[1])
                self.assertTrue(all(current['slots']))
                self.assertEqual(request('POST', '/api/state', {'layout': 'grid'})[0], 200)
                before = json.loads(request('GET', '/api/state')[1])
                for bad in [{'slot': 6, 'value': None}, {'slot': 0, 'value': {'dex': -1, 'form': '', 'name': ''}}, {'layout': 'invalid'}, {'layout': []}]:
                    self.assertEqual(request('POST', '/api/state', bad)[0], 400)
                self.assertEqual(request('POST', '/api/state', {'slot': 0, 'value': None}, {'Origin': 'https://foreign.example'})[0], 403)
                self.assertEqual(json.loads(request('GET', '/api/state')[1]), before)
                server.STATE = {'slots': [None] * 6, 'layout': 'vertical'}
                server.load_state()
                self.assertEqual(server.STATE, before)
                self.assertEqual(request('POST', '/api/state', {'slot': 0, 'value': None})[0], 200)
                self.assertIsNone(json.loads(request('GET', '/api/state')[1])['slots'][0])
            finally:
                for c, r in streams:
                    r.close(); c.close()
                httpd.shutdown(); httpd.server_close()

if __name__ == '__main__':
    unittest.main()
