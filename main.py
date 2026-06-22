#!/usr/bin/env python3
"""
main.py
Prueba directa de hardware: Raspberry Pi -> relé -> válvula/bomba (pistola de agua).

No usa cámara ni YOLO. Solo valida conectividad y activación de relés.

Uso:
  python main.py
  python main.py --config config/settings.yaml --burst 1.0
  python main.py --only valve
  python main.py --only pump
  python main.py --dry-run

Notas:
- Asume relés active LOW (LOW=ON, HIGH=OFF), que es lo habitual en módulos 2CH.
- Lee pines desde config/settings.yaml:
    fire.valve_gpio_pin
    fire.pump_gpio_pin
"""

import argparse
import platform
import sys
import time
from pathlib import Path

import yaml


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_test(valve_pin: int, pump_pin: int, burst: float, only: str, dry_run: bool) -> int:
    is_rpi = platform.machine().startswith("aarch64") or Path("/proc/device-tree/model").exists()
    if not is_rpi:
        print("ERROR: Este script es solo para Raspberry Pi.")
        return 1

    try:
        import RPi.GPIO as GPIO
    except ImportError:
        print("ERROR: No se pudo importar RPi.GPIO. Instálalo en la Raspberry Pi.")
        return 1

    print(f"Usando pines BCM: valve={valve_pin}, pump={pump_pin}")
    print("Relé active LOW: LOW=ON, HIGH=OFF")
    print(f"Modo: {'DRY-RUN (sin activar pines)' if dry_run else 'REAL'}")

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(valve_pin, GPIO.OUT, initial=GPIO.HIGH)
    GPIO.setup(pump_pin, GPIO.OUT, initial=GPIO.HIGH)

    def set_pin(pin: int, state: int, label: str) -> None:
        txt = "ON" if state == GPIO.LOW else "OFF"
        if dry_run:
            print(f"[DRY-RUN] {label} -> {txt}")
            return
        GPIO.output(pin, state)
        print(f"{label} -> {txt}")

    try:
        if only in ("all", "valve"):
            print("\n1) Test relé válvula (1s)")
            set_pin(valve_pin, GPIO.LOW, "VALVE")
            time.sleep(1.0)
            set_pin(valve_pin, GPIO.HIGH, "VALVE")
            time.sleep(0.7)

        if only in ("all", "pump"):
            print("\n2) Test relé bomba (1s)")
            set_pin(pump_pin, GPIO.LOW, "PUMP")
            time.sleep(1.0)
            set_pin(pump_pin, GPIO.HIGH, "PUMP")
            time.sleep(0.7)

        if only == "all":
            print("\n3) Test cadena completa (bomba -> válvula -> agua)")
            set_pin(pump_pin, GPIO.LOW, "PUMP")
            time.sleep(0.15)
            set_pin(valve_pin, GPIO.LOW, "VALVE")
            time.sleep(burst)
            set_pin(valve_pin, GPIO.HIGH, "VALVE")
            time.sleep(0.05)
            set_pin(pump_pin, GPIO.HIGH, "PUMP")

        print("\nOK: prueba finalizada")
        return 0

    except KeyboardInterrupt:
        print("\nInterrumpido por usuario")
        return 130

    finally:
        # Estado seguro al salir
        try:
            GPIO.output(valve_pin, GPIO.HIGH)
            GPIO.output(pump_pin, GPIO.HIGH)
            GPIO.cleanup([valve_pin, pump_pin])
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prueba Raspberry Pi -> relé -> pistola (válvula/bomba)"
    )
    parser.add_argument("--config", default="config/settings.yaml", help="Ruta del YAML de configuración")
    parser.add_argument("--burst", type=float, default=1.0, help="Duración de agua en prueba completa (segundos)")
    parser.add_argument(
        "--only",
        choices=["all", "valve", "pump"],
        default="all",
        help="Ejecutar solo una parte de la prueba",
    )
    parser.add_argument("--dry-run", action="store_true", help="No activa GPIO, solo imprime acciones")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: No existe {config_path}")
        return 1

    cfg = load_config(config_path)
    fire_cfg = cfg.get("fire", {})

    try:
        valve_pin = int(fire_cfg["valve_gpio_pin"])
        pump_pin = int(fire_cfg["pump_gpio_pin"])
    except KeyError as e:
        print(f"ERROR: Falta clave en config: fire.{e.args[0]}")
        return 1
    except (TypeError, ValueError):
        print("ERROR: Los pines GPIO en config deben ser enteros")
        return 1

    if args.burst <= 0:
        print("ERROR: --burst debe ser > 0")
        return 1

    return run_test(
        valve_pin=valve_pin,
        pump_pin=pump_pin,
        burst=args.burst,
        only=args.only,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
