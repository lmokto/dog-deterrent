#!/usr/bin/env python3
"""
03_full_system.py — Paso 3: Sistema completo (modo simulación en Mac).

Ejecuta el pipeline completo:
  Cámara → YOLO → Zona → Alerta → [Disparo simulado]

En Mac: simula el disparo con sonido y flash visual.
En RPi: activa GPIO real (válvula + bomba).

Controles:
  q       → Salir
  a       → Armar/desarmar sistema
  f       → Disparo manual (test)
  space   → Pausa/reanudar detección
  c       → Captura de pantalla

Uso:
  python src/03_full_system.py
"""
import cv2
import yaml
import time
import os
import sys
import platform
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from detector import DogDetector, CameraSource

# --- Logging ---
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/system.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("DogDeterrent")


# --- Detectar plataforma ---
IS_MAC = platform.system() == "Darwin"
IS_RPI = platform.machine().startswith("aarch64") or os.path.exists(
    "/proc/device-tree/model"
)


class WaterGunSimulator:
    """Simula el disparo en Mac. En RPi, usa GPIO real."""

    def __init__(self, config):
        self.burst_duration = config["fire"]["burst_duration"]
        self.is_firing = False

        if IS_RPI:
            try:
                import RPi.GPIO as GPIO

                self.GPIO = GPIO
                GPIO.setmode(GPIO.BCM)
                self.valve_pin = config["fire"]["valve_gpio_pin"]
                self.pump_pin = config["fire"]["pump_gpio_pin"]
                GPIO.setup(self.valve_pin, GPIO.OUT, initial=GPIO.HIGH)
                GPIO.setup(self.pump_pin, GPIO.OUT, initial=GPIO.HIGH)
                self.hw_available = True
                log.info(f"GPIO inicializado: valve={self.valve_pin}, "
                         f"pump={self.pump_pin}")
            except ImportError:
                self.hw_available = False
        else:
            self.hw_available = False
            log.info("Modo simulación (Mac) — disparo visual + sonido")

    def fire(self):
        """Ejecuta un disparo."""
        self.is_firing = True
        log.warning(f"DISPARANDO! burst={self.burst_duration}s")

        if self.hw_available:
            # RPi: activar hardware real
            self.GPIO.output(self.pump_pin, self.GPIO.LOW)
            time.sleep(0.15)
            self.GPIO.output(self.valve_pin, self.GPIO.LOW)
            time.sleep(self.burst_duration)
            self.GPIO.output(self.valve_pin, self.GPIO.HIGH)
            time.sleep(0.05)
            self.GPIO.output(self.pump_pin, self.GPIO.HIGH)
        else:
            # Mac: simular con sonido del sistema
            if IS_MAC:
                os.system('afplay /System/Library/Sounds/Sosumi.aiff &')
            time.sleep(self.burst_duration)

        self.is_firing = False

    def cleanup(self):
        if self.hw_available:
            self.GPIO.output(self.valve_pin, self.GPIO.HIGH)
            self.GPIO.output(self.pump_pin, self.GPIO.HIGH)
            self.GPIO.cleanup([self.valve_pin, self.pump_pin])


