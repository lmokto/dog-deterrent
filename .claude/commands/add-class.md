Añade soporte para detectar una nueva clase de objeto al sistema.

1. Busca el class_id correcto en las clases COCO (0-79)
2. Añádelo a COCO_CLASSES en src/detector.py
3. Añádelo a self.target_classes en DogDetector.__init__
4. Actualiza la lógica de zona en 03_full_system.py si es necesario
5. Actualiza config/settings.yaml con los parámetros relevantes
6. Actualiza CLAUDE.md con la nueva clase

La nueva clase a añadir es: $ARGUMENTS
