import socket
import threading

HOST = "0.0.0.0"
PORT = 50000

# Active clients: username -> socket
clients = {}
clients_lock = threading.Lock()


def safe_send(sock: socket.socket, text: str) -> bool:
    """Return True if sent, False if failed."""
    try:
        sock.sendall(text.encode("utf-8"))
        return True
    except:
        return False


def send_to_user(username: str, text: str) -> bool:
    with clients_lock:
        sock = clients.get(username)
    if not sock:
        return False
    return safe_send(sock, text)


def broadcast(text: str, exclude: str | None = None) -> None:
    """Send to everyone, optionally excluding a username."""
    with clients_lock:
        items = list(clients.items())

    dead = []
    for name, sock in items:
        if exclude is not None and name == exclude:
            continue
        if not safe_send(sock, text):
            dead.append(name)

    if dead:
        with clients_lock:
            for name in dead:
                if name in clients:
                    try:
                        clients[name].close()
                    except:
                        pass
                    del clients[name]


def build_user_list() -> str:
    with clients_lock:
        names = sorted(clients.keys(), key=lambda s: s.lower())
    return ", ".join(names) if names else "None"


def cleanup_user(username: str) -> None:
    with clients_lock:
        sock = clients.pop(username, None)
    if sock:
        try:
            sock.close()
        except:
            pass
    broadcast(f"SYS USER_LEFT {username}\n")
    broadcast(f"SYS ONLINE {build_user_list()}\n")


def handle_client(conn: socket.socket, addr):
    username = None
    try:
        conn.settimeout(60)

        safe_send(conn, "SYS WELCOME\n")
        safe_send(conn, "SYS PROTOCOL Commands: LOGIN <name> | LIST | ALL <msg> | DM <name> <msg> | QUIT\n")
        safe_send(conn, "SYS TIP In client you can type: /all hi, /dm shaked hi, /list, /quit\n")

        buffer = ""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                parts = line.split(" ", 2)
                cmd = parts[0].upper()

                if cmd == "LOGIN":
                    if username is not None:
                        safe_send(conn, "ERR Already logged in\n")
                        continue
                    if len(parts) < 2:
                        safe_send(conn, "ERR Usage: LOGIN <name>\n")
                        continue

                    requested = parts[1].strip()
                    if not requested or len(requested) > 20 or " " in requested:
                        safe_send(conn, "ERR Invalid username (1-20 chars, no spaces)\n")
                        continue

                    with clients_lock:
                        if requested in clients:
                            safe_send(conn, "ERR Username taken\n")
                            continue
                        clients[requested] = conn
                        username = requested

                    conn.settimeout(None)  # after login, no timeout
                    safe_send(conn, f"OK Logged in as {username}\n")
                    broadcast(f"SYS USER_JOINED {username}\n")
                    broadcast(f"SYS ONLINE {build_user_list()}\n")
                    continue

                # All other commands require login
                if username is None:
                    safe_send(conn, "ERR Please LOGIN first\n")
                    continue

                if cmd == "LIST":
                    safe_send(conn, f"SYS ONLINE {build_user_list()}\n")

                elif cmd == "ALL":
                    if len(parts) < 2:
                        safe_send(conn, "ERR Usage: ALL <message>\n")
                        continue
                    msg = line[len("ALL "):].strip()
                    if not msg:
                        safe_send(conn, "ERR Empty message\n")
                        continue
                    broadcast(f"MSG GROUP {username} {msg}\n")

                elif cmd == "DM":
                    # DM <name> <message>
                    if len(parts) < 3:
                        safe_send(conn, "ERR Usage: DM <name> <message>\n")
                        continue
                    target = parts[1].strip()
                    msg = parts[2].strip()
                    if not msg:
                        safe_send(conn, "ERR Empty message\n")
                        continue

                    if target == username:
                        safe_send(conn, "ERR Cannot DM yourself\n")
                        continue

                    if send_to_user(target, f"MSG DM {username} {msg}\n"):
                        safe_send(conn, f"OK Sent to {target}\n")
                    else:
                        safe_send(conn, f"ERR User not found: {target}\n")

                elif cmd == "QUIT":
                    safe_send(conn, "SYS BYE\n")
                    raise ConnectionAbortedError()

                else:
                    safe_send(conn, "ERR Unknown command. Use LIST | ALL | DM | QUIT\n")

    except Exception:
        pass
    finally:
        if username is not None:
            cleanup_user(username)
        else:
            try:
                conn.close()
            except:
                pass


def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(10)

    print("======================================")
    print(f" SERVER RUNNING ON {HOST}:{PORT}")
    print("======================================")

    while True:
        conn, addr = server_socket.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()


if __name__ == "__main__":
    main()
