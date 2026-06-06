#!/usr/bin/env python3
"""
02_calibrate_zone.py — Paso 2: Calibrar zona de exclusión.

Abre la cámara y te permite definir la zona del tacho de basura
haciendo click en la imagen. La zona se guarda en config/settings.yaml.

Controles:
  Click izquierdo → Definir esquina de la zona (2 clicks)
  r               → Resetear zona
  s               → Guardar zona en config
  q               → Salir

Uso:
  python src/02_calibrate_zone.py
"""
import cv2
import yaml
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from detector import DogDetector, CameraSource


class ZoneCalibrator:
    def __init__(self):
        self.points = []  # Puntos clickeados (normalizados)
        self.zone = None
        self.frame_shape = None

    def on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and self.frame_shape is not None:
            h, w = self.frame_shape[:2]
            nx = round(x / w, 3)
            ny = round(y / h, 3)

            if len(self.points) < 2:
                self.points.append((nx, ny))
                print(f"  Punto {len(self.points)}: ({nx}, {ny})")

                if len(self.points) == 2:
                    p1, p2 = self.points
                    self.zone = {
                        "x_min": min(p1[0], p2[0]),
                        "y_min": min(p1[1], p2[1]),
                        "x_max": max(p1[0], p2[0]),
                        "y_max": max(p1[1], p2[1]),
                    }
                    print(f"\n  Zona definida: {self.zone}")
                    print("  Presiona 's' para guardar, 'r' para resetear")

    def reset(self):
        self.points = []
        self.zone = None
        print("  Zona reseteada. Click en dos esquinas.")

    def draw_zone(self, frame):
        """Dibuja la zona de exclusión en el frame."""
        if not self.zone:
            # Dibujar puntos individuales
            h, w = frame.shape[:2]
            for px, py in self.points:
                cv2.circle(frame, (int(px * w), int(py * h)),
                           6, (0, 0, 255), -1)
            return frame

        h, w = frame.shape[:2]
        z = self.zone
        pt1 = (int(z["x_min"] * w), int(z["y_min"] * h))
        pt2 = (int(z["x_max"] * w), int(z["y_max"] * h))

        # Zona semitransparente
        overlay = frame.copy()
        cv2.rectangle(overlay, pt1, pt2, (0, 0, 255), -1)
        cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)

        # Borde
        cv2.rectangle(frame, pt1, pt2, (0, 0, 255), 2)

        # Label
        cv2.putText(frame, "ZONA PROHIBIDA", (pt1[0] + 5, pt1[1] + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        return frame

    def save_to_config(self, config_path="config/settings.yaml"):
        """Guarda la zona en el archivo de configuración."""
        if not self.zone:
            print("  No hay zona definida. Haz click en 2 esquinas primero.")
            return False

        with open(config_path) as f:
            config = yaml.safe_load(f)

        config["zone"] = self.zone

        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print(f"\n  ✅ Zona guardada en {config_path}:")
        print(f"     x_min: {self.zone['x_min']}")
        print(f"     y_min: {self.zone['y_min']}")
        print(f"     x_max: {self.zone['x_max']}")
        print(f"     y_max: {self.zone['y_max']}")
        return True


def main():
    print("=" * 50)
    print("  PASO 2: Calibrar zona de exclusión")
    print("=" * 50)
    print()
    print("Instrucciones:")
    print("  1. Apunta la cámara a la zona de la cocina")
    print("  2. Click en la esquina SUPERIOR-IZQUIERDA del tacho")
    print("  3. Click en la esquina INFERIOR-DERECHA del tacho")
    print("  4. Presiona 's' para guardar")
    print()
    print("Controles: r=resetear, s=guardar, q=salir")
    print()

    camera = CameraSource(source=0, width=640, height=480)
    detector = DogDetector(model_path="yolov8n.pt", confidence=0.5)
    calibrator = ZoneCalibrator()

    window_name = "Calibrar Zona (click 2 esquinas, s=guardar, q=salir)"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, calibrator.on_mouse)

    while True:
        ret, frame = camera.read()
        if not ret:
            break

        calibrator.frame_shape = frame.shape

        # Detectar perro para verificar zona
        detections = detector.detect(frame)

        # Dibujar detecciones
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            label = det["class_name"]
            conf = det["confidence"]
            color = (0, 0, 255) if label == "dog" else (255, 200, 0)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{label} {conf:.0%}", (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # Verificar si perro está en zona
            if label == "dog" and calibrator.zone:
                h, w = frame.shape[:2]
                cx, cy = det["center"]
                nx, ny = cx / w, cy / h
                z = calibrator.zone

                in_zone = (z["x_min"] <= nx <= z["x_max"] and
                           z["y_min"] <= ny <= z["y_max"])

                status = "EN ZONA!" if in_zone else "fuera"
                s_color = (0, 0, 255) if in_zone else (0, 255, 0)
                cv2.putText(frame, status, (x1, y2 + 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, s_color, 2)

        # Dibujar zona
        frame = calibrator.draw_zone(frame)

        # Instrucciones en pantalla
        if not calibrator.zone:
            n_points = len(calibrator.points)
            if n_points == 0:
                hint = "Click esquina SUPERIOR-IZQUIERDA del tacho"
            else:
                hint = "Click esquina INFERIOR-DERECHA del tacho"
            cv2.putText(frame, hint, (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        else:
            cv2.putText(frame, "Zona OK. 's'=guardar, 'r'=resetear",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 255, 0), 2)

        cv2.imshow(window_name, frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("r"):
            calibrator.reset()
        elif key == ord("s"):
            if calibrator.save_to_config():
                print("\n  Siguiente paso: python src/03_full_system.py")

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
