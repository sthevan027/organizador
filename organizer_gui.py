#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import sys
from pathlib import Path
import json
import time
import os
from typing import Optional

# Importa o organizador
from organizer import organize, load_map, DEFAULT_MAP

class OrganizerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("📁 Organizador de Arquivos")
        self.root.geometry("800x600")
        self.root.configure(bg='#f0f0f0')
        
        # Variáveis
        self.source_path = tk.StringVar()
        self.dest_path = tk.StringVar()
        self.mode = tk.StringVar(value="move")
        self.dry_run = tk.BooleanVar(value=True)
        self.delete_empty = tk.BooleanVar(value=False)
        self.unknown_name = tk.StringVar(value="Outros")
        self.config_path = tk.StringVar()
        self.max_workers = tk.IntVar(value=4)
        
        # Queue para comunicação entre threads
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        
        # Estado da operação
        self.is_organizing = False
        
        self.setup_ui()
        self.check_log_queue()
        
    def setup_ui(self):
        """Configura a interface do usuário."""
        
        # Título
        title_frame = tk.Frame(self.root, bg='#2c3e50', height=60)
        title_frame.pack(fill='x', padx=10, pady=10)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(title_frame, text="📁 Organizador de Arquivos", 
                              font=('Arial', 16, 'bold'), fg='white', bg='#2c3e50')
        title_label.pack(expand=True)
        
        # Frame principal
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Configurações
        self.setup_config_section(main_frame)
        
        # Opções
        self.setup_options_section(main_frame)
        
        # Botões
        self.setup_buttons_section(main_frame)
        
        # Progress Bar
        self.setup_progress_section(main_frame)
        
        # Log
        self.setup_log_section(main_frame)
        
    def setup_config_section(self, parent):
        """Configura a seção de configurações."""
        config_frame = tk.LabelFrame(parent, text="📂 Configurações", 
                                   font=('Arial', 10, 'bold'), bg='#f0f0f0')
        config_frame.pack(fill='x', pady=5)
        
        # Pasta origem
        tk.Label(config_frame, text="Pasta de Origem:", bg='#f0f0f0').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        tk.Entry(config_frame, textvariable=self.source_path, width=50).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(config_frame, text="📁", command=self.browse_source, 
                 bg='#3498db', fg='white', width=3).grid(row=0, column=2, padx=5, pady=5)
        
        # Pasta destino
        tk.Label(config_frame, text="Pasta de Destino:", bg='#f0f0f0').grid(row=1, column=0, sticky='w', padx=5, pady=5)
        tk.Entry(config_frame, textvariable=self.dest_path, width=50).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(config_frame, text="📁", command=self.browse_dest, 
                 bg='#3498db', fg='white', width=3).grid(row=1, column=2, padx=5, pady=5)
        
        # Configuração personalizada
        tk.Label(config_frame, text="Config. JSON:", bg='#f0f0f0').grid(row=2, column=0, sticky='w', padx=5, pady=5)
        tk.Entry(config_frame, textvariable=self.config_path, width=50).grid(row=2, column=1, padx=5, pady=5)
        tk.Button(config_frame, text="📄", command=self.browse_config, 
                 bg='#e67e22', fg='white', width=3).grid(row=2, column=2, padx=5, pady=5)
        
    def setup_options_section(self, parent):
        """Configura a seção de opções."""
        options_frame = tk.LabelFrame(parent, text="⚙️ Opções", 
                                    font=('Arial', 10, 'bold'), bg='#f0f0f0')
        options_frame.pack(fill='x', pady=5)
        
        # Modo
        mode_frame = tk.Frame(options_frame, bg='#f0f0f0')
        mode_frame.pack(fill='x', padx=5, pady=5)
        
        tk.Label(mode_frame, text="Modo:", bg='#f0f0f0').pack(side='left')
        tk.Radiobutton(mode_frame, text="Mover (remove originais)", variable=self.mode, 
                      value="move", bg='#f0f0f0').pack(side='left', padx=10)
        tk.Radiobutton(mode_frame, text="Copiar (mantém originais)", variable=self.mode, 
                      value="copy", bg='#f0f0f0').pack(side='left', padx=10)
        
        # Opções adicionais
        options_frame2 = tk.Frame(options_frame, bg='#f0f0f0')
        options_frame2.pack(fill='x', padx=5, pady=5)
        
        tk.Checkbutton(options_frame2, text="🧪 Teste (Dry-run)", variable=self.dry_run, 
                      bg='#f0f0f0').pack(side='left', padx=5)
        tk.Checkbutton(options_frame2, text="🗑️ Apagar pastas vazias", variable=self.delete_empty, 
                      bg='#f0f0f0').pack(side='left', padx=5)
        
        # Nome para arquivos desconhecidos
        unknown_frame = tk.Frame(options_frame, bg='#f0f0f0')
        unknown_frame.pack(fill='x', padx=5, pady=5)
        
        tk.Label(unknown_frame, text="Pasta para arquivos desconhecidos:", bg='#f0f0f0').pack(side='left')
        tk.Entry(unknown_frame, textvariable=self.unknown_name, width=15).pack(side='left', padx=5)
        
        # Threads paralelas
        threads_frame = tk.Frame(options_frame, bg='#f0f0f0')
        threads_frame.pack(fill='x', padx=5, pady=5)
        
        tk.Label(threads_frame, text="Threads paralelas:", bg='#f0f0f0').pack(side='left')
        tk.Scale(threads_frame, from_=1, to=8, orient='horizontal', 
                variable=self.max_workers, bg='#f0f0f0').pack(side='left', padx=5)
        
    def setup_buttons_section(self, parent):
        """Configura a seção de botões."""
        buttons_frame = tk.Frame(parent, bg='#f0f0f0')
        buttons_frame.pack(fill='x', pady=10)
        
        # Botão organizar
        self.organize_btn = tk.Button(buttons_frame, text="🚀 ORGANIZAR", 
                                    command=self.start_organize, font=('Arial', 12, 'bold'),
                                    bg='#27ae60', fg='white', height=2)
        self.organize_btn.pack(side='left', padx=5)
        
        # Botão limpar log
        tk.Button(buttons_frame, text="🧹 Limpar Log", 
                 command=self.clear_log, bg='#95a5a6', fg='white').pack(side='left', padx=5)
        
        # Botão salvar log
        tk.Button(buttons_frame, text="💾 Salvar Log", 
                 command=self.save_log, bg='#3498db', fg='white').pack(side='left', padx=5)
        
        # Botão configuração padrão
        tk.Button(buttons_frame, text="⚙️ Config Padrão", 
                 command=self.show_default_config, bg='#9b59b6', fg='white').pack(side='left', padx=5)
        
        # Botão cancelar
        self.cancel_btn = tk.Button(buttons_frame, text="❌ Cancelar", 
                                   command=self.cancel_operation, bg='#e74c3c', fg='white', state='disabled')
        self.cancel_btn.pack(side='left', padx=5)
        
    def setup_progress_section(self, parent):
        """Configura a seção de progresso."""
        progress_frame = tk.LabelFrame(parent, text="📊 Progresso", 
                                     font=('Arial', 10, 'bold'), bg='#f0f0f0')
        progress_frame.pack(fill='x', pady=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                          maximum=100, length=400)
        self.progress_bar.pack(pady=5)
        
        # Label de status
        self.status_label = tk.Label(progress_frame, text="Pronto para organizar", 
                                   bg='#f0f0f0', font=('Arial', 9))
        self.status_label.pack(pady=2)
        
    def setup_log_section(self, parent):
        """Configura a seção de log."""
        log_frame = tk.LabelFrame(parent, text="📝 Log de Operações", 
                                font=('Arial', 10, 'bold'), bg='#f0f0f0')
        log_frame.pack(fill='both', expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, 
                                                font=('Consolas', 9), bg='#2c3e50', fg='#ecf0f1')
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)
        
    def browse_source(self):
        """Abre diálogo para selecionar pasta de origem."""
        folder = filedialog.askdirectory(title="Selecionar pasta de origem")
        if folder:
            self.source_path.set(folder)
            # Se destino não estiver definido, usa a mesma pasta
            if not self.dest_path.get():
                self.dest_path.set(folder)
    
    def browse_dest(self):
        """Abre diálogo para selecionar pasta de destino."""
        folder = filedialog.askdirectory(title="Selecionar pasta de destino")
        if folder:
            self.dest_path.set(folder)
    
    def browse_config(self):
        """Abre diálogo para selecionar arquivo de configuração."""
        file = filedialog.askopenfilename(title="Selecionar arquivo de configuração JSON",
                                        filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file:
            self.config_path.set(file)
    
    def clear_log(self):
        """Limpa o log."""
        self.log_text.delete(1.0, tk.END)
    
    def save_log(self):
        """Salva o log em arquivo."""
        content = self.log_text.get(1.0, tk.END)
        if not content.strip():
            messagebox.showwarning("Aviso", "Log está vazio!")
            return
        
        file = filedialog.asksaveasfilename(title="Salvar log",
                                          defaultextension=".txt",
                                          filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file:
            try:
                with open(file, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Sucesso", f"Log salvo em: {file}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar log: {e}")
    
    def show_default_config(self):
        """Mostra a configuração padrão."""
        config_window = tk.Toplevel(self.root)
        config_window.title("Configuração Padrão")
        config_window.geometry("600x400")
        config_window.configure(bg='#f0f0f0')
        
        # Texto da configuração
        config_text = scrolledtext.ScrolledText(config_window, font=('Consolas', 10))
        config_text.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Converte DEFAULT_MAP para JSON formatado
        config_json = json.dumps(DEFAULT_MAP, indent=2, ensure_ascii=False)
        config_text.insert(1.0, config_json)
        config_text.config(state='disabled')
        
        # Botão salvar
        tk.Button(config_window, text="💾 Salvar como...", 
                 command=lambda: self.save_config_file(config_json),
                 bg='#27ae60', fg='white').pack(pady=10)
    
    def save_config_file(self, config_json):
        """Salva a configuração padrão em arquivo."""
        file = filedialog.asksaveasfilename(title="Salvar configuração",
                                          defaultextension=".json",
                                          filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if file:
            try:
                with open(file, 'w', encoding='utf-8') as f:
                    f.write(config_json)
                messagebox.showinfo("Sucesso", f"Configuração salva em: {file}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar configuração: {e}")
    
    def log_message(self, message):
        """Adiciona mensagem ao log."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def check_log_queue(self):
        """Verifica a queue de log e atualiza a interface."""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_message(message)
        except queue.Empty:
            pass
        
        # Verifica progresso
        try:
            while True:
                progress_data = self.progress_queue.get_nowait()
                if isinstance(progress_data, dict):
                    if 'progress' in progress_data:
                        self.progress_var.set(progress_data['progress'])
                    if 'status' in progress_data:
                        self.status_label.config(text=progress_data['status'])
                elif isinstance(progress_data, (int, float)):
                    self.progress_var.set(progress_data)
        except queue.Empty:
            pass
        
        # Agenda próxima verificação
        self.root.after(100, self.check_log_queue)
    
    def cancel_operation(self):
        """Cancela a operação em andamento."""
        if self.is_organizing:
            self.is_organizing = False
            self.log_message("⚠️ Operação cancelada pelo usuário")
            self.update_ui_state(False)
    
    def update_ui_state(self, organizing: bool):
        """Atualiza o estado da interface."""
        self.is_organizing = organizing
        
        if organizing:
            self.organize_btn.config(state='disabled', text="⏳ Organizando...")
            self.cancel_btn.config(state='normal')
            self.progress_var.set(0)
            self.status_label.config(text="Iniciando organização...")
        else:
            self.organize_btn.config(state='normal', text="🚀 ORGANIZAR")
            self.cancel_btn.config(state='disabled')
            self.status_label.config(text="Pronto para organizar")
    
    def start_organize(self):
        """Inicia o processo de organização em thread separada."""
        # Validações
        if not self.source_path.get():
            messagebox.showerror("Erro", "Selecione uma pasta de origem!")
            return
        
        if not self.dest_path.get():
            messagebox.showerror("Erro", "Selecione uma pasta de destino!")
            return
        
        # Atualiza estado da UI
        self.update_ui_state(True)
        
        # Inicia thread
        thread = threading.Thread(target=self.organize_thread)
        thread.daemon = True
        thread.start()
    
    def organize_thread(self):
        """Thread para executar a organização."""
        try:
            # Prepara parâmetros
            source = Path(self.source_path.get())
            dest = Path(self.dest_path.get())
            config_path = Path(self.config_path.get()) if self.config_path.get() else None
            
            # Carrega configuração
            ext_map = load_map(config_path)
            
            # Log inicial
            self.log_queue.put("=" * 60)
            self.log_queue.put(f"🚀 Iniciando organização...")
            self.log_queue.put(f"📂 Origem: {source}")
            self.log_queue.put(f"📁 Destino: {dest}")
            self.log_queue.put(f"🔄 Modo: {'Mover' if self.mode.get() == 'move' else 'Copiar'}")
            self.log_queue.put(f"🧪 Dry-run: {'Sim' if self.dry_run.get() else 'Não'}")
            self.log_queue.put("=" * 60)
            
            # Conta itens para progresso
            total_items = sum(1 for _ in source.iterdir())
            processed_items = 0
            
            # Executa organização
            report, moved, skipped, errors = organize(
                source=source,
                dest_root=dest,
                mode=self.mode.get(),
                dry_run=self.dry_run.get(),
                delete_empty=self.delete_empty.get(),
                unknown_name=self.unknown_name.get(),
                ext_map=ext_map,
                log_path=None,  # Não salva log em arquivo, usa interface
                max_workers=self.max_workers.get()
            )
            
            # Adiciona relatório ao log
            for line in report.split('\n'):
                if line.strip():
                    self.log_queue.put(line)
            
            # Resultado final
            if errors > 0:
                self.log_queue.put(f"\n⚠️ Organização concluída com {errors} erro(s).")
            elif moved > 0:
                self.log_queue.put(f"\n✅ Organização concluída com sucesso! {moved} item(s) processado(s).")
            else:
                self.log_queue.put(f"\nℹ️ Nenhum item foi processado.")
                
        except Exception as e:
            self.log_queue.put(f"\n❌ Erro: {e}")
        
        finally:
            # Atualiza estado final
            self.progress_queue.put({'progress': 100, 'status': 'Concluído'})
            self.root.after(0, lambda: self.update_ui_state(False))

def main():
    """Função principal."""
    root = tk.Tk()
    app = OrganizerGUI(root)
    
    # Define pasta Downloads como padrão
    downloads_path = str(Path.home() / "Downloads")
    app.source_path.set(downloads_path)
    app.dest_path.set(downloads_path)
    
    root.mainloop()

if __name__ == "__main__":
    main()
