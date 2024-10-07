import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
import json

class ProgramManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Менеджер Програм")
        self.root.geometry("600x400")  # Збільшено розмір вікна

        self.programs = self.load_programs()

        # Інтерфейс
        self.program_listbox = tk.Listbox(root)
        self.program_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.add_button = tk.Button(root, text="Додати", command=self.add_program)
        self.edit_button = tk.Button(root, text="Редагувати", command=self.edit_program)
        self.remove_button = tk.Button(root, text="Видалити", command=self.remove_program)
        self.move_up_button = tk.Button(root, text="Вгору", command=self.move_up)
        self.move_down_button = tk.Button(root, text="Вниз", command=self.move_down)

        self.add_button.pack(fill=tk.X)
        self.edit_button.pack(fill=tk.X)
        self.remove_button.pack(fill=tk.X)
        self.move_up_button.pack(fill=tk.X)
        self.move_down_button.pack(fill=tk.X)

        self.populate_listbox()

    def load_programs(self):
        try:
            with open('programs.json', 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save_programs(self):
        with open('programs.json', 'w', encoding='utf-8') as file:
            json.dump(self.programs, file, ensure_ascii=False, indent=4)

    def populate_listbox(self):
        self.program_listbox.delete(0, tk.END)
        for program_name, program_data in self.programs.items():
            attributes = program_data.get('attributes', [])
            if 'hide' not in attributes:  # Не відображаємо програми з атрибутом 'hide'
                self.program_listbox.insert(tk.END, program_name)

    def add_program(self):
        self.edit_program(new=True)

    def edit_program(self, new=False):
        program_name = ""
        original_position = None
        if not new:
            try:
                program_name = self.program_listbox.get(self.program_listbox.curselection())
                original_position = list(self.programs.keys()).index(program_name)
            except:
                messagebox.showerror("Помилка", "Виберіть програму для редагування")
                return
        
        # Форма для введення даних
        form = tk.Toplevel(self.root)
        form.title("Додати/Редагувати програму")
        form.geometry("400x300")  # Збільшено розмір форми

        tk.Label(form, text="Назва програми:").grid(row=0, column=0)
        tk.Label(form, text="Шлях:").grid(row=1, column=0)
        tk.Label(form, text="Команда запуску:").grid(row=2, column=0)
        tk.Label(form, text="Команда закриття:").grid(row=3, column=0)
        tk.Label(form, text="Кількість запусків:").grid(row=4, column=0)
        tk.Label(form, text="Загальний час роботи:").grid(row=5, column=0)
        tk.Label(form, text="Опис:").grid(row=6, column=0)
        tk.Label(form, text="Атрибути:").grid(row=7, column=0)

        program_name_entry = tk.Entry(form, width=50)
        path_entry = tk.Entry(form, width=50)
        command_entry = tk.Entry(form, width=50)
        close_command_entry = tk.Entry(form, width=50)
        launch_count_entry = tk.Entry(form, width=50)
        runtime_entry = tk.Entry(form, width=50)
        description_entry = tk.Entry(form, width=50)
        attributes_entry = tk.Entry(form, width=50)

        program_name_entry.grid(row=0, column=1)
        path_entry.grid(row=1, column=1)
        command_entry.grid(row=2, column=1)
        close_command_entry.grid(row=3, column=1)
        launch_count_entry.grid(row=4, column=1)
        runtime_entry.grid(row=5, column=1)
        description_entry.grid(row=6, column=1)
        attributes_entry.grid(row=7, column=1)

        if not new:
            program = self.programs[program_name]
            program_name_entry.insert(0, program_name)
            path_entry.insert(0, program['path'])
            command_entry.insert(0, program['command'])
            close_command_entry.insert(0, program['close_command'])
            launch_count_entry.insert(0, program['launch_count'])
            runtime_entry.insert(0, program['total_runtime'])
            description_entry.insert(0, program['description'])
            attributes_entry.insert(0, ','.join(program['attributes']))

        def save_changes():
            name = program_name_entry.get()
            path = path_entry.get()
            command = command_entry.get()
            close_command = close_command_entry.get()
            launch_count = int(launch_count_entry.get())
            runtime = float(runtime_entry.get())
            description = description_entry.get()
            attributes = attributes_entry.get().split(',')

            if new:
                self.programs[name] = {
                    "path": path,
                    "command": command,
                    "close_command": close_command,
                    "launch_count": launch_count,
                    "total_runtime": runtime,
                    "description": description,
                    "attributes": attributes
                }
            else:
                self.programs.pop(program_name)
                self.programs = {k: v for k, v in list(self.programs.items())[:original_position] + [(name, {
                    "path": path,
                    "command": command,
                    "close_command": close_command,
                    "launch_count": launch_count,
                    "total_runtime": runtime,
                    "description": description,
                    "attributes": attributes
                })] + list(self.programs.items())[original_position:]}
            
            self.save_programs()
            self.populate_listbox()
            form.destroy()

        save_button = tk.Button(form, text="Зберегти", command=save_changes)
        save_button.grid(row=8, columnspan=2)

    def remove_program(self):
        try:
            program_name = self.program_listbox.get(self.program_listbox.curselection())
            if messagebox.askokcancel("Підтвердження", f"Ви впевнені, що хочете видалити програму {program_name}?"):
                self.programs.pop(program_name)
                self.save_programs()
                self.populate_listbox()
        except:
            messagebox.showerror("Помилка", "Виберіть програму для видалення")

    def move_up(self):
        index = self.program_listbox.curselection()[0]
        if index > 0:
            items = list(self.programs.items())
            items[index], items[index-1] = items[index-1], items[index]
            self.programs = dict(items)
            self.save_programs()
            self.populate_listbox()
            self.program_listbox.select_set(index-1)

    def move_down(self):
        index = self.program_listbox.curselection()[0]
        if index < len(self.programs) - 1:
            items = list(self.programs.items())
            items[index], items[index+1] = items[index+1], items[index]
            self.programs = dict(items)
            self.save_programs()
            self.populate_listbox()
            self.program_listbox.select_set(index+1)

root = tk.Tk()
app = ProgramManager(root)
root.mainloop()
