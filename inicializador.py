import customtkinter as ctk
from servidor import ServidorApp
from cliente_visualizador import ClienteApp
import tkinter.messagebox as messagebox

class Launcher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Holograma Stream")
        self.geometry("450x200")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        frm = ctk.CTkFrame(self, corner_radius=15)
        frm.pack(expand=True, fill="both", padx=20, pady=20)
        ctk.CTkLabel(frm, text="Escolha o modo:", font=("Arial", 16, "bold")).pack(pady=(0, 20))
        ctk.CTkButton(frm, text="Enviar o Vídeo", command=self.open_server,
                      corner_radius=10, fg_color="#4caf50", hover_color="#45a049").pack(pady=10, fill="x")
        ctk.CTkButton(frm, text="Receber o Vídeo", command=self.open_client,
                      corner_radius=10, fg_color="#2196f3", hover_color="#1976d2").pack(pady=10, fill="x")

        # Adiciona confirmação ao fechar
        self.protocol("WM_DELETE_WINDOW", self.confirm_exit)

    def open_server(self):
        self.destroy()
        app = ServidorApp()
        app.mainloop()

    def open_client(self):
        self.destroy()
        root = ctk.CTk()
        app = ClienteApp(root)
        root.mainloop()

    def confirm_exit(self):
        if messagebox.askokcancel("Fechar", "Deseja realmente fechar?"):
            self.destroy()

if __name__ == "__main__":
    app = Launcher()
    app.mainloop()