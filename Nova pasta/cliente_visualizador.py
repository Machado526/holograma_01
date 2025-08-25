#!/usr/bin/env python3
import cv2
import socket
import struct
import threading
import time
from PIL import Image, ImageTk
import numpy as np
import customtkinter as ctk
import tkinter.messagebox as messagebox
from typing import Optional

# Configurações de tema
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ClienteApp:
    """Aplicação cliente para visualização do holograma transmitido pelo servidor."""

    def __init__(self, master: ctk.CTk):
        self.master = master
        self.master.title("Cliente de Holograma")
        self.master.geometry("600x300")
        self.master.resizable(False, False)

        self.sock: Optional[socket.socket] = None
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None
        self.ping_thread: Optional[threading.Thread] = None
        self.preview_window: Optional[ctk.CTkToplevel] = None

        # Frame principal
        frm = ctk.CTkFrame(master, corner_radius=15, fg_color="#2b2b2b")
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        # IP e Porta
        ctk.CTkLabel(frm, text="IP do servidor:", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="e", pady=6)
        self.ip_var = ctk.StringVar(value="127.0.0.1")
        ctk.CTkEntry(frm, textvariable=self.ip_var, width=150, corner_radius=8).grid(row=0, column=1, sticky="w", pady=6)

        ctk.CTkLabel(frm, text="Porta:", font=("Arial", 12, "bold")).grid(row=1, column=0, sticky="e", pady=6)
        self.port_var = ctk.IntVar(value=9999)
        ctk.CTkEntry(frm, textvariable=self.port_var, width=80, corner_radius=8).grid(row=1, column=1, sticky="w", pady=6)

        # Botões Conectar / Desconectar
        self.btn_connect = ctk.CTkButton(frm, text="Conectar", command=self.connect_server, corner_radius=10, fg_color="#4caf50")
        self.btn_connect.grid(row=2, column=0, padx=6, pady=10, sticky="ew")
        self.btn_disconnect = ctk.CTkButton(frm, text="Desconectar", command=self.disconnect_server, state="disabled", corner_radius=10, fg_color="#f44336")
        self.btn_disconnect.grid(row=2, column=1, padx=6, pady=10, sticky="ew")

        # Status e Ping
        ctk.CTkLabel(frm, text="Status:", font=("Arial", 12, "bold")).grid(row=3, column=0, sticky="e", pady=4)
        self.status_var = ctk.StringVar(value="Desconectado")
        ctk.CTkLabel(frm, textvariable=self.status_var, font=("Arial", 12)).grid(row=3, column=1, sticky="w", pady=4)

        ctk.CTkLabel(frm, text="Ping (ms):", font=("Arial", 12, "bold")).grid(row=4, column=0, sticky="e", pady=4)
        self.ping_var = ctk.StringVar(value="--")
        ctk.CTkLabel(frm, textvariable=self.ping_var, font=("Arial", 12)).grid(row=4, column=1, sticky="w", pady=4)

        frm.grid_columnconfigure(0, weight=1)
        frm.grid_columnconfigure(1, weight=1)

        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    def connect_server(self) -> None:
        """Tenta conectar ao servidor e iniciar threads de recebimento e ping."""
        ip = self.ip_var.get()
        port = int(self.port_var.get())

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((ip, port))
        except (socket.error, ConnectionRefusedError) as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar, IP incorreto ou conexão instável:\n{e}")
            self.sock = None
            return

        self.running = True
        self.btn_connect.configure(state="disabled")
        self.btn_disconnect.configure(state="normal")
        self.status_var.set(f"Conectado a {ip}:{port}")

        # Janela de preview
        self.preview_window = ctk.CTkToplevel(self.master)
        self.preview_window.title("Transmissão")
        self.preview_window.geometry("960x540")
        self.preview_label = ctk.CTkLabel(self.preview_window, text="")
        self.preview_label.pack(expand=True, fill="both")
        self.preview_window.protocol("WM_DELETE_WINDOW", self.disconnect_server)
        self.preview_label.imgtk_refs = []

        # Threads
        self.thread = threading.Thread(target=self.recv_loop, daemon=True)
        self.thread.start()
        self.ping_thread = threading.Thread(target=self.ping_loop, daemon=True)
        self.ping_thread.start()

    def disconnect_server(self) -> None:
        """Desconecta do servidor e finaliza threads e recursos."""
        self.running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            except Exception as e:
                print(f"Erro ao fechar socket: {e}")
            finally:
                self.sock.close()
            self.sock = None
        self.btn_connect.configure(state="normal")
        self.btn_disconnect.configure(state="disabled")
        self.status_var.set("Desconectado")
        self.ping_var.set("--")
        if self.preview_window:
            self.preview_window.destroy()
            self.preview_window = None

    def recv_all(self, size: int) -> Optional[bytes]:
        """Recebe exatamente 'size' bytes do socket."""
        data = b""
        while len(data) < size and self.running:
            try:
                chunk = self.sock.recv(min(65536, size - len(data)))
            except (socket.error, OSError) as e:
                print(f"Erro ao receber dados: {e}")
                return None
            if not chunk:
                return None
            data += chunk
        return data

    def recv_loop(self) -> None:
        """Loop de recebimento de frames."""
        try:
            while self.running:
                header = self.recv_all(4)
                if header is None:
                    if self.running:
                        messagebox.showerror("Erro de Conexão", "Conexão perdida com o servidor!")
                    break
                (length,) = struct.unpack("!I", header)
                payload = self.recv_all(length)
                if payload is None:
                    if self.running:
                        messagebox.showerror("Erro de Conexão", "Conexão perdida com o servidor!")
                    break
                frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                frame = cv2.resize(frame, (1920, 1080))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.master.after(1, self.update_image, imgtk)
        finally:
            self.disconnect_server()

    def update_image(self, imgtk: ImageTk.PhotoImage) -> None:
        """Atualiza o preview com a imagem recebida."""
        self.preview_label.imgtk_refs.append(imgtk)
        # Mantém só as duas últimas referências para liberar memória
        if len(self.preview_label.imgtk_refs) > 2:
            self.preview_label.imgtk_refs.pop(0)
        self.preview_label.configure(image=imgtk)

    def ping_loop(self) -> None:
        """Envia ping ao servidor a cada segundo e atualiza o valor."""
        while self.running and self.sock:
            start = time.time()
            try:
                self.sock.sendall(struct.pack("!I", 0))
            except (socket.error, OSError) as e:
                if self.running:
                    messagebox.showerror("Erro de Conexão", f"Conexão perdida durante o ping! {e}")
                break
            elapsed = (time.time() - start) * 1000
            self.ping_var.set(f"{int(elapsed)}")
            time.sleep(1)

    def on_close(self) -> None:
        """Finaliza recursos ao fechar a janela principal."""
        self.disconnect_server()
        self.master.after(300, self.master.destroy)

if __name__ == "__main__":
    root = ctk.CTk()
    app = ClienteApp(root)
    root.mainloop()