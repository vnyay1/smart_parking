import cv2
import numpy as np


class Preprocesseur:

    @staticmethod
    def preparer(image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        if w < 300:
            scale = 300 / w
            image = cv2.resize(image, None, fx=scale, fy=scale,
                               interpolation=cv2.INTER_CUBIC)

        gray     = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        clahe    = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contraste = clahe.apply(gray)
        debruite  = cv2.medianBlur(contraste, 3)
        binaire   = cv2.adaptiveThreshold(
            debruite, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        return binaire

    @staticmethod
    def preparer_multiple(image: np.ndarray) -> list:
        """
        Retourne 5 versions différentes pour maximiser les chances de lecture.
        """
        versions = []
        h, w = image.shape[:2]

        # Agrandir si nécessaire
        if w < 400:
            scale = 400 / w
            image = cv2.resize(image, None, fx=scale, fy=scale,
                               interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # V1 : pipeline standard (CLAHE + médian + adaptatif)
        clahe    = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        v1       = clahe.apply(gray)
        v1       = cv2.medianBlur(v1, 3)
        v1       = cv2.adaptiveThreshold(v1, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        versions.append(v1)

        # V2 : Otsu binarisation directe
        _, v2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        versions.append(v2)

        # V3 : image couleur originale (EasyOCR marche bien en couleur)
        versions.append(image)

        # V4 : contraste forcé + sharpening
        sharpen_k = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
        v4 = cv2.filter2D(gray, -1, sharpen_k)
        versions.append(v4)

        # V5 : image agrandie x2 sans autre traitement
        v5 = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        versions.append(v5)

        return versions