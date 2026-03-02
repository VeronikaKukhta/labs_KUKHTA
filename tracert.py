import socket
import struct
import time
import sys
import select

ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0
ICMP_TIME_EXCEEDED = 11

def calculate_checksum(data):
    if len(data) % 2 != 0:
        data += b'\x00'
    
    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i+1]
        checksum += word
    
    checksum = (checksum >> 16) + (checksum & 0xFFFF)
    checksum = ~checksum & 0xFFFF
    return checksum

def create_icmp_packet(identifier, sequence):
    header = struct.pack('!BBHHH', ICMP_ECHO_REQUEST, 0, 0, identifier, sequence)
    data = struct.pack('!d', time.time())
    checksum = calculate_checksum(header + data)
    header = struct.pack('!BBHHH', ICMP_ECHO_REQUEST, 0, checksum, identifier, sequence)
    return header + data

def parse_icmp_response(data):
    ip_header = data[:20]
    iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
    source_ip = socket.inet_ntoa(iph[8])
    icmp_data = data[20:]
    
    if len(icmp_data) >= 8:
        icmp_type, icmp_code, checksum, packet_id, sequence = struct.unpack('!BBHHH', icmp_data[:8])
        
        if icmp_type == ICMP_TIME_EXCEEDED:
            if len(icmp_data) >= 28:
                nested_icmp = icmp_data[28:36]
                if len(nested_icmp) >= 8:
                    _, _, _, packet_id, sequence = struct.unpack('!BBHHH', nested_icmp)
        
        return icmp_type, source_ip, packet_id, sequence
    
    return None, None, None, None

def tracert(dest_addr, max_hops=30, timeout=2, resolve_names=False):
    try:
        dest_ip = socket.gethostbyname(dest_addr)
        print(f"Трассировка маршрута к {dest_addr} [{dest_ip}]")
        print(f"с максимальным числом прыжков {max_hops}:\n")
    except socket.gaierror:
        print("Ошибка: не удалось разрешить имя хоста")
        return

    dest_addr = dest_ip
    identifier = 0x0001
    base_sequence = 1
    
    for ttl in range(1, max_hops + 1):
        print(f"{ttl:2}", end="  ")
        current_ip = None
        times = []
        
        for seq in range(3):
            sequence = base_sequence + seq
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
                sock.settimeout(timeout)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
                
            except PermissionError:
                print("Ошибка: требуются права администратора!")
                return
            except Exception as e:
                print(f"Ошибка создания сокета: {e}")
                return
            
            packet = create_icmp_packet(identifier, sequence)
            
            try:
                start_time = time.time()
                sock.sendto(packet, (dest_addr, 0))
                
                ready = select.select([sock], [], [], timeout)
                if ready[0]:
                    response, addr = sock.recvfrom(1024)
                    end_time = time.time()
                    rtt = (end_time - start_time) * 1000
                    
                    icmp_type, source_ip, packet_id, response_seq = parse_icmp_response(response)
                    
                    if packet_id == identifier:
                        current_ip = source_ip
                        times.append(f"{rtt:6.0f} ms")
                    else:
                        times.append(f"{'*':>6}")
                else:
                    times.append(f"{'*':>6}")
                    
            except socket.timeout:
                times.append(f"{'*':>6}")
            except Exception:
                times.append(f"{'*':>6}")
            finally:
                sock.close()
            
            time.sleep(0.1)
        
        base_sequence += 3
        
        for t in times:
            print(t, end="  ")
        
        if current_ip:
            if resolve_names:
                try:
                    hostname = socket.gethostbyaddr(current_ip)[0]
                    print(f"{current_ip} [{hostname}]")
                except:
                    print(f"{current_ip}")
            else:
                print(f"{current_ip}")
        else:
            print()
        
        if current_ip == dest_addr:
            print("\nТрассировка завершена.")
            break

def main():
    if len(sys.argv) < 2:
        print("  -d    Разрешать DNS имена")
        return
    
    target = sys.argv[1]
    resolve_names = False
    
    if len(sys.argv) > 2 and sys.argv[2] == '-d':
        resolve_names = True
    
    try:
        tracert(target, resolve_names=resolve_names)
    except KeyboardInterrupt:
        print("\nТрассировка прервана пользователем")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()