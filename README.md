# Dog Deterrent System — Desarrollo en Mac

Sistema de disuasión automática para perro con visión por computadora.
Desarrolla y prueba en tu Mac con webcam, luego despliega en Raspberry Pi 5.

## Setup rápido (Mac)

```bash
# 1. Crear entorno virtual
cd dog-deterrent
python3 -m venv venv
source venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Test rápido: ¿detecta a tu perro?
python src/01_test_detection.py

# 4. Calibrar zona del tacho de basura
python src/02_calibrate_zone.py

# 5. Sistema completo (modo simulación)
python src/03_full_system.py
```

## Estructura

```
dog-deterrent/
├── README.md
├── requirements.txt
├── config/
│   └── settings.yaml        # Configuración (zona, umbrales)
├── logs/
│   └── captures/             # Fotos de alertas
└── src/
    ├── 01_test_detection.py  # Paso 1: verificar detección
    ├── 02_calibrate_zone.py  # Paso 2: definir zona prohibida
    ├── 03_full_system.py     # Paso 3: sistema completo
    └── detector.py           # Módulo de detección reutilizable
```

## Migrar a Raspberry Pi

El código está diseñado para funcionar en ambos entornos.
Al mover a la RPi, solo cambia la fuente de video en settings.yaml:

```yaml
# Mac (webcam)
camera_source: 0

# Raspberry Pi (picamera2)
camera_source: "picamera2"
```

El sistema detecta automáticamente si estás en Mac o RPi.
