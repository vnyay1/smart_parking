# vision/tests/test_pipeline.py
import cv2
import numpy as np
import os
import sys
from pathlib import Path
import django

# Permet l'exécution directe: `python vision/tests/test_pipeline.py`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Setup Django pour accéder aux settings si besoin
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from vision.preprocessor import Preprocesseur
from vision.detecteur_plaque import DetecteurPlaque
from vision.lecteur_ocr import LecteurOCR
from vision.reconnaissance import SystemeReconnaissance


def creer_image_test(texte_plaque: str = "12345-A-6") -> np.ndarray:
    """
    Crée une image synthétique de plaque pour les tests
    sans avoir besoin d'une vraie photo.
    """
    # Fond blanc 400x120
    img = np.ones((120, 400, 3), dtype=np.uint8) * 255

    # Bordure noire
    cv2.rectangle(img, (5, 5), (395, 115), (0, 0, 0), 3)

    # Texte de la plaque
    cv2.putText(
        img, texte_plaque,
        (40, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        2.0,
        (0, 0, 0),
        4
    )
    return img


def test_preprocesseur():
    print("\n=== Test Preprocesseur ===")
    img = creer_image_test()
    result = Preprocesseur.preparer(img)
    assert result is not None
    assert len(result.shape) == 2   # image en niveaux de gris
    print("[OK] Preprocesseur")


def test_lecteur_ocr():
    print("\n=== Test LecteurOCR ===")
    img    = creer_image_test("12345-A-6")
    reader = LecteurOCR()
    plaque, confiance = reader.lire(img)
    print(f"  Plaque lue    : {plaque}")
    print(f"  Confiance     : {confiance:.0%}")
    print("[OK] LecteurOCR (resultat peut varier selon l'image)")


def test_comparaison_levenshtein():
    print("\n=== Test comparaison Levenshtein ===")
    # Même plaque
    assert SystemeReconnaissance.comparer_plaques("12345-A-6", "12345-A-6") == True
    # 1 caractère d'erreur — toléré
    assert SystemeReconnaissance.comparer_plaques("12345-B-6", "12345-A-6") == True
    # 2 caractères d'erreur — refusé
    assert SystemeReconnaissance.comparer_plaques("12345-B-7", "12345-A-6") == False
    print("[OK] Levenshtein")


def test_sur_image_reelle(chemin: str):
    """
    Test sur une vraie photo — passer le chemin en argument.
    Usage : python test_pipeline.py ma_plaque.jpg
    """
    print(f"\n=== Test sur image réelle : {chemin} ===")
    systeme = SystemeReconnaissance()
    plaque, confiance = systeme.analyser_image_path(chemin)

    if plaque:
        print(f"  [OK] Plaque detectee : {plaque} (confiance : {confiance:.0%})")
    else:
        print("  [KO] Plaque non detectee")


if __name__ == '__main__':
    test_preprocesseur()
    test_lecteur_ocr()
    test_comparaison_levenshtein()

    # Test sur image réelle si un chemin est passé en argument
    if len(sys.argv) > 1:
        test_sur_image_reelle(sys.argv[1])

    print("\n[OK] Tous les tests passes.")
