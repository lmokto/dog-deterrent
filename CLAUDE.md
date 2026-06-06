# Dog Deterrent System

Sistema de disuasión automática para perro con visión por computadora.
Detecta cuando el perro se acerca al tacho de basura y dispara agua.

## Stack

- Python 3.11+
- YOLOv8 (ultralytics) para detección de objetos
- OpenCV para captura y procesamiento de video
- PyYAML para configuración
- RPi.GPIO + adafruit-servokit (solo en Raspberry Pi)

## Estructura del proyecto

```
dog-deterrent/
├── CLAUDE.md              ← este archivo
├── requirements.txt
├── config/
│   └── settings.yaml      # Configuración central (zona, umbrales, GPIO)
├── logs/
│   └── captures/           # Fotos de alertas automáticas
└── src/
    ├── detector.py         # DogDetector + CameraSource (dual Mac/RPi)
    ├── 01_test_detection.py
    ├── 02_calibrate_zone.py
    └── 03_full_system.py
```

## Entorno

- Desarrollo en macOS con webcam (camera_source: 0)
- Producción en Raspberry Pi 5 + Camera Module 3 + Hailo-8L AI HAT+
- En Mac se simula: GPIO, válvula solenoide, bomba
- El código detecta la plataforma automáticamente (IS_MAC / IS_RPI)

## Comandos

```bash
# Activar entorno virtual
source venv/bin/activate

# Ejecutar tests de detección
python src/01_test_detection.py

# Calibrar zona del tacho
python src/02_calibrate_zone.py

# Sistema completo
python src/03_full_system.py
```

## Convenciones de código

- Python con type hints cuando sea práctico
- Logging con módulo `logging`, no print() para producción
- Configuración centralizada en config/settings.yaml, nunca hardcoded
- Clases con docstrings descriptivas
- Coordenadas de zona siempre normalizadas (0.0 a 1.0)
- GPIO siempre con try/except ImportError para compatibilidad Mac
- Todo archivo nuevo debe funcionar tanto en Mac como en RPi

## Clases COCO relevantes

- 0: person (safety check — no disparar a humanos)
- 15: cat
- 16: dog (objetivo principal)

## Hardware en producción

- Raspberry Pi 5 (8GB) + AI HAT+ (Hailo-8L, 13 TOPS)
- Camera Module 3 (Sony IMX708, 22-pin CSI)
- Módulo relé 2CH con optoacoplador (active LOW)
- Válvula solenoide 12V DC, normalmente cerrada
- Bomba de diafragma 12V (opcional si hay presión de grifo)
- Servos MG996R en bracket pan-tilt 2-DOF con PCA9685

## Patrones importantes

- Cooldown entre disparos (configurable, default 10s)
- Requiere N frames consecutivos antes de disparar (default 3)
- Safety check: si hay persona en zona, NO disparar
- Válvula solenoide es active LOW en la mayoría de relés
- Secuencia: bomba ON → 150ms → válvula ON → burst → válvula OFF → bomba OFF
- PID para tracking pan-tilt: Kp=0.07, Ki=0.015, Kd=0.04 (ajustar)

## Errores comunes a evitar

- No usar cv2.VideoCapture en RPi — usar picamera2 con formato RGB888
- No olvidar GPIO.cleanup() en finally/cleanup
- El cable de cámara RPi 5 va con contactos hacia el Ethernet (inverso a RPi 4)
- Nunca sudo pip install — usar --break-system-packages en RPi OS Bookworm
- Los módulos relé baratos son active LOW (HIGH=off, LOW=on)
