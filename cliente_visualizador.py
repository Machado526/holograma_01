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
import pyaudio
import pickle

# Tema
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ClienteApp:
    """Cliente que recebe payloads pickled {'video': jpg_bytes, 'audio': raw_audio_bytes'}"""

    def __init__(self, master: ctk.CTk):
        self.master = master
        self.master.title("Cliente de Holograma (Áudio+Vídeo)")
        self.master.geometry("600x300")
        self.master.resizable(False, False)

        self.audio_stream_out = None
        self.pyaudio_instance = None

        self.sock: Optional[socket.socket] = None
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None
        self.preview_window: Optional[ctk.CTkToplevel] = None

        frm = ctk.CTkFrame(master, corner_radius=15, fg_color="#2b2b2b")
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frm, text="IP do servidor:", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="e", pady=6)
        self.ip_var = ctk.StringVar(value="127.0.0.1")
        ctk.CTkEntry(frm, textvariable=self.ip_var, width=150, corner_radius=8).grid(row=0, column=1, sticky="w", pady=6)

        ctk.CTkLabel(frm, text="Porta:", font=("Arial", 12, "bold")).grid(row=1, column=0, sticky="e", pady=6)
        self.port_var = ctk.IntVar(value=9999)
        ctk.CTkEntry(frm, textvariable=self.port_var, width=80, corner_radius=8).grid(row=1, column=1, sticky="w", pady=6)

        self.btn_connect = ctk.CTkButton(frm, text="Conectar", command=self.connect_server, corner_radius=10, fg_color="#4caf50")
        self.btn_connect.grid(row=2, column=0, padx=6, pady=10, sticky="ew")
        self.btn_disconnect = ctk.CTkButton(frm, text="Desconectar", command=self.disconnect_server, state="disabled", corner_radius=10, fg_color="#f44336")
        self.btn_disconnect.grid(row=2, column=1, padx=6, pady=10, sticky="ew")

        ctk.CTkLabel(frm, text="Status:", font=("Arial", 12, "bold")).grid(row=3, column=0, sticky="e", pady=4)
        self.status_var = ctk.StringVar(value="Desconectado")
        ctk.CTkLabel(frm, textvariable=self.status_var, font=("Arial", 12)).grid(row=3, column=1, sticky="w", pady=4)

        frm.grid_columnconfigure(0, weight=1)
        frm.grid_columnconfigure(1, weight=1)

        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

    def connect_server(self) -> None:
        ip = self.ip_var.get()
        port = int(self.port_var.get())

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((ip, port))
        except (socket.error, ConnectionRefusedError) as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar: {e}")
            self.sock = None
            return

        self.running = True
        self.btn_connect.configure(state="disabled")
        self.btn_disconnect.configure(state="normal")
        self.status_var.set(f"Conectado a {ip}:{port}")

        # Preview window
        self.preview_window = ctk.CTkToplevel(self.master)
        self.preview_window.title("Transmissão")
        self.preview_window.geometry("960x540")
        self.preview_label = ctk.CTkLabel(self.preview_window, text="")
        self.preview_label.pack(expand=True, fill="both")
        self.preview_window.protocol("WM_DELETE_WINDOW", self.disconnect_server)
        self.preview_label.imgtk_refs = []

        # Áudio: inicializa pyaudio e stream de saída
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
            self.audio_stream_out = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                output=True,
                frames_per_buffer=1024
            )
            print("Áudio inicializado: 44100Hz, 1 canal")
        except Exception as e:
            messagebox.showwarning("Áudio", f"Não foi possível inicializar áudio: {e}")
            self.audio_stream_out = None

        # Start recv thread
        self.thread = threading.Thread(target=self.recv_loop, daemon=True)
        self.thread.start()

    def disconnect_server(self) -> None:
        self.running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            except Exception as e:
                print(f"Erro ao fechar socket: {e}")
            finally:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.sock = None

        self.btn_connect.configure(state="normal")
        self.btn_disconnect.configure(state="disabled")
        self.status_var.set("Desconectado")
        if self.preview_window:
            self.preview_window.destroy()
            self.preview_window = None

        # fechar audio
        try:
            if self.audio_stream_out:
                self.audio_stream_out.stop_stream()
                self.audio_stream_out.close()
        except Exception:
            pass
        try:
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
        except Exception:
            pass

    def recv_all(self, size: int) -> Optional[bytes]:
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

    def recv_loop(self):
        while self.running and self.sock:
            try:
                header = self.recv_all(4)
                if header is None:
                    break
                length = struct.unpack("!I", header)[0]
                if length == 0:
                    # protocolo: comprimento zero -> ignorar
                    continue
                payload_bytes = self.recv_all(length)
                if payload_bytes is None:
                    break

                # Desserializar
                try:
                    payload = pickle.loads(payload_bytes)
                except Exception as e:
                    print(f"Erro ao desserializar payload: {e}")
                    continue

                # Vídeo
                video_bytes = payload.get('video')
                if video_bytes:
                    arr = np.frombuffer(video_bytes, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                else:
                    frame = None

                # Áudio
                audio_bytes = payload.get('audio')
                if audio_bytes and self.audio_stream_out:
                    try:
                        # escreve o buffer inteiro (PyAudio aceita buffers maiores)
                        self.audio_stream_out.write(audio_bytes)
                    except Exception as e:
                        print(f"Erro ao reproduzir áudio: {e}")
                elif self.audio_stream_out:
                    # se não veio áudio, escreve silêncio curto para manter o stream
                    try:
                        self.audio_stream_out.write(b"\x00" * 2048)
                    except Exception:
                        pass

                # Atualiza preview
                if frame is not None:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.master.after(1, self.update_image, imgtk)

            except Exception as e:
                print(f"Erro no loop de recebimento: {e}")
                break

        # quando sai do loop, garante desconexão limpa
        self.disconnect_server()

    def update_image(self, imgtk: ImageTk.PhotoImage) -> None:
        self.preview_label.imgtk_refs.append(imgtk)
        if len(self.preview_label.imgtk_refs) > 2:
            self.preview_label.imgtk_refs.pop(0)
        self.preview_label.configure(image=imgtk)

    def on_close(self) -> None:
        self.disconnect_server()
        self.master.after(200, self.master.destroy)

if __name__ == "__main__":
    root = ctk.CTk()
    app = ClienteApp(root)
    root.mainloop()
