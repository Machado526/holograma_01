import cv2
import socket
import struct
import threading
import time
import queue
import numpy as np
import netifaces
import mediapipe as mp
from utilitarios_holograma import composicao_holograma, aplicar_filtro
import customtkinter as ctk
from PIL import Image, ImageTk
from typing import Callable, Optional, Tuple, List
import pyaudio
import pickle

HOST = ""
PORT = 9999

class ClientPool:
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, status_callback: Optional[Callable[[str], None]] = None):
        self.clients: List[Tuple[socket.socket, Tuple[str, int]]] = []
        self.lock = threading.Lock()
        self.log_cb = log_callback
        self.status_cb = status_callback

    def add(self, sock: socket.socket, addr: Tuple[str, int]) -> None:
        with self.lock:
            self.clients.append((sock, addr))
            if self.log_cb:
                self.log_cb(f"Cliente conectado: {addr[0]}:{addr[1]}")
            if self.status_cb:
                self.status_cb(f"Cliente conectado: {addr[0]} | Total: {len(self.clients)}")

    def _notify_disconnected(self, addr: Tuple[str, int]) -> None:
        if self.log_cb:
            self.log_cb(f"Cliente desconectado: {addr[0]}:{addr[1]}")
        if self.status_cb:
            self.status_cb(f"Cliente desconectado: {addr[0]} | Total: {len(self.clients)}")

    def broadcast(self, payload: bytes) -> None:
        header = struct.pack("!I", len(payload))
        removidos: List[Tuple[str, int]] = []
        with self.lock:
            ativos = []
            for s, addr in self.clients:
                try:
                    s.sendall(header + payload)
                    ativos.append((s, addr))
                except (socket.error, OSError):
                    try:
                        s.close()
                    except Exception:
                        pass
                    removidos.append(addr)
            self.clients = ativos

        for addr in removidos:
            self._notify_disconnected(addr)

    def close_all(self) -> None:
        with self.lock:
            for s, _ in self.clients:
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    s.close()
                except Exception:
                    pass
            self.clients.clear()

def get_local_ip() -> str:
    try:
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            for a in addrs:
                ip = a.get("addr")
                if ip and ip != "127.0.0.1":
                    return ip
    except Exception:
        pass
    return "127.0.0.1"

class ServidorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Servidor Holograma")
        self.geometry("900x950")

        # Áudio
        self.audio_enabled = True
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.chunk = 1024  # frames per read
        self.pyaudio_instance = None
        self.audio_thread = None
        self.audio_queue = queue.Queue(maxsize=100)  # fila para chunks de áudio

        # Controle
        self.running = threading.Event()
        self.capture_thread: Optional[threading.Thread] = None
        self.accept_thread: Optional[threading.Thread] = None
        self.server_socket: Optional[socket.socket] = None

        self.client_pool = ClientPool()
        self.frame_queue = queue.Queue(maxsize=5)

        # Tema
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # MediaPipe
        self.mp_selfie_segmentation = mp.solutions.selfie_segmentation
        self.segmentation = self.mp_selfie_segmentation.SelfieSegmentation(model_selection=1)

        # Layout
        self._build_interface()
        self.after(1000, self.update_status)

    def _build_interface(self) -> None:
        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ip = get_local_ip()
        ctk.CTkLabel(self.main_frame, text=f"IP local: {ip}", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.port_var = ctk.IntVar(value=PORT)
        ctk.CTkLabel(self.main_frame, text="Porta:", font=("Arial", 12)).grid(row=0, column=1, sticky="e", padx=5)
        ctk.CTkEntry(self.main_frame, textvariable=self.port_var, width=80, corner_radius=8).grid(row=0, column=2, sticky="w")

        # Holograma & filtros
        holo_frame = ctk.CTkFrame(self.main_frame, corner_radius=12)
        holo_frame.grid(row=2, column=0, columnspan=3, pady=10, sticky="ew")
        ctk.CTkLabel(holo_frame, text="Layout:", font=("Arial", 12)).grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.mode_var = ctk.StringVar(value="Normal")
        ctk.CTkComboBox(holo_frame, values=["Normal","Cross"], variable=self.mode_var, width=120).grid(row=0, column=1, sticky="w")
        self.flip_v = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(holo_frame, text="Espelhar vertical", variable=self.flip_v).grid(row=0, column=2, padx=5)
        self.remove_bg_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(holo_frame, text="Remover fundo", variable=self.remove_bg_var).grid(row=0, column=3, padx=5)

        self.filter_var = ctk.StringVar(value="Nenhum")
        ctk.CTkLabel(holo_frame, text="Filtro:", font=("Arial", 12)).grid(row=1, column=0, padx=5, pady=5, sticky="e")
        ctk.CTkComboBox(holo_frame, values=["Nenhum", "Sépia", "Vermelho", "Azul", "Canny"], variable=self.filter_var, width=120).grid(row=1, column=1, sticky="w")

        # Botões
        ctrl_frame = ctk.CTkFrame(self.main_frame, corner_radius=12)
        ctrl_frame.grid(row=3, column=0, columnspan=3, pady=10)
        self.btn_start = ctk.CTkButton(ctrl_frame, text="Iniciar transmissão", command=self.start_server, corner_radius=10, fg_color="#4caf50")
        self.btn_start.grid(row=0, column=0, padx=5)
        self.btn_stop = ctk.CTkButton(ctrl_frame, text="Parar transmissão", command=self.stop_server, state="disabled", corner_radius=10, fg_color="#f44336")
        self.btn_stop.grid(row=0, column=1, padx=5)
        self.preview_v = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(ctrl_frame, text="Mostrar preview local", variable=self.preview_v).grid(row=0, column=2, padx=5)

        # Status & logs
        self.status_var = ctk.StringVar(value="Aguardando...")
        ctk.CTkLabel(self.main_frame, textvariable=self.status_var, font=("Arial", 12, "bold")).grid(row=4, column=0, columnspan=3, sticky="w", pady=5)
        self.log_text = ctk.CTkTextbox(self.main_frame, height=120, corner_radius=10)
        self.log_text.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=5)
        self.preview_label = ctk.CTkLabel(self.main_frame, text="")
        self.preview_label.grid(row=6, column=0, columnspan=3, pady=10)

        self.label_clients = ctk.CTkLabel(self.main_frame, text="Clientes conectados: 0", font=("Arial", 12))
        self.label_clients.grid(row=7, column=0, sticky="w", padx=5)
        self.label_fps_info = ctk.CTkLabel(self.main_frame, text="FPS atual: 0", font=("Arial", 12))
        self.label_fps_info.grid(row=7, column=1, sticky="w")
        self.label_ping_info = ctk.CTkLabel(self.main_frame, text="Ping médio: N/A", font=("Arial", 12))
        self.label_ping_info.grid(row=7, column=2, sticky="w")

        for i in range(3):
            self.main_frame.grid_columnconfigure(i, weight=1)

    def _set_status_threadsafe(self, text: str) -> None:
        self.after(0, lambda: self.status_var.set(text))

    def _log_threadsafe(self, text: str) -> None:
        self.after(0, lambda: self.log(text))

    def log(self, msg: str) -> None:
        self.log_text.insert("end", f"{time.strftime('%H:%M:%S')} - {msg}\n")
        self.log_text.see("end")

    def update_status(self) -> None:
        self.label_clients.configure(text=f"Clientes conectados: {len(self.client_pool.clients)}")
        self.label_fps_info.configure(text=f"FPS atual: {getattr(self, 'last_fps', 0)}")
        self.after(1000, self.update_status)

    def start_server(self) -> None:
        if self.running.is_set():
            return

        port = int(self.port_var.get())
        self.running.set()

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_var.set(f"Transmitindo em {get_local_ip()}:{port}")
        self.client_pool = ClientPool( log_callback=self._log_threadsafe, status_callback=self._set_status_threadsafe)

        if self.audio_enabled:
            self.pyaudio_instance = pyaudio.PyAudio()
            self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
            self.audio_thread.start()

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((HOST, port))
            self.server_socket.listen(8)
            self.server_socket.settimeout(1.0)
        except Exception as e:
            self.log(f"Erro ao iniciar servidor: {e}")
            self.status_var.set("Falha ao iniciar servidor.")
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.running.clear()
            return

        self.accept_thread = threading.Thread(target=self.accept_loop, daemon=True)
        self.accept_thread.start()

        self.capture_thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.capture_thread.start()

        self.log("Servidor iniciado!")

    def stop_server(self) -> None:
        if not self.running.is_set():
            return

        self.running.clear()

        try:
            if self.server_socket:
                try:
                    self.server_socket.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.server_socket.close()
        except Exception as e:
            self.log(f"Erro ao fechar socket servidor: {e}")
        finally:
            self.server_socket = None

        self.client_pool.close_all()

        try:
            if self.pyaudio_instance:
                try:
                    self.pyaudio_instance.terminate()
                except Exception:
                    pass
                self.pyaudio_instance = None
        except Exception:
            pass

        self.status_var.set("Transmissão parada.")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.log("Servidor parado.")

    def accept_loop(self) -> None:
        while self.running.is_set():
            try:
                conn, addr = self.server_socket.accept()
                conn.settimeout(1.0)
                self.client_pool.add(conn, addr)
                t = threading.Thread(target=self._client_listener, args=(conn, addr), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                self._set_status_threadsafe(f"Erro aceitar conexão: {e}")
                self._log_threadsafe(f"Erro aceitar conexão: {e}")
                time.sleep(0.3)
        self._log_threadsafe("Loop de aceitação encerrado.")

    def _client_listener(self, conn: socket.socket, addr: Tuple[str,int]) -> None:
        try:
            while self.running.is_set():
                try:
                    data = conn.recv(16)
                    if not data:
                        break
                    time.sleep(0.01)
                except socket.timeout:
                    continue
                except (ConnectionResetError, OSError):
                    break
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def remove_bg_mediapipe_fast(self, frame: np.ndarray, bg_color=(0,0,0),proc_width=320, proc_height=180) -> np.ndarray:
        small = cv2.resize(frame, (proc_width, proc_height))
        rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        results = self.segmentation.process(rgb_small)
        mask = results.segmentation_mask
        mask = cv2.resize(mask, (frame.shape[1], frame.shape[0]))
        mask = np.stack((mask,)*3, axis=-1)
        mask = (mask > 0.5).astype(np.uint8)
        frame = frame*mask + np.array(bg_color, dtype=np.uint8)*(1-mask)
        return frame

    def _audio_capture_loop(self) -> None:
        try:
            stream = self.pyaudio_instance.open(format=self.audio_format, channels=self.channels, rate=self.rate, input=True, frames_per_buffer=self.chunk)
            self.log(f"Captura de áudio iniciada em {self.rate}Hz, {self.channels} canais")
        except Exception as e:
            self.log(f"Falha ao abrir microfone: {e}")
            try:
                self.rate, self.channels = 48000, 2
                stream = self.pyaudio_instance.open(format=self.audio_format, channels=self.channels, rate=self.rate, input=True, frames_per_buffer=self.chunk)
                self.log(f"Captura de áudio fallback em {self.rate}Hz, {self.channels} canais")
            except Exception as e2:
                self.log(f"Falha no fallback de áudio: {e2}")
                return

        try:
            while self.running.is_set():
                try:
                    data = stream.read(self.chunk, exception_on_overflow=False)
                except Exception:
                    data = b"\x00" * (self.chunk * 2 * self.channels)
                try:
                    self.audio_queue.put_nowait(data)
                except queue.Full:
                    try:
                        _ = self.audio_queue.get_nowait()
                    except Exception:
                        pass
                    try:
                        self.audio_queue.put_nowait(data)
                    except Exception:
                        pass
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass

    def capture_loop(self) -> None:
        cam_idx = 0
        w, h = 1920, 1080
        fps_target = 30

        cap = cv2.VideoCapture(cam_idx)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_FPS, fps_target)

        last = time.time()
        frame_count = 0
        fps_report_interval = 2.0
        fps_last_report_time = time.time()

        try:
            while self.running.is_set():
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue

                mode = self.mode_var.get()
                if self.remove_bg_var.get():
                    frame = self.remove_bg_mediapipe_fast(frame, bg_color=(0, 0, 0))

                filtro = self.filter_var.get()
                frame = aplicar_filtro(frame, filtro)
                frame = composicao_holograma(frame, mode=mode, flip_v=self.flip_v.get())

                if self.preview_v.get():
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    preview_width, preview_height = 500, 500
                    img = img.resize((preview_width, preview_height))
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.preview_label.configure(image=imgtk)
                    self.preview_label.image = imgtk

                ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ok:
                    audio_chunks = []

                    max_chunks_take = 50
                    taken = 0
                    while not self.audio_queue.empty() and taken < max_chunks_take:
                        try:
                            c = self.audio_queue.get_nowait()
                            audio_chunks.append(c)
                            taken += 1
                        except Exception:
                            break

                    if audio_chunks:
                        audio_bytes = b"".join(audio_chunks)
                    else:
                        audio_bytes = b"\x00" * (self.chunk * 2 * self.channels)

                    payload_obj = {"video": buf.tobytes(), "audio": audio_bytes}
                    try:
                        payload = pickle.dumps(payload_obj, protocol=pickle.HIGHEST_PROTOCOL)
                        self.client_pool.broadcast(payload)
                    except Exception as e:
                        self.log(f"Erro ao serializar/enviar payload: {e}")

                frame_count += 1
                now = time.time()
                elapsed = now - last
                target_dt = 1.0 / fps_target
                if elapsed < target_dt:
                    time.sleep(max(0.0, target_dt - elapsed))
                last = time.time()

                if (now - fps_last_report_time) > fps_report_interval:
                    self.last_fps = int(frame_count / (now - fps_last_report_time))
                    frame_count = 0
                    fps_last_report_time = now

        finally:
            cap.release()

if __name__ == "__main__":
    app = ServidorApp()
    app.mainloop()
