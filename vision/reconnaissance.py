# vision/reconnaissance.py
import cv2
import numpy as np
import Levenshtein
import re
from typing import Optional
from pathlib import Path
from .preprocessor import Preprocesseur
from .detecteur_plaque import DetecteurPlaque
from .lecteur_ocr import LecteurOCR


class SystemeReconnaissance:
    """
    Orchestrateur principal.
    Prend une frame brute → retourne la plaque lue + score de confiance.
    """

    MAX_TENTATIVES = 3   # nombre de prétraitements essayés si le premier échoue
    MIN_CHIFFRES_PLAUSIBLES = 4
    _PLATE_FULL_RE = re.compile(r'^\d{1,5}-[A-Z]{1,3}-\d{1,2}$')
    _AR_MAP = {
        "أ": "A", "ا": "A", "ب": "B", "د": "D", "ه": "H", "و": "W", "ط": "T", "ي": "Y",
        "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
        "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    }

    def __init__(self):
        self.ocr      = LecteurOCR()
        self.detecteur = DetecteurPlaque()
        self.modele_yolo = self._charger_modele_yolo()

    @staticmethod
    def _charger_modele_yolo():
        """
        Charge YOLOv8 s'il est présent localement.
        """
        model_path = Path(__file__).resolve().parent / "models" / "yolov8n.pt"
        if not model_path.exists():
            return None

        try:
            from ultralytics import YOLO
            return YOLO(str(model_path))
        except Exception as e:
            print(f"[Reconnaissance] YOLO indisponible ({e}), fallback detecteur classique.")
            return None

    def analyser_frame(
        self,
        frame: np.ndarray,
        expected_plates: Optional[list[str]] = None,
    ) -> tuple[Optional[str], float]:
        """
        Pipeline complète sur une frame webcam.
        Retourne (plaque, confiance) ou (None, 0.0).
        """
        # Étape 1 : détecter et extraire la zone de la plaque (YOLO en priorité)
        zone_plaque = None
        if self.modele_yolo is not None:
            zone_plaque = DetecteurPlaque.detecter_avec_yolo(frame, self.modele_yolo)

        if zone_plaque is None:
            zone_plaque = DetecteurPlaque.detecter(frame)

        if zone_plaque is None:
            # Fallback: essayer l'OCR sur l'image entière.
            # Utile quand la détection de contour échoue malgré une plaque visible.
            print("[Reconnaissance] Aucune zone plaque nette detectee, tentative OCR globale.")
            zone_plaque = frame

        # Étape 2 : essayer plusieurs prétraitements
        versions = Preprocesseur.preparer_multiple(zone_plaque)

        meilleur_plaque: Optional[str] = None
        meilleure_confiance = 0.0
        meilleur_score = -1.0
        meilleure_attendue: Optional[str] = None
        meilleure_attendue_dist: Optional[int] = None
        meilleure_attendue_conf = 0.0

        expected_norm = []
        if expected_plates:
            for p in expected_plates:
                n = self._normaliser_plaque(p)
                if self._est_format_complet(n):
                    expected_norm.append(n)

        for i, version in enumerate(versions):
            plaque, confiance = self.ocr.lire(version)
            if not plaque:
                continue

            if expected_norm:
                resolue, dist = self._resoudre_plaque_attendue(plaque, expected_norm)
                if resolue is not None:
                    if meilleure_attendue_dist is None or dist < meilleure_attendue_dist:
                        meilleure_attendue = resolue
                        meilleure_attendue_dist = dist
                        meilleure_attendue_conf = max(float(confiance), 0.70 if dist <= 1 else 0.55)
                    if dist == 0:
                        print(
                            f"[Reconnaissance] Plaque resolue via reservations attendues "
                            f"(version {i+1}) : {resolue}"
                        )
                        return resolue, meilleure_attendue_conf

            nb_chiffres = len(re.findall(r'\d', plaque))

            # Accepter immédiatement un format complet correctement confiant
            if (
                self._est_format_complet(plaque)
                and nb_chiffres >= self.MIN_CHIFFRES_PLAUSIBLES
                and confiance >= 0.35
            ):
                print(f"[Reconnaissance] Plaque lue (version {i+1}) : {plaque} ({confiance:.0%})")
                return plaque, confiance

            # Sinon conserver le meilleur fallback (partiel inclus)
            score = float(confiance) + (0.20 * min(nb_chiffres, 5))
            if score > meilleur_score:
                meilleur_plaque = plaque
                meilleure_confiance = confiance
                meilleur_score = score

        if meilleure_attendue is not None:
            print(f"[Reconnaissance] Plaque resolue via reservations attendues : {meilleure_attendue}")
            return meilleure_attendue, meilleure_attendue_conf

        if meilleur_plaque:
            print(f"[Reconnaissance] Lecture partielle retenue : {meilleur_plaque} ({meilleure_confiance:.0%})")
            return meilleur_plaque, meilleure_confiance

        print("[Reconnaissance] Echec de lecture sur toutes les versions.")
        return None, 0.0

    def analyser_image_path(
        self,
        chemin: str,
        expected_plates: Optional[list[str]] = None,
    ) -> tuple[Optional[str], float]:
        """
        Analyse une image depuis un chemin fichier — utile pour les tests.
        """
        frame = cv2.imread(chemin)
        if frame is None:
            raise ValueError(f"Impossible de lire l'image : {chemin}")
        return self.analyser_frame(frame, expected_plates=expected_plates)

    def analyser_base64(
        self,
        image_b64: str,
        expected_plates: Optional[list[str]] = None,
    ) -> tuple[Optional[str], float]:
        """
        Analyse une image encodée en base64 — utilisée par l'API Django.
        """
        import base64
        img_bytes = base64.b64decode(image_b64)
        arr       = np.frombuffer(img_bytes, np.uint8)
        frame     = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return self.analyser_frame(frame, expected_plates=expected_plates)

    @staticmethod
    def comparer_plaques(plaque_lue: str, plaque_reference: str, tolerance: int = 1) -> bool:
        """
        Retourne True si les deux plaques sont similaires (distance Levenshtein ≤ tolerance).
        Permet de tolérer une erreur de lecture OCR.
        """
        if not plaque_lue or not plaque_reference:
            return False

        lue = SystemeReconnaissance._normaliser_plaque(plaque_lue)
        ref = SystemeReconnaissance._normaliser_plaque(plaque_reference)
        if not lue or not ref:
            return False

        if lue == ref:
            return True

        # Cas standard format complet
        if SystemeReconnaissance._est_format_complet(lue) and SystemeReconnaissance._est_format_complet(ref):
            return Levenshtein.distance(lue, ref) <= tolerance

        # Comparaison par composant (supporte lectures partielles)
        n_lue, s_lue, r_lue = SystemeReconnaissance._extraire_composants(lue)
        n_ref, s_ref, r_ref = SystemeReconnaissance._extraire_composants(ref)

        if n_lue and n_ref:
            dist_num = Levenshtein.distance(n_lue, n_ref)
            long_ok = abs(len(n_lue) - len(n_ref)) <= 1
            seuil_num = 2 if min(len(n_lue), len(n_ref)) >= 5 else 1
            if dist_num <= seuil_num and long_ok:
                serie_ok = (not s_lue or not s_ref or Levenshtein.distance(s_lue, s_ref) <= 1)
                region_ok = (not r_lue or not r_ref or Levenshtein.distance(r_lue, r_ref) <= 1)
                if serie_ok and region_ok:
                    return True

        # Fallback sur forme compacte alphanumérique
        lue_compact = re.sub(r'[^A-Z0-9]', '', lue)
        ref_compact = re.sub(r'[^A-Z0-9]', '', ref)
        if len(lue_compact) >= 4 and len(ref_compact) >= 4:
            if lue_compact in ref_compact or ref_compact in lue_compact:
                return True
            if Levenshtein.distance(lue_compact, ref_compact) <= 2:
                return True

        return False

    @staticmethod
    def _normaliser_plaque(texte: str) -> str:
        texte = texte.strip().upper()
        for ar, lat in SystemeReconnaissance._AR_MAP.items():
            texte = texte.replace(ar, lat)
        texte = texte.replace("|", "-").replace("/", "-").replace("_", "-")
        texte = re.sub(r'[^A-Z0-9\-\s]', '', texte)
        texte = re.sub(r'[\s]+', '-', texte)
        texte = re.sub(r'-{2,}', '-', texte).strip('-')
        return texte

    @staticmethod
    def _est_format_complet(texte: str) -> bool:
        return bool(SystemeReconnaissance._PLATE_FULL_RE.match(texte))

    @staticmethod
    def _extraire_composants(texte: str) -> tuple[str, str, str]:
        m = re.search(r'(\d{1,5})-?([A-Z]{1,3})?-?(\d{1,2})?$', texte)
        if m:
            return (m.group(1) or "", m.group(2) or "", m.group(3) or "")

        nums = re.findall(r'\d{1,5}', texte)
        if nums:
            return (nums[0], "", "")
        return ("", "", "")

    @staticmethod
    def _distance_compact(a: str, b: str) -> int:
        aa = re.sub(r'[^A-Z0-9]', '', a)
        bb = re.sub(r'[^A-Z0-9]', '', b)
        if not aa or not bb:
            return 999
        return Levenshtein.distance(aa, bb)

    @staticmethod
    def _resoudre_plaque_attendue(plaque_lue: str, expected_norm: list[str]) -> tuple[Optional[str], int]:
        """
        Associe une lecture (même partielle) à une plaque attendue.
        Retourne (plaque_complete, distance_compacte).
        """
        candidats = []
        for exp in expected_norm:
            if not SystemeReconnaissance.comparer_plaques(plaque_lue, exp):
                continue
            dist = SystemeReconnaissance._distance_compact(
                SystemeReconnaissance._normaliser_plaque(plaque_lue),
                exp,
            )
            candidats.append((dist, exp))

        if not candidats:
            return None, 999

        candidats.sort(key=lambda t: t[0])
        return candidats[0][1], candidats[0][0]
