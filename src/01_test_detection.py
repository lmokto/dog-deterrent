#!/usr/bin/env python3
"""
01_test_detection.py — Paso 1: Verificar detección de perro.

Abre tu webcam y detecta perros en tiempo real.
Muestra bounding boxes y confianza en pantalla.

Controles:
  q     → Salir
  s     → Guardar captura de pantalla
  +/-   → Ajustar confianza mínima

Uso:
  python src/01_test_detection.py
"""
import cv2
import time
import sys
import os

# Añadir directorio src al path
sys.path.insert(0, os.path.dirname(__file__))
from detector import DogDetector, CameraSource


def main():
    print("=" * 50)
    print("  PASO 1: Test de detección de perro")
    print("=" * 50)
    print()
    print("Controles:")
    print("  q     → Salir")
    print("  s     → Guardar captura")
    print("  +/-   → Ajustar confianza")
    print()

    # Inicializar
    camera = CameraSource(source=0, width=640, height=480)
    detector = DogDetector(model_path="yolov8n.pt", confidence=0.5)
    confidence = 0.5

    # Métricas
    frame_count = 0
    fps = 0
    fps_start = time.time()
    dog_detected_count = 0

    print("\nApunta la cámara a tu perro... ¡a ver si lo detecta!")
    print()

    while True:
        ret, frame = camera.read()
        if not ret:
            print("Error leyendo cámara")
            break

        # Detectar
        t0 = time.time()
        detections = detector.detect(frame)
        inference_ms = (time.time() - t0) * 1000

        # Dibujar detecciones
        dogs_this_frame = 0
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            label = det["class_name"]
            conf = det["confidence"]

            if label == "dog":
                color = (0, 0, 255)  # Rojo para perros
                dogs_this_frame += 1
                dog_detected_count += 1
            else:
                color = (255, 200, 0)  # Azul para personas

            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            # Label con fondo
            text = f"{label} {conf:.0%}"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX,
                                          0.6, 1)
            cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw, y1),
                          color, -1)
            cv2.putText(frame, text, (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (255, 255, 255), 1)

            # Centro
            cx, cy = det["center"]
            cv2.circle(frame, (cx, cy), 4, color, -1)

        # FPS counter
        frame_count += 1
        if frame_count % 10 == 0:
            elapsed = time.time() - fps_start
            fps = frame_count / elapsed

        # HUD
        cv2.putText(frame, f"FPS: {fps:.1f} | Inferencia: {inference_ms:.0f}ms",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 255, 0), 2)
        cv2.putText(frame, f"Confianza: {confidence:.0%} (+/- para ajustar)",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (200, 200, 200), 1)

        status = (f"PERRO DETECTADO! ({dogs_this_frame})"
                  if dogs_this_frame > 0
                  else "Buscando perro...")
        status_color = (0, 0, 255) if dogs_this_frame > 0 else (0, 255, 0)
        cv2.putText(frame, status, (10, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

        # Log en terminal
        if dogs_this_frame > 0:
            for det in detections:
                if det["class_name"] == "dog":
                    cx, cy = det["center"]
                    print(f"  PERRO conf={det['confidence']:.0%} "
                          f"centro=({cx},{cy}) "
                          f"[{inference_ms:.0f}ms]")

        # Mostrar
        cv2.imshow("Dog Deterrent - Test Detection (q=salir)", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("s"):
            path = f"logs/captures/test_{int(time.time())}.jpg"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            cv2.imwrite(path, frame)
            print(f"  Captura guardada: {path}")
        elif key == ord("+") or key == ord("="):
            confidence = min(0.95, confidence + 0.05)
            detector.confidence = confidence
            print(f"  Confianza: {confidence:.0%}")
        elif key == ord("-"):
            confidence = max(0.1, confidence - 0.05)
            detector.confidence = confidence
            print(f"  Confianza: {confidence:.0%}")

    # Cleanup
    camera.release()
    cv2.destroyAllWindows()

    print()
    print("=" * 50)
    print(f"  Resumen: {dog_detected_count} detecciones de perro")
    print(f"  FPS promedio: {fps:.1f}")
    print("=" * 50)

    if dog_detected_count > 0:
        print("\n  ✅ ¡Funciona! Tu cámara detecta al perro.")
        print("  Siguiente paso: python src/02_calibrate_zone.py")
    else:
        print("\n  ❌ No se detectó ningún perro.")
        print("  Tips:")
        print("  - Asegúrate de que el perro esté visible")
        print("  - Baja la confianza con '-'")
        print("  - Prueba con más luz")


if __name__ == "__main__":
    main()
