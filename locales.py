import yaml
import os

class Localization:
    def __init__(self, locale, locales_dir='locales', default_locale='en'):
        self.locales_dir = locales_dir
        self.locale = locale
        self.default_locale = default_locale
        self.translations = self.load_translations()

    def load_translations(self):
        """Завантажує переклад з YAML файлу для заданої мови. Якщо файл не знайдено, завантажує файл за замовчуванням або видає попередження."""
        locale_file = os.path.join(self.locales_dir, f'{self.locale}.yml')
        if not os.path.exists(locale_file):
            print(f"Warning: Translation file for '{self.locale}' not found. Loading default locale '{self.default_locale}'.")
            locale_file = os.path.join(self.locales_dir, f'{self.default_locale}.yml')
            if not os.path.exists(locale_file):
                raise FileNotFoundError(f"Default translation file for '{self.default_locale}' also not found.")
        
        with open(locale_file, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    def _(self, key):
        """Повертає переклад для заданого ключа або сам ключ, якщо переклад не знайдений."""
        return self.translations.get(key, key)

    def set_locale(self, locale):
        """Змінює мову на нову та перезавантажує переклади."""
        self.locale = locale
        self.translations = self.load_translations()
