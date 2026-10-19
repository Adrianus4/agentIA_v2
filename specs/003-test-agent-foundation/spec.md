# Especificación: referencia inicial y ejecutor local de pruebas

Fecha: 2026-10-18 (America/Lima). Estado: propuesta lista para implementar.

## Objetivo y alcance

Completar los trabajos 1 y 2 del agente de pruebas acordado: conocer el estado
real del proyecto y disponer de un ejecutor Python utilizable desde VS Code.
El entregable permite ejecutar las pruebas Python existentes y registrar sus
resultados. Los fallos previos del producto forman parte de la referencia inicial.

La plataforma AgentIA y sus microservicios generados son los objetivos de la
primera versión completa. En este incremento se inventariarán ambos, pero solo se
integra la ejecución automatizada de la suite Python existente. Las pruebas Java,
React, navegador y servicios reales requieren adaptadores de trabajos posteriores.

## Restricciones confirmadas

- Uso local en Windows con Python y VS Code; Docker y virtualización no son requisitos.
- Python mínimo 3.11; entorno de referencia 3.12, coherente con las imágenes existentes.
- Node, JDK, Maven, Git, uv y acceso a servicios externos son capacidades opcionales.
- Poder instalar paquetes Python en un entorno de usuario debe comprobarse; no se
  infiere a partir de tener VS Code o sus extensiones.
- La ejecución predeterminada no necesita claves ni hace llamadas reales a LLM.
- La IA por API, con Gemini, DeepSeek y GPT, se incorporará en el trabajo 7.
  Las llamadas reales durante las pruebas y el análisis de resultados serán opciones distintas.
- La automatización en GitHub corresponde al trabajo 8.

## Requisitos

| ID | Requisito verificable |
| --- | --- |
| RF-01 | Inventariar suites, herramientas, simulaciones, efectos laterales y recorridos de referencia con evidencia de archivos existentes. |
| RF-02 | Registrar el resultado observado de las comprobaciones iniciales, o un bloqueo explícito cuando no se puedan ejecutar. |
| RF-03 | Ofrecer comandos `doctor`, `list` y `run` desde Python, con ayuda comprensible en español. |
| RF-04 | Detectar el repositorio mediante ruta explícita o ubicación del ejecutor; admitir rutas con espacios y ejecución desde otro directorio. |
| RF-05 | Detectar dependencias sin instalarlas ni iniciar servicios. La ausencia de herramientas opcionales no bloquea la suite Python. |
| RF-06 | Ejecutar únicamente suites registradas y seleccionadas; en este incremento la suite ejecutable es `python`, asociada a `tests/`. |
| RF-07 | Obtener métricas estructuradas del proceso pytest, incluyendo errores de colección, omisiones y ausencia de casos. |
| RF-08 | Aplicar tiempo máximo, gestionar interrupciones y detener exclusivamente los procesos creados por el ejecutor. |
| RF-09 | Emitir resumen en terminal y evidencia mínima JSON/JUnit, con identificador y códigos de salida definidos. |
| RF-10 | Aislar estado y archivos temporales y excluir secretos de la evidencia guardada. |
| RF-11 | Un resultado satisfactorio exige al menos una prueba aprobada y ninguna comprobación seleccionada fallida, bloqueada o con error. |
| RF-12 | Mantener separados el ejecutor de QA, la CLI de negocio y el verificador Maven existentes. |

## Escenarios de aceptación

| ID | Escenario y resultado esperado |
| --- | --- |
| CA-01 | Con Python compatible y sin Node, Java, Maven ni Docker, `doctor` identifica las ausencias; una suite Python simulada elegible sigue siendo ejecutable. |
| CA-02 | Sin pytest o una dependencia requerida de la suite, `doctor` explica el requisito y `run` devuelve ejecución incompleta, sin intentar instalarlo. |
| CA-03 | Desde otro directorio, una ruta absoluta al lanzador y un repositorio con espacios permiten listar y ejecutar los casos seleccionados. |
| CA-04 | Una suite controlada aprobada produce casos y duración observados, artefactos válidos y salida 0. |
| CA-05 | Una aserción fallida produce salida 1 y conserva el nombre del caso y un diagnóstico útil. |
| CA-06 | Una selección vacía o no implementada nunca se informa como aprobada. Una suite desconocida es un error de configuración. |
| CA-07 | Un error de colección, un timeout o una interrupción quedan diferenciados de una aserción fallida; no quedan procesos hijos propios activos. |
| CA-08 | Dos ejecuciones simultáneas usan directorios e identificadores distintos y preservan un archivo centinela del proyecto. |
| CA-09 | Credenciales ficticias sembradas en variables y mensajes de un proceso controlado quedan redactadas en consola y artefactos. |
| CA-10 | Desaparecer o corromper el XML, o un desacuerdo entre XML y código del proceso, impide concluir que la ejecución fue satisfactoria. |
| CA-11 | Una prueba omitida o xfail pendiente mantiene el resultado incompleto. No se altera la suite existente para obtener un resultado verde. |

Las pruebas de aceptación del propio ejecutor usarán fixtures controlados en
`qa_tests/`, separados de la suite del producto. Se comprobarán antes de implementar
la capacidad correspondiente, siguiendo la constitución del repositorio.

## Cierre del incremento

El trabajo 1 termina con inventario, referencia observada y limitaciones documentadas,
aunque haya fallos previos. El trabajo 2 termina cuando el ejecutor refleja fielmente
esos resultados y supera sus propios escenarios de aceptación. La evidencia de este
incremento no equivale a validar todavía Java real, navegador o toda la plataforma.
