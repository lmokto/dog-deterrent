# Arquitectura de Software — Dog Deterrent System

## 1. Visión General

El sistema es un **pipeline de visión por computadora en tiempo real** que:
1. Captura video desde una cámara
2. Detecta perros usando un modelo YOLOv8
3. Evalúa si el perro está dentro de una zona configurada
4. Activa un mecanismo de disuasión (agua) si se cumple la condición
5. En Mac, simula el hardware con sonido y efecto visual; en RPi, activa GPIO real

El diseño prioriza **portabilidad entre plataformas** (macOS y Raspberry Pi) y **separación de responsabilidades** a través de clases cohesivas.

---

## 2. Diagrama de Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────────┐
│                    Dog Deterrent System                     │
│                                                             │
│  ┌──────────────┐     ┌──────────────┐    ┌─────────────┐  │
│  │ CameraSource │────▶│ DogDetector  │───▶│  Zona Logic │  │
│  │  (captura)   │     │  (YOLOv8)    │    │  (is_in_zone│  │
│  └──────────────┘     └──────────────┘    └──────┬──────┘  │
│         │                                         │         │
│  ┌──────┴──────────────────────────────────────── ▼──────┐  │
│  │              DogDeterrentSystem (orquestador)          │  │
│  │  Estado: armed / paused / consecutive_detections       │  │
│  │  Lógica: cooldown / safety_check / N frames           │  │
│  └───────────────────────────────┬────────────────────────┘  │
│                                  │                           │
│              ┌───────────────────┴──────────────┐           │
│              ▼                                  ▼           │
│    ┌──────────────────┐               ┌──────────────────┐  │
│    │ WaterGunSimulator│               │   draw_hud()     │  │
│    │  Mac: afplay     │               │ (OpenCV overlay) │  │
│    │  RPi: GPIO real  │               └──────────────────┘  │
│    └──────────────────┘                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Flujo de datos por frame:
CameraSource.read() ──▶ detector.detect() ──▶ is_in_zone() 
    ──▶ consecutive counter ──▶ fire() ──▶ draw_hud() ──▶ imshow()
```

---

## 3. Estructura de Archivos

```
dog-deterrent/
├── config/
│   └── settings.yaml        ← Única fuente de configuración
├── docs/
│   └── arquitectura.md      ← Este archivo
├── logs/
│   ├── system.log           ← Log de ejecución (generado en runtime)
│   └── captures/            ← Fotos de alertas y capturas manuales
├── src/
│   ├── detector.py          ← Módulo core (DogDetector + CameraSource)
│   ├── 01_test_detection.py ← Paso 1: verificar que el modelo funciona
│   ├── 02_calibrate_zone.py ← Paso 2: calibrar zona gráficamente
│   └── 03_full_system.py    ← Paso 3: sistema completo en producción
├── yolov8n.pt               ← Pesos del modelo YOLO (nano)
└── requirements.txt
```

**Por qué esta estructura:**
- `detector.py` es reutilizado por los tres scripts → núcleo separado
- Los scripts numerados `01_`, `02_`, `03_` expresan el flujo de trabajo del usuario de forma explícita
- Todo el estado mutable de configuración vive en `settings.yaml` → nunca hardcodeado

---

## 4. Módulo `detector.py` — Núcleo Reutilizable

Este módulo es la única dependencia compartida entre todos los scripts. Define dos clases ortogonales: una para **visión** y otra para **cámara**.

### 4.1 Constante `COCO_CLASSES`

```python
COCO_CLASSES = {0: "person", 15: "cat", 16: "dog", ...}
```

Mapa de IDs del dataset COCO a nombres legibles. Se usa para:
- Etiquetar las detecciones en pantalla
- Identificar perros (`id=16`) y personas (`id=0`) en la lógica de disparo

Solo se declaran las clases **relevantes para el dominio del sistema**, no las 80 clases COCO completas.

---

### 4.2 Clase `DogDetector`

**Responsabilidad:** Abstraer el modelo YOLOv8 y exponer una interfaz simple de detección.

| Atributo | Tipo | Descripción |
|---|---|---|
| `model` | `YOLO` | Modelo cargado desde archivo `.pt` |
| `confidence` | `float` | Umbral mínimo de confianza (0.0–1.0) |
| `input_size` | `int` | Tamaño de entrada para inferencia (px) |
| `target_classes` | `list[int]` | Solo detectar `[0 (person), 16 (dog)]` |

#### `__init__(model_path, confidence, input_size)`

Carga el modelo en memoria. La restricción a `target_classes = [0, 16]` es un **filtro en el nivel de inferencia** de YOLO, no en postprocesado. Esto mejora la velocidad porque el modelo descarta clases innecesarias antes de calcular bounding boxes.

#### `detect(frame) → list[dict]`

**Entrada:** Un frame BGR de OpenCV (numpy array H×W×3)  
**Salida:** Lista de diccionarios, uno por objeto detectado:

```python
{
    "class_name":  str,         # "dog" | "person"
    "class_id":    int,         # ID COCO
    "confidence":  float,       # 0.0–1.0
    "bbox":        (x1,y1,x2,y2),  # píxeles absolutos
    "center":      (cx, cy),    # punto central del bbox
    "area":        int,         # ancho*alto en píxeles²
}
```

**Por qué coordenadas absolutas en píxeles aquí:** Los scripts de visualización (OpenCV) trabajan en píxeles. La normalización a 0.0–1.0 ocurre **después**, en la capa de lógica de zona, para que sea independiente de la resolución.

**Por qué `verbose=False`:** YOLO imprime resultados por defecto en stdout. Esto suprime ese ruido para no interferir con los prints del sistema.

---

### 4.3 Clase `CameraSource`

**Responsabilidad:** Proveer una interfaz unificada de captura de video que funcione tanto en Mac (OpenCV webcam) como en Raspberry Pi (picamera2), con el mismo contrato de uso.

| Atributo | Tipo | Descripción |
|---|---|---|
| `use_picamera` | `bool` | `True` si `source == "picamera2"` |
| `picam` | `Picamera2` | Solo en RPi |
| `cap` | `cv2.VideoCapture` | Solo en Mac/webcam |

#### Decisión de diseño — detección de plataforma por parámetro

La clase **no detecta la plataforma automáticamente** (ej: no usa `platform.machine()`). En cambio, la distinción la hace el **valor del parámetro `source`**:
- `source=0` (o cualquier entero) → usar OpenCV
- `source="picamera2"` → usar picamera2

Esto es intencional: permite testear el path de OpenCV también en RPi (conectando una webcam USB), sin que el código asuma nada sobre el hardware.

#### `__init__(source, width, height)`

- **Caso OpenCV:** Llama `cv2.VideoCapture(int(source))` y configura resolución via `CAP_PROP_FRAME_WIDTH/HEIGHT`. Verifica que la cámara se abra exitosamente y aborta con mensaje descriptivo si falla.
- **Caso picamera2:** Importa `Picamera2` dentro del bloque (lazy import) para no romper Mac donde el módulo no existe. Configura formato `RGB888` explícitamente porque OpenCV espera RGB en este path. El `time.sleep(2)` es un **warm-up** necesario: el sensor IMX708 necesita tiempo para estabilizar exposición.

#### `read() → (bool, frame)`

Interfaz idéntica a `cv2.VideoCapture.read()`. Esto permite que todo el código consumer use exactamente el mismo patrón:

```python
ret, frame = camera.read()
```

En picamera2, `capture_array()` siempre tiene éxito (no retorna bool), por lo que `read()` retorna `(True, frame)` hardcodeado.

#### `release()`

Cierra la cámara y libera recursos. En picamera2 llama `.stop()` (no `.release()`).

---

## 5. Script `01_test_detection.py` — Verificación del Modelo

**Propósito:** Validar que el modelo YOLO detecta correctamente en el entorno del usuario antes de pasar a configurar el hardware.

### Función `load_config(config_path)`

Carga el YAML de configuración con manejo silencioso de errores. Si el archivo no existe o está malformado, retorna `{}` (dict vacío), permitiendo que los valores por defecto del argparser tomen control. Esto evita que el script de test falle solo por una configuración incorrecta.

### Función `main()`

**Detección de modo headless automática:**
```python
ssh_active = bool(os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"))
no_display = not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")
headless = args.headless or (ssh_active and no_display)
```

El modo headless se activa automáticamente cuando el sistema detecta que está corriendo via SSH sin X11 forwarding. Esto es crítico para poder ejecutar el script en la RPi desde una laptop sin pantalla conectada.

**Modo normal (con ventana):**
- Renderiza detecciones sobre el frame con `cv2.rectangle` y `cv2.putText`
- Permite ajustar la confianza en tiempo real con `+`/`-`
- Muestra FPS y latencia de inferencia en el frame

**Modo headless (SSH):**
- No llama `cv2.imshow` (que fallaría sin display)
- Guarda frames como JPG en `logs/captures/` cuando detecta un perro
- Opcionalmente guarda un frame periódico cada N segundos para monitoreo visual remoto (flag `--save-interval`)

**Ajuste de confianza en runtime:** El usuario puede cambiar `confidence` con `+`/`-`, y el cambio se aplica directamente en `detector.confidence`. El modelo YOLO re-usa este valor en cada llamada a `detect()` porque lo lee del atributo en cada inferencia.

---

## 6. Script `02_calibrate_zone.py` — Calibración Visual de Zona

**Propósito:** Permitir al usuario definir visualmente la zona de exclusión (donde está el tacho de basura) con dos clicks sobre el frame de la cámara, y persistir esos valores en `settings.yaml`.

### Clase `ZoneCalibrator`

**Responsabilidad:** Manejar el estado de los puntos clickeados y la lógica de dibujo/guardado de la zona.

| Atributo | Tipo | Descripción |
|---|---|---|
| `points` | `list` | Puntos clickeados como coords normalizadas `[(x,y), ...]` |
| `zone` | `dict` | Zona calculada `{x_min, y_min, x_max, y_max}` |
| `frame_shape` | `tuple` | Shape del frame actual, para normalizar coords del mouse |

#### `on_mouse(event, x, y, flags, param)`

Callback registrado en OpenCV via `cv2.setMouseCallback`. Al detectar `EVENT_LBUTTONDOWN`:

1. Normaliza las coordenadas del mouse (`px/w`, `py/h`) a rango 0.0–1.0, redondeando a 3 decimales
2. Acumula en `self.points` hasta tener 2 puntos
3. Con 2 puntos, calcula `zone` usando `min`/`max` para que sea independiente del orden en que se clickeen las esquinas (esquina superior-izquierda primero o inferior-derecha primero, cualquiera funciona)

**Por qué coordenadas normalizadas:** La zona se guarda normalizada para ser independiente de la resolución. Si en producción la cámara RPi usa 1920×1080 y en desarrollo la webcam Mac usa 640×480, la zona sigue siendo válida sin reescalarla.

#### `draw_zone(frame)`

- Si hay 0 o 1 puntos: dibuja círculos rojos en los puntos ya marcados como feedback visual
- Si hay zona completa: dibuja un rectángulo semitransparente (usando `cv2.addWeighted` con alpha=0.2) más el borde sólido y la etiqueta "ZONA PROHIBIDA"

La técnica de superposición semitransparente (`overlay = frame.copy()` → `addWeighted`) es estándar en OpenCV porque la librería no tiene soporte nativo de alpha blending; se hace copiando el frame, pintando sobre la copia, y luego mezclando.

#### `save_to_config(config_path)`

Lee el YAML completo, actualiza solo la clave `zone`, y lo reescribe. Esto preserva todos los demás parámetros de configuración intactos. Usa `default_flow_style=False` para que el YAML resultante sea legible (formato block, no inline).

---

## 7. Script `03_full_system.py` — Sistema Completo en Producción

Este es el script principal. Orquesta todos los componentes y ejecuta el pipeline completo.

### Constantes de plataforma

```python
IS_MAC = platform.system() == "Darwin"
IS_RPI = platform.machine().startswith("aarch64") or \
         os.path.exists("/proc/device-tree/model")
```

Se declaran al nivel de módulo para que toda la lógica condicional de hardware las pueda usar. La detección de RPi usa **dos condiciones** porque `aarch64` también aplica a otras ARM boards, pero `/proc/device-tree/model` es específico de Raspberry Pi.

### Configuración de logging

```python
logging.basicConfig(
    handlers=[
        logging.FileHandler("logs/system.log"),
        logging.StreamHandler(),
    ],
)
```

Log doble: a archivo (`system.log`) y a consola simultáneamente. El archivo permite revisar el historial de disparos y errores sin necesidad de tener la terminal abierta durante la ejecución.

---

### 7.1 Clase `WaterGunSimulator`

**Responsabilidad:** Encapsular el mecanismo de disparo, con implementación real (GPIO) en RPi y simulada en Mac.

| Atributo | Tipo | Descripción |
|---|---|---|
| `burst_duration` | `float` | Duración del chorro en segundos |
| `is_firing` | `bool` | Flag de estado (no usado para sincronizar, solo informativo) |
| `hw_available` | `bool` | Si el GPIO fue inicializado correctamente |
| `valve_pin` | `int` | Pin BCM de la válvula solenoide |
| `pump_pin` | `int` | Pin BCM de la bomba |

#### `__init__(config)`

Detecta `IS_RPI` y hace import condicional de `RPi.GPIO`. Configura ambos pines con `initial=GPIO.HIGH` — esto es crítico porque los relés de optoacoplador baratos son **active LOW** (HIGH = apagado, LOW = encendido). Inicializar en HIGH evita un disparo involuntario al arrancar.

Si la importación de GPIO falla (ej: corriendo en Mac accidentalmente con `IS_RPI=True`), `hw_available = False` y el sistema cae al modo simulado sin abortar.

#### `fire()`

**Secuencia RPi (GPIO real):**
```
pump LOW (on) → 150ms espera → valve LOW (on) → burst_duration → 
valve HIGH (off) → 50ms → pump HIGH (off)
```

**Por qué encender la bomba antes que la válvula:** La bomba necesita presurizar la línea antes de abrir la válvula. Si se abriera primero la válvula sin presión, el flujo sería irregular. Los 150ms son suficientes para que una bomba de diafragma 12V alcance presión.

**Secuencia Mac (simulación):**
- Llama `afplay /System/Library/Sounds/Sosumi.aiff &` (en background con `&` para no bloquear)
- Espera `burst_duration` segundos para simular el tiempo del chorro

#### `cleanup()`

Asegura que ambos pines queden en `HIGH` (apagados) antes de llamar `GPIO.cleanup()`. El argumento `[self.valve_pin, self.pump_pin]` libera solo los pines usados por este sistema, no todos los pines del GPIO.

---

### 7.2 Clase `DogDeterrentSystem`

**Responsabilidad:** Orquestador principal. Mantiene el estado del sistema y ejecuta el pipeline frame-a-frame.

#### Estado interno

| Atributo | Tipo | Descripción |
|---|---|---|
| `armed` | `bool` | Si el sistema está activo (toggle con `a`) |
| `paused` | `bool` | Pausa el procesamiento sin cerrar la ventana (toggle con `space`) |
| `consecutive_detections` | `int` | Contador de frames consecutivos con perro en zona |
| `required_consecutive` | `int` | N frames necesarios antes de disparar (anti-falso-positivo) |
| `cooldown` | `float` | Segundos mínimos entre disparos |
| `last_fire_time` | `float` | Timestamp Unix del último disparo |
| `fire_flash_until` | `float` | Timestamp hasta el que mostrar el flash rojo en pantalla |
| `stats` | `dict` | Contadores de sesión (detecciones, intrusiones, disparos) |

#### `__init__(config_path)`

Lee `settings.yaml` e instancia todos los componentes: `CameraSource`, `DogDetector`, `WaterGunSimulator`. El sistema está armado por defecto (`self.armed = True`).

#### `is_in_zone(detection, frame_shape) → bool`

```python
nx, ny = cx / w, cy / h  # normalizar el centro del bbox
return (z["x_min"] <= nx <= z["x_max"] and z["y_min"] <= ny <= z["y_max"])
```

Usa el **centro del bounding box** (no el bbox completo) para determinar si el perro está en la zona. Esta decisión evita falsos positivos cuando el perro está cerca del borde de la zona pero no completamente dentro. El centro normalizado se compara contra la zona normalizada, haciendo la comparación independiente de la resolución.

#### `is_in_cooldown() → bool`

```python
return (time.time() - self.last_fire_time) < self.cooldown
```

Evita disparos repetidos mientras el perro sigue en zona. Sin cooldown, el sistema dispararía cada pocos frames (a 30 FPS, dispararía 30 veces por segundo).

#### `save_capture(frame, detection)`

Guarda un JPG anotado con timestamp en `logs/captures/alert_YYYYMMDD_HHMMSS.jpg`. La copia del frame se hace con `.copy()` para no modificar el frame que sigue siendo procesado por `draw_hud`.

#### `process_frame(frame) → (detections, inference_ms)`

**Pipeline de decisión por frame:**

```
1. Si paused → retornar sin procesar
2. Detectar con YOLO
3. Separar dogs / persons
4. Para cada perro:
   a. ¿Está en zona?
      - Sí → incrementar consecutive_detections
              ¿Hay persona en zona? → bloquear (safety check)
              ¿consecutive >= required AND armed AND !cooldown?
                → fire(), reset counter, log
      - No → decrementar consecutive_detections (mín 0)
5. Sin perros → reset a 0
```

**Por qué decrementar en vez de resetear al instante:** Si el perro sale de zona un solo frame (por oclusión o movimiento) y el contador se resetea a 0, el sistema sería frágil. El decremento gradual da tolerancia a detecciones intermitentes.

**Safety check:** Si `person_class_id` está en la zona simultáneamente con el perro, el disparo se bloquea completamente. Esto previene disparar a personas accidentalmente. Es configurable (`safety_check_person: true/false` en YAML).

#### `draw_hud(frame, fps, inference_ms, detections)`

Renderiza toda la información visual sobre el frame:

1. **Zona de exclusión:** Rectángulo semitransparente (verde = libre, rojo = perro detectado). El alpha aumenta de 0.1 a 0.25 cuando hay peligro para hacerlo más visible.
2. **Bounding boxes:** Rojo para perros, amarillo para personas. Los perros en zona tienen la etiqueta `[ZONA!]`.
3. **Flash rojo al disparar:** `fire_flash_until` es un timestamp futuro seteado en `fire()`. Mientras el tiempo actual sea menor a ese timestamp, se pinta un overlay rojo semitransparente con el texto "DISPARANDO!".
4. **Barra de estado superior:** Estado del sistema (ARMADO/DESARMADO/PAUSADO/COOLDOWN), FPS, latencia de inferencia, contador de frames consecutivos.
5. **Estadísticas de sesión:** Tiempo transcurrido, total de intrusiones y disparos.

#### `run()`

Bucle `while True` principal. Por cada iteración:
1. Lee un frame de la cámara
2. Llama `process_frame()`
3. Calcula FPS cada 15 frames (evita calcular cada frame, que sería más costoso)
4. Llama `draw_hud()` y muestra con `cv2.imshow()`
5. Lee teclas con `cv2.waitKey(1)` (1ms de espera, suficiente para OpenCV procesar eventos)

**Manejo de pausa:** Cuando `process_frame()` retorna el frame sin modificar (condición de pausa), se trata como lista de detecciones vacía para que `draw_hud` no explote. Este es el único punto donde hay un manejo ad-hoc del tipo de retorno.

#### `cleanup()`

Registrado para ejecutarse en el bloque `finally` del try/except del bucle principal. Garantiza que la cámara y GPIO se liberen incluso si ocurre una excepción, y registra el resumen de la sesión en el log.

---

## 8. Flujo de Trabajo de 3 Pasos

El diseño en 3 scripts numerados refleja un **proceso de onboarding progresivo**:

```
Paso 1: 01_test_detection.py
  ↓ Verifica que YOLO detecta el perro correctamente
  ↓ Ajusta confidence si hay falsos positivos

Paso 2: 02_calibrate_zone.py
  ↓ Define visualmente dónde está el tacho de basura
  ↓ Guarda zona en config/settings.yaml

Paso 3: 03_full_system.py
  ↓ Sistema completo con zona + disparo
```

Esto reduce la fricción para el usuario: no necesita entender todo el sistema antes de empezar. Cada paso tiene un objetivo claro y verificable.

---

## 9. Configuración Centralizada (`settings.yaml`)

Toda la configuración del sistema vive en un único archivo YAML. No hay valores hardcodeados en el código.

| Sección | Parámetros clave | Propósito |
|---|---|---|
| `camera_source` | `0` / `"picamera2"` | Selección de cámara por plataforma |
| `model` | `path`, `confidence`, `input_size` | Control del modelo YOLO |
| `zone` | `x_min/y_min/x_max/y_max` (0.0–1.0) | Coordenadas normalizadas de la zona |
| `detection` | `consecutive_frames_required`, `safety_check_person` | Anti-falso-positivo y seguridad |
| `fire` | `cooldown_seconds`, `burst_duration`, `valve_gpio_pin`, `pump_gpio_pin` | Parámetros de disparo y hardware |
| `alerts` | `save_captures`, `captures_dir` | Persistencia de evidencia |
| `display` | `show_window`, `show_fps`, `zone_color_*` | Control visual |

Las coordenadas de zona se almacenan normalizadas (0.0–1.0) para ser **independientes de la resolución de la cámara**. La conversión a píxeles ocurre solo en tiempo de renderizado y comparación, multiplicando por el ancho/alto del frame actual.

---

## 10. Patrones de Diseño Aplicados

### Abstracción de Hardware (Strategy Pattern implícito)
`WaterGunSimulator` encapsula dos implementaciones (GPIO real y simulación) detrás de la misma interfaz `fire()` / `cleanup()`. El código consumidor (`DogDeterrentSystem`) no sabe ni le importa cuál implementación se usa.

### Configuración Externalizada
Ningún valor numérico relevante (pins GPIO, umbrales, duraciones, colores) está en el código. Todo viene de `settings.yaml`. Esto permite ajustar el comportamiento sin modificar código.

### Detección de Plataforma en los Bordes
La lógica de "¿estoy en Mac o RPi?" se concentra en dos lugares: `CameraSource.__init__()` y `WaterGunSimulator.__init__()`. El resto del código es agnóstico a la plataforma. Esto facilita testear en Mac y desplegar en RPi sin cambios.

### Pipeline Frame-a-Frame
El diseño `read → detect → evaluate → draw → show` es un pipeline lineal sin paralelismo. En el contexto de un sistema embebido (RPi), esto simplifica el debugging y evita condiciones de carrera. Si la latencia fuera un problema crítico, se podría paralelizar captura e inferencia con threading, pero no es necesario para esta aplicación.

### Guard Clauses para Safety
La verificación `person_in_zone` antes de disparar es un **guard clause** que bloquea la acción. Se evalúa después de confirmar que hay un perro en zona y antes de verificar el cooldown, porque la seguridad tiene prioridad sobre la eficiencia.

---

## 11. Dependencias

| Librería | Versión mínima | Uso |
|---|---|---|
| `ultralytics` | ≥8.0.0 | YOLOv8: inferencia y carga de modelo |
| `opencv-python` | ≥4.8.0 | Captura de video, rendering, I/O de imágenes |
| `numpy` | ≥1.24.0 | Operaciones matriciales (requerido por ultralytics y cv2) |
| `PyYAML` | ≥6.0 | Lectura/escritura de `settings.yaml` |
| `picamera2` | — | Solo RPi: captura de Camera Module (no en requirements.txt) |
| `RPi.GPIO` | — | Solo RPi: control de GPIO (no en requirements.txt) |

Las dependencias de RPi se omiten de `requirements.txt` porque el entorno de Mac no puede instalarlas (y fallarían). El código las importa de forma lazy (dentro de `try/except ImportError`) para mantener la compatibilidad cross-platform sin archivos de requirements separados.
