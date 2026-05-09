import easyocr
import numpy as np
import re
from typing import Optional
from collections import Counter

CHIFFRES_ARABES = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
MOTS_PARASITES  = {'MA', 'MAR', 'MAROC', 'MAI', 'MAL'}


class LecteurOCR:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            print("[OCR] Initialisation reader Latin (fr + en)...")
            cls._instance.reader_latin = easyocr.Reader(['fr', 'en'], gpu=False)
            print("[OCR] Initialisation reader Arabe (ar + en)...")
            cls._instance.reader_arabe = easyocr.Reader(['ar', 'en'], gpu=False)
            print("[OCR] EasyOCR prêt.")
        return cls._instance

    # ─── API publique ────────────────────────────────────────────────────────

    def lire(self, image: np.ndarray) -> tuple[Optional[str], float]:
        """Lecture globale — essaie les deux readers."""
        for reader in [self.reader_latin, self.reader_arabe]:
            try:
                resultats = reader.readtext(image)
                if not resultats:
                    continue
                meilleur = max(resultats, key=lambda r: r[2])
                plaque = self._nettoyer_texte_brut(meilleur[1])
                if plaque:
                    return plaque, meilleur[2]
            except Exception as e:
                print(f"[OCR] Erreur lecteur global : {e}")
        return None, 0.0

    def lire_zones(self, image: np.ndarray) -> tuple[Optional[str], float]:
        """
        Collecte tous les fragments des deux readers,
        tente d'abord un pattern direct, puis une reconstruction intelligente.
        """
        try:
            fragments = []   # (x_pos, texte, confiance)

            for reader in [self.reader_latin, self.reader_arabe]:
                for bbox, texte, conf in reader.readtext(image):
                    if conf > 0.15:
                        x_pos = bbox[0][0]
                        fragments.append((x_pos, texte, conf))

            if not fragments:
                return None, 0.0

            fragments.sort(key=lambda f: f[0])  # gauche → droite

            textes   = [f[1] for f in fragments]
            conf_moy = sum(f[2] for f in fragments) / len(fragments)

            print(f"[OCR] Fragments : {textes}")

            # Essai 1 : chercher le pattern directement dans le texte concaténé
            texte_brut = ' '.join(textes)
            plaque = self._extraire_pattern_direct(texte_brut)
            if plaque:
                print(f"[OCR] Pattern direct → {plaque}")
                return plaque, conf_moy

            # Essai 2 : reconstruction intelligente depuis fragments
            plaque = self._reconstruire_smart(fragments)
            if plaque:
                return plaque, conf_moy

            return None, 0.0

        except Exception as e:
            print(f"[OCR] Erreur zones : {e}")
            return None, 0.0

    # ─── Méthodes privées ────────────────────────────────────────────────────

    @staticmethod
    def _norm(texte: str) -> str:
        """Normalise les chiffres arabes-indics et strip."""
        return texte.translate(CHIFFRES_ARABES).strip()
    
    CARACTERES_INVALIDES_LETTRE = re.compile(r'^[\u060C\u061B\u061F\u0021-\u002F\u003A-\u0040\u005B-\u0060\u007B-\u007E\s]+$')
    # Lettres arabes valides sur plaques marocaines
    LETTRES_ARABES_VALIDES = set('ابتثجحخدذرزسشصضطظعغفقكلمنهويآإأءة')

    @staticmethod
    def _est_lettre_valide(lettre: str) -> bool:
        """
        Vérifie que la lettre extraite est bien une lettre (arabe ou latine)
        et non de la ponctuation ou du bruit OCR.
        """
        if not lettre:
            return False
        # Lettre latine courte
        if re.match(r'^[A-Z]{1,2}$', lettre.upper()):
            return True
        # Chaque caractère doit être une lettre arabe valide
        for c in lettre:
            if c not in LecteurOCR.LETTRES_ARABES_VALIDES:
                return False
        return True

    @staticmethod
    def _extraire_pattern_direct(texte: str) -> Optional[str]:
        t = LecteurOCR._norm(texte)

        # Cas 1 : lettre arabe explicite entre séparateurs
        m = re.search(
            r'(\d{4,5})\s*[\|\-\s]?\s*([\u0600-\u06FF]{1,2})\s*[\|\-\s]?\s*(\d{1,2})',
            t
        )
        if m:
            lettre = m.group(2)
            if LecteurOCR._est_lettre_valide(lettre):
                return f"{m.group(1)}-{lettre}-{m.group(3)}"

        # Cas 2 : lettre latine explicite
        m = re.search(
            r'(\d{4,5})\s*[\|\-\s]\s*([A-Z]{1,2})\s*[\|\-\s]\s*(\d{1,2})',
            t.upper()
        )
        if m and m.group(2) not in MOTS_PARASITES:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        # Cas 3 : ا lue comme | ou 1 ou I
        m = re.search(r'(\d{4,5})([^0-9]{1,5})(\d{1,2})\s*$', t)
        if m:
            sep = m.group(2)
            if re.search(r'[|1Ii/\\l]', sep):
                lettre = LecteurOCR._deviner_lettre_depuis_sep(sep)
                return f"{m.group(1)}-{lettre}-{m.group(3)}"

        # Cas 4 : tout collé
        sans_espaces = re.sub(r'\s+', '', t)
        m = re.match(r'^(\d{5})(\d{1,2})$', sans_espaces)
        if m:
            return f"{m.group(1)}-ا-{m.group(2)}"

        return None

    @staticmethod
    def _deviner_lettre_depuis_sep(sep: str) -> str:
        """
        Tente de deviner la lettre arabe depuis un séparateur mal lu.
        Par défaut retourne ا (la plus commune sur les plaques marocaines).
        """
        sep = sep.strip()
        # و ressemble parfois à 9 ou à un chiffre
        if '9' in sep:
            return 'و'
        # ا est le plus courant quand c'est | ou 1
        return 'ا'

    @staticmethod
    def _reconstruire_smart(fragments: list) -> Optional[str]:
        numeros = []
        lettres = []

        for x_pos, texte, conf in fragments:
            t_norm = LecteurOCR._norm(texte).strip()
            t_up   = t_norm.upper()

            if not t_norm or t_up in MOTS_PARASITES:
                continue

            if re.match(r'^\d+$', t_norm):
                numeros.append((x_pos, t_norm))

            elif re.match(r'^[\u0600-\u06FF]+$', texte.strip()):
                # ← Vérifier que c'est une vraie lettre arabe, pas de la ponctuation
                if LecteurOCR._est_lettre_valide(texte.strip()):
                    lettres.append((x_pos, texte.strip()))

            elif re.match(r'^[A-Z]{1,2}$', t_up) and t_up not in MOTS_PARASITES:
                lettres.append((x_pos, t_up))

            else:
                # Extraire lettres arabes valides uniquement
                arabe_chars = ''.join(
                    c for c in texte if c in LecteurOCR.LETTRES_ARABES_VALIDES
                )
                if arabe_chars:
                    lettres.append((x_pos, arabe_chars))

                chiff = re.findall(r'\d+', t_norm)
                for c in chiff:
                    numeros.append((x_pos, c))

        print(f"[OCR] Numeros: {[n[1] for n in numeros]}  |  Lettres: {[l[1] for l in lettres]}")

        if not numeros:
            return None

        princ_vals = [v for _, v in numeros if 4 <= len(v) <= 5]
        if not princ_vals:
            return None

        principal, _ = Counter(princ_vals).most_common(1)[0]
        x_principal  = min(x for x, v in numeros if v == principal)

        wilaya_droite = [(x, v) for x, v in numeros if 1 <= len(v) <= 2 and x > x_principal]
        wilaya_pool   = wilaya_droite if wilaya_droite else [(x, v) for x, v in numeros if 1 <= len(v) <= 2]

        if not wilaya_pool:
            return None

        wilaya_freq = Counter([v for _, v in wilaya_pool]).most_common()
        wilaya      = wilaya_freq[0][0]
        top_freq    = wilaya_freq[0][1]
        for val, freq in wilaya_freq:
            if freq == top_freq and len(val) == 2:
                wilaya = val
                break

        x_wilaya = min((x for x, v in wilaya_pool if v == wilaya), default=9999)

        lettre_entre = [(x, v) for x, v in lettres if x_principal <= x <= x_wilaya]
        lettre_pool  = lettre_entre if lettre_entre else lettres

        if not lettre_pool:
            # Fallback : aucune lettre trouvée → mettre ا par défaut
            lettre = 'ا'
        else:
            lettre, _ = Counter([v for _, v in lettre_pool]).most_common(1)[0]

        if not LecteurOCR._est_lettre_valide(lettre):
            lettre = 'ا'  # fallback si lettre invalide

        plaque = f"{principal}-{lettre}-{wilaya}"

        if re.match(r'^\d{1,5}-[\u0600-\u06FFA-Z]{1,3}-\d{1,2}$', plaque):
            return plaque

        return None

    @staticmethod
    def _nettoyer_texte_brut(texte: str) -> Optional[str]:
        """Valide un texte brut unique comme plaque."""
        t = LecteurOCR._norm(texte)
        t = re.sub(r'[^\d\u0600-\u06FF\-\s\|A-Za-z]', '', t)
        t = re.sub(r'[\s\|]+', '-', t).strip('-')

        if re.match(r'^\d{1,5}-[\u0600-\u06FF]{1,3}-\d{1,2}$', t):
            return t
        if re.match(r'^\d{1,5}-[A-Z]{1,3}-\d{1,2}$', t.upper()):
            return t.upper()
        return None