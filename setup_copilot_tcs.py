"""
================================================================================
 TCS GenAI Lab - GitHub Copilot Setup & Patch Tool
 Permite usar las API Keys de TCS GenAI Lab (LiteLLM) en GitHub Copilot Chat.
 Compatible con Windows / VS Code.
================================================================================
"""

import os
import sys
import glob
import json
import shutil
import sqlite3
import subprocess
import argparse

GATEWAY_URL = "https://genailab.tcs.in/v1/chat/completions"

TEAMS = {
    "1": ("Peru_1", "sk-sEZQ17xfkLIKsL6ZCQedCg", "d2cd3bb0-82cb-41c9-9a7c-0ce820e4dff7"),
    "2": ("Peru_2", "sk-fbZOm3fIMSM8wGFGWEan4g", "2f8bed3e-7221-48b3-a543-bbe61ea1ae0b"),
    "3": ("Peru_3", "sk-CByAy7d-BkMHe0mFcW2HaQ", "3f71cb52-bbae-46b2-8bbb-49e4aa74684a"),
    "4": ("Peru_4", "sk-7kfmeraEZPTdbHQj-4shlw", "38e85e8d-1fe5-4204-b5aa-2d2d986cc444"),
    "5": ("Peru_5", "sk-ALROzqwo1PV6ZL8xYCKR4Q", "9482cafc-251b-49ad-87b8-69954f9a9a9e"),
    "6": ("Peru_6", "sk-tJdq6z8_PwjUCcizbF5TIA", "1f4f01ae-dbf8-44fe-ad3e-a6e81da90235"),
}

DEFAULT_MODELS_CONFIG = [
    {
        "id": "genailab-maas-gpt-5.3-codex",
        "name": "TCS: GPT-5.3 Codex",
        "url": GATEWAY_URL,
        "maxInputTokens": 128000,
        "maxOutputTokens": 8192,
        "toolCalling": True,
        "vision": True,
        "isDefault": True
    },
    {
        "id": "genailab-maas-gpt-4o",
        "name": "TCS: GPT-4o",
        "url": GATEWAY_URL,
        "maxInputTokens": 128000,
        "maxOutputTokens": 4096,
        "toolCalling": True,
        "vision": True,
        "isDefault": False
    },
    {
        "id": "genailab-maas-sonnet-4.6",
        "name": "TCS: Claude Sonnet 4.6",
        "url": GATEWAY_URL,
        "maxInputTokens": 200000,
        "maxOutputTokens": 8192,
        "toolCalling": True,
        "vision": True,
        "isDefault": False
    },
    {
        "id": "gemini-3.1-pro-preview",
        "name": "TCS: Gemini 3.1 Pro",
        "url": GATEWAY_URL,
        "maxInputTokens": 128000,
        "maxOutputTokens": 8192,
        "toolCalling": True,
        "vision": True,
        "isDefault": False
    },
    {
        "id": "genailab-maas-gpt-5.4",
        "name": "TCS: GPT-5.4",
        "url": GATEWAY_URL,
        "maxInputTokens": 128000,
        "maxOutputTokens": 8192,
        "toolCalling": True,
        "vision": True,
        "isDefault": False
    },
    {
        "id": "genailab-maas-gpt-5.2-codex",
        "name": "TCS: GPT-5.2 Codex",
        "url": GATEWAY_URL,
        "maxInputTokens": 128000,
        "maxOutputTokens": 8192,
        "toolCalling": True,
        "vision": True,
        "isDefault": False
    },
    {
        "id": "genailab-maas-gpt-5.1",
        "name": "TCS: GPT-5.1",
        "url": GATEWAY_URL,
        "maxInputTokens": 128000,
        "maxOutputTokens": 8192,
        "toolCalling": True,
        "vision": True,
        "isDefault": False
    },
    {
        "id": "azure/genailab-maas-gpt-4o-mini",
        "name": "TCS: GPT-4o Mini",
        "url": GATEWAY_URL,
        "maxInputTokens": 128000,
        "maxOutputTokens": 4096,
        "toolCalling": True,
        "vision": True,
        "isDefault": False
    }
]


