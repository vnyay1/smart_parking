# vision/preprocessor.py
import cv2
import numpy as np


class Preprocesseur:
    """
    Prépare une image brute pour maximiser la précision de l'OCR.
    Pipeline : redimensionnement → niveaux de gris → CLAHE → débruitage → seuillage
    """

    @staticmethod
    def preparer(image: np.ndarray) -> np.ndarray:
        """
        Applique toute la pipeline de prétraitement.
        Retourne une image binarisée prête pour l'OCR.
        """
        # 1. Redimensionner si trop petite (améliore la précision OCR)
        h, w = image.shape[:2]
        if w < 300:
            scale = 300 / w
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # 2. Convertir en niveaux de gris
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 3. CLAHE — améliore le contraste localement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contraste = clahe.apply(gray)

        # 4. Filtre médian — réduit le bruit sans flouter les bords
        debruite = cv2.medianBlur(contraste, 3)

        # 5. Seuillage adaptatif — binarisation robuste aux variations d'éclairage
        binaire = cv2.adaptiveThreshold(
            debruite, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        return binaire

    @staticmethod
    def preparer_multiple(image: np.ndarray) -> list:
        """
        Retourne plusieurs versions prétraitées pour augmenter les chances de lecture.
        Utile quand une version échoue (image sombre, surexposée, etc.)
        """
        versions = []

        # Version 1 : pipeline standard
        versions.append(Preprocesseur.preparer(image))

        # Version 2 : contraste agressif
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        versions.append(otsu)

        # Version 3 : image originale en gris (fallback)
        versions.append(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))

        return versions