# utilitarios_holograma.py
import cv2
import numpy as np
from typing import Optional, Tuple

def composicao_holograma(frame: Optional[np.ndarray], mode: str = "mirror", flip_v: bool = False) -> Optional[np.ndarray]:
    """
    Aplica transformações para criar efeitos de holograma na imagem.

    Args:
        frame: Imagem de entrada (BGR, np.ndarray).
        mode: Tipo de layout ("raw", "mirror", "quad2x2").
        flip_v: Espelha verticalmente.

    Returns:
        Imagem transformada ou None se o frame for inválido.
    """
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
        # Garante que largura e altura são pares para evitar distorção
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
    else:
        # Se modo desconhecido, retorna original
        pass
    return out

def fullscreen_window(win_name: str) -> None:
    """
    Tenta colocar uma janela do OpenCV em tela cheia em múltiplos SOs.

    Args:
        win_name: Nome da janela.
    """
    try:
        cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    except Exception:
        # fallback: maximiza
        try:
            cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
        except Exception:
            print(f"Não foi possível maximizar a janela: {win_name}")