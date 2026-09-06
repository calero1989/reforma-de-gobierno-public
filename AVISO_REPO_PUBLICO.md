# Simulador de Reforma Legislativa (repo pÃºblico)

Esta es la **copia pÃºblica sanitizada** del proyecto.

| Repo | Uso |
|------|-----|
| [reforma-de-gobierno](https://github.com/calero1989/reforma-de-gobierno) | Privado / completo (desarrollo propio) |
| **Este repo** | PÃºblico, sin secretos ni datos de usuarios |

## QuÃ© NO incluye a propÃ³sito
- ContraseÃ±as, .env, tokens de tÃºnel
- Datos de comunidad (usuarios, correos, comentarios reales del servidor)
- IP / credenciales reales del VPS (sustituidas por placeholders)

## Arranque rÃ¡pido
1. Instala Python 3
2. Crea un .env local a partir de herramientas/smtp.env.example (opcional)
3. Descarga leyes: `python herramientas/descargar_legislacion_boe.py`
4. Arranca: `.\iniciar.ps1`

Los textos legales se obtienen del BOE (legislaciÃ³n consolidada). Las simulaciones son orientativas.

Ãšltima sincronizaciÃ³n pÃºblica: 2026-09-06 14:05