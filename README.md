# 📁 Organizador de Arquivos

Script Python para organizar automaticamente arquivos por tipo/extensão na pasta Downloads (ou qualquer outra pasta).

## ✨ Funcionalidades

- 🗂️ **Organização automática** por tipo de arquivo (imagens, documentos, vídeos, etc.)
- 🔄 **Modo move ou copy** - escolha se quer mover ou copiar os arquivos
- 🧪 **Dry-run** - teste sem alterar nada
- ⚙️ **Configuração personalizada** via arquivo JSON
- 📝 **Log detalhado** de todas as operações
- 🗑️ **Limpeza opcional** de pastas vazias
- 🛡️ **Proteção contra sobrescrita** - adiciona contador se arquivo já existir

## 🚀 Instalação

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

### Alternar tema claro/escuro

No canto superior direito da janela há um botão `☀ / 🌙` que alterna entre
claro e escuro. A preferência fica salva em
`%APPDATA%\organizador\config.json`.

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

Para criar um arquivo .exe (Windows) já com o ícone embutido:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=assets/organizer.ico run.py
```

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
