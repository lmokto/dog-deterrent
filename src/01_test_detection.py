#!/usr/bin/env python3
"""
01_test_detection.py — Paso 1: Verificar detección de perro.

Controles (modo normal con ventana):
  q     → Salir
  s     → Guardar captura de pantalla
  +/-   → Ajustar confianza mínima

Modo headless (SSH sin pantalla):
  Ctrl+C → Salir
  Guarda frames con detecciones en logs/captures/

Uso:
  python src/01_test_detection.py
  python src/01_test_detection.py --headless
  python src/01_test_detection.py --headless --confidence 0.4
  python src/01_test_detection.py --headless --save-interval 10
"""
import cv2
import time
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(__file__))
from detector import DogDetector, CameraSource


def load_config(config_path):
    try:
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(description="Test de detección de perro")
    parser.add_argument("--headless", action="store_true",
                        help="Sin interfaz gráfica (para SSH sin X11)")
    parser.add_argument("--confidence", type=float, default=None,
                        help="Confianza mínima 0.0-1.0 (override config)")
    parser.add_argument("--save-interval", type=int, default=0,
                        help="Guardar frame cada N segundos en headless (0=solo al detectar perro)")
    parser.add_argument("--config", default="config/settings.yaml")
    args = parser.parse_args()

    # Auto-detect headless: SSH activo sin display disponible
    ssh_active = bool(os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"))
    no_display = not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")
    headless = args.headless or (ssh_active and no_display)

    # Cargar configuración
    config = load_config(args.config)
    camera_source = config.get("camera_source", 0)
    model_cfg = config.get("model", {})
    confidence = args.confidence if args.confidence is not None else model_cfg.get("confidence", 0.5)
    input_size = model_cfg.get("input_size", 640)
    model_path = model_cfg.get("path", "yolov8n.pt")

    print("=" * 50)
    print("  PASO 1: Test de detección de perro")
    print(f"  Modo:    {'HEADLESS (SSH)' if headless else 'VENTANA'}")
    print(f"  Cámara:  {camera_source}")
    print(f"  Modelo:  {model_path}")
    print(f"  Conf:    {confidence:.0%}")
    print("=" * 50)
    print()

    if headless:
        print("Controles: Ctrl+C → Salir")
        if args.save_interval > 0:
            print(f"Guardando frame periódico cada {args.save_interval}s en logs/captures/")
        else:
            print("Guardando frames en logs/captures/ solo cuando detecta perro")
    else:
        print("Controles:")
        print("  q     → Salir")
        print("  s     → Guardar captura")
        print("  +/-   → Ajustar confianza")
    print()

    captures_dir = "logs/captures"
    os.makedirs(captures_dir, exist_ok=True)

    camera = CameraSource(source=camera_source, width=640, height=480)
    detector = DogDetector(model_path=model_path, confidence=confidence,
                           input_size=input_size)

    frame_count = 0
    fps = 0
    fps_start = time.time()
    dog_detected_count = 0
    last_save_time = 0

    print("\nApuntá la cámara al perro... ¡a ver si lo detecta!")
    print()

    try:
        while True:
            ret, frame = camera.read()
            if not ret:
                print("Error leyendo cámara")
                break

            t0 = time.time()
            detections = detector.detect(frame)
            inference_ms = (time.time() - t0) * 1000

            dogs_this_frame = 0
            for det in detections:
                x1, y1, x2, y2 = det["bbox"]
                label = det["class_name"]
                conf = det["confidence"]
                color = (0, 0, 255) if label == "dog" else (255, 200, 0)

                if label == "dog":
                    dogs_this_frame += 1
                    dog_detected_count += 1

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                text = f"{label} {conf:.0%}"
                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw, y1), color, -1)
                cv2.putText(frame, text, (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                cx, cy = det["center"]
                cv2.circle(frame, (cx, cy), 4, color, -1)

            frame_count += 1
            if frame_count % 10 == 0:
                fps = frame_count / (time.time() - fps_start)

            if dogs_this_frame > 0:
                for det in detections:
                    if det["class_name"] == "dog":
                        cx, cy = det["center"]
                        print(f"  PERRO conf={det['confidence']:.0%} "
                              f"centro=({cx},{cy}) [{inference_ms:.0f}ms]")

            now = time.time()

            if headless:
                # Guardar frame inmediatamente al detectar perro
                if dogs_this_frame > 0:
                    path = f"{captures_dir}/detect_{int(now)}.jpg"
                    cv2.imwrite(path, frame)
                    print(f"  → Captura guardada: {path}")

                # Guardar frame periódico para monitoreo visual
                if args.save_interval > 0 and (now - last_save_time) >= args.save_interval:
                    path = f"{captures_dir}/live_{int(now)}.jpg"
                    cv2.imwrite(path, frame)
                    print(f"  [live] {path} | FPS={fps:.1f} | Inf={inference_ms:.0f}ms")
                    last_save_time = now

            else:
                cv2.putText(frame, f"FPS: {fps:.1f} | Inferencia: {inference_ms:.0f}ms",
                            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(frame, f"Confianza: {confidence:.0%} (+/- para ajustar)",
                            (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                status = (f"PERRO DETECTADO! ({dogs_this_frame})"
                          if dogs_this_frame > 0 else "Buscando perro...")
                status_color = (0, 0, 255) if dogs_this_frame > 0 else (0, 255, 0)
                cv2.putText(frame, status, (10, 75),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

                cv2.imshow("Dog Deterrent - Test Detection (q=salir)", frame)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break
                elif key == ord("s"):
                    path = f"{captures_dir}/test_{int(now)}.jpg"
                    cv2.imwrite(path, frame)
                    print(f"  Captura guardada: {path}")
                elif key in (ord("+"), ord("=")):
                    confidence = min(0.95, confidence + 0.05)
                    detector.confidence = confidence
                    print(f"  Confianza: {confidence:.0%}")
                elif key == ord("-"):
                    confidence = max(0.1, confidence - 0.05)
                    detector.confidence = confidence
                    print(f"  Confianza: {confidence:.0%}")

    except KeyboardInterrupt:
        print("\nDetenido por usuario (Ctrl+C)")

    finally:
        camera.release()
        if not headless:
            cv2.destroyAllWindows()

    print()
    print("=" * 50)
    print(f"  Resumen: {dog_detected_count} detecciones de perro")
    print(f"  FPS promedio: {fps:.1f}")
    print("=" * 50)

    if dog_detected_count > 0:
        print("\n  Funciona! Tu camara detecta al perro.")
        print("  Siguiente paso: python src/02_calibrate_zone.py")
    else:
        print("\n  No se detecto ningun perro.")
        print("  Tips:")
        print("  - Asegurate de que el perro este visible")
        print("  - Baja la confianza: --confidence 0.3")
        print("  - Proba con mas luz")


if __name__ == "__main__":
    main()
