#!/usr/bin/env python3
"""
test_relay.py — Diagnóstico de conexión RPi 5 → Módulo relé SONGLE

Verifica paso a paso que cada cable está bien conectado:
  1. DC+ y DC- (alimentación del relé)
  2. IN1 (GPIO 17 → canal 1, válvula)
  3. IN2 (GPIO 27 → canal 2, bomba)

Requisitos:
  - Ejecutar en la Raspberry Pi 5
  - Cables conectados: 5V→DC+, GND→DC-, GPIO17→IN1, GPIO27→IN2
  - Jumpers del relé en posición LOW

Uso:
  python3 test_relay.py

Qué buscar:
  - LED rojo en el relé = DC+ y DC- bien conectados
  - Click audible = IN1 o IN2 funcionando
  - LED del canal encendido = relé activado
"""
import sys
import time
import platform

# ============================================================
# Detectar plataforma y librería GPIO disponible
# ============================================================
IS_RPI = platform.machine().startswith("aarch64") or \
         platform.machine().startswith("arm")

if not IS_RPI:
    print("=" * 50)
    print("  ERROR: Este script debe ejecutarse en la Raspberry Pi")
    print("  Estás en:", platform.machine(), platform.system())
    print("=" * 50)
    sys.exit(1)

# Intentar importar librería GPIO compatible con RPi 5
GPIO_LIB = None
gpio = None

try:
    from gpiozero import OutputDevice
    GPIO_LIB = "gpiozero"
    print("  Librería: gpiozero (recomendada para RPi 5)")
except ImportError:
    pass

if not GPIO_LIB:
    try:
        import RPi.GPIO as gpio_rpi
        GPIO_LIB = "RPi.GPIO"
        gpio = gpio_rpi
        print("  Librería: RPi.GPIO")
    except ImportError:
        pass

if not GPIO_LIB:
    print("ERROR: No se encontró librería GPIO")
    print("Instala una:")
    print("  sudo apt install python3-gpiozero")
    print("  pip install RPi.GPIO --break-system-packages")
    sys.exit(1)


# ============================================================
# Funciones de control según librería
# ============================================================
class RelayTester:
    """Controlador de relé compatible con gpiozero y RPi.GPIO."""

    def __init__(self, pin_in1=17, pin_in2=27):
        self.pin_in1 = pin_in1
        self.pin_in2 = pin_in2

        if GPIO_LIB == "gpiozero":
            # active_high=False porque el relé es active LOW
            self.relay1 = OutputDevice(pin_in1, active_high=False,
                                       initial_value=False)
            self.relay2 = OutputDevice(pin_in2, active_high=False,
                                       initial_value=False)
        else:
            gpio.setmode(gpio.BCM)
            gpio.setwarnings(False)
            # HIGH = relé OFF (active LOW)
            gpio.setup(pin_in1, gpio.OUT, initial=gpio.HIGH)
            gpio.setup(pin_in2, gpio.OUT, initial=gpio.HIGH)

    def activate(self, channel):
        """Activa un relé (channel 1 o 2)."""
        if GPIO_LIB == "gpiozero":
            if channel == 1:
                self.relay1.on()
            else:
                self.relay2.on()
        else:
            pin = self.pin_in1 if channel == 1 else self.pin_in2
            gpio.output(pin, gpio.LOW)

    def deactivate(self, channel):
        """Desactiva un relé."""
        if GPIO_LIB == "gpiozero":
            if channel == 1:
                self.relay1.off()
            else:
                self.relay2.off()
        else:
            pin = self.pin_in1 if channel == 1 else self.pin_in2
            gpio.output(pin, gpio.HIGH)

    def deactivate_all(self):
        """Desactiva ambos relés."""
        self.deactivate(1)
        self.deactivate(2)

    def cleanup(self):
        """Limpieza al salir."""
        self.deactivate_all()
        if GPIO_LIB == "gpiozero":
            self.relay1.close()
            self.relay2.close()
        else:
            gpio.cleanup([self.pin_in1, self.pin_in2])


def ask_yes_no(question):
    """Pregunta sí/no al usuario."""
    while True:
        resp = input(f"  {question} (s/n): ").strip().lower()
        if resp in ("s", "si", "sí", "y", "yes"):
            return True
        if resp in ("n", "no"):
            return False
        print("  Responde 's' o 'n'")


