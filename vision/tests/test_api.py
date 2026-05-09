# vision/tests/test_api.py
import requests
import base64
import cv2
import numpy as np
import sys


def image_vers_base64(chemin: str) -> str:
    with open(chemin, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def image_numpy_vers_base64(img: np.ndarray) -> str:
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')


def tester_endpoint(image_b64: str, url: str = 'http://localhost:8000/api/detect/'):
    print(f"\n=== Test endpoint {url} ===")
    response = requests.post(url, json={'image': image_b64})
    print(f"  Status  : {response.status_code}")
    print(f"  Réponse : {response.json()}")
    return response.json()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Image réelle passée en argument
        b64 = image_vers_base64(sys.argv[1])
    else:
        # Image synthétique de test
        img = np.ones((120, 400, 3), dtype=np.uint8) * 255
        cv2.putText(img, "12345-A-6", (40, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0,0,0), 4)
        b64 = image_numpy_vers_base64(img)

    tester_endpoint(b64)