# Hologram Stream

**Hologram Stream** é uma aplicação Python para transmissão e visualização de vídeo em tempo real, com efeitos para holograma (ex: Pepper's Ghost), utilizando interface gráfica moderna (CustomTkinter) e processamento de imagens (OpenCV, MediaPipe).

## Funcionalidades

- **Modo Servidor:** Captura vídeo da webcam, aplica efeitos holográficos e transmite para clientes pela rede.
- **Modo Cliente:** Recebe, exibe e monitora a transmissão.
- **Remoção de fundo:** Utiliza MediaPipe para segmentação rápida.
- **Layouts para holograma:** Espelhamento simples ou quad 2x2 para pirâmides.
- **Interface amigável:** CustomTkinter, visual moderno e responsivo.
- **Logs e status:** Monitoramento de FPS, ping, clientes conectados.

## Instalação

### Pré-requisitos

- Python 3.8+
- Pip (gerenciador de pacotes)

### Dependências

Instale as principais dependências com:

```bash
pip install opencv-python customtkinter Pillow mediapipe netifaces
```

> **Obs.:** Para Windows, pode ser necessário instalar [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/pt-br/cpp/windows/latest-supported-vc-redist).

### Clone o projeto

```bash
git clone https://github.com/SEU_USUARIO/HologramStream.git
cd HologramStream
```

## Como usar

### 1. Inicie o Launcher

```bash
python inicializador.py
```

Escolha entre **Enviar o Vídeo** (Servidor) ou **Receber o Vídeo** (Cliente).

### 2. Servidor

- Configure câmera, resolução, FPS e efeitos.
- Clique em "Iniciar transmissão".
- Compartilhe o IP e porta exibidos com quem for conectar como cliente.

### 3. Cliente

- Informe o IP e porta do servidor.
- Clique em "Conectar".
- Visualize o vídeo transmitido em tempo real.

## Estrutura dos arquivos

- `launcher.py` - Tela inicial para seleção do modo.
- `server_gui.py` - Aplicação servidor (transmissão e processamento).
- `client_viewer.py` - Aplicação cliente (recepção e visualização).
- `hologram_utils.py` - Funções para manipulação de imagem/holograma.


## Dicas & Troubleshooting

- Se a câmera não abrir, verifique se está conectada e livre para uso.
- Verifique o firewall para liberar a porta TCP usada.
- Para melhor desempenho, use redes cabeadas e câmeras compatíveis.