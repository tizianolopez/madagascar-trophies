# 🔄 Sincronización Madagascar FC - Liga Meiland

## Cómo funciona

La PWA **siempre carga los datos desde Supabase**, no hay botón de sincronización en el frontend.

Los datos se sincronizan ejecutando el script Python:

```bash
python sync_meiland.py
```

## ¿Qué sincroniza?

### 1. **Jugadores** (`players` table)
- Nombre
- Goles totales
- Partidos jugados
- Asistencias

### 2. **Partidos** (`matches` table)
- Fecha y hora
- Rival
- Goles a favor / en contra
- Local o visitante
- **Goleadores separados por equipo** (en campo `notes` como JSON):
  ```json
  {
    "madagascar_scorers": [
      {"name": "Tiziano", "goals": 2},
      {"name": "Hugo", "goals": 1}
    ],
    "rival_scorers": [
      {"name": "Alex", "goals": 1}
    ]
  }
  ```

### 3. **Clasificación** (cuando esté disponible en Meiland)

## Configurar cronjob automático

Para sincronizar automáticamente cada día:

### Windows (Programador de Tareas)
1. Abre "Programador de tareas"
2. Crear tarea básica
3. Nombre: "Sync Madagascar Meiland"
4. Activador: Diariamente a las 2:00 AM
5. Acción: Iniciar programa
   - Programa: `C:\Python313\python.exe`
   - Argumentos: `sync_meiland.py`
   - Directorio: `C:\Users\tizib\Desktop\New code\madagascar`

### Linux/Mac (crontab)
```bash
# Editar crontab
crontab -e

# Agregar línea (ejecutar diario a las 2 AM)
0 2 * * * cd /path/to/madagascar && python3 sync_meiland.py >> sync.log 2>&1
```

## Verificar sincronización

Después de ejecutar el script, verás algo como:

```
✅ SINCRONIZACIÓN COMPLETADA
👥 Jugadores: 11 actualizados
⚽ Partidos: 12 actualizados
📊 Goleadores separados por equipo ✓
```

## ¿Y si necesito sincronizar manualmente?

Simplemente ejecuta desde la terminal:

```bash
cd "C:\Users\tizib\Desktop\New code\madagascar"
python sync_meiland.py
```

La PWA se actualizará automáticamente al recargar la página.
