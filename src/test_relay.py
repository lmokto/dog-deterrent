#!/usr/bin/env python3
"""
test_relay.py — Diagnóstico de conexión RPi 5 → Relé → Pistola de agua

Verifica paso a paso:
  1. DC+ y DC- (alimentación del relé)
  2. IN1 (GPIO 17 → canal 1 → switch gatillo pistola)
  3. Disparo real de la pistola

Cableado:
  RPi pin 2  (5V)      →  DC+  (terminal tornillo relé)
  RPi pin 6  (GND)     →  DC-  (terminal tornillo relé)
  RPi pin 11 (GPIO 17) →  IN1  (terminal tornillo relé)
  Relé NO1             →  patilla A del switch (pistola)
  Relé COM1            →  patilla B del switch (pistola)

Uso:
  python3 src/test_relay.py
"""
import sys
import time
import platform

# ============================================================
# Detectar plataforma
# ============================================================
IS_RPI = platform.machine().startswith("aarch64") or \
         platform.machine().startswith("arm")

if not IS_RPI:
    print("=" * 50)
    print("  ERROR: Ejecuta este script en la Raspberry Pi")
    print(f"  Plataforma detectada: {platform.machine()} {platform.system()}")
    print("=" * 50)
    sys.exit(1)

# ============================================================
# Importar librería GPIO compatible con RPi 5
# ============================================================
GPIO_LIB = None

try:
    from gpiozero import OutputDevice
    GPIO_LIB = "gpiozero"
except ImportError:
    pass

if not GPIO_LIB:
    try:
        import RPi.GPIO as gpio_rpi
        GPIO_LIB = "RPi.GPIO"
    except ImportError:
        pass

if not GPIO_LIB:
    print("ERROR: No se encontró librería GPIO")
    print("Instala: sudo apt install python3-gpiozero")
    sys.exit(1)


# ============================================================
# Controlador del relé (solo canal 1)
# ============================================================
TRIGGER_PIN = 17  # GPIO 17 = pin físico 11

class RelayTester:
    def __init__(self, pin=TRIGGER_PIN):
        self.pin = pin
        if GPIO_LIB == "gpiozero":
            self.relay = OutputDevice(pin, active_high=False,
                                      initial_value=False)
        else:
            gpio_rpi.setmode(gpio_rpi.BCM)
            gpio_rpi.setwarnings(False)
            gpio_rpi.setup(pin, gpio_rpi.OUT, initial=gpio_rpi.HIGH)

    def activate(self):
        if GPIO_LIB == "gpiozero":
            self.relay.on()
        else:
            gpio_rpi.output(self.pin, gpio_rpi.LOW)

    def deactivate(self):
        if GPIO_LIB == "gpiozero":
            self.relay.off()
        else:
            gpio_rpi.output(self.pin, gpio_rpi.HIGH)

    def fire(self, duration=0.3):
        self.activate()
        time.sleep(duration)
        self.deactivate()

    def cleanup(self):
        self.deactivate()
        if GPIO_LIB == "gpiozero":
            self.relay.close()
        else:
            gpio_rpi.cleanup([self.pin])


def ask(question):
    while True:
        resp = input(f"  {question} (s/n): ").strip().lower()
        if resp in ("s", "si", "sí", "y", "yes"):
            return True
        if resp in ("n", "no"):
            return False

def wait(msg="Presiona Enter cuando estés listo..."):
    input(f"  {msg}")


