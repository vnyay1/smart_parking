# vision/lecteur_ocr.py
import easyocr
import numpy as np
import re
import os
import sys
from typing import Optional


class LecteurOCR:
    """
    Lit le texte d'une image de plaque via EasyOCR.
    Singleton : le reader est initialisé une seule fois (lourd en mémoire).
    """

    _instance = None
    _PLATE_FULL_RE = re.compile(r'^\d{1,5}-[A-Z]{1,3}-\d{1,2}$')
    _OCR_ALLOWLIST = (
        "0123456789"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "-|/ _"
        "أابدهوطي"
        "٠١٢٣٤٥٦٧٨٩"
        "۰۱۲۳۴۵۶۷۸۹"
    )

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialisation unique — prend ~10 secondes au premier appel
            print("[OCR] Initialisation EasyOCR (premiere fois, ~10 sec)...")
            os.environ.setdefault("PYTHONIOENCODING", "utf-8")
            if hasattr(sys.stdout, "reconfigure"):
                try:
                    sys.stdout.reconfigure(encoding="utf-8")
                except Exception:
                    pass

            # Plaques marocaines: lettre arabe centrale => modèle ar+en prioritaire.
            try:
                cls._instance.reader = easyocr.Reader(['ar', 'en'], gpu=False)
            except Exception as err:
                print(f"[OCR] Mode ar/en indisponible ({err}), fallback fr/en.")
                cls._instance.reader = easyocr.Reader(['fr', 'en'], gpu=False)
            print("[OCR] EasyOCR pret.")
        return cls._instance

    def lire(self, image: np.ndarray) -> tuple[Optional[str], float]:
        """
        Retourne (texte_plaque, score_confiance) ou (None, 0.0) si échec.
        """
        try:
            resultats = self._lire_ocr_multi_pass(image)
            if not resultats:
                return None, 0.0

            candidats = self._extraire_candidats(resultats)
            if not candidats:
                return None, 0.0

            meilleur_partiel: tuple[Optional[str], float] = (None, 0.0)
            for texte, confiance in candidats:
                plaque = self._nettoyer(texte)
                if not plaque:
                    continue

                if self._est_format_complet(plaque):
                    return plaque, float(confiance)

                # Garder le meilleur partiel en fallback (ex: "65528")
                if float(confiance) > meilleur_partiel[1]:
                    meilleur_partiel = (plaque, float(confiance))

            return meilleur_partiel if meilleur_partiel[0] else (None, 0.0)

        except Exception as e:
            print(f"[OCR] Erreur lecture : {e}")
            return None, 0.0

    def _lire_ocr_multi_pass(self, image: np.ndarray) -> list:
        """
        Applique plusieurs réglages OCR.
        L'allowlist réduit les caractères parasites pour les plaques.
        """
        essais = [
            {
                "allowlist": self._OCR_ALLOWLIST,
                "decoder": "beamsearch",
                "detail": 1,
                "paragraph": False,
                "contrast_ths": 0.05,
                "adjust_contrast": 0.7,
            },
            {
                "allowlist": self._OCR_ALLOWLIST,
                "decoder": "greedy",
                "detail": 1,
                "paragraph": False,
                "rotation_info": [90, 270],
            },
            {
                "detail": 1,
                "paragraph": False,
            },
        ]

        tout = []
        for params in essais:
            try:
                res = self.reader.readtext(image, **params)
                if res:
                    tout.extend(res)
            except Exception:
                continue
        return tout

    @staticmethod
    def _extraire_candidats(resultats: list) -> list[tuple[str, float]]:
        """
        Construit des chaînes candidates depuis les sorties EasyOCR.
        - textes individuels
        - concaténation gauche→droite (quand la plaque est coupée en blocs)
        """
        candidats: dict[str, float] = {}
        elements_ordonnes = []

        for item in resultats:
            if len(item) < 3:
                continue
            bbox, texte, confiance = item[0], str(item[1]), float(item[2])
            if not texte.strip():
                continue

            prev = candidats.get(texte, 0.0)
            if confiance > prev:
                candidats[texte] = confiance

            try:
                x = float(min(pt[0] for pt in bbox))
                elements_ordonnes.append((x, texte, confiance))
            except Exception:
                continue

        # Concaténation prudente: utile seulement quand la plaque est fragmentée
        # en quelques morceaux fiables. Evite les faux positifs issus de texte de fond.
        if elements_ordonnes:
            fiables = [
                (x, t.strip(), c)
                for x, t, c in elements_ordonnes
                if t.strip() and c >= 0.45 and len(t.strip()) <= 10
            ]
            fiables.sort(key=lambda t: t[0])
            if 1 < len(fiables) <= 3:
                joint = "-".join(t[1] for _, t, _ in fiables)
                candidats[joint] = max(c for _, _, c in fiables)

        tries = sorted(candidats.items(), key=lambda kv: kv[1], reverse=True)
        return [(txt, conf) for txt, conf in tries]

    @staticmethod
    def _nettoyer(texte: str) -> Optional[str]:
        """
        Nettoie et normalise le texte OCR au format plaque marocaine.
        Exemples : '12345 A 6' → '12345-A-6', '12345-a-6' → '12345-A-6'
        """
        # Normaliser quelques lettres arabes fréquentes sur les plaques marocaines
        map_ar_to_lat = {
            "أ": "A",
            "ا": "A",
            "ب": "B",
            "د": "D",
            "ه": "H",
            "و": "W",
            "ط": "T",
            "ي": "Y",
            "٠": "0",
            "١": "1",
            "٢": "2",
            "٣": "3",
            "٤": "4",
            "٥": "5",
            "٦": "6",
            "٧": "7",
            "٨": "8",
            "٩": "9",
            "۰": "0",
            "۱": "1",
            "۲": "2",
            "۳": "3",
            "۴": "4",
            "۵": "5",
            "۶": "6",
            "۷": "7",
            "۸": "8",
            "۹": "9",
        }
        for ar, lat in map_ar_to_lat.items():
            texte = texte.replace(ar, lat)

        # Uniformiser séparateurs fréquents reconnus par OCR
        texte = texte.replace("|", "-").replace("/", "-").replace("_", "-")

        # Supprimer les caractères indésirables, garder chiffres/lettres/tirets/espaces
        texte = re.sub(r'[^A-Za-z0-9\-\s]', '', texte).strip().upper()

        # Remplacer les espaces multiples ou simples par un tiret
        texte = re.sub(r'[\s]+', '-', texte)
        texte = re.sub(r'-{2,}', '-', texte).strip('-')

        # Valider le format final : 12345-A-6
        if LecteurOCR._est_format_complet(texte):
            return texte

        # Cas OCR compacté sans séparateurs: 12345A6
        m = re.search(r'(\d{1,5})\s*-?\s*([A-Z]{1,3})\s*-?\s*(\d{1,2})', texte)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        # Tentative de reconstruction si le format est proche
        parties = texte.split('-')
        if len(parties) == 3:
            p1 = re.sub(r'[^0-9]', '', parties[0])
            p2 = re.sub(r'[^A-Z]', '', parties[1])
            p3 = re.sub(r'[^0-9]', '', parties[2])
            reconstruit = f"{p1}-{p2}-{p3}"
            if LecteurOCR._est_format_complet(reconstruit):
                return reconstruit

        # Fallback partiel: garder un numéro principal pour la comparaison
        chiffres = re.findall(r'\d{4,5}', texte)
        if chiffres:
            return chiffres[0]

        return None  # format non reconnu

    @staticmethod
    def _est_format_complet(texte: str) -> bool:
        return bool(LecteurOCR._PLATE_FULL_RE.match(texte))