def select_api_key():
    print("=" * 70)
    print(" TCS GenAI Lab - Configurador de GitHub Copilot")
    print("=" * 70)
    print("Seleccione el equipo o API Key a configurar:\n")
    for k, v in sorted(TEAMS.items()):
        marker = " (Default)" if k == "1" else ""
        print(f"  [{k}] {v[0]}  -  {v[1][:14]}...{marker}")
    print("  [C] Ingresar otra API Key manualmente\n")

    try:
        choice = input("Ingrese una opcion [1-6/C] (Enter para 1): ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"

    if not choice:
        choice = "1"

    if choice in TEAMS:
        alias, key, team_id = TEAMS[choice]
        print(f"\n-> Seleccionado: {alias} ({key})")
        return key, alias
    elif choice.upper() == "C":
        key = input("Pegue su API Key (sk-...): ").strip()
        if not key.startswith("sk-"):
            print("Advertencia: La clave no comienza con 'sk-'. Continuando...")
        return key, "Custom"
    else:
        print("Opcion no reconocida. Usando Peru_1 por defecto.")
        return TEAMS["1"][1], TEAMS["1"][0]


def patch_settings_json():
    print("\n[1/5] Actualizando configuracion de VS Code (settings.json)...")
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    settings_path = os.path.join(appdata, "Code", "User", "settings.json")

    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                # Quitar comentarios simples si existen
                content = f.read()
                settings = json.loads(content)
        except Exception as e:
            print(f"  Aviso: No se pudo parsear settings.json como JSON estricto ({e}). Creando respaldo...")
            shutil.copy(settings_path, settings_path + ".bak")

    settings["http.proxyStrictSSL"] = False
    settings["chat.agentHost.byokModels.enabled"] = True

    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)
    print("  [OK] settings.json configurado correctamente.")


def create_chat_language_models_json(api_key, team_alias):
    print("\n[2/5] Generando chatLanguageModels.json...")
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    config_path = os.path.join(appdata, "Code", "User", "chatLanguageModels.json")

    models_list = []
    for m in DEFAULT_MODELS_CONFIG:
        models_list.append({
            "id": m["id"],
            "name": m["name"],
            "url": m["url"],
            "toolCalling": m["toolCalling"],
            "vision": m["vision"],
            "maxInputTokens": m["maxInputTokens"],
            "maxOutputTokens": m["maxOutputTokens"]
        })

    config_data = [
        {
            "name": f"GenAI Lab LiteLLM ({team_alias})",
            "vendor": "customendpoint",
            "apiKey": api_key,
            "apiType": "chat-completions",
            "models": models_list
        }
    ]

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    print(f"  [OK] chatLanguageModels.json generado con {len(models_list)} modelos.")


def ensure_extensions_registered():
    print("\n[3/5] Verificando extensiones en extensions.json...")
    ext_dir = os.path.join(os.path.expanduser("~"), ".vscode", "extensions")
    ext_json_path = os.path.join(ext_dir, "extensions.json")

    if not os.path.exists(ext_json_path):
        print("  [INFO] No se encontro extensions.json, omitiendo registro manual.")
        return

    try:
        with open(ext_json_path, "r", encoding="utf-8") as f:
            exts = json.load(f)

        has_copilot = any(e.get("identifier", {}).get("id", "").lower() == "github.copilot" for e in exts)
        if not has_copilot:
            copilot_folders = glob.glob(os.path.join(ext_dir, "github.copilot-[0-9]*"))
            if copilot_folders:
                folder_name = os.path.basename(sorted(copilot_folders)[-1])
                version = folder_name.replace("github.copilot-", "")
                exts.append({
                    "identifier": {"id": "GitHub.copilot"},
                    "version": version,
                    "location": {
                        "$mid": 1,
                        "path": f"/c:/{ext_dir.replace('\\', '/')}/{folder_name}",
                        "scheme": "file"
                    },
                    "relativeLocation": folder_name,
                    "metadata": {
                        "isApplicationScoped": True,
                        "isMachineScoped": False,
                        "isBuiltin": False,
                        "pinned": False,
                        "source": "gallery",
                        "publisherDisplayName": "GitHub"
                    }
                })
                with open(ext_json_path, "w", encoding="utf-8") as f:
                    json.dump(exts, f, indent=2)
                print("  [OK] Extension GitHub.copilot registrada en extensions.json.")
        else:
            print("  [OK] Extensiones Copilot ya registradas.")
    except Exception as e:
        print(f"  [AVISO] No se pudo actualizar extensions.json ({e})")


