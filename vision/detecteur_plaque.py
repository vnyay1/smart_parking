import cv2
import numpy as np
from typing import Optional


class DetecteurPlaque:
    """
    Détecte et extrait la zone de la plaque dans une image.
    Approche : contours rectangulaires (robuste sans modèle spécialisé).
    """

    MIN_RATIO = 2.0
    MAX_RATIO = 7.5
    MIN_WIDTH = 60
    MIN_HEIGHT = 20

    @staticmethod
    def detecter(image: np.ndarray) -> Optional[np.ndarray]:
        """
        Retourne l'image recadrée sur la plaque, ou None si non trouvée.
        """
        if image is None or image.size == 0:
            return None

        # On calcule plusieurs candidats puis on choisit la zone la plus exploitable.
        # En pratique, un recadrage trop serré peut faire échouer l'OCR.
        candidats = []
        for detecteur in (DetecteurPlaque._detecter_par_contours, DetecteurPlaque._detecter_par_morphologie):
            zone = detecteur(image)
            if zone is None or zone.size == 0:
                continue
            h, w = zone.shape[:2]
            area = h * w
            candidats.append((area, zone))

        if not candidats:
            return None

        # Conserver le candidat ayant la plus grande zone plausible.
        # Cela évite de couper les caractères quand le contour est trop fin.
        _, meilleure_zone = max(candidats, key=lambda c: c[0])
        return meilleure_zone

    @staticmethod
    def _detecter_par_contours(image: np.ndarray) -> Optional[np.ndarray]:
        gray    = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.bilateralFilter(gray, 11, 17, 17)
        edges   = cv2.Canny(blurred, 30, 200)

        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        # Trier par aire décroissante, garder davantage de candidats.
        # Avec de vraies photos, la bordure de plaque n'est pas toujours dans les 10 premiers.
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:120]

        candidats = []
        for contour in contours:
            perimetre = cv2.arcLength(contour, True)
            approx    = cv2.approxPolyDP(contour, 0.018 * perimetre, True)
            x, y, w, h = cv2.boundingRect(contour)

            ratio = w / max(h, 1)
            if not (DetecteurPlaque.MIN_RATIO < ratio < DetecteurPlaque.MAX_RATIO):
                continue
            if w < DetecteurPlaque.MIN_WIDTH or h < DetecteurPlaque.MIN_HEIGHT:
                continue

            # On priorise les contours quadrilatères mais sans les rendre obligatoires.
            rect_area = w * h
            bonus_quad = 1.2 if len(approx) == 4 else 1.0
            score = rect_area * bonus_quad
            candidats.append((score, x, y, w, h))

        if not candidats:
            return None

        _, x, y, w, h = max(candidats, key=lambda c: c[0])
        return DetecteurPlaque._extraire_avec_marge(image, x, y, w, h)

    @staticmethod
    def _detecter_par_morphologie(image: np.ndarray) -> Optional[np.ndarray]:
        """
        Détection inspirée d'ANPR classique:
        met en évidence du texte sombre sur fond clair, puis cherche un rectangle plausible.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        rect_kern = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
        sq_kern   = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kern)
        grad_x = cv2.Sobel(blackhat, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
        grad_x = np.absolute(grad_x)

        min_val, max_val = float(np.min(grad_x)), float(np.max(grad_x))
        if max_val - min_val < 1e-6:
            return None

        grad_x = (255 * ((grad_x - min_val) / (max_val - min_val))).astype("uint8")
        grad_x = cv2.GaussianBlur(grad_x, (5, 5), 0)
        grad_x = cv2.morphologyEx(grad_x, cv2.MORPH_CLOSE, rect_kern)

        thresh = cv2.threshold(grad_x, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, sq_kern, iterations=2)
        thresh = cv2.erode(thresh, None, iterations=1)
        thresh = cv2.dilate(thresh, None, iterations=1)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        img_h, img_w = image.shape[:2]
        img_area = img_h * img_w
        candidats = []

        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:40]:
            x, y, w, h = cv2.boundingRect(contour)
            ratio = w / max(h, 1)
            area = w * h

            if not (DetecteurPlaque.MIN_RATIO - 0.5 < ratio < DetecteurPlaque.MAX_RATIO):
                continue
            if w < DetecteurPlaque.MIN_WIDTH or h < DetecteurPlaque.MIN_HEIGHT:
                continue
            if area < img_area * 0.01:
                continue

            candidats.append((area, x, y, w, h))

        if not candidats:
            return None

        _, x, y, w, h = max(candidats, key=lambda c: c[0])
        return DetecteurPlaque._extraire_avec_marge(image, x, y, w, h)

    @staticmethod
    def _extraire_avec_marge(image: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
        """Recadre une zone avec une petite marge pour ne pas couper les caractères."""
        marge_x = int(w * 0.04)
        marge_y = int(h * 0.12)

        x1 = max(0, x - marge_x)
        y1 = max(0, y - marge_y)
        x2 = min(image.shape[1], x + w + marge_x)
        y2 = min(image.shape[0], y + h + marge_y)
        return image[y1:y2, x1:x2]

    @staticmethod
    def detecter_avec_yolo(image: np.ndarray, model) -> Optional[np.ndarray]:
        """
        Détection via YOLOv8.
        Utilisé en priorité si un modèle est disponible.
        """
        if image is None or image.size == 0 or model is None:
            return None

        img_h, img_w = image.shape[:2]
        img_area = float(img_h * img_w)

        # Noms de classes probables pour un modèle "license plate" custom
        plate_like_names = {
            "plate", "licence_plate", "license_plate", "number_plate",
            "numberplate", "plaque", "plaque_immatriculation",
        }
        vehicle_like_names = {"car", "truck", "bus", "motorcycle", "train"}

        meilleurs = []
        # Essai en résolution native + agrandie (utile sur petites images)
        for scale in (1.0, 2.0):
            if scale == 1.0:
                src = image
            else:
                src = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

            try:
                results = model(src, verbose=False, conf=0.10)
            except Exception:
                continue

            if not results:
                continue

            result = results[0]
            names = result.names if hasattr(result, "names") else {}
            for box in result.boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0]) if box.cls is not None else -1
                label = str(names.get(cls, "")).lower()
                x1, y1, x2, y2 = map(float, box.xyxy[0])

                if scale != 1.0:
                    x1, y1, x2, y2 = x1 / scale, y1 / scale, x2 / scale, y2 / scale

                x1 = max(0, min(img_w - 1, int(round(x1))))
                y1 = max(0, min(img_h - 1, int(round(y1))))
                x2 = max(0, min(img_w, int(round(x2))))
                y2 = max(0, min(img_h, int(round(y2))))
                w = max(0, x2 - x1)
                h = max(0, y2 - y1)
                if w < 10 or h < 10:
                    continue

                ratio = w / max(h, 1)
                area_ratio = (w * h) / img_area

                # Plaque attendue: zone horizontale pas trop grande.
                looks_like_plate_shape = 2.0 <= ratio <= 8.5 and 0.01 <= area_ratio <= 0.60
                label_is_plate = label in plate_like_names
                label_is_vehicle = label in vehicle_like_names

                if not (label_is_plate or looks_like_plate_shape or label_is_vehicle):
                    continue

                # Si c'est une classe véhicule générique, rejeter les boîtes quasi plein écran.
                if label_is_vehicle and area_ratio > 0.90:
                    continue

                score = conf
                if label_is_plate:
                    score += 0.60
                if looks_like_plate_shape:
                    score += 0.25
                # Préférer les boîtes pas trop grandes (plaque > voiture entière).
                score += max(0.0, 0.20 - area_ratio)

                meilleurs.append((score, x1, y1, w, h))

        if not meilleurs:
            return None

        _, x, y, w, h = max(meilleurs, key=lambda c: c[0])
        return DetecteurPlaque._extraire_avec_marge(image, x, y, w, h)