def wait_enter(msg="Presiona Enter cuando estés listo..."):
    """Espera a que el usuario presione Enter."""
    input(f"  {msg}")


# ============================================================
# Tests
# ============================================================
def main():
    print()
    print("=" * 55)
    print("  DIAGNÓSTICO DE CONEXIÓN: RPi 5 → Relé SONGLE")
    print("=" * 55)
    print()
    print("  Pines configurados:")
    print("    GPIO 17 (pin físico 11) → IN1 (canal 1, válvula)")
    print("    GPIO 27 (pin físico 13) → IN2 (canal 2, bomba)")
    print("    5V     (pin físico 2)  → DC+")
    print("    GND    (pin físico 6)  → DC-")
    print()
    print("  Referencia de pines (mirando la RPi con USB abajo):")
    print()
    print("         columna izq    columna der")
    print("       ┌─────────────┬─────────────┐")
    print("       │ pin 1 (3.3V)│ pin 2 (5V)  │ ← DC+")
    print("       │ pin 3 (SDA) │ pin 4 (5V)  │")
    print("       │ pin 5 (SCL) │ pin 6 (GND) │ ← DC-")
    print("       │ pin 7       │ pin 8       │")
    print("       │ pin 9 (GND) │ pin 10      │")
    print("       │ pin 11 GP17 │ pin 12      │ ← IN1")
    print("       │ pin 13 GP27 │ pin 14 (GND)│ ← IN2")
    print("       │  ...        │  ...        │")
    print("       └─────────────┴─────────────┘")
    print("                    ↓")
    print("              puertos USB")
    print()

    tester = RelayTester(pin_in1=17, pin_in2=27)

    try:
        # ---- TEST 1: Alimentación ----
        print("-" * 55)
        print("  TEST 1: Alimentación (DC+ y DC-)")
        print("-" * 55)
        print()
        print("  Mira el módulo relé ahora mismo.")
        print("  ¿Ves algún LED encendido en la placa del relé?")
        print("  (Suele ser un LED rojo pequeño de power)")
        print()

        if ask_yes_no("¿Hay algún LED encendido en el relé?"):
            print("  ✅ DC+ y DC- están bien conectados!")
        else:
            print("  ❌ No hay LED encendido. Posibles causas:")
            print("     - Cable 5V (pin 2) no conectado a DC+")
            print("     - Cable GND (pin 6) no conectado a DC-")
            print("     - Cables al revés (5V en DC- y GND en DC+)")
            print("     - Cable mal atornillado (afloja, reinserta, aprieta)")
            print()
            if not ask_yes_no("¿Quieres continuar con los otros tests?"):
                tester.cleanup()
                return
        print()

        # ---- TEST 2: IN1 (GPIO 17, canal 1) ----
        print("-" * 55)
        print("  TEST 2: Canal 1 — IN1 (GPIO 17 → válvula)")
        print("-" * 55)
        print()
        print("  Voy a activar el relé 1. Deberías escuchar un CLICK")
        print("  y ver un LED encenderse en el relé.")
        print()
        wait_enter()

        print("  Activando relé 1...", end=" ", flush=True)
        tester.activate(1)
        print("ACTIVADO")
        time.sleep(0.5)

        heard_click = ask_yes_no("¿Escuchaste un CLICK en el relé 1 (izquierdo)?")
        saw_led = ask_yes_no("¿Se encendió un LED en el canal 1?")

        print()
        print("  Desactivando relé 1...", end=" ", flush=True)
        tester.deactivate(1)
        print("DESACTIVADO")
        time.sleep(0.3)

        if heard_click and saw_led:
            print("  ✅ IN1 (GPIO 17) funciona perfectamente!")
        elif heard_click and not saw_led:
            print("  ⚠️  Click sí pero LED no. El relé funciona,")
            print("     el LED podría estar fundido (no es problema).")
        elif not heard_click and saw_led:
            print("  ⚠️  LED sí pero click no. Raro. Verifica la conexión.")
        else:
            print("  ❌ IN1 no responde. Posibles causas:")
            print("     - Cable GPIO 17 (pin 11) no conectado a IN1")
            print("     - Jumpers en posición incorrecta (deben estar en LOW)")
            print("     - Cable mal atornillado en el terminal IN1")
        print()

        # ---- TEST 3: IN2 (GPIO 27, canal 2) ----
        print("-" * 55)
        print("  TEST 3: Canal 2 — IN2 (GPIO 27 → bomba)")
        print("-" * 55)
        print()
        print("  Voy a activar el relé 2.")
        print()
        wait_enter()

        print("  Activando relé 2...", end=" ", flush=True)
        tester.activate(2)
        print("ACTIVADO")
        time.sleep(0.5)

        heard_click = ask_yes_no("¿Escuchaste un CLICK en el relé 2 (derecho)?")
        saw_led = ask_yes_no("¿Se encendió un LED en el canal 2?")

        print()
        print("  Desactivando relé 2...", end=" ", flush=True)
        tester.deactivate(2)
        print("DESACTIVADO")
        time.sleep(0.3)

        if heard_click and saw_led:
            print("  ✅ IN2 (GPIO 27) funciona perfectamente!")
        elif heard_click and not saw_led:
            print("  ⚠️  Click sí pero LED no. Relé funciona, LED puede estar fundido.")
        elif not heard_click and saw_led:
            print("  ⚠️  LED sí pero click no. Verifica la conexión.")
        else:
            print("  ❌ IN2 no responde. Posibles causas:")
            print("     - Cable GPIO 27 (pin 13) no conectado a IN2")
            print("     - Jumpers en posición incorrecta")
            print("     - Cable mal atornillado en el terminal IN2")
        print()

        # ---- TEST 4: Ambos simultáneamente ----
        print("-" * 55)
        print("  TEST 4: Ambos relés simultáneamente")
        print("-" * 55)
        print()
        print("  Voy a activar AMBOS relés a la vez.")
        print()
        wait_enter()

        print("  Activando ambos...", end=" ", flush=True)
        tester.activate(1)
        tester.activate(2)
        print("ACTIVADOS")
        time.sleep(1)

        both_ok = ask_yes_no("¿Escuchaste DOS clicks (casi simultáneos)?")

        tester.deactivate_all()
        print("  Desactivados.")
        print()

        if both_ok:
            print("  ✅ Ambos canales funcionan simultáneamente!")
        else:
            print("  ⚠️  Revisa que ambos canales estén conectados.")
        print()

        # ---- TEST 5: Ráfaga rápida (simula disparo) ----
        print("-" * 55)
        print("  TEST 5: Simulación de disparo (ráfaga rápida)")
        print("-" * 55)
        print()
        print("  Voy a hacer 3 disparos rápidos en el relé 1")
        print("  (como haría el sistema con la válvula de agua)")
        print()
        wait_enter()

        for i in range(3):
            print(f"  Disparo {i+1}/3...", end=" ", flush=True)
            tester.activate(1)
            time.sleep(0.3)
            tester.deactivate(1)
            print("click!")
            time.sleep(0.4)

        print()
        burst_ok = ask_yes_no("¿Escuchaste 3 clicks rápidos?")

        if burst_ok:
            print("  ✅ Ráfaga OK! El relé responde a disparos rápidos.")
        else:
            print("  ⚠️  Los clicks no fueron claros. Puede ser normal")
            print("     si los disparos son muy rápidos para tu oído.")
        print()

        # ---- RESUMEN ----
        print("=" * 55)
        print("  RESUMEN DEL DIAGNÓSTICO")
        print("=" * 55)
        print()
        print("  Si todos los tests pasaron:")
        print("  ✅ Tu cableado RPi → Relé está correcto")
        print("  ✅ Siguiente paso: conectar la válvula/pistola")
        print("     al lado de salida (NO y COM)")
        print()
        print("  Si algún test falló:")
        print("  1. Verifica que los jumpers estén en LOW")
        print("  2. Afloja y reaprieta los tornillos del terminal")
        print("  3. Confirma los pines con: pinout (en terminal RPi)")
        print("  4. Prueba intercambiar IN1 ↔ IN2 para descartar")
        print("     un canal dañado")
        print()

    except KeyboardInterrupt:
        print("\n\n  Interrumpido por usuario.")
    finally:
        tester.cleanup()
        print("  GPIO limpiado. Test terminado.")


if __name__ == "__main__":
    main()