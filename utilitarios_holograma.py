import cv2
import numpy as np
from typing import Optional

def aplicar_filtro(frame: np.ndarray, filtro: str = "Nenhum") -> np.ndarray:

    if filtro == "Nenhum":
        return frame
    elif filtro == "Sépia":
        kernel = np.array([[0.272, 0.534, 0.131],
                           [0.349, 0.686, 0.168],
                           [0.393, 0.769, 0.189]])
        frame_sepia = cv2.transform(frame, kernel)
        frame_sepia = np.clip(frame_sepia, 0, 255)
        return frame_sepia.astype(np.uint8)
    elif filtro == "Vermelho":
        frame_Vermelho = np.zeros_like(frame)
        frame_Vermelho[:, :, 2] = frame[:, :, 2]
        return frame_Vermelho
    elif filtro == "Azul":
        frame_Azul = np.zeros_like(frame)
        frame_Azul[:,:,0] = frame[:,:,0]
        return frame_Azul
    elif filtro == "Canny":
        edges = cv2.Canny(frame, 100, 200)
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    else:
        return frame

def composicao_holograma(frame: Optional[np.ndarray], mode: str = "Normal", flip_v: bool = False) -> Optional[np.ndarray]:

    if frame is None or not isinstance(frame, np.ndarray):
        return None
    out = frame.copy()

    if mode == "Normal":
        pass
    elif mode == "Cross":
        h, w = out.shape[:2]
        size = min(h, w) // 2
        small = cv2.resize(out, (size, size), interpolation=cv2.INTER_AREA)
        top = small
        bottom = cv2.rotate(small, cv2.ROTATE_180)
        left = cv2.rotate(small, cv2.ROTATE_90_COUNTERCLOCKWISE)
        right = cv2.rotate(small, cv2.ROTATE_90_CLOCKWISE)
        cross = np.zeros((size * 3, size * 3, 3), dtype=np.uint8)
        cross[0:size, size:size*2] = top
        cross[size*2:size*3, size:size*2] = bottom
        cross[size:size*2, 0:size] = left
        cross[size:size*2, size*2:size*3] = right
        out = cross
        if flip_v:
            out = cv2.flip(out, 0)
    else:
        pass
    return out