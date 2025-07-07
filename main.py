#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import threading
from queue import Queue

def should_ignore_url(url: str) -> bool:
    """Проверяет, нужно ли игнорировать URL (скачиваемые файлы)"""
    # Список расширений для игнорирования (можно дополнять)
    IGNORED_EXTENSIONS = {
        '.zip', '.rar', '.tar', '.gz', '.7z',  # Архивы
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',  # Документы
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',  # Изображения
        '.mp3', '.mp4', '.avi', '.mov', '.wmv',  # Медиа
        '.exe', '.msi', '.dmg', '.deb', '.rpm'  # Исполняемые файлы
    }

    path = urlparse(url).path  # Получаем путь из URL
    extension = os.path.splitext(path)[1].lower()  # Извлекаем расширение

    return extension in IGNORED_EXTENSIONS


def worker(base_domain, visited, queue, lock, words_to_find, filename):
    while True:
        url = queue.get()
        if url is None:  # Сигнал завершения
            queue.task_done()
            break

        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                queue.task_done()
                continue
        except requests.RequestException:
            queue.task_done()
            continue

        soup = BeautifulSoup(response.text, 'lxml')
        current_page_links = set()


        for link in soup.select('a[href]'):
            href = link['href']
            full_url = urljoin(url, href)
            parsed_url = urlparse(full_url)

            if (parsed_url.netloc == base_domain and
                    not parsed_url.fragment and
                    not should_ignore_url(full_url)):
                current_page_links.add(full_url)

        for a_tag in soup.select('a[href]'):
            a_tag.decompose()
        page_text = soup.get_text().lower()
        found_words = [
            word for word in words_to_find
            if re.search(rf'\b{re.escape(word.lower())}\b', page_text)
        ]
        if found_words:
            with lock:
                with open(filename, 'a', encoding='utf-8') as f:
                    f.write(f"URL: {url}\nНайденные слова: {', '.join(found_words)}\n\n")

        # Добавляем новые ссылки в очередь и в посещенные
        with lock:
            new_links = current_page_links - visited
            visited.update(new_links)
            for link in new_links:
                queue.put(link)
        queue.task_done()


def get_all_links(url, base_domain, words_to_find, num_threads=15):
    name = urlparse(url).netloc.replace('www.', '').replace('.', '_')
    filename = f"links_{name}.txt"
    visited = set()
    queue = Queue()
    lock = threading.Lock()

    # Инициализация очереди начальным URL
    if not should_ignore_url(url):
        queue.put(url)
        visited.add(url)

    # Создаем и запускаем потоки
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(
            target=worker,
            args=(base_domain, visited, queue, lock, words_to_find, filename)
        )
        t.start()
        threads.append(t)

    # Ждем завершения всех задач в очереди
    queue.join()

    # Останавливаем потоки
    for _ in range(num_threads):
        queue.put(None)

    for t in threads:
        t.join()

    return filename


def start(start_url, words):
    # Пример использования
    parsed_start_url = urlparse(start_url)
    base_domain = parsed_start_url.netloc
    filename = get_all_links(start_url, base_domain, words)
    return filename


def select_file():
    # Ограничение только на текстовые файлы
    filetypes = (
        ('Текстовые файлы', '*.txt'),
    )

    filepath = filedialog.askopenfilename(
        title="Выберите файл",
        filetypes=filetypes
    )
    if not filepath:  # Если пользователь отменил выбор
        return
    try:
        filename = os.path.basename(filepath)
        # Читаем файл и получаем слова
        with open(filepath, 'r', encoding='utf-8') as file:
            words = [line.strip() for line in file if line.strip()]
            filePath.config(state='normal')
            filePath.delete(1.0, tk.END)
            filePath.insert(tk.END, filename)
            filePath.config(state='disabled')
            global word_list
            word_list = words
            messagebox.showinfo("Успех", f"Загружено {len(words)} слов")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось прочитать файл:\n{str(e)}")


def handle_paste(event):
    # Вставляем текст из буфера обмена
    entrySite.event_generate('<<Paste>>')
    # Возвращаем "break" чтобы предотвратить стандартную обработку
    return "break"



def start_finding():
    x = False
    # Шаблон ссылки
    url_pattern = re.compile(
        r'^(https?://)?'  # http:// или https:// (опционально)
        r'([a-zA-Z0-9-]+\.)+'  # поддомены (один или несколько)
        r'[a-zA-Z]{2,}'  # домен верхнего уровня (min 2 буквы)
    )
    if entrySite.get() != "" and url_pattern.match(entrySite.get()):
        x = start(entrySite.get(), word_list)
    if x:
        messagebox.showinfo("Успех", f"Поиск выполнен\nСсылки и найденные слова записаны в файл {x}")
    else:
        messagebox.showerror("Ошибка", "Ссылка не указана или указана неверно")


root = tk.Tk()
root.title("WordParser")
root.geometry("500x250")

word_list = []

entryLabel = tk.Label(root, text="Вставьте корневую ссылку сайта (пример - https://www.axion.ru/):")
entrySite = tk.Entry(root)
entrySite.bind('<Control-v>', handle_paste)

filePathLabel = tk.Label(root, text="Файл с ключевыми словами")
filePath = tk.Text(root, height=5, width=30)
filePath.config(state='disabled')

select_button = tk.Button(root, text="Выбрать файл", command=select_file)

findWords = tk.Button(root, text="Начать поиск", command=start_finding)

entryLabel.place(x=10, y=10)
entrySite.place(x=10, y=30, width=250, height=20)
filePathLabel.place(x=10, y=60)
filePath.place(x=10, y=80, width=250, height=20)
select_button.place(x=300, y=80, width=100, height=20)
findWords.place(x=10, y=150, width=100, height=50)

root.mainloop()