def patch_copilot_chat(api_key):
    print("\n[4/5] Aplicando parches de compatibilidad a github.copilot-chat...")
    ext_base = os.path.join(os.path.expanduser("~"), ".vscode", "extensions")
    copilot_chat_dirs = sorted(glob.glob(os.path.join(ext_base, "github.copilot-chat-*")))

    if not copilot_chat_dirs:
        raise FileNotFoundError("No se encontro ninguna carpeta de la extension github.copilot-chat en ~/.vscode/extensions")

    patched_count = 0
    for target_dir in copilot_chat_dirs:
        ext_file = os.path.join(target_dir, "dist", "extension.js")
        if not os.path.exists(ext_file):
            continue

        print(f"  Procesando: {os.path.basename(target_dir)}")
        backup_file = ext_file + ".bak"

        # Si ya hay un respaldo limpio original, partimos de él para garantizar idempotencia
        if os.path.exists(backup_file):
            with open(backup_file, "r", encoding="utf-8") as f_bak:
                text = f_bak.read()
        else:
            with open(ext_file, "r", encoding="utf-8") as f_in:
                text = f_in.read()
            with open(backup_file, "w", encoding="utf-8") as f_out:
                f_out.write(text)
            print("  -> Respaldo creado en extension.js.bak")

        # 1. Parche Nee (Habilitar BYOK)
        t_nee = 'function Nee(r,e){let t=e.dotComAPIURL!=="https://api.github.com";return(r.isInternal||r.isIndividual)&&!t}'
        r_nee = 'function Nee(r,e){return true}'
        if t_nee in text:
            text = text.replace(t_nee, r_nee, 1)

        # 2. Parche UZe (Validacion de URL de endpoint)
        t_uze = 'function UZe(r){let e=/^https:\\/\\/([^.]+)\\..*\\.models\\.ai\\.azure\\.com\\//,t=r.match(e);if(t&&t[1])return t[1];let n=/\\/openai\\/deployments\\/([^\\/]+)\\//,o=r.match(n);if(o&&o[1])return o[1]}'
        r_uze = 'function UZe(r){let e=/^https:\\/\\/([^.]+)\\..*\\.models\\.ai\\.azure\\.com\\//,t=r.match(e);if(t&&t[1])return t[1];let n=/\\/openai\\/deployments\\/([^\\/]+)\\//,o=r.match(n);if(o&&o[1])return o[1];return "custom-model"}'
        if t_uze in text:
            text = text.replace(t_uze, r_uze, 1)

        # 3. Parche kee y Dee (Habilitar seleccion y default)
        t_kee = 'function kee(r){let e=r.capabilities.limits?.max_output_tokens??4096,t=r.capabilities.limits?.max_prompt_tokens??(r.capabilities.limits?.max_context_window_tokens||64e3)-e;return{family:r.capabilities.family,vendor:"copilot-byok",version:"1.0.0",maxOutputTokens:e,maxInputTokens:t,name:r.name,isUserSelectable:!0,capabilities:{agentMode:r.capabilities.supports.tool_calls,toolCalling:r.capabilities.supports.tool_calls,vision:r.capabilities.supports.vision}}}'
        r_kee = 'function kee(r){let e=r.capabilities.limits?.max_output_tokens??4096,t=r.capabilities.limits?.max_prompt_tokens??(r.capabilities.limits?.max_context_window_tokens||64e3)-e;return{family:r.capabilities.family,vendor:"copilot-byok",version:"1.0.0",maxOutputTokens:e,maxInputTokens:t,name:r.name,isDefault:!!r.is_chat_default,isUserSelectable:!0,capabilities:{agentMode:r.capabilities.supports.tool_calls,toolCalling:r.capabilities.supports.tool_calls,vision:r.capabilities.supports.vision}}}'
        if t_kee in text:
            text = text.replace(t_kee, r_kee, 1)

        t_dee = 'is_chat_default:!1,is_chat_fallback:!1,model_picker_enabled:!0}}function Nee('
        r_dee = 'is_chat_default:!!(o?.isDefault||r.includes("5.3")),is_chat_fallback:!1,model_picker_enabled:!0}}function Nee('
        if t_dee in text:
            text = text.replace(t_dee, r_dee, 1)

        # 4. Parche Yne y _TCS_DEFAULTS (Inyeccion de catalogo y API Key)
        t_yne = 'var Yne=class{constructor(e){this._extensionContext=e}async getAPIKey(e,t){if(t){let o=await this._extensionContext.secrets.get(`copilot-byok-${e}-${t}-api-key`);if(o)return o}return await this._extensionContext.secrets.get(`copilot-byok-${e}-api-key`)}async storeAPIKey(e,t,n,o){n!==2&&(n===0?await this._extensionContext.secrets.store(`copilot-byok-${e}-api-key`,t):n===1&&o&&await this._extensionContext.secrets.store(`copilot-byok-${e}-${o}-api-key`,t))}async deleteAPIKey(e,t,n){t!==2&&(t===0?await this._extensionContext.secrets.delete(`copilot-byok-${e}-api-key`):t===1&&n&&await this._extensionContext.secrets.delete(`copilot-byok-${e}-${n}-api-key`))}async getStoredModelConfigs(e){return this._extensionContext.globalState.get(`copilot-byok-${e}-models-config`,{})}async saveModelConfig(e,t,n,o){let s={isCustomModel:n.isCustomModel,deploymentUrl:n.deploymentUrl,isRegistered:!0,modelCapabilities:n.modelCapabilities},a=await this.getStoredModelConfigs(t);a[e]=s,await this._extensionContext.globalState.update(`copilot-byok-${t}-models-config`,a),await this.storeAPIKey(t,n.apiKey,o,e)}async removeModelConfig(e,t,n){let o=await this.getStoredModelConfigs(t),s=o[e],a=s?.isCustomModel||!1;s&&(n||!a)?(delete o[e],await this._extensionContext.globalState.update(`copilot-byok-${t}-models-config`,o),await this._extensionContext.secrets.delete(`copilot-byok-${t}-${e}-api-key`)):(s.isRegistered=!1,await this._extensionContext.globalState.update(`copilot-byok-${t}-models-config`,o))}};'

        r_yne = f'''var _TCS_DEFAULTS={{
"genailab-maas-gpt-5.3-codex":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: GPT-5.3 Codex",maxInputTokens:128e3,maxOutputTokens:8192,toolCalling:!0,vision:!0,isDefault:!0}}}},
"genailab-maas-gpt-4o":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: GPT-4o",maxInputTokens:128e3,maxOutputTokens:4096,toolCalling:!0,vision:!0,isDefault:!1}}}},
"genailab-maas-sonnet-4.6":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: Claude Sonnet 4.6",maxInputTokens:200e3,maxOutputTokens:8192,toolCalling:!0,vision:!0,isDefault:!1}}}},
"gemini-3.1-pro-preview":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: Gemini 3.1 Pro",maxInputTokens:128e3,maxOutputTokens:8192,toolCalling:!0,vision:!0,isDefault:!1}}}},
"genailab-maas-gpt-5.4":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: GPT-5.4",maxInputTokens:128e3,maxOutputTokens:8192,toolCalling:!0,vision:!0,isDefault:!1}}}},
"genailab-maas-gpt-5.2-codex":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: GPT-5.2 Codex",maxInputTokens:128e3,maxOutputTokens:8192,toolCalling:!0,vision:!0,isDefault:!1}}}},
"genailab-maas-gpt-5.1":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: GPT-5.1",maxInputTokens:128e3,maxOutputTokens:8192,toolCalling:!0,vision:!0,isDefault:!1}}}},
"azure/genailab-maas-gpt-4o-mini":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: GPT-4o Mini",maxInputTokens:128e3,maxOutputTokens:4096,toolCalling:!0,vision:!0,isDefault:!1}}}}
}};
var Yne=class{{constructor(e){{this._extensionContext=e}}async getAPIKey(e,t){{if(t){{let o=await this._extensionContext.secrets.get(`copilot-byok-${{e}}-${{t}}-api-key`);if(o&&o.trim())return o.trim()}}let k=await this._extensionContext.secrets.get(`copilot-byok-${{e}}-api-key`);if(k&&k.trim())return k.trim();if(e==="Azure")return"{api_key}";return void 0}}async storeAPIKey(e,t,n,o){{n!==2&&(n===0?await this._extensionContext.secrets.store(`copilot-byok-${{e}}-api-key`,t):n===1&&o&&await this._extensionContext.secrets.store(`copilot-byok-${{e}}-${{o}}-api-key`,t))}}async deleteAPIKey(e,t,n){{t!==2&&(t===0?await this._extensionContext.secrets.delete(`copilot-byok-${{e}}-api-key`):t===1&&n&&await this._extensionContext.secrets.delete(`copilot-byok-${{e}}-${{n}}-api-key`))}}async getStoredModelConfigs(e){{let g=this._extensionContext.globalState.get(`copilot-byok-${{e}}-models-config`,{{}});if(e==="Azure")return{{..._TCS_DEFAULTS,...g}};return g}}async saveModelConfig(e,t,n,o){{let s={{isCustomModel:n.isCustomModel,deploymentUrl:n.deploymentUrl,isRegistered:!0,modelCapabilities:n.modelCapabilities}},a=await this.getStoredModelConfigs(t);a[e]=s,await this._extensionContext.globalState.update(`copilot-byok-${{t}}-models-config`,a),await this.storeAPIKey(t,n.apiKey,o,e)}}async removeModelConfig(e,t,n){{let o=await this.getStoredModelConfigs(t),s=o[e],a=s?.isCustomModel||!1;s&&(n||!a)?(delete o[e],await this._extensionContext.globalState.update(`copilot-byok-${{t}}-models-config`,o),await this._extensionContext.secrets.delete(`copilot-byok-${{t}}-${{e}}-api-key`)):(s.isRegistered=!1,await this._extensionContext.globalState.update(`copilot-byok-${{t}}-models-config`,o))}}}};'''

        if t_yne in text:
            text = text.replace(t_yne, r_yne, 1)

        # 5. Parche Sh.interceptBody (Evita Error 400 por top_p/temperature/stream_options y fija el ID del modelo)
        t_body = 'interceptBody(t){super.interceptBody(t),t?.tools?.length===0&&delete t.tools,t&&(t.stream_options={include_usage:!0})}'
        r_body = 'interceptBody(t){super.interceptBody(t),t?.tools?.length===0&&delete t.tools,t&&(this._modelInfo?.id&&(t.model=this._modelInfo.id),t.stream?t.stream_options={include_usage:!0}:delete t.stream_options,delete t.top_p,delete t.n,(t.model?.includes("gpt-5")||t.model?.startsWith("o"))&&delete t.temperature)}'
        if t_body in text:
            text = text.replace(t_body, r_body, 1)

        # 6. Parche switchToBaseModel (Evita que Copilot cambie el modelo a gpt-5-mini al terminarse la cuota de GitHub)
        idx_switch = text.find('async switchToBaseModel(e,t)')
        if idx_switch != -1:
            idx_switch_end = text.find('};LX=T(', idx_switch)
            if idx_switch_end != -1:
                target_switch = text[idx_switch:idx_switch_end]
                text = text.replace(target_switch, 'async switchToBaseModel(e,t){return e}', 1)

        # 7. Parche quotaExhausted (Evita banderas de cuota agotada)
        t_quota = 'get quotaExhausted(){return this._quotaInfo?this._quotaInfo.used>=this._quotaInfo.quota&&!this._quotaInfo.overageEnabled&&!this._quotaInfo.unlimited:!1}'
        r_quota = 'get quotaExhausted(){return!1}'
        if t_quota in text:
            text = text.replace(t_quota, r_quota, 1)

        with open(ext_file, "w", encoding="utf-8") as f:
            f.write(text)

        # Validar sintaxis usando node si esta disponible
        res = subprocess.run(["node", "--check", ext_file], capture_output=True, text=True)
        if res.returncode == 0:
            print("  [OK] Parches aplicados y sintaxis JavaScript validada exitosamente.")
            patched_count += 1
        else:
            print(f"  [ERROR] Error de sintaxis tras parchear {ext_file}: {res.stderr}")
            # Restaurar respaldo en caso de falla
            shutil.copy(backup_file, ext_file)
            print("  [INFO] Se restauro el archivo original desde extension.js.bak")

    if patched_count == 0:
        print("  [AVISO] No se pudo parchear ningun archivo de extension.")


