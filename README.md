# 📁 Organizador de Arquivos

![Status](https://img.shields.io/badge/status-em%20produ%C3%A7%C3%A3o-success)
[![Release](https://img.shields.io/github/v/release/sthevan027/organizador)](https://github.com/sthevan027/organizador/releases/latest)

![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white) ![CustomTkinter](https://img.shields.io/badge/CustomTkinter-5.2-3776AB?logo=python&logoColor=white) ![Pillow](https://img.shields.io/badge/Pillow-10-3776AB?logo=python&logoColor=white)

Script Python para organizar automaticamente arquivos por tipo/extensão na pasta Downloads (ou qualquer outra pasta).

## ✨ Funcionalidades

- 🗂️ **Organização automática** por tipo de arquivo (imagens, documentos, vídeos, etc.)
- 🏠 **Modo bibliotecas do sistema** (Windows) — envia arquivos direto para Documentos, Imagens, Vídeos e Música reais
- 🔄 **Modo move ou copy** - escolha se quer mover ou copiar os arquivos
- 🧪 **Dry-run** - teste sem alterar nada
- ⚙️ **Configuração personalizada** via arquivo JSON
- 📝 **Log detalhado** de todas as operações
- 🗑️ **Limpeza opcional** de pastas vazias
- 🛡️ **Proteção contra sobrescrita** - adiciona contador se arquivo já existir
- 🧹 **Limpeza de Disco** - temporários do Windows, cache de navegadores, Lixeira, downloads parados e cache de desenvolvimento (veja a seção dedicada abaixo)

## 🚀 Instalação

> **Windows, sem instalar Python**: baixe o `.exe` pronto em
> [Releases](https://github.com/sthevan027/organizador/releases/latest) e
> dê duplo clique. O Windows pode avisar "Windows protegeu seu PC"
> (SmartScreen, por ser um `.exe` não assinado) — clique em "Mais
> informações" → "Executar assim mesmo".

Pra rodar a partir do código-fonte:

1. **Clone ou baixe** os arquivos do projeto
2. **Python 3.10+** é necessário
3. Instale as dependências da interface:

```bash
pip install -r requirements.txt
```

> O core (`organizer.py`) usa apenas a biblioteca padrão. As dependências são
> só para a GUI moderna (`customtkinter`) e geração do ícone (`Pillow`).

### Abrir a interface gráfica

- **Windows**: basta dar duplo clique em `iniciar.bat` (ele instala as
  dependências no primeiro uso e abre a GUI sem console preto).
- **Linux/macOS**: `./iniciar.sh` ou `python run.py`.

### Criar atalho na Área de Trabalho (Windows)

Dê duplo clique em `scripts/criar_atalho.bat`. Um atalho
**Organizador de Arquivos** com ícone customizado será criado na sua Área de
Trabalho, apontando para o `pythonw run.py` (GUI sem console).

### Navegação e tema

Ao lado do título, dois ícones trocam de tela sem abrir outra janela: 🗂️
**Organizador** e 🧹 **Limpeza de Disco**. No canto superior direito fica o
seletor `☀ / 🌙` de tema claro/escuro — a preferência fica salva em
`%APPDATA%\organizador\config.json`.

Opções usadas com menos frequência (pasta para tipos não reconhecidos,
config JSON personalizada, dias de inatividade etc.) ficam recolhidas em
**"▸ Opções avançadas"**, tanto no Organizador quanto na Limpeza — a tela
principal mostra só o essencial.

## 📖 Como Usar

### Uso Básico

```bash
# Organizar pasta Downloads movendo arquivos
python organizer.py --source "C:/Users/SEU_USUARIO/Downloads"

# Organizar pasta Downloads copiando arquivos (mantém originais)
python organizer.py --source "C:/Users/SEU_USUARIO/Downloads" --mode copy
```

### Teste Seguro (Dry-run)

```bash
# Ver o que seria feito sem alterar nada
python organizer.py --source "C:/Users/SEU_USUARIO/Downloads" --dry-run
```

### Destino Personalizado

```bash
# Organizar em pasta diferente
python organizer.py --source "C:/Users/SEU_USUARIO/Downloads" --dest "C:/Users/SEU_USUARIO/Downloads/Organizado"
```

### Com Log

```bash
# Salvar log das operações
python organizer.py --source "C:/Users/SEU_USUARIO/Downloads" --log logs/organizer.log
```

### Configuração Personalizada

```bash
# Usar seu próprio mapeamento de extensões
python organizer.py --source "C:/Users/SEU_USUARIO/Downloads" --config config_extensoes.json
```

### Limpeza de Pastas Vazias

```bash
# Apagar subpastas vazias após organização
python organizer.py --source "C:/Users/SEU_USUARIO/Downloads" --delete-empty
```

### Modo Bibliotecas do Sistema (Windows)

Envia cada arquivo diretamente para a biblioteca real do Windows, respeitando
redirecionamentos do OneDrive e configurações de perfil:

```bash
# Simular (ver o que aconteceria)
python organizer.py --source "C:/Users/SEU_USUARIO/Downloads" --system-folders --dry-run

# Organizar de verdade
python organizer.py --source "C:/Users/SEU_USUARIO/Downloads" --system-folders --mode move
```

| Categoria | Destino no modo bibliotecas |
|-----------|----------------------------|
| Imagens | Pasta Imagens do Windows (`%USERPROFILE%\Pictures`) |
| Documentos | Pasta Documentos (`%USERPROFILE%\Documents`) |
| Vídeos | Pasta Vídeos (`%USERPROFILE%\Videos`) |
| Áudio | Pasta Música (`%USERPROFILE%\Music`) |
| Compactados | Raiz de Documentos |
| Programas | `source\Programas` (subpasta na origem) |
| Código / Design / Fontes / Outros | `Documentos\<nome da categoria>` |
| Categorias personalizadas (JSON) | `Documentos\<nome da categoria>` |

> **Observação**: o campo Destino é ignorado para as categorias acima.
> Instaladores (`.exe`, `.msi`, …) sempre ficam em uma subpasta `Programas`
> dentro da pasta de origem para facilitar limpeza manual posterior.

## 🧹 Limpeza de Disco

Funcionalidade separada (`cleaner.py` / `cleaner_gui.py`) para liberar espaço
em disco. Sempre analisa antes de apagar — nada é removido sem revisão.

### Categorias

| Categoria | O que é |
|-----------|---------|
| Temporários | `%TEMP%` do usuário, `C:\Windows\Temp` e Prefetch |
| Cache de navegadores | Cache de Chrome, Edge e Firefox — **nunca** senhas, histórico ou cookies |
| Lixeira | Esvazia a Lixeira do Windows |
| Downloads parados | **Lista** (não apaga sozinho) arquivos sem uso há X dias em Downloads |
| Cache de dev | `node_modules` de projetos parados + cache do npm/pip/Docker |
| Crash dumps de apps | Dumps de erro do Windows (WER) e `%LOCALAPPDATA%\CrashDumps` — sobras de apps que travaram |

### Pela interface gráfica

Clique no ícone 🧹 ao lado do título para trocar pra tela de Limpeza de
Disco (mesma janela, sem abrir outra). Fluxo: marque as categorias →
**Analisar** (sempre seguro, só lista e soma tamanhos) → revise o
relatório → **Limpar selecionadas** (com "Modo Teste" ligado por padrão;
desligue e confirme para remover de verdade). Clique no ícone 🗂️ pra
voltar à tela de organização.

### Pela linha de comando

```bash
# Analisar tudo, sem apagar nada (padrão)
python cleaner.py

# Analisar só temporários e cache de navegador
python cleaner.py --categories temp,browser_cache

# Aplicar de verdade (pede confirmação, a menos que --yes seja usado)
python cleaner.py --apply

# Incluir cache de dev, procurando node_modules órfãos em D:/Projetos
python cleaner.py --categories dev_cache --dev-search-root D:/Projetos --apply

# Analisar crash dumps de apps (WER)
python cleaner.py --categories crash_dumps
```

| Parâmetro | Descrição | Padrão |
|-----------|-----------|---------|
| `--categories` | Categorias separadas por vírgula | todas |
| `--apply` | Remove de verdade (sem isso, só simula) | False |
| `--yes` | Não pede confirmação antes de aplicar | False |
| `--old-downloads-days` | Dias sem uso para listar em Downloads parados | 30 |
| `--dev-search-root` | Pasta onde procurar `node_modules` órfãos (repetível) | nenhuma |
| `--dev-stale-days` | Dias sem atividade para considerar `node_modules` órfão | 60 |

## ⚙️ Configuração

### Arquivo de Configuração (config_extensoes.json)

```json
{
  "Imagens": [".jpg", ".jpeg", ".png", ".gif"],
  "Documentos": [".pdf", ".docx", ".txt"],
  "Compactados": [".zip", ".rar"],
  "Planilhas": [".xls", ".xlsx", ".csv"]
}
```

### Categorias Padrão

O script já vem com categorias pré-definidas:

- **Imagens**: .jpg, .jpeg, .png, .gif, .bmp, .tiff, .webp, .svg, .heic
- **Documentos**: .pdf, .doc, .docx, .txt, .rtf, .odt, .csv, .xls, .xlsx, .ppt, .pptx, .md
- **Compactados**: .zip, .rar, .7z, .tar, .gz, .bz2, .xz
- **Vídeos**: .mp4, .mkv, .mov, .avi, .wmv, .flv, .webm
- **Áudio**: .mp3, .wav, .flac, .aac, .ogg, .m4a
- **Programas**: .exe, .msi, .dmg, .pkg, .apk
- **Código**: .py, .js, .ts, .java, .c, .cpp, .cs, .php, .go, .rb, .rs, .sh, .ps1
- **Design**: .psd, .ai, .xd, .fig, .sketch, .eps
- **Fontes**: .ttf, .otf, .woff, .woff2

## 📋 Parâmetros

| Parâmetro | Descrição | Padrão |
|-----------|-----------|---------|
| `--source`, `-s` | Pasta a organizar (obrigatório) | - |
| `--dest`, `-d` | Pasta de destino | Mesma da origem |
| `--mode` | Modo: move ou copy | move |
| `--dry-run` | Apenas simular, não alterar | False |
| `--delete-empty` | Apagar subpastas vazias | False |
| `--unknown-name` | Nome da pasta para extensões não mapeadas | "Outros" |
| `--config` | Arquivo JSON com configuração | Padrão |
| `--log` | Arquivo de log | - |
| `--system-folders` | Enviar para bibliotecas reais do Windows | False |

## 📝 Exemplos de Log

```
[OK] MOVER: foto.jpg -> C:\Users\Usuario\Downloads\Imagens\foto.jpg
[OK] MOVER: documento.pdf -> C:\Users\Usuario\Downloads\Documentos\documento.pdf
[DRY-RUN] COPIAR: video.mp4 -> C:\Users\Usuario\Downloads\Vídeos\video.mp4

Arquivos processados: 15 | movidos/cop.: 12 | pulados: 2 | erros: 1
```

## 🛡️ Segurança

- **Dry-run**: Sempre teste primeiro com `--dry-run`
- **Backup**: Use `--mode copy` para manter originais
- **Proteção**: Arquivos com mesmo nome recebem contador (arquivo (1).txt)
- **Logs**: Todas as operações são registradas

## 🔧 Criando Executável

Para criar um arquivo .exe (Windows) já com o ícone embutido (é assim que
o `.exe` das [Releases](https://github.com/sthevan027/organizador/releases)
é gerado):

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=assets/organizer.ico --name Organizador run.py
```

O executável final fica em `dist/Organizador.exe`.

## 🐛 Solução de Problemas

### Erro de Permissão
- Execute como administrador (Windows)
- Verifique permissões da pasta

### Arquivo não encontrado
- Use caminhos absolutos
- Verifique se a pasta existe

### Python não encontrado
- Instale Python 3.10+ do [python.org](https://python.org)
- Adicione Python ao PATH

## 📄 Licença

Este projeto é de código aberto. Use e modifique livremente.

## 🤝 Contribuições

Sugestões e melhorias são bem-vindas!

---

**⚠️ Importante**: Sempre teste com `--dry-run` antes de usar em pastas importantes!
