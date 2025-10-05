#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path

# Cria pasta de teste se não existir
test_dir = Path("test_files")
test_dir.mkdir(exist_ok=True)

# Lista de arquivos de teste
test_files = [
    ("documento.txt", "Este é um arquivo de texto para teste"),
    ("script.py", "print('Este é um script Python para teste')"),
    ("imagem.jpg", "Dados simulados de uma imagem"),
    ("video.mp4", "Dados simulados de um vídeo"),
    ("musica.mp3", "Dados simulados de um arquivo de áudio"),
    ("arquivo.zip", "Dados simulados de um arquivo compactado"),
    ("planilha.xlsx", "Dados simulados de uma planilha Excel"),
    ("apresentacao.pptx", "Dados simulados de uma apresentação"),
    ("codigo.js", "console.log('Este é um arquivo JavaScript para teste')"),
    ("estilo.css", "body { color: blue; }"),
]

# Cria os arquivos de teste
for filename, content in test_files:
    file_path = test_dir / filename
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Criado: {file_path}")

print(f"\nArquivos de teste criados em: {test_dir.absolute()}")
print("Total de arquivos:", len(test_files))