class DogDeterrentSystem:
    """Sistema completo de disuasión."""

    def __init__(self, config_path="config/settings.yaml"):
        # Cargar config
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Componentes
        self.camera = CameraSource(
            source=self.config["camera_source"],
            width=self.config["frame_width"],
            height=self.config["frame_height"],
        )
        self.detector = DogDetector(
            model_path=self.config["model"]["path"],
            confidence=self.config["model"]["confidence"],
            input_size=self.config["model"]["input_size"],
        )
        self.water = WaterGunSimulator(self.config)

        # Zona de exclusión
        self.zone = self.config["zone"]
        log.info(f"Zona de exclusión: {self.zone}")

        # Estado
        self.armed = True
        self.paused = False
        self.consecutive_detections = 0
        self.required_consecutive = self.config["detection"][
            "consecutive_frames_required"
        ]
        self.cooldown = self.config["fire"]["cooldown_seconds"]
        self.last_fire_time = 0
        self.safety_check_person = self.config["detection"][
            "safety_check_person"
        ]

        # Capturas
        self.captures_dir = Path(
            self.config["alerts"].get("captures_dir", "logs/captures")
        )
        self.captures_dir.mkdir(parents=True, exist_ok=True)

        # Estadísticas
        self.stats = {
            "total_detections": 0,
            "zone_intrusions": 0,
            "fires": 0,
            "start_time": time.time(),
        }

        # Visual state
        self.fire_flash_until = 0

    def is_in_zone(self, detection, frame_shape):
        """Verifica si una detección está dentro de la zona."""
        h, w = frame_shape[:2]
        cx, cy = detection["center"]
        nx, ny = cx / w, cy / h

        z = self.zone
        return (z["x_min"] <= nx <= z["x_max"] and
                z["y_min"] <= ny <= z["y_max"])

    def is_in_cooldown(self):
        return (time.time() - self.last_fire_time) < self.cooldown

    def save_capture(self, frame, detection):
        """Guarda foto del momento de la alerta."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.captures_dir / f"alert_{ts}.jpg"

        annotated = frame.copy()
        x1, y1, x2, y2 = detection["bbox"]
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 3)
        cv2.putText(
            annotated, f"ALERTA {ts}",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
        )
        cv2.imwrite(str(path), annotated)
        log.info(f"Captura guardada: {path}")

    def draw_hud(self, frame, fps, inference_ms, detections):
        """Dibuja la interfaz visual sobre el frame."""
        h, w = frame.shape[:2]
        z = self.zone

        # Zona de exclusión
        pt1 = (int(z["x_min"] * w), int(z["y_min"] * h))
        pt2 = (int(z["x_max"] * w), int(z["y_max"] * h))

        dogs_in_zone = any(
            d["class_name"] == "dog" and self.is_in_zone(d, frame.shape)
            for d in detections
        )

        zone_color = (0, 0, 255) if dogs_in_zone else (0, 255, 0)
        overlay = frame.copy()
        cv2.rectangle(overlay, pt1, pt2, zone_color, -1)
        alpha = 0.25 if dogs_in_zone else 0.1
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        cv2.rectangle(frame, pt1, pt2, zone_color, 2)

        zone_label = "ZONA PELIGRO" if dogs_in_zone else "Zona vigilada"
        cv2.putText(frame, zone_label, (pt1[0] + 5, pt1[1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, zone_color, 1)

        # Detecciones
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            name = det["class_name"]
            conf = det["confidence"]

            if name == "dog":
                color = (0, 0, 255)
                in_z = self.is_in_zone(det, frame.shape)
                label = f"DOG {conf:.0%}" + (" [ZONA!]" if in_z else "")
            else:
                color = (255, 200, 0)
                label = f"{name} {conf:.0%}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cx, cy = det["center"]
            cv2.circle(frame, (cx, cy), 4, color, -1)

        # Flash rojo cuando dispara
        if time.time() < self.fire_flash_until:
            red_overlay = frame.copy()
            red_overlay[:] = (0, 0, 255)
            cv2.addWeighted(red_overlay, 0.3, frame, 0.7, 0, frame)
            cv2.putText(frame, "DISPARANDO!", (w // 2 - 100, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

        # Barra de estado superior
        bar_color = (40, 40, 40)
        cv2.rectangle(frame, (0, 0), (w, 85), bar_color, -1)

        # Estado del sistema
        if self.paused:
            status, s_color = "PAUSADO", (200, 200, 0)
        elif not self.armed:
            status, s_color = "DESARMADO", (200, 200, 200)
        elif self.is_in_cooldown():
            remaining = self.cooldown - (time.time() - self.last_fire_time)
            status = f"COOLDOWN {remaining:.0f}s"
            s_color = (0, 200, 255)
        else:
            status, s_color = "ARMADO", (0, 255, 0)

        cv2.putText(frame, status, (10, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, s_color, 2)

        # Métricas
        cv2.putText(
            frame,
            f"FPS: {fps:.0f} | Inf: {inference_ms:.0f}ms | "
            f"Det: {self.consecutive_detections}/{self.required_consecutive}",
            (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1,
        )

        # Estadísticas
        elapsed = time.time() - self.stats["start_time"]
        mins = int(elapsed // 60)
        cv2.putText(
            frame,
            f"Tiempo: {mins}m | Intrusiones: {self.stats['zone_intrusions']}"
            f" | Disparos: {self.stats['fires']}",
            (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1,
        )

        # Controles
        cv2.putText(
            frame,
            "q=salir | a=armar | f=disparo manual | space=pausa | c=captura",
            (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 120, 120), 1,
        )

        # Plataforma
        plat = "Mac (simulacion)" if IS_MAC else "Raspberry Pi"
        cv2.putText(frame, plat, (w - 180, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)

        return frame

    def process_frame(self, frame):
        """Pipeline principal: detectar → evaluar → actuar."""
        if self.paused:
            return frame, False

        # Detectar
        t0 = time.time()
        detections = self.detector.detect(frame)
        inference_ms = (time.time() - t0) * 1000

        dogs = [d for d in detections if d["class_name"] == "dog"]
        persons = [d for d in detections if d["class_name"] == "person"]

        fired = False

        if dogs:
            self.stats["total_detections"] += 1

            for dog in dogs:
                if self.is_in_zone(dog, frame.shape):
                    self.consecutive_detections += 1
                    self.stats["zone_intrusions"] += 1

                    # Safety check: no disparar si hay persona en zona
                    person_in_zone = any(
                        self.is_in_zone(p, frame.shape) for p in persons
                    )
                    if person_in_zone and self.safety_check_person:
                        log.info("Persona en zona — disparo bloqueado")
                        continue

                    # ¿Suficientes frames consecutivos?
                    if (self.consecutive_detections >= self.required_consecutive
                            and self.armed
                            and not self.is_in_cooldown()):

                        log.warning("PERRO EN ZONA PROHIBIDA — DISPARANDO!")

                        # Guardar captura
                        self.save_capture(frame, dog)

                        # Disparar
                        self.water.fire()
                        self.last_fire_time = time.time()
                        self.fire_flash_until = time.time() + 0.5
                        self.consecutive_detections = 0
                        self.stats["fires"] += 1
                        fired = True
                        break
                else:
                    # Perro visible pero fuera de zona
                    self.consecutive_detections = max(
                        0, self.consecutive_detections - 1
                    )
        else:
            # Sin perro: resetear contador
            self.consecutive_detections = 0

        return detections, inference_ms

    def run(self):
        """Bucle principal."""
        log.info("=" * 50)
        log.info("  Dog Deterrent System — INICIADO")
        log.info(f"  Plataforma: {'Mac' if IS_MAC else 'Raspberry Pi'}")
        log.info(f"  Armado: {self.armed}")
        log.info("=" * 50)

        frame_count = 0
        fps = 0
        fps_start = time.time()

        window = "Dog Deterrent System"

        try:
            while True:
                ret, frame = self.camera.read()
                if not ret:
                    log.error("Error leyendo cámara")
                    continue

                # Procesar
                detections, inference_ms = self.process_frame(frame)
                if isinstance(detections, type(frame)):
                    # Pausa: detections es el frame sin procesar
                    detections = []
                    inference_ms = 0

                # FPS
                frame_count += 1
                if frame_count % 15 == 0:
                    fps = frame_count / (time.time() - fps_start)

                # Dibujar HUD
                display = self.draw_hud(frame, fps, inference_ms, detections)

                # Mostrar
                cv2.imshow(window, display)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break
                elif key == ord("a"):
                    self.armed = not self.armed
                    status = "ARMADO" if self.armed else "DESARMADO"
                    log.info(f"Sistema {status}")
                elif key == ord("f"):
                    log.info("Disparo manual")
                    self.water.fire()
                    self.fire_flash_until = time.time() + 0.5
                    self.stats["fires"] += 1
                elif key == ord(" "):
                    self.paused = not self.paused
                    log.info(f"{'PAUSADO' if self.paused else 'REANUDADO'}")
                elif key == ord("c"):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    path = self.captures_dir / f"manual_{ts}.jpg"
                    cv2.imwrite(str(path), frame)
                    log.info(f"Captura manual: {path}")

        except KeyboardInterrupt:
            log.info("Detenido por usuario (Ctrl+C)")

        finally:
            self.cleanup()

    def cleanup(self):
        """Limpieza al salir."""
        self.camera.release()
        self.water.cleanup()
        cv2.destroyAllWindows()

        # Resumen final
        elapsed = time.time() - self.stats["start_time"]
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)

        log.info("")
        log.info("=" * 50)
        log.info("  RESUMEN DE SESIÓN")
        log.info(f"  Duración: {mins}m {secs}s")
        log.info(f"  Detecciones totales: {self.stats['total_detections']}")
        log.info(f"  Intrusiones en zona: {self.stats['zone_intrusions']}")
        log.info(f"  Disparos ejecutados: {self.stats['fires']}")
        log.info("=" * 50)


def main():
    print()
    print("  🐕 Dog Deterrent System")
    print(f"  Plataforma: {'Mac (simulación)' if IS_MAC else 'Raspberry Pi'}")
    print()

    config_path = "config/settings.yaml"
    if not os.path.exists(config_path):
        print(f"ERROR: No se encontró {config_path}")
        print("Ejecuta primero: python src/02_calibrate_zone.py")
        sys.exit(1)

    system = DogDeterrentSystem(config_path)
    system.run()


if __name__ == "__main__":
    main()
