# Lunova v0.1

**Transforma tus ideas. Conserva tu esencia.**

Esta carpeta contiene la base completa de **Lunova v0.1**. La numeración permanece en `0.1` hasta que la versión sea aprobada; las mejoras internas y avisos a usuarios se pueden publicar sin subir a `0.2`.

## Qué incluye

- Interfaz web responsiva con la identidad visual de Lunova.
- Registro e inicio de sesión con Supabase Auth.
- Datos persistentes fuera del código: perfiles, preferencias, documentos y revisiones.
- Almacenamiento privado de los `.docx` originales en Supabase Storage.
- Row Level Security (RLS): cada usuario solo puede acceder a sus propios registros y archivos.
- Editor con modos Natural, Académico y Profundo.
- Modo Investigación con protección de citas, URL, cifras y porcentajes.
- Motor de varias pasadas internas: reestructuración, naturalidad y, cuando corresponde, pulido final.
- Guardado manual de borradores y guardado automático de cada revisión generada.
- Historial persistente de revisiones.
- Comparación original / revisión y exportación TXT.
- Carga de Word y generación de una copia revisada sin destruir el archivo original.
- Panel de administrador oculto para usuarios normales.
- Avisos de actualización que cada usuario puede marcar como leídos.
- Banner global, modo mantenimiento e instrucción editorial configurable desde el panel administrador.
- La configuración del motor puede cambiar sin borrar documentos del usuario.

## Arquitectura

```text
GitHub / Streamlit Cloud     Supabase
(código de Lunova)           (datos persistentes)
        │                         │
        ├─ app.py                 ├─ Auth
        ├─ lunova/*               ├─ PostgreSQL + RLS
        ├─ assets                 └─ Storage privado
        └─ requirements.txt
```

Actualizar el repositorio cambia la aplicación, **no las tablas ni los archivos del usuario**. No vuelvas a ejecutar comandos destructivos sobre Supabase cuando publiques cambios de interfaz o código.

## 1. Crear Supabase

1. Crea un proyecto en Supabase.
2. Abre **SQL Editor**.
3. Copia y ejecuta completo `supabase_setup.sql` una sola vez.
4. En Auth decide si exigir confirmación por correo. Si la dejas activada, el usuario confirmará su correo antes de iniciar sesión.
5. Copia la URL del proyecto, la clave `anon/publishable` y la `service_role`.

**La clave `service_role` jamás debe estar en GitHub ni mostrarse al usuario.** Solo va en Secrets de Streamlit.

## 2. Configurar secretos

En Streamlit Community Cloud > App settings > Secrets agrega:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR_ANON_OR_PUBLISHABLE_KEY"
SUPABASE_SERVICE_ROLE_KEY = "YOUR_SERVICE_ROLE_KEY"
ADMIN_EMAILS = "tu-correo@dominio.com"

OPENAI_API_KEY = "YOUR_OPENAI_KEY"
OPENAI_MODEL = "gpt-5.6-terra"
```

Puedes separar varios administradores con comas en `ADMIN_EMAILS`.

## 3. Publicar

Sube **el contenido de esta carpeta** a la raíz de un repositorio GitHub. En Streamlit Community Cloud crea una app con:

- Branch: `main`
- Main file path: `app.py`
- Python: una versión soportada por Community Cloud

Los secretos se agregan en Advanced settings / App settings, no en archivos públicos.

## Cómo actualizar sin borrar usuarios

Para cambiar diseño, funciones o prompts base:

1. Trabaja en una rama de prueba, por ejemplo `develop`.
2. Despliega una segunda app de prueba apuntando a `develop`.
3. Cuando esté validada, fusiona el cambio a `main`.
4. La app pública se actualiza, mientras que Supabase conserva cuentas, documentos, historial y preferencias.

Para cambios que **no requieren desplegar código**, entra con el correo definido en `ADMIN_EMAILS` y usa **Administración**:

- Publicar un aviso de “Nueva actualización disponible”.
- Ajustar la instrucción editorial del motor.
- Mostrar un banner global.
- Activar/desactivar mantenimiento.

La versión visible seguirá siendo **v0.1** hasta que decidas que esta base está terminada.

## Pruebas incluidas

```bash
pytest -q
```

Las pruebas cubren protección/restauración de citas y cifras, métricas y lectura/exportación segura de DOCX.

## Uso académico

Lunova está diseñada para mejorar claridad, cohesión y paráfrasis manteniendo citas y datos. No garantiza evasión de detectores de IA o de similitud y no debe utilizarse para ocultar fuentes o atribución.
