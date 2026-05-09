# vision/download_model.py — à lancer une seule fois
# Ce script télécharge automatiquement le modèle
from ultralytics import YOLO

model = YOLO('yolov8n.pt')  
print("Modèle YOLOv8n téléchargé.")