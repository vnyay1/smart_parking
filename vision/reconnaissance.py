import cv2
import numpy as np
import Levenshtein
import os
import re
from typing import Optional
from .preprocessor import Preprocesseur
from .detecteur_plaque import DetecteurPlaque
from .lecteur_ocr import LecteurOCR


class SystemeReconnaissance:

    def __init__(self, debug=False):
        self.ocr       = LecteurOCR()
        self.debug     = debug
        self.debug_dir = 'vision/debug_output'
        if debug:
            os.makedirs(self.debug_dir, exist_ok=True)

    def analyser_frame(self, frame: np.ndarray, nom_debug: str = 'frame') -> tuple[Optional[str], float]:

        zone = DetecteurPlaque.detecter(frame)
        if zone is None:
            print("[Reconnaissance] Aucune zone détectée.")
            return None, 0.0

        if self.debug:
            cv2.imwrite(f"{self.debug_dir}/{nom_debug}_zone.jpg", zone)

        versions = Preprocesseur.preparer_multiple(zone)

        for i, version in enumerate(versions):
            if self.debug:
                cv2.imwrite(f"{self.debug_dir}/{nom_debug}_v{i+1}.jpg", version)

            # Lecture globale
            plaque, conf = self.ocr.lire(version)
            if plaque and conf >= 0.3:
                print(f"[Reconnaissance] ✓ Globale v{i+1} : {plaque} ({conf:.0%})")
                return plaque, conf

            # Lecture par zones
            plaque, conf = self.ocr.lire_zones(version)
            if plaque and conf >= 0.2:
                print(f"[Reconnaissance] ✓ Zones v{i+1} : {plaque} ({conf:.0%})")
                return plaque, conf

        print("[Reconnaissance] ✗ Échec.")
        return None, 0.0

    def analyser_image_path(self, chemin: str) -> tuple[Optional[str], float]:
        frame = cv2.imread(chemin)
        if frame is None:
            raise ValueError(f"Impossible de lire : {chemin}")
        nom = os.path.splitext(os.path.basename(chemin))[0]
        return self.analyser_frame(frame, nom_debug=nom)

    def analyser_base64(self, image_b64: str) -> tuple[Optional[str], float]:
        import base64
        arr   = np.frombuffer(base64.b64decode(image_b64), np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return self.analyser_frame(frame)

    # ─── Comparaison ─────────────────────────────────────────────────────────

    @staticmethod
    def comparer_plaques(lue: str, reference: str, tolerance: int = 1) -> bool:
        """
        Comparaison complète avec tolérance Levenshtein.
        Priorité 1 : comparaison plaque entière (tolère 1 erreur OCR).
        """
        return Levenshtein.distance(lue.upper().strip(), reference.upper().strip()) <= tolerance

    @staticmethod
    def comparer_numeros_seulement(lue: str, reference: str) -> bool:
        """
        Comparaison des chiffres uniquement — fallback si la lettre est illisible.
        Extrait [premier_numero, wilaya] et compare les deux.
        Ex: '78904-ا-6' vs '78904-و-6' → True (chiffres identiques)
        """
        def extraire_chiffres(plaque: str) -> tuple:
            parties = plaque.split('-')
            if len(parties) >= 3:
                return (parties[0].strip(), parties[2].strip())
            return (plaque.strip(), '')

        chiff_lue = extraire_chiffres(lue)
        chiff_ref = extraire_chiffres(reference)

        if chiff_lue == ('', '') or chiff_ref == ('', ''):
            return False

        return chiff_lue == chiff_ref