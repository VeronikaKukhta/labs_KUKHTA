import socket
import threading
import time
import sys
import argparse
from datetime import datetime
import select
import struct

class ChatNode:
    MSG_TYPE_HELLO = 1
    MSG_TYPE_NAME = 2
    MSG_TYPE_MESSAGE = 3
    MSG_TYPE_GET_HISTORY = 4
    MSG_TYPE_HISTORY = 5
    MSG_TYPE_DISCONNECT = 6
    
    def __init__(self, ip, name, udp_port, tcp_port=None):
        self.ip = ip
        self.name = name
        self.udp_port = udp_port
        
        self.nodes = {}
        self.running = True
        self.history = []
        self.received_messages = set()
        self.message_counter = 0
        
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        if tcp_port:
            try:
                self.tcp_socket.bind((self.ip, tcp_port))
                self.tcp_port = tcp_port
            except OSError:
                self.tcp_port = self.find_available_tcp_port()
        else:
            self.tcp_port = self.find_available_tcp_port()
        
        self.tcp_socket.listen(5)
        
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        try:
            self.udp_socket.bind((self.ip, self.udp_port))
        except:
            self.udp_socket.bind((self.ip, 0))
            self.udp_port = self.udp_socket.getsockname()[1]
        
        self.sockets = [self.tcp_socket, self.udp_socket]
        
        print(f"Node started: {self.name} ({self.ip}:{self.tcp_port})")
        self.add_to_history("SYSTEM", f"Node started")
        
        self.broadcast_presence()
    
    def find_available_tcp_port(self):
        for port in range(8889, 9000):
            try:
                self.tcp_socket.bind((self.ip, port))
                return port
            except:
                continue
        self.tcp_socket.bind((self.ip, 0))
        return self.tcp_socket.getsockname()[1]
    
    def _pack_message(self, msg_type, data=b''):
        length = len(data)
        header = struct.pack('!BB', msg_type, length)
        return header + data
    
    def _unpack_message(self, data):
        if len(data) < 2:
            return None, None, None
        msg_type, length = struct.unpack('!BB', data[:2])
        if len(data) < 2 + length:
            return None, None, None
        content = data[2:2+length]
        return msg_type, length, content
    
    def _encode_string(self, s):
        return s.encode('utf-8')
    
    def _decode_string(self, b):
        return b.decode('utf-8')
    
    def broadcast_presence(self):
        try:
            data = self._encode_string(f"{self.name}|{self.tcp_port}")
            packet = self._pack_message(self.MSG_TYPE_HELLO, data)
            self.udp_socket.sendto(packet, ('255.255.255.255', self.udp_port))
        except:
            pass
    
    def add_to_history(self, sender, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {sender}: {message}"
        if not self.history or entry != self.history[-1]:
            self.history.append(entry)
        return entry
        
    def show_history(self):
        print("\n--- HISTORY ---")
        for entry in self.history[-20:]:
            print(entry)
        print("----------------\n")
        print("> ", end='', flush=True)
    
    def show_nodes(self):
        print(f"\n--- NODES ({len(self.nodes)}) ---")
        for node_id, node in self.nodes.items():
            display_port = node.get('real_port', node['port'])
            print(f"  {node['name']} ({node['ip']}:{display_port})")
        print("--------------\n")
        print("> ", end='', flush=True)
    
    def get_node_id(self, ip, port):
        return (ip, port)
    
    def connect_to_node(self, ip, port, remote_name):
        if ip == self.ip and port == self.tcp_port:
            return
        node_id = self.get_node_id(ip, port)
        if node_id in self.nodes:
            return
            
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))
            
            name_data = self._encode_string(f"{self.name}|{self.tcp_port}")
            sock.send(self._pack_message(self.MSG_TYPE_NAME, name_data))
            
            data = sock.recv(1024)
            msg_type, length, content = self._unpack_message(data)
            
            remote_node_port = port
            if msg_type == self.MSG_TYPE_NAME:
                content_str = self._decode_string(content)
                parts = content_str.split('|')
                remote_name = parts[0]
                if len(parts) >= 2:
                    remote_node_port = int(parts[1])
            
            node_id = self.get_node_id(ip, remote_node_port)
            
            self.nodes[node_id] = {
                'name': remote_name, 
                'socket': sock,
                'ip': ip,
                'port': port,
                'real_port': remote_node_port
            }
            self.sockets.append(sock)
            
            self.add_to_history("SYSTEM", f"New node: {remote_name} ({ip}:{remote_node_port})")
            print(f"\n[+] New node: {remote_name} ({ip}:{remote_node_port})")
            print("> ", end='', flush=True)
            
            sock.send(self._pack_message(self.MSG_TYPE_GET_HISTORY))
        except:
            pass
    
    def handle_tcp_connection(self):
        try:
            client_sock, addr = self.tcp_socket.accept()
            ip = addr[0]
            
            data = client_sock.recv(1024)
            msg_type, length, content = self._unpack_message(data)
            
            if msg_type == self.MSG_TYPE_NAME:
                content_str = self._decode_string(content)
                parts = content_str.split('|')
                name = parts[0]
                client_tcp_port = int(parts[1]) if len(parts) >= 2 else None
                
                if client_tcp_port:
                    node_id = self.get_node_id(ip, client_tcp_port)
                    if node_id in self.nodes:
                        client_sock.close()
                        return
                
                name_data = self._encode_string(f"{self.name}|{self.tcp_port}")
                client_sock.send(self._pack_message(self.MSG_TYPE_NAME, name_data))
                
                client_port = client_sock.getpeername()[1]
                node_id = self.get_node_id(ip, client_port)
                
                if node_id not in self.nodes:
                    self.nodes[node_id] = {
                        'name': name, 
                        'socket': client_sock,
                        'ip': ip,
                        'port': client_port,
                        'real_port': client_tcp_port
                    }
                    self.sockets.append(client_sock)
                    
                    display_port = client_tcp_port if client_tcp_port else client_port
                    self.add_to_history("SYSTEM", f"New node: {name} ({ip}:{display_port})")
                    print(f"\n[+] New node: {name} ({ip}:{display_port})")
                    print("> ", end='', flush=True)
                else:
                    client_sock.close()
        except:
            pass
    
    def handle_udp_message(self):
        try:
            packet, addr = self.udp_socket.recvfrom(1024)
            ip = addr[0]
            udp_port = addr[1]
            
            if ip == self.ip and udp_port == self.udp_port:
                return
            
            msg_type, length, content = self._unpack_message(packet)
            
            if msg_type == self.MSG_TYPE_HELLO:
                content_str = self._decode_string(content)
                parts = content_str.split('|')
                if len(parts) >= 2:
                    name = parts[0]
                    tcp_port = int(parts[1])
                    
                    node_id = self.get_node_id(ip, tcp_port)
                    if node_id not in self.nodes:
                        self.connect_to_node(ip, tcp_port, name)
        except:
            pass
    
    def handle_tcp_message(self, sock):
        try:
            data = sock.recv(1024)
            if not data:
                return False
            
            msg_type, length, content = self._unpack_message(data)
            
            if msg_type == self.MSG_TYPE_MESSAGE:
                content_str = self._decode_string(content)
                parts = content_str.split('|', 2)
                if len(parts) >= 3:
                    msg_id = parts[0]
                    msg_sender = parts[1]
                    msg = parts[2]
                    
                    if msg_id not in self.received_messages:
                        self.received_messages.add(msg_id)
                        self.add_to_history(msg_sender, msg)
                        print(f"\n[{msg_sender}]: {msg}")
                        print("> ", end='', flush=True)
                        
                        for node_id, node in self.nodes.items():
                            if node['socket'] != sock:
                                try:
                                    node['socket'].send(data)
                                except:
                                    pass
            
            elif msg_type == self.MSG_TYPE_GET_HISTORY:
                history_str = ';;;'.join(self.history[-30:])
                history_data = self._encode_string(history_str)
                sock.send(self._pack_message(self.MSG_TYPE_HISTORY, history_data))
                
            elif msg_type == self.MSG_TYPE_HISTORY:
                history_str = self._decode_string(content)
                if history_str:
                    entries = history_str.split(';;;')
                    for entry in entries:
                        if entry and entry not in self.history:
                            self.history.append(entry)
                    print(f"\n[+] History received")
                    print("> ", end='', flush=True)
                    
            elif msg_type == self.MSG_TYPE_DISCONNECT:
                found_node_id = None
                for node_id, node in self.nodes.items():
                    if node['socket'] == sock:
                        found_node_id = node_id
                        break
                if found_node_id:
                    self.remove_node(found_node_id)
            
            return True
        except:
            return False
    
    def send_message(self, message):
        if not message.strip():
            return
        
        self.message_counter += 1
        msg_id = f"{self.ip}_{self.tcp_port}_{self.message_counter}_{time.time()}"
        self.received_messages.add(msg_id)
        
        self.add_to_history(self.name, message)
        
        content_str = f"{msg_id}|{self.name}|{message}"
        content_data = self._encode_string(content_str)
        full_message = self._pack_message(self.MSG_TYPE_MESSAGE, content_data)
        
        disconnected = []
        for node_id, node in self.nodes.items():
            try:
                node['socket'].send(full_message)
            except:
                disconnected.append(node_id)
        
        for node_id in disconnected:
            self.remove_node(node_id)
    
    def remove_node(self, node_id):
        if node_id in self.nodes:
            node = self.nodes[node_id]
            name = node['name']
            ip = node['ip']
            display_port = node.get('real_port', node['port'])
            sock = node['socket']
            
            if sock in self.sockets:
                self.sockets.remove(sock)
            
            try:
                sock.close()
            except:
                pass
                
            del self.nodes[node_id]
            self.add_to_history("SYSTEM", f"Node disconnected: {name} ({ip}:{display_port})")
            print(f"\n[-] Node disconnected: {name} ({ip}:{display_port})")
            print("> ", end='', flush=True)
    
    def run(self):
        def input_thread():
            while self.running:
                try:
                    message = input()
                    if message.lower() == '/exit':
                        for node in self.nodes.values():
                            try:
                                node['socket'].send(self._pack_message(self.MSG_TYPE_DISCONNECT))
                            except:
                                pass
                        self.running = False
                        break
                    elif message.lower() == '/history':
                        self.show_history()
                    elif message.lower() == '/nodes':
                        self.show_nodes()
                    else:
                        self.send_message(message)
                except:
                    break
        
        threading.Thread(target=input_thread, daemon=True).start()
        
        while self.running:
            try:
                ready, _, _ = select.select(self.sockets, [], [], 0.5)
                
                for sock in ready:
                    if sock == self.tcp_socket:
                        self.handle_tcp_connection()
                    elif sock == self.udp_socket:
                        self.handle_udp_message()
                    else:
                        if not self.handle_tcp_message(sock):
                            found_node_id = None
                            for node_id, node in self.nodes.items():
                                if node['socket'] == sock:
                                    found_node_id = node_id
                                    break
                            if found_node_id:
                                self.remove_node(found_node_id)
            except:
                time.sleep(0.1)
        
        for sock in self.sockets:
            try:
                sock.close()
            except:
                pass
        print("Program terminated")

def check_port_available(ip, port, sock_type):
    try:
        if sock_type == 'udp':
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ip, port))
        s.close()
        return True
    except:
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--port', type=int, default=8888)
    parser.add_argument('--tcp-port', type=int)
    
    args = parser.parse_args()
    
    if not args.name:
        print("Error: name cannot be empty")
        sys.exit(1)
    if '|' in args.name:
        print("Error: name cannot contain '|' character")
        sys.exit(1)
    
    
    if args.tcp_port and args.port == args.tcp_port:
        print("Error: UDP and TCP ports cannot be the same")
        sys.exit(1)
    
    
    
    if args.tcp_port and not check_port_available(args.ip, args.tcp_port, 'tcp'):
        print(f"Error: TCP port {args.tcp_port} is already in use")
        sys.exit(1)
    
    node = ChatNode(args.ip, args.name, args.port, args.tcp_port)
    
    try:
        node.run()
    except KeyboardInterrupt:
        node.running = False
        print("\nProgram terminated")

if __name__ == "__main__":
    main()