# ============================================================
# Tests
# ============================================================
def main():
    print()
    print("=" * 55)
    print("  DIAGNÓSTICO: RPi 5 → Relé → Pistola de agua")
    print("=" * 55)
    print(f"  Librería GPIO: {GPIO_LIB}")
    print(f"  Pin de disparo: GPIO {TRIGGER_PIN} (pin físico 11)")
    print()
    print("  Cableado esperado:")
    print()
    print("  RPi              Relé           Pistola")
    print("  ─────────────    ──────────     ──────────────")
    print("  pin 2  (5V)  →   DC+")
    print("  pin 6  (GND) →   DC-")
    print("  pin 11 (GP17)→   IN1")
    print("                    NO1       →   patilla A switch")
    print("                    COM1      →   patilla B switch")
    print()
    print("  Referencia GPIO (USB hacia abajo):")
    print()
    print("       ┌──────────────┬──────────────┐")
    print("       │ pin 1  3.3V  │ pin 2  ★ 5V  │ → DC+")
    print("       │ pin 3       │ pin 4        │")
    print("       │ pin 5       │ pin 6  ★ GND │ → DC-")
    print("       │ pin 7       │ pin 8        │")
    print("       │ pin 9       │ pin 10       │")
    print("       │ pin 11 ★GP17│ pin 12       │ → IN1")
    print("       │  ...        │  ...         │")
    print("       └──────────────┴──────────────┘")
    print("                     ↓")
    print("               puertos USB")
    print()

    tester = RelayTester()
    results = {}

    try:
        # ---- TEST 1: Alimentación ----
        print("─" * 55)
        print("  TEST 1: Alimentación del relé (DC+ y DC-)")
        print("─" * 55)
        print()
        print("  Mira el módulo relé. ¿Ves un LED rojo encendido")
        print("  en la placa? Eso indica que recibe alimentación.")
        print()

        if ask("¿Hay un LED encendido en el relé?"):
            print("\n  ✅ Alimentación OK — DC+ y DC- bien conectados")
            results["alimentación"] = "OK"
        else:
            print("\n  ❌ Sin alimentación. Revisa:")
            print("     1. Cable pin 2 (5V) bien atornillado a DC+")
            print("     2. Cable pin 6 (GND) bien atornillado a DC-")
            print("     3. Que no estén invertidos")
            results["alimentación"] = "FALLO"
            if not ask("¿Continuar con los otros tests?"):
                tester.cleanup()
                return
        print()

        # ---- TEST 2: Click del relé ----
        print("─" * 55)
        print("  TEST 2: Señal IN1 (GPIO 17 → relé)")
        print("─" * 55)
        print()
        print("  Voy a activar el relé. Escucha si hace CLICK.")
        print()
        wait()

        print("  Activando...", end=" ", flush=True)
        tester.activate()
        print("ON")
        time.sleep(1)

        click_ok = ask("¿Escuchaste un CLICK en el relé?")
        led_ok = ask("¿Se encendió un LED en el canal 1 del relé?")

        print("\n  Desactivando...", end=" ", flush=True)
        tester.deactivate()
        print("OFF")
        time.sleep(0.3)

        if click_ok:
            print("\n  ✅ Relé responde — IN1 (GPIO 17) funciona")
            results["señal IN1"] = "OK"
        else:
            print("\n  ❌ Sin click. Revisa:")
            print("     1. Cable pin 11 (GPIO 17) atornillado a IN1")
            print("     2. Jumpers amarillos en posición LOW")
            results["señal IN1"] = "FALLO"
            if not ask("¿Continuar?"):
                tester.cleanup()
                return
        print()

        # ---- TEST 3: Pistola conectada ----
        print("─" * 55)
        print("  TEST 3: Conexión relé → pistola")
        print("─" * 55)
        print()
        print("  ⚠️  ASEGÚRATE de que:")
        print("     - La pistola tiene batería cargada")
        print("     - La pistola está encendida (switch ON)")
        print("     - El depósito tiene agua (o está vacío para test)")
        print("     - NO apuntas a nada que se pueda mojar")
        print()
        wait("Presiona Enter cuando la pistola esté lista...")

        print("\n  Activando relé por 0.5 segundos...")
        print("  (Si la pistola está conectada, debería disparar)")
        print()
        tester.fire(duration=0.5)

        if ask("¿La pistola disparó (escuchaste motor o salió agua)?"):
            print("\n  ✅ ¡Pistola funciona! Conexión completa OK")
            results["pistola"] = "OK"
        else:
            print("\n  ❌ La pistola no disparó. Revisa:")
            print("     1. Cables NO1 y COM1 soldados/conectados al switch")
            print("     2. Que la pistola esté encendida y con batería")
            print("     3. Prueba apretar el gatillo manualmente")
            print("        (si manual tampoco funciona, es la pistola)")
            results["pistola"] = "FALLO"
        print()

        # ---- TEST 4: Ráfaga ----
        if results.get("pistola") == "OK":
            print("─" * 55)
            print("  TEST 4: Ráfaga de disparos (simula sistema real)")
            print("─" * 55)
            print()
            print("  Voy a hacer 3 disparos cortos de 0.3 segundos")
            print("  con 0.5 segundos de pausa entre cada uno.")
            print()
            wait("¿Listo? Enter para disparar ráfaga...")

            for i in range(3):
                print(f"  💦 Disparo {i+1}/3", flush=True)
                tester.fire(duration=0.3)
                time.sleep(0.5)

            if ask("¿Se ejecutaron los 3 disparos correctamente?"):
                print("\n  ✅ Ráfaga OK — sistema listo para producción")
                results["ráfaga"] = "OK"
            else:
                print("\n  ⚠️  Ráfaga parcial. Puede ser normal si los")
                print("     disparos son muy rápidos para la bomba.")
                results["ráfaga"] = "PARCIAL"
            print()

        # ---- TEST 5: Duración configurable ----
        if results.get("pistola") == "OK":
            print("─" * 55)
            print("  TEST 5: Ajuste de duración del chorro")
            print("─" * 55)
            print()
            print("  Prueba diferentes duraciones para encontrar")
            print("  la ideal para tu perro (0.2s corto → 1.0s largo)")
            print()

            while True:
                try:
                    dur = input("  Duración en segundos (0.2-2.0, q=salir): ")
                    if dur.strip().lower() == "q":
                        break
                    dur = float(dur)
                    if 0.1 <= dur <= 3.0:
                        print(f"  💦 Disparando {dur}s...", flush=True)
                        tester.fire(duration=dur)
                        print("  Listo.")
                    else:
                        print("  Usa un valor entre 0.1 y 3.0")
                except ValueError:
                    print("  Escribe un número (ej: 0.5)")
            print()

        # ---- RESUMEN ----
        print("=" * 55)
        print("  RESUMEN DEL DIAGNÓSTICO")
        print("=" * 55)
        print()
        all_ok = all(v == "OK" for v in results.values())

        for test, result in results.items():
            icon = "✅" if result == "OK" else "⚠️ " if result == "PARCIAL" else "❌"
            print(f"  {icon} {test}: {result}")

        print()
        if all_ok:
            print("  🎉 ¡Todo funciona! Tu sistema está listo.")
            print()
            print("  Siguiente paso:")
            print("    1. Cierra la pistola con los cables saliendo")
            print("    2. Ejecuta el sistema completo:")
            print("       python3 src/03_full_system.py")
            print("    3. Acerca tu perro al tacho y observa 💦")
        else:
            print("  Revisa las conexiones de los tests que fallaron")
            print("  y vuelve a ejecutar: python3 src/test_relay.py")
        print()

    except KeyboardInterrupt:
        print("\n\n  Interrumpido.")
    finally:
        tester.cleanup()
        print("  GPIO limpiado. Test terminado.")


if __name__ == "__main__":
    main()