def sync_vscdb(api_key):
    print("\n[5/5] Sincronizando base de datos local (state.vscdb)...")
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    db_path = os.path.join(appdata, "Code", "User", "globalStorage", "state.vscdb")

    if not os.path.exists(db_path):
        print("  [INFO] state.vscdb no existe aun (se creara automaticamente al iniciar VS Code).")
        return

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT value FROM ItemTable WHERE key = 'GitHub.copilot-chat'")
        row = cur.fetchone()
        state = json.loads(row[0]) if row else {}

        models_dict = {}
        for m in DEFAULT_MODELS_CONFIG:
            models_dict[m["id"]] = {
                "isCustomModel": True,
                "deploymentUrl": m["url"],
                "isRegistered": True,
                "modelCapabilities": {
                    "name": m["name"],
                    "maxInputTokens": m["maxInputTokens"],
                    "maxOutputTokens": m["maxOutputTokens"],
                    "toolCalling": m["toolCalling"],
                    "vision": m["vision"],
                    "isDefault": m["isDefault"]
                }
            }

        state["copilot-byok-Azure-models-config"] = models_dict
        cur.execute("UPDATE ItemTable SET value = ? WHERE key = 'GitHub.copilot-chat'", (json.dumps(state),))
        conn.commit()
        conn.close()
        print("  [OK] Base de datos state.vscdb actualizada.")
    except Exception as e:
        print(f"  [AVISO] Error al actualizar state.vscdb ({e}). Los parches en extension.js seguiran funcionando.")


