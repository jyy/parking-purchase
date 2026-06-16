import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from purchase import when_to_date
from parkonect_purchase import run_purchase

class PurchaseHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Allow a health check on /favicon.ico to just return 404 and not trigger a purchase
        if self.path == '/favicon.ico':
            self.send_response(404)
            self.end_headers()
            return
            
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        # Require action=buy to actually trigger the purchase
        action = query_params.get("action", [""])[0]
        if action != "buy":
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            current_time = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z").strip()
            self.wfile.write(f"OK - Current local time: {current_time}".encode('utf-8'))
            return
        
        # Determine the target date (default to today)
        when_param = query_params.get("when", ["today"])[0]
        
        target_date = when_to_date(when_param)
        if target_date is None:
            self.send_response(400)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Invalid 'when' parameter: {when_param}".encode('utf-8'))
            return
            
        print(f"Executing purchase for: {target_date} ({when_param})")
        
        try:
            result = run_purchase(target_date)
            
            if result.success:
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                
                date_str = target_date.strftime("%b %d, %Y")
                code_str = result.code if result.code else "NO_CODE"
                response_text = f"{code_str},{date_str}"
                
                print(f"Purchase Success: {response_text}", flush=True)
                self.wfile.write(response_text.encode('utf-8'))
            else:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Purchase Failed: {result.message}".encode('utf-8'))
                
        except BrokenPipeError:
            print("Client disconnected before we could send the response.")
        except Exception as e:
            try:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Unexpected Error: {str(e)}".encode('utf-8'))
            except BrokenPipeError:
                pass

port = int(os.environ.get('PORT', 8080))
httpd = HTTPServer(('0.0.0.0', port), PurchaseHTTPRequestHandler)
print(f"Listening on port {port}...")
httpd.serve_forever()
