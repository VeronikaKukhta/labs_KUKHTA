import socket
import threading
import os
from datetime import datetime

class ProxyServer:
    def __init__(self, host='127.0.0.1', port=8888, blacklist_file='blacklist.txt'):
        self.host = host
        self.port = port
        self.blacklist = self.load_blacklist(blacklist_file)
        self.lock = threading.Lock()
        
    def load_blacklist(self, filename):
        blacklist = []
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                blacklist = [line.strip() for line in f if line.strip()]
        return blacklist
    
    def is_blocked(self, url):
        for blocked in self.blacklist:
            if blocked in url:
                return True
        return False
    
    def get_blocked_page(self, url):
        return f"""HTTP/1.1 403 Forbidden\r
Content-Type: text/html; charset=utf-8\r
Connection: close\r
\r
<!DOCTYPE html>
<html>
<head><title>Доступ заблокирован</title></head>
<body>
    <h1>403 Forbidden</h1>
    <p>Доступ к ресурсу <strong>{url}</strong> заблокирован.</p>
    <p>Причина: ресурс находится в черном списке.</p>
</body>
</html>"""
    
    def parse_request(self, data):
        lines = data.split('\r\n')
        if not lines:
            return None
        
        first_line = lines[0].split()
        if len(first_line) < 3:
            return None
        
        method, full_url, version = first_line
        
        if not full_url.startswith('http://'):
            return None
        
        url_parts = full_url[7:].split('/', 1)
        host_port = url_parts[0]
        path = '/' + url_parts[1] if len(url_parts) > 1 else '/'
        
        if ':' in host_port:
            host, port = host_port.split(':')
            port = int(port)
        else:
            host = host_port
            port = 80
        
        return {
            'method': method,
            'full_url': full_url,
            'host': host,
            'port': port,
            'path': path,
            'version': version,
            'headers': lines[1:-2] if len(lines) > 2 else []
        }
    
    def forward_request(self, client_socket, request_data):
        server_socket = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.settimeout(10)
            server_socket.connect((request_data['host'], request_data['port']))
            
            modified_request = f"{request_data['method']} {request_data['path']} {request_data['version']}\r\n"
            
            for header in request_data['headers']:
                if header and not header.lower().startswith('proxy-'):
                    modified_request += header + '\r\n'
            
            modified_request += '\r\n'
            
            server_socket.send(modified_request.encode())
            
            first_chunk = True
            while True:
                response = server_socket.recv(8192)
                if not response:
                    break
                
                
                if first_chunk:
                    try:
                        response_text = response.decode('utf-8', errors='ignore')
                        status_line = response_text.split('\r\n')[0]
                        
                        parts = status_line.split(' ', 2)
                        if len(parts) >= 2:
                            status_code = parts[1] + (' ' + parts[2] if len(parts) > 2 else '')
                            self.log_request(request_data['full_url'], status_code)
                    except:
                        self.log_request(request_data['full_url'], "Unknown")
                    first_chunk = False
                
                client_socket.send(response)
                
        except socket.timeout:
            print(f"")
        except ConnectionRefusedError:
            print(f"Connection refused by {request_data['host']}:{request_data['port']}")
        except Exception as e:
            print(f"Error forwarding request to {request_data['host']}: {e}")
        finally:
            if server_socket:
                server_socket.close()
    
    def log_request(self, url, status_code):
        with self.lock:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {url} - {status_code}")
    
    def handle_client(self, client_socket, address):
        try:
            client_socket.settimeout(10)
            request_data = client_socket.recv(8192).decode('utf-8', errors='ignore')
            
            if not request_data:
                return
            
            parsed = self.parse_request(request_data)
            if not parsed:
                return
            
            if self.is_blocked(parsed['full_url']):
                blocked_page = self.get_blocked_page(parsed['full_url'])
                client_socket.send(blocked_page.encode())
                self.log_request(parsed['full_url'], "403 Forbidden")
                return
            
            
            self.forward_request(client_socket, parsed)
            
        except socket.timeout:
            print(f"Timeout from {address}")
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
    
    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"Proxy server started on {self.host}:{self.port}")
            print(f"Blacklist contains {len(self.blacklist)} entries")
            print("Press Ctrl+C to stop")
            
            while True:
                client_socket, address = server_socket.accept()
                thread = threading.Thread(target=self.handle_client, args=(client_socket, address))
                thread.daemon = True
                thread.start()
                
        except KeyboardInterrupt:
            print("\nShutting down proxy server...")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            server_socket.close()

if __name__ == "__main__":
    proxy = ProxyServer(host='127.0.0.1', port=8888, blacklist_file='blacklist.txt')
    proxy.start()