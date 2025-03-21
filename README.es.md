**Integración Airzone Control**

[🇬🇧 Read this document in English](README.md)


Esta integración permite controlar y supervisar sistemas de climatización Airzone mediante su API local (por defecto, en el puerto 3000). A diferencia de la integración oficial, esta versión está diseñada para:

- Soportar sistemas con múltiples zonas.
- Exponer un conjunto ampliado de sensores (por ejemplo, temperatura, humedad, batería, firmware, IAQ y diagnóstico).
- Agrupar las entidades por dispositivo en Home Assistant.
- Ofrecer control manual del modo del termostato maestro mediante un selector.
-----
**Características**

- **Detección automática de zonas:**
  La integración detecta las zonas disponibles mediante llamadas a la API local.
- **Control individual por zona (climate):**
  Por cada zona se crea una entidad de clima que permite:
  - Encender o apagar la zona.
  - Cambiar el modo (según la información devuelta por la API).
  - Ajustar la consigna de temperatura.
  - Visualizar la temperatura ambiente actual.
- **Sensores de zona (sensor):**
  Se crean sensores para cada zona, incluyendo:
  - Temperatura (basada en roomTemp).
  - Humedad (si el firmware la reporta).
  - Estado de la batería (mostrando “Ok” o “Low”, detectando Error 8 o niveles bajos).
  - Firmware del termostato (valor de thermos\_firmware).
  - Datos de demanda (calor, frío y ventilación) si la API los reporta.
  - Consignas diferenciadas en caso de doble consigna (coolsetpoint y heatsetpoint).
  - Sensor global IAQ (con valores de CO₂, PM2.5, PM10, TVOC, presión, índice y puntuación, según la información disponible).
- **Control del sistema global:**
  Además de las entidades individuales por zona, la integración agrupa en un dispositivo “Airzone System”:
  - Un sensor que muestra el modo global.
  - Un sensor que indica la velocidad del ventilador.
  - Un sensor que muestra el estado de “modo dormir”.
  - Sensores opcionales para el ID del sistema, firmware, errores y unidades (Celsius/Fahrenheit).
  - Un sensor agregado que muestra, de forma resumida, las zonas con batería baja (mostrando el nombre de la zona, por ejemplo, “Cuina, Estudi”, o “Ninguna” si todo está bien).
- **Control manual del modo maestro:**
  Se incluye un selector (select) para forzar manualmente el modo del termostato maestro (por ejemplo, “Stop” o “Heat”). Al iniciarse, el selector lee el modo actual desde la API y se sincroniza con él, permitiendo al usuario anular el comportamiento automático cuando sea necesario.
-----
**Requisitos previos**

- Dispositivo Airzone con la API local habilitada (normalmente accesible en http://<IP>:3000).
- Que el Webserver Airzone esté en la misma red local que Home Assistant.
- Verifica que, al acceder manualmente (por ejemplo, con curl o un navegador) a http://<IP>:3000/api/v1/hvac?systemid=1&zoneid=1, se obtenga la respuesta JSON esperada.
-----
**Instalación**

1. Descarga los archivos de este repositorio (o clónalo) en tu carpeta config/custom\_components/airzone\_control. La estructura debe quedar similar a: 

pgsql

Copiar

custom\_components

└── airzone\_control

`    `├── \_\_init\_\_.py

`    `├── manifest.json

`    `├── config\_flow.py

`    `├── const.py

`    `├── coordinator.py

`    `├── climate.py

`    `├── sensor.py

`    `├── switch.py

`    `├── select.py

`    `└── translations

`        `├── es.json

`        `└── ca.json

1. Reinicia Home Assistant para que se reconozca la nueva integración.
1. Configura la integración: 
   1. Ve a **Ajustes → Dispositivos y Servicios → + Añadir integración**.
   1. Busca “Airzone Control” en la lista.
   1. Ingresa la IP del Webserver Airzone y el puerto (por defecto, 3000) y pulsa **Enviar**.
   1. Tras unos segundos, la integración se instalará y comenzará a mostrar las entidades.
-----
**Entidades creadas**

- **Clima:**
  Se crea una entidad de clima por cada zona detectada, permitiendo controlar individualmente cada termostato.
- **Sensores:**
  Se generan sensores para:
  - Temperatura, humedad, batería y firmware en cada zona.
  - Datos de demanda (calor, frío, aire) y, si corresponde, los setpoints de doble consigna.
  - Sensores IAQ global (CO₂, PM2.5, PM10, TVOC, presión, índice, puntuación y modo de ventilación).
  - Datos del sistema global (modo, velocidad del ventilador, modo dormir, ID, firmware, errores y unidades).
  - Un sensor agregado que resume las zonas con batería baja.
- **Switches:**
  Se incluyen switches para:
  - Encender o apagar globalmente el sistema.
  - Activar o desactivar el modo ECO.
- **Selector:**
  Una entidad de tipo “select” para forzar manualmente el modo del termostato maestro (opciones: “Stop” y “Heat”), que se sincroniza automáticamente con el estado actual tras reiniciar.
-----
**Dispositivos en Home Assistant**

- Cada zona aparece como un dispositivo independiente (por ejemplo, “Airzone Zone Estudi”) con sus respectivas entidades de clima y sensores.
- El sistema global (Airzone System) agrupa las entidades correspondientes a datos del sistema, incluyendo el sensor de baterías bajas y el selector de modo manual.
- El sensor global IAQ se muestra como un dispositivo adicional (“Airzone IAQ Sensor”).
-----
**Modo de uso**

- **Encendido/Apagado:**
  Utiliza la tarjeta de clima en Home Assistant para encender o apagar cada zona.
- **Cambio de consigna:**
  Ajusta la temperatura deseada directamente desde la interfaz del clima.
- **Control manual del modo:**
  Usa el selector “Airzone Manual Mode” para forzar manualmente el modo del termostato maestro (por ejemplo, “Stop” para mantenerlo apagado o “Heat” para encender la calefacción).
- **Supervisión de baterías:**
  Consulta el sensor “Zones amb Bateria Baixa” para ver rápidamente cuáles zonas requieren atención en cuanto a nivel de batería.
-----
**Preguntas Frecuentes**

- **¿Qué ocurre si solo algunas zonas reportan ciertos datos (por ejemplo, humedad)?**
  Es normal que algunos termostatos inalámbricos no reporten ciertos valores (como humedad) o lo hagan de forma intermitente (por baterías bajas o problemas de comunicación).
- **¿Qué significa “Error 8” en la API?**
  Generalmente indica que el termostato Lite no se comunica correctamente con la central, lo que puede ser consecuencia de pilas bajas o problemas de conexión inalámbrica.
-----
**Limitaciones**

- Se ha probado con versiones de firmware 3.6x y 3.7x en el Webserver Airzone.
- La lectura de datos IAQ depende de que el hardware y el firmware del sistema lo soporten.
- Algunas funcionalidades de diagnóstico o actualización de firmware podrían no estar disponibles si el dispositivo o la API no lo implementan.
-----
**Contribuciones**

Se aceptan contribuciones y sugerencias para mejorar esta integración. Puedes abrir un PR o enviar issues a través de GitHub.

-----
**Licencia**

Esta obra está bajo una [Licencia Internacional Creative Commons Atribución-NoComercial-CompartirIgual 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).

