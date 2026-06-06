"""
detector.py — Módulo de detección reutilizable.
Funciona en Mac (webcam) y Raspberry Pi (picamera2).
"""
from ultralytics import YOLO
import cv2
import sys
import time


# Clases COCO relevantes para el proyecto
COCO_CLASSES = {
    0: "person",
    15: "cat",
    16: "dog",
    24: "backpack",   # A veces detecta mochilas como "objetos"
    26: "handbag",
    28: "suitcase",
}


class DogDetector:
    """Detector de perros (y personas) usando YOLOv8."""

    def __init__(self, model_path="yolov8n.pt", confidence=0.5,
                 input_size=640):
        print(f"Cargando modelo {model_path}...")
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.input_size = input_size
        # Solo detectar perros y personas
        self.target_classes = [0, 16]  # person + dog
        print(f"Modelo cargado. Clases objetivo: person, dog")

    def detect(self, frame):
        """
        Detecta objetos en un frame.
        Returns: lista de detecciones con formato:
            {class_name, class_id, confidence, bbox, center, area}
        """
        results = self.model(
            frame,
            conf=self.confidence,
            imgsz=self.input_size,
            classes=self.target_classes,
            verbose=False
        )[0]

        detections = []
        for box in results.boxes:
            class_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            detections.append({
                "class_name": COCO_CLASSES.get(class_id, f"cls_{class_id}"),
                "class_id": class_id,
                "confidence": conf,
                "bbox": (x1, y1, x2, y2),
                "center": (cx, cy),
                "area": (x2 - x1) * (y2 - y1),
            })

        return detections


class CameraSource:
    """
    Fuente de video compatible Mac/RPi.
    Detecta automáticamente el entorno.
    """

    def __init__(self, source=0, width=640, height=480):
        self.use_picamera = (source == "picamera2")

        if self.use_picamera:
            try:
                from picamera2 import Picamera2
                self.picam = Picamera2()
                config = self.picam.create_preview_configuration(
                    main={"size": (width, height), "format": "RGB888"}
                )
                self.picam.configure(config)
                self.picam.start()
                time.sleep(2)  # Warm-up
                print("Cámara: Picamera2 (Raspberry Pi)")
            except ImportError:
                print("ERROR: picamera2 no disponible.")
                print("¿Estás en Mac? Usa camera_source: 0 en settings.yaml")
                sys.exit(1)
        else:
            self.cap = cv2.VideoCapture(int(source))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            if not self.cap.isOpened():
                print(f"ERROR: No se pudo abrir la cámara {source}")
                print("Tips:")
                print("  - ¿Tienes webcam conectada?")
                print("  - ¿Diste permiso de cámara a Terminal?")
                print("    (System Settings > Privacy > Camera > Terminal)")
                sys.exit(1)
            print(f"Cámara: OpenCV webcam (source={source})")

    def read(self):
        """Captura un frame. Returns: (success, frame)"""
        if self.use_picamera:
            frame = self.picam.capture_array()
            return True, frame
        else:
            return self.cap.read()

    def release(self):
        """Libera la cámara."""
        if self.use_picamera:
            self.picam.stop()
        else:
            self.cap.release()
