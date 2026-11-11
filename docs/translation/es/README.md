<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="512">
</div>

# 🔗 OMEGA-CONNECT

**Vincula entre sí las aplicaciones de la suite omega, en una máquina y en toda la red**

> Desarrollado por [kraynux](https://github.com/kraynux) para [Omega-Server](https://kraynux.snake-mackarel.ts.net)   

Página oficial: [OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/es/) &nbsp; Vista previa: [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 Interfaz disponible en **17 idiomas** — véase [Idiomas de la interfaz](#idiomas-de-la-interfaz).  
**Idiomas:**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](../zh-CN/README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** es el interconector de la suite `omega-`: encuentra las aplicaciones omega instaladas (omega-serv, omega-fire, omega-jail…) en esta máquina y en las máquinas de su red, muestra lo que está vinculado entre sí y lo que no, y vuelve a poner en su sitio lo que falta — mostrando siempre primero lo que va a hacer. Una vez vinculadas, las aplicaciones se encuentran entre sí sin que omega-connect esté en ejecución.

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/es/omega-connect/D.png" width="24%" />
</p>

## 1. Visión y alcance

Las aplicaciones omega están hechas para trabajar juntas: los logs de omega-serv los leen los jails de omega-jail, los baneos de fail2ban llegan a la lista negra de omega-serv, omega-fire lo muestra todo. Pero hace falta que los archivos estén en el lugar correcto, con los permisos correctos, y que cada aplicación sepa dónde están las demás. De eso se encarga omega-connect.

### Lo que hace Omega-connect

- Encuentra las aplicaciones omega de esta máquina (carpeta personal, servicios systemd, OpenRC o runit, `/srv`, registro de instancias de omega-serv) y las de las demás máquinas, a las que accede por SSH con sus claves.
- Mantiene un **registro** de todas las aplicaciones de todas las máquinas, con su versión y su estado.
- Comprueba cada **vínculo** entre aplicaciones (logs leídos por los jails, puente hacia la lista negra, lista protegida, archivos de omega-jail en fail2ban, tarjetas de identidad, espacio compartido) e indica lo que no va bien.
- **Sincroniza**: crea las tarjetas de identidad que faltan y prepara el **espacio compartido** donde las aplicaciones se encuentran entre sí.
- **Repara**: hace que cada discrepancia la corrija la aplicación propietaria del archivo; nunca omega-connect en su lugar.
- **Actualiza o reinstala** una aplicación demasiado antigua o mal instalada de una máquina de la red, desde su Release de GitHub (huella verificada).
- Actúa sobre una máquina de la red **desde su equipo**: nada que teclear allí, su contraseña se pide una vez, por la propia máquina.
- Genera un **informe** completo (texto, JSON o página HTML).

### Lo que Omega-connect no hace

- No sustituye a ninguna aplicación: fail2ban, omega-fire, omega-jail y omega-serv conservan cada uno su papel.
- Nunca reescribe el archivo de otra aplicación.
- No instala nada permanente en una máquina de la red para escanearla, y no deja ningún servicio en ejecución.
- Nunca pide la contraseña SSH, y nunca ve su contraseña de administrador.

## 2. Instalación

### Requisitos

- Linux, Python 3.10+.
- Para las máquinas de la red: un acceso SSH por clave, y Python 3.10+ en esas máquinas.
- Conexión a Internet para las dependencias (y para las actualizaciones desde GitHub).

### Instalación

Desde la carpeta donde se encuentra el archivo:

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`:

1. Crea el entorno virtual `.venv` (un `.venv` incompleto se aparta y se vuelve a crear).
2. Instala omega-lib (biblioteca de la suite, incluida en el archivo) y omega-connect.
3. Hace ejecutables `omega-connect.sh` e `install.sh`.
4. Añade el alias `connect` a `~/.bashrc` y `~/.zshrc` (sin duplicados).

Ningún paso requiere privilegios de administrador.

### Actualización

Desde la carpeta que CONTIENE `omega-connect/` (nunca desde dentro: `tar` crearía una carpeta anidada), extraiga el nuevo archivo encima y vuelva a ejecutar `install.sh`. El archivo no contiene ningún dato local (`var/`: registro de las máquinas, ajustes, exportaciones): no se sobrescribe nada de lo que existe.

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. Uso

### Modo interactivo (TUI)

```bash
./omega-connect.sh
```

o, si se ha creado el alias, `connect`.

El menú principal tiene dos columnas:

| Gestión | Mantenimiento |
|---|---|
| **Registro** — todas las aplicaciones de todas las máquinas, su versión y su estado | **Reparar** — la lista de todo lo que no va bien, y usted elige |
| **Escanear** — esta máquina, y la incorporación de las máquinas de la red | **Informe** — un documento completo, para exportar |
| **Vínculos** — lo que está vinculado o no, con su estado | **Ajustes** — idioma, temas, carpetas, purga |
| **Sincronización** — vincular las aplicaciones, en todas las máquinas | **Ayuda** — cada menú, su función y el detalle |
| **Panel** — la vista general | **Salir** |

Recorrido típico: **Escanear** (esta máquina y luego sus otras máquinas, propuestas a partir de sus perfiles Unison, `~/.ssh/config` y `known_hosts`) → **Registro** (actualizar o reinstalar una aplicación antigua) → **Sincronización** (marcar y después sincronizar) → **Vínculos** y **Panel** para ver el resultado → **Reparar** si queda alguna discrepancia.

Cada acción muestra primero su plan; no se ejecuta nada antes de su conformidad. Para una máquina de la red, la interfaz cede el sitio al terminal mientras dura la acción: la propia máquina pide su contraseña, una vez.

#### Atajos de teclado

| Tecla | Acción |
|---|---|
| `↑` / `↓` | Pasar de un elemento a otro |
| `Tab` / `Mayús+Tab` | Pasar de una zona de la pantalla a otra |
| `Intro` / `Espacio` | Activar; marcar una línea (Sincronización) |
| `Esc` | Volver a la pantalla anterior |
| `a` | Ayuda |
| `s` | Ajustes |
| `t` | Tema siguiente |
| `r` | Redibujar la pantalla |
| `q` | Salir (con confirmación) |
| `Ctrl+P` | Comandos: tema, captura de pantalla, salir |

### Estados

| Aplicaciones | Vínculos |
|---|---|
| ● Vinculada — en el espacio compartido, al día | OK |
| ◐ Inscrita — tiene su tarjeta de identidad, aún no está en el espacio compartido | por reparar |
| ○ Detectada — sin tarjeta de identidad | por reparar (bloqueante) |
| ▲ Por reparar — una discrepancia | ausente — nada que vincular |
| ◌ Versión antigua — por actualizar | no verificable |
| ◇ Instalación incompleta — por reinstalar | |
| ✕ Inaccesible — la máquina ya no responde | |

### Idiomas de la interfaz

La interfaz está disponible en 17 idiomas: francés, inglés, español, portugués (Brasil), italiano, alemán, neerlandés, polaco, ruso, chino simplificado, vietnamita, tailandés, indonesio, japonés, coreano, hindi y árabe. La elección se hace en los Ajustes (« Langue / Language ») y se aplica tras reiniciar la interfaz; la variable `OMEGA_CONNECT_LANG` (por ejemplo `OMEGA_CONNECT_LANG=en ./omega-connect.sh`) fuerza un idioma durante una sesión. En una consola de texto Linux (TTY), los idiomas de escritura no latina se muestran en inglés durante la sesión. La línea de comandos sigue en francés.

### Contacto y soporte

La ayuda (tecla `a`) ofrece una pantalla **Contacto y soporte**: *Invitar a un café* (página de PayPal del desarrollador), *Contactar con el soporte* (dirección de correo y formulario de contacto del sitio, mostrados en claro), *Declararme usuario (anónimo)* y *Buscar actualizaciones*. La declaración es voluntaria, está desactivada por defecto y se envía una sola vez: solo sirve para contar a los usuarios y, si se desea, su continente o su país (listas cerradas, nunca texto libre). Envía una clave aleatoria, el nombre del software (`omega-connect`) y su versión; nunca un nombre, el nombre de la máquina, una dirección ni un ajuste. La dirección IP no se registra en las declaraciones, pero, como cualquier visita, pasa por los controles de seguridad y el registro del servidor de recepción. Se puede retirar en cualquier momento desde la misma pantalla. La búsqueda de actualizaciones solo lee la lista de versiones publicadas, y nunca sin un clic.

### Modo scriptable (CLI)

Cualquier comando activa el modo de línea de comandos:

```bash
# Aplicaciones de esta máquina, o de una máquina de la red (SSH con sus claves)
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# Vincular las aplicaciones de esta máquina, o de una máquina de la red
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# Actualizar las aplicaciones demasiado antiguas de una máquina de la red (Release de GitHub)
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# Reparar: esta máquina, o una máquina de la red
./omega-connect.sh reparer --machine moi@192.168.1.109

# Estado de cada vínculo, e informe completo
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` muestra el plan sin ejecutar nada; `--oui` ejecuta sin preguntar; `--toutes-machines` recorre todas las máquinas conocidas, una a una.

## 4. Máquinas de la red

- **Conexión:** SSH solo con sus claves; se respeta `~/.ssh/config` (alias, puerto, usuario). Una clave protegida por una frase de contraseña debe estar cargada en el agente SSH.
- **Primera conexión:** la huella de la clave de la máquina se muestra antes que nada; una clave que ha cambiado se rechaza.
- **Escaneo:** se envía un programa en memoria, en solo lectura; no se instala ni se escribe nada, no se pide ninguna contraseña.
- **Acción** (sincronizar, reparar, actualizar): una carpeta privada temporal recibe el programa y, si procede, los archivos comprimidos; se borra al final. La propia máquina pide la contraseña de administrador, una vez.
- **Identidad:** una máquina se reconoce por la huella de su identificador de sistema, no por su dirección: aunque se acceda a ella por dos redes, sigue siendo una sola máquina.
- **Actualizaciones:** desde la Release de GitHub de cada aplicación; la huella del archivo se verifica con `sha.txt` antes de cualquier envío, y de nuevo en la máquina. Cada aplicación se instala como indica la sección « Actualización » de su README.

## 5. Tarjeta de identidad y espacio compartido

- **Tarjeta de identidad:** al instalarse, cada aplicación omega escribe un pequeño archivo que dice quién es (aplicación, versión, identificador, máquina). Legible por todos, nunca modificable por las demás cuentas.
- **Espacio compartido:** `/var/lib/omega-synchro`, reservado al grupo `omega-synchro`, donde solo escribe el administrador. Omega-connect copia en él las tarjetas de identidad y la descripción de cada aplicación; las aplicaciones se encuentran allí entre sí, incluso cuando omega-connect no está en ejecución.
- **Registro del espacio compartido:** todo lo que crea omega-connect queda inscrito en él; una retirada solo deshace lo que está inscrito, y un archivo desconocido nunca se elimina.

## 6. Seguridad

- Ninguna elevación al arrancar: omega-connect se ejecuta con su cuenta; sudo se pide acción por acción, con el comando mostrado antes.
- Las correcciones las hace la aplicación propietaria del archivo (omega-jail para lo que coloca en fail2ban, omega-serv para los permisos de su `var/`, cada aplicación para su tarjeta de identidad).
- No se lanza ninguna aplicación si corre el riesgo de pedir una contraseña sin terminal.
- La búsqueda nunca sigue un enlace simbólico, no cambia de sistema de archivos e ignora los montajes de red.
- La purga de las carpetas de exportaciones y de capturas rechaza las carpetas del sistema, las personales y la de omega-connect.

## 7. Exportaciones

- **Informe**: balance de todas las máquinas, lista precisa de lo que queda por hacer, registro, máquinas de la red, vínculos de cada máquina, espacio compartido. Texto, JSON o página HTML (tema a elegir).
- **Ayuda**: exportable como página HTML.
- **Capturas de pantalla**: `Ctrl+P` → « Captura de pantalla » (SVG).
- Carpetas por defecto: `var/exports/` y `var/screenshots/` de la carpeta de omega-connect, modificables en los Ajustes.

## 8. Arquitectura

Clean Architecture, como el resto de la suite: `domain/` (reglas puras), `application/` (casos de uso), `ports/`, `infrastructure/` (SSH, archivos, GitHub, portapapeles), `interfaces/` (línea de comandos e interfaz Textual), `app/` (ensamblaje). Las dependencias apuntan siempre hacia el interior, comprobadas por `import-linter`. Los contratos compartidos entre aplicaciones (tarjeta de identidad, descripción, espacio compartido) viven en `omega-lib`.

## 9. Pruebas

```bash
source .venv/bin/activate
lint-imports        # comprueba la regla de las dependencias
pytest -q
ruff check src tests
mypy src
```

Las pruebas nunca tocan el `var/` real, ni la red, ni sudo: SSH falso ejecutado en local, GitHub falso, carpetas temporales.

## 10. Fuera del alcance

- Sustituir a fail2ban, omega-fire u omega-jail.
- Vigilar de forma continua (ningún servicio permanente).
- Instalar una aplicación omega por primera vez en una máquina de la red.
- Panel de control web.

## Licencia

MIT — véase [LICENSE](../../../LICENSE).

---

> Omega-connect — Encontrar, vincular, reparar.
> Las aplicaciones omega se comunican entre sí; omega-connect se asegura de que puedan hacerlo.
