#!/usr/bin/env python3
import argparse
import socket
import threading


def handle_client(conn, addr):
    print(f"[server] client connecté: {addr}", flush=True)
    try:
        while True:
            data = conn.recv(65536)
            if not data:
                break
    except Exception as exc:
        print(f"[server] erreur client {addr}: {exc}", flush=True)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Serveur TCP simple pour générer du trafic continu")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7001)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(20)
    print(f"[server] écoute sur {args.host}:{args.port}", flush=True)

    try:
        while True:
            conn, addr = sock.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("[server] arrêt demandé", flush=True)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
