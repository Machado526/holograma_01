import cv2
import numpy as np
from typing import Optional

def aplicar_filtro(frame: np.ndarray, filtro: str = "Nenhum") -> np.ndarray:
    if filtro == "Nenhum":
        return frame
    elif filtro == "Cinza":
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    elif filtro == "Sépia":
        kernel = np.array([[0.272, 0.534, 0.131],
                           [0.349, 0.686, 0.168],
                           [0.393, 0.769, 0.189]])
        sepia = cv2.transform(frame, kernel)
        sepia = np.clip(sepia, 0, 255)
        return sepia.astype(np.uint8)
    elif filtro == "Blue BGR":
        # Mantém apenas o canal azul, zera verde e vermelho
        blue_frame = np.zeros_like(frame)
        blue_frame[:,:,0] = frame[:,:,0]  # Canal azul
        return blue_frame
    elif filtro == "Desfoque":
        return cv2.GaussianBlur(frame, (15, 15), 0)
    elif filtro == "Canny":
        edges = cv2.Canny(frame, 100, 200)
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    else:
        return frame

def composicao_holograma(frame: Optional[np.ndarray], mode: str = "mirror", flip_v: bool = False) -> Optional[np.ndarray]:

    if frame is None or not isinstance(frame, np.ndarray):
        return None
    out = frame.copy()

    if mode == "raw":
        pass
    elif mode == "mirror":
        out = cv2.flip(out, 1)
        if flip_v:
            out = cv2.flip(out, 0)
    elif mode == "quad2x2":
        h, w = out.shape[:2]
        half_w, half_h = w // 2, h // 2
        half = cv2.resize(out, (half_w, half_h), interpolation=cv2.INTER_AREA)
        right = cv2.flip(half, 1)
        bottom = cv2.flip(half, 0)
        bottom_right = cv2.flip(right, 0)
        top_row = np.hstack([half, right])
        bottom_row = np.hstack([bottom, bottom_right])
        out = np.vstack([top_row, bottom_row])
        if flip_v:
            out = cv2.flip(out, 0)
    elif mode == "cross":
        h, w = out.shape[:2]
        # Define o tamanho do quadrado central dos braços
        size = min(h, w) // 2
        small = cv2.resize(out, (size, size), interpolation=cv2.INTER_AREA)
        # Aplica rotações
        top = small  # Sem rotação
        bottom = cv2.rotate(small, cv2.ROTATE_180)
        left = cv2.rotate(small, cv2.ROTATE_90_COUNTERCLOCKWISE)
        right = cv2.rotate(small, cv2.ROTATE_90_CLOCKWISE)
        # Cria fundo preto (altura e largura = size * 3)
        cross = np.zeros((size * 3, size * 3, 3), dtype=np.uint8)
        # Centraliza os quadrados nos braços
        # Top (centro superior)
        cross[0:size, size:size*2] = top
        # Bottom (centro inferior)
        cross[size*2:size*3, size:size*2] = bottom
        # Left (centro esquerdo)
        cross[size:size*2, 0:size] = left
        # Right (centro direito)
        cross[size:size*2, size*2:size*3] = right
        # Centro permanece preto
        out = cross
        if flip_v:
            out = cv2.flip(out, 0)
    else:
        pass
    return out