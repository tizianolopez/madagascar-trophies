# Supabase Edge Functions - Madagascar FC

## sync-meiland

Esta Edge Function sincroniza datos desde Liga Meiland a Supabase.

### Datos que sincroniza:
- **Jugadores**: Nombre, partidos jugados, goles, asistencias
- **Clasificación**: Posiciones, puntos, partidos, goles a favor/contra
- **Partidos**: Calendario, resultados, próximos encuentros

### Configuración de Secrets

Antes de desplegar, configura estos secrets en Supabase:

```bash
# Instalar Supabase CLI si no lo tienes
npm install -g supabase

# Login a Supabase
supabase login

# Linkar tu proyecto
supabase link --project-ref TU_PROJECT_REF

# Configurar secrets para Meiland
supabase secrets set MEILAND_EMAIL="tizi.barca@gmail.com"
supabase secrets set MEILAND_PASSWORD="Tizilop7."
```

### Desplegar la función

```bash
# Desde la carpeta raíz del proyecto
cd supabase/functions

# Desplegar
supabase functions deploy sync-meiland --no-verify-jwt
```

### Usar la función

Desde tu app:
```javascript
const response = await fetch(
  'https://TU_PROJECT_REF.supabase.co/functions/v1/sync-meiland',
  {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer TU_ANON_KEY',
      'Content-Type': 'application/json'
    }
  }
);
```

### Programar sincronización automática (Cron)

Puedes usar [Supabase Scheduled Functions](https://supabase.com/docs/guides/functions/schedule) o un servicio externo como:

1. **cron-job.org** (gratis)
2. **GitHub Actions** con schedule
3. **Supabase pg_cron** (extensión de PostgreSQL)

Ejemplo de cron cada domingo a las 15:00:
```sql
-- En Supabase SQL Editor
select cron.schedule(
  'sync-meiland-weekly',
  '0 15 * * 0',  -- Domingo a las 15:00
  $$
  select net.http_post(
    url := 'https://TU_PROJECT_REF.supabase.co/functions/v1/sync-meiland',
    headers := '{"Authorization": "Bearer TU_SERVICE_KEY"}'::jsonb
  );
  $$
);
```

### Troubleshooting

Si el scraping falla:
1. Verifica que las credenciales de Meiland sean correctas
2. Meiland puede haber cambiado su estructura HTML
3. Revisa los logs: `supabase functions logs sync-meiland`