def main():
    parser = argparse.ArgumentParser(description="TCS GenAI Lab - Setup de GitHub Copilot")
    parser.add_argument("--key", help="API Key de LiteLLM (sk-...)")
    parser.add_argument("--team", help="Numero de equipo (1-6)")
    args = parser.parse_args()

    if args.key:
        api_key = args.key
        team_alias = "Custom"
    elif args.team and args.team in TEAMS:
        team_alias, api_key, _ = TEAMS[args.team]
    else:
        api_key, team_alias = select_api_key()

    print(f"\nIniciando configuracion con API Key de: {team_alias}")
    patch_settings_json()
    create_chat_language_models_json(api_key, team_alias)
    ensure_extensions_registered()
    patch_copilot_chat(api_key)
    sync_vscdb(api_key)

    print("\n" + "=" * 70)
    print(" INSTALACION COMPLETADA CON EXITO")
    print("=" * 70)
    print("Para aplicar los cambios en Visual Studio Code:")
    print("  1. Abre o ve a Visual Studio Code.")
    print("  2. Presiona Ctrl + Shift + P")
    print("  3. Ejecuta: Developer: Reload Window  (o reinicia VS Code)")
    print("  4. Abre GitHub Copilot Chat (Ctrl + Alt + I) y selecciona")
    print("     'TCS: GPT-5.3 Codex' o cualquiera de los modelos TCS.")
    print("=" * 70)


if __name__ == "__main__":
    main()

