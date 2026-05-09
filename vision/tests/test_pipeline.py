import cv2
import numpy as np
import os
import sys
from pathlib import Path

# Ajouter le dossier racine du projet au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from vision.preprocessor import Preprocesseur
from vision.detecteur_plaque import DetecteurPlaque
from vision.lecteur_ocr import LecteurOCR
from vision.reconnaissance import SystemeReconnaissance

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def test_preprocesseur():
    print("\n=== Test Preprocesseur ===")
    img = np.ones((120, 400, 3), dtype=np.uint8) * 255
    cv2.putText(img, "12345-A-6", (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0,0,0), 4)
    result = Preprocesseur.preparer(img)
    assert result is not None and len(result.shape) == 2
    print("✓ Preprocesseur OK")


def test_lecteur_ocr():
    print("\n=== Test LecteurOCR (image synthétique) ===")
    img    = np.ones((120, 400, 3), dtype=np.uint8) * 255
    cv2.putText(img, "12345-A-6", (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0,0,0), 4)
    reader = LecteurOCR()
    plaque, confiance = reader.lire(img)
    print(f"  Plaque lue : {plaque}  |  Confiance : {confiance:.0%}")
    print("✓ LecteurOCR OK")


def test_comparaison_levenshtein():
    print("\n=== Test Levenshtein ===")
    assert SystemeReconnaissance.comparer_plaques("12345-A-6", "12345-A-6") == True
    assert SystemeReconnaissance.comparer_plaques("12345-B-6", "12345-A-6") == True   # 1 erreur OK
    assert SystemeReconnaissance.comparer_plaques("12345-B-7", "12345-A-6") == False  # 2 erreurs KO
    print("✓ Levenshtein OK")


def test_sur_image_reelle(chemin: str):
    """
    Test complet sur une image réelle avec mode debug activé.
    Sauvegarde les images intermédiaires dans vision/debug_output/
    """
    print(f"\n=== Test image réelle : {chemin} ===")

    if not os.path.exists(chemin):
        print(f"✗ Fichier non trouvé : {chemin}")
        return

    # Mode debug=True pour sauvegarder les images intermédiaires
    systeme = SystemeReconnaissance(debug=True)
    plaque, confiance = systeme.analyser_image_path(chemin)

    if plaque:
        print(f"✓ Plaque détectée : {plaque}  |  Confiance : {confiance:.0%}")
    else:
        print("✗ Plaque non détectée")
        print("  → Vérifier les images dans vision/debug_output/ pour diagnostiquer")

    return plaque, confiance


def test_detection_seule(chemin: str):
    """
    Teste uniquement la détection (sans OCR) et affiche la zone détectée.
    Utile pour vérifier si le problème vient de la détection ou de l'OCR.
    """
    print(f"\n=== Test détection seule : {chemin} ===")
    frame = cv2.imread(chemin)
    if frame is None:
        print("✗ Image non lisible")
        return

    zone = DetecteurPlaque.detecter(frame)
    if zone is not None:
        nom = os.path.splitext(os.path.basename(chemin))[0]
        out = f"vision/debug_output/{nom}_detection.jpg"
        os.makedirs("vision/debug_output", exist_ok=True)
        cv2.imwrite(out, zone)
        print(f"✓ Zone détectée sauvegardée : {out}  ({zone.shape[1]}x{zone.shape[0]}px)")
    else:
        print("✗ Aucune zone détectée")


def test_batch(dossier: str):
    """
    Teste toutes les images d'un dossier et affiche un résumé.
    """
    print(f"\n=== Test batch : {dossier} ===")
    extensions = ('.jpg', '.jpeg', '.png')
    images = [f for f in os.listdir(dossier) if f.lower().endswith(extensions)]

    if not images:
        print("Aucune image trouvée.")
        return

    systeme   = SystemeReconnaissance(debug=True)
    resultats = []

    for nom in sorted(images):
        chemin = os.path.join(dossier, nom)
        print(f"\n--- {nom} ---")
        plaque, conf = systeme.analyser_image_path(chemin)
        resultats.append((nom, plaque, conf))

    print("\n" + "="*50)
    print("RÉSUMÉ")
    print("="*50)
    detectees  = [(n, p, c) for n, p, c in resultats if p]
    rate       = len(detectees) / len(resultats) * 100

    for nom, plaque, conf in resultats:
        statut = f"✓  {plaque}  ({conf:.0%})" if plaque else "✗  non détectée"
        print(f"  {nom:<25} {statut}")

    print(f"\nTaux de réussite : {len(detectees)}/{len(resultats)} ({rate:.0f}%)")


if __name__ == '__main__':
    test_preprocesseur()
    test_lecteur_ocr()
    test_comparaison_levenshtein()

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.isdir(arg):
            # Dossier → test batch
            test_batch(arg)
        else:
            # Fichier unique → test complet + détection seule
            test_detection_seule(arg)
            test_sur_image_reelle(arg)
    else:
        print("\nUsage :")
        print("  python vision/tests/test_pipeline.py photos/plaque1.jpg  # une image")
        print("  python vision/tests/test_pipeline.py photos/             # toutes les images")