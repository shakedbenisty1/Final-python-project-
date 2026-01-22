import socket
import threading

SERVER_IP = "192.168.1.73"
PORT = 50000


def recv_loop(sock):
    try:
        buffer = ""
        while True:
            data = sock.recv(4096)
            if not data:
                print("[Disconnected]")
                break

            buffer += data.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if line.strip():
                    print(line.strip())
    except:
        print("[Disconnected]")


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect((SERVER_IP, PORT))
        print("Connected to server")
    except Exception as e:
        print("Connection failed:", e)
        return

    threading.Thread(target=recv_loop, args=(sock,), daemon=True).start()

    username = input("Enter username: ").strip()
    if not username:
        print("No username")
        return

    sock.sendall(f"LOGIN {username}\n".encode("utf-8"))

    while True:
        try:
            msg = input()
            if not msg:
                continue

            if msg == "/quit":
                break

            if msg.startswith("/"):
                sock.sendall(msg[1:].upper().encode("utf-8") + b"\n")
            else:
                sock.sendall(f"ALL {msg}\n".encode("utf-8"))

        except KeyboardInterrupt:
            break

    sock.close()


if __name__ == "__main__":
    main()