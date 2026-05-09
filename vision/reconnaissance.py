import cv2
import numpy as np
import Levenshtein
import os
import re
import unicodedata
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

    _TRADUCTION_CHIFFRES_ARABES = str.maketrans({
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    })

    _TRADUCTION_TIRETS = str.maketrans({
        '—': '-', '–': '-', '−': '-', '_': '-', '/': '-', '\\': '-',
    })

    @staticmethod
    def normaliser_plaque(plaque: str) -> str:
        """
        Harmonise les variantes Unicode/ponctuation pour fiabiliser la comparaison.
        """
        if not plaque:
            return ''

        texte = unicodedata.normalize('NFKC', plaque).strip()
        texte = texte.translate(SystemeReconnaissance._TRADUCTION_CHIFFRES_ARABES)
        texte = texte.translate(SystemeReconnaissance._TRADUCTION_TIRETS)
        texte = re.sub(r'\s+', '', texte)
        texte = re.sub(r'-{2,}', '-', texte)
        return texte.upper()

    @staticmethod
    def comparer_plaques(lue: str, reference: str, tolerance: int = 1) -> bool:
        """
        Comparaison complète avec tolérance Levenshtein.
        Priorité 1 : comparaison plaque entière (tolère 1 erreur OCR).
        """
        lue_norm = SystemeReconnaissance.normaliser_plaque(lue)
        ref_norm = SystemeReconnaissance.normaliser_plaque(reference)
        if not lue_norm or not ref_norm:
            return False
        return Levenshtein.distance(lue_norm, ref_norm) <= tolerance

    @staticmethod
    def comparer_numeros_seulement(lue: str, reference: str) -> bool:
        """
        Comparaison des chiffres uniquement — fallback si la lettre est illisible.
        Extrait [premier_numero, wilaya] et compare les deux.
        Ex: '78904-ا-6' vs '78904-و-6' → True (chiffres identiques)
        """
        lue = SystemeReconnaissance.normaliser_plaque(lue)
        reference = SystemeReconnaissance.normaliser_plaque(reference)

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
