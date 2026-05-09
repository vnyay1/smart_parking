import cv2
import numpy as np
from typing import Optional


class DetecteurPlaque:

    @staticmethod
    def detecter(image: np.ndarray) -> Optional[np.ndarray]:
        """
        Essaie plusieurs stratégies de détection dans l'ordre.
        """
        # Stratégie 1 : contours rectangulaires (image nette)
        result = DetecteurPlaque._par_contours(image)
        if result is not None:
            return result

        # Stratégie 2 : MSER (robuste aux variations d'éclairage)
        result = DetecteurPlaque._par_mser(image)
        if result is not None:
            return result

        # Stratégie 3 : recadrage central (fallback — si rien ne marche,
        # on prend la bande centrale de l'image qui contient souvent la plaque)
        return DetecteurPlaque._recadrage_central(image)

    @staticmethod
    def _par_contours(image: np.ndarray) -> Optional[np.ndarray]:
        gray    = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.bilateralFilter(gray, 11, 17, 17)
        edges   = cv2.Canny(blurred, 30, 200)

        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours    = sorted(contours, key=cv2.contourArea, reverse=True)[:15]

        for contour in contours:
            perimetre = cv2.arcLength(contour, True)
            approx    = cv2.approxPolyDP(contour, 0.018 * perimetre, True)

            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                ratio = w / max(h, 1)
                # Plaques marocaines : ratio ≈ 4 à 5.5
                if 2.5 < ratio < 7.0 and w > 80 and h > 20:
                    # Ajouter une petite marge
                    marge = 5
                    x = max(0, x - marge)
                    y = max(0, y - marge)
                    w = min(image.shape[1] - x, w + 2 * marge)
                    h = min(image.shape[0] - y, h + 2 * marge)
                    return image[y:y+h, x:x+w]

        return None

    @staticmethod
    def _par_mser(image: np.ndarray) -> Optional[np.ndarray]:
        """
        MSER détecte les régions de texte — utile pour les plaques avec fond clair.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mser = cv2.MSER_create()
        regions, _ = mser.detectRegions(gray)

        if not regions:
            return None

        hulls = [cv2.convexHull(r.reshape(-1, 1, 2)) for r in regions]
        rects = [cv2.boundingRect(h) for h in hulls]

        if not rects:
            return None

        # Trouver le plus grand rectangle avec bon ratio
        for x, y, w, h in sorted(rects, key=lambda r: r[2]*r[3], reverse=True):
            ratio = w / max(h, 1)
            if 2.5 < ratio < 7.0 and w > 100:
                return image[y:y+h, x:x+w]

        return None

    @staticmethod
    def _recadrage_central(image: np.ndarray) -> np.ndarray:
        """
        Fallback : retourne la bande centrale de l'image.
        Sur une photo de voiture, la plaque est souvent au centre-bas.
        """
        h, w = image.shape[:2]
        y1 = int(h * 0.3)
        y2 = int(h * 0.9)
        x1 = int(w * 0.1)
        x2 = int(w * 0.9)
        return image[y1:y2, x1:x2]