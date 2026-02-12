"""Hybrid Text Manager - Гибридная система локализации

Приоритеты:
1. БД (text_templates) - кастомизация через админ-панель
2. YAML (locales/*.yaml) - дефолтные тексты
3. Hardcoded - fallback для критичных сообщений
"""

import logging
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite
from cachetools import TTLCache

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


class HybridTextManager:
    """Hybrid text manager with DB + YAML + Hardcoded fallbacks"""

    # Кэш на 5 минут (тексты не меняются часто)
    _cache: TTLCache = TTLCache(maxsize=500, ttl=300)

    # YAML трансляции (загружаются один раз)
    _yaml_translations: Dict[str, Dict] = {}
    _yaml_loaded = False

    # Hardcoded fallbacks для критичных сообщений
    _hardcoded_defaults = {
        "common.back": "⬅️ Назад",
        "common.cancel": "❌ Отмена",
        "common.error": "❌ Ошибка",
        "common.loading": "⏳ Загрузка...",
        "errors.unknown_error": "❌ Неизвестная ошибка",
        "system.unauthorized": "❌ У вас нет доступа",
    }

    @classmethod
    def _load_yaml(cls, locales_dir: str = "locales"):
        """Загрузить YAML файлы локализации"""
        if cls._yaml_loaded:
            return

        locales_path = Path(locales_dir)

        if not locales_path.exists():
            logger.warning(f"Locales directory not found: {locales_dir}")
            cls._yaml_loaded = True
            return

        for yaml_file in locales_path.glob("*.yaml"):
            lang = yaml_file.stem  # ru, en, etc.

            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    cls._yaml_translations[lang] = yaml.safe_load(f) or {}
                logger.info(f"✅ Loaded {lang} translations from {yaml_file.name}")
            except Exception as e:
                logger.error(f"❌ Error loading {yaml_file}: {e}")

        cls._yaml_loaded = True
        logger.info(
            f"✅ Localization loaded: {list(cls._yaml_translations.keys())} ({len(cls._cache)} keys cached)"
        )

    @classmethod
    def _get_from_yaml(cls, key: str, lang: str) -> Optional[str]:
        """Получить текст из YAML

        Args:
            key: Ключ в формате "category.subcategory.key"
            lang: Язык (ru, en)

        Returns:
            Текст или None
        """
        if not cls._yaml_loaded:
            cls._load_yaml()

        translations = cls._yaml_translations.get(lang, {})
        if not translations:
            return None

        # Навигация по вложенным dict: "booking.success" -> translations['booking']['success']
        keys = key.split(".")
        value = translations

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None

        return str(value) if value is not None else None

    @classmethod
    async def _get_from_db(cls, key: str, lang: str) -> Optional[str]:
        """Получить текст из БД (кастомизация)

        Args:
            key: Ключ текста
            lang: Язык

        Returns:
            Текст или None
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                column = f"text_{lang}"
                query = f"SELECT {column}, is_custom FROM text_templates WHERE key = ?"

                async with db.execute(query, (key,)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        # Возвращаем только если is_custom=1 (кастомизировано)
                        if row[1] == 1:
                            return row[0]
                    return None
        except Exception as e:
            logger.error(f"Error loading text from DB {key}: {e}")
            return None

    @classmethod
    async def get(
        cls, key: str, lang: str = "ru", default: str = None, **kwargs
    ) -> str:
        """Получить текст с приоритетами: БД > YAML > Hardcoded > Default

        Args:
            key: Ключ текста (например, 'booking.success')
            lang: Язык ('ru' или 'en')
            default: Дефолтное значение если не найдено
            **kwargs: Параметры для форматирования (например, {date}, {time})

        Returns:
            Отформатированный текст

        Example:
            >>> await TextManager.get('booking.success', date='10.02.2026', time='14:00')
            '✅ Вы записаны на 10.02.2026 в 14:00'
        """
        cache_key = f"{key}:{lang}"

        # Проверяем кэш
        if cache_key in cls._cache:
            template = cls._cache[cache_key]
        else:
            # 1. Приоритет 1: БД (кастомизация)
            template = await cls._get_from_db(key, lang)

            # 2. Приоритет 2: YAML (дефолты)
            if not template:
                template = cls._get_from_yaml(key, lang)

            # 3. Приоритет 3: Hardcoded fallbacks
            if not template:
                template = cls._hardcoded_defaults.get(key)

            # 4. Приоритет 4: Default аргумент
            if not template:
                template = default or f"[{key}]"
                logger.warning(f"⚠️ Text not found: {key} ({lang})")

            # Кэшируем
            cls._cache[cache_key] = template

        # Форматируем если есть параметры
        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                logger.error(f"❌ Missing parameter {e} in template '{key}'")
                # Возвращаем неотформатированный текст
                return template
            except Exception as e:
                logger.error(f"❌ Error formatting template '{key}': {e}")
                return template

        return template

    @classmethod
    async def update(
        cls, key: str, text: str, lang: str = "ru", admin_id: int = None
    ) -> bool:
        """Обновить текст в БД и сбросить кэш

        Args:
            key: Ключ текста
            text: Новый текст
            lang: Язык
            admin_id: ID админа, который обновил

        Returns:
            True если успешно
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                column = f"text_{lang}"

                # Проверяем существует ли ключ
                async with db.execute(
                    "SELECT id FROM text_templates WHERE key = ?", (key,)
                ) as cursor:
                    exists = await cursor.fetchone()

                if exists:
                    # Обновляем
                    await db.execute(
                        f"""UPDATE text_templates 
                        SET {column} = ?, is_custom = 1, updated_by = ?
                        WHERE key = ?""",
                        (text, admin_id, key),
                    )
                else:
                    # Создаем новую запись
                    await db.execute(
                        f"""INSERT INTO text_templates (key, {column}, is_custom, updated_by)
                        VALUES (?, ?, 1, ?)""",
                        (key, text, admin_id),
                    )

                await db.commit()

                # Сбрасываем кэш
                cache_key = f"{key}:{lang}"
                cls._cache.pop(cache_key, None)

                logger.info(f"✅ Text template updated: {key} by admin {admin_id}")
                return True
        except Exception as e:
            logger.error(f"❌ Error updating text template {key}: {e}")
            return False

    @classmethod
    async def reset_to_default(cls, key: str, lang: str = "ru") -> bool:
        """Сбросить текст к дефолтному значению (YAML)

        Args:
            key: Ключ текста
            lang: Язык

        Returns:
            True если успешно
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                # Удаляем кастомизацию (либо отмечаем is_custom=0)
                await db.execute(
                    "UPDATE text_templates SET is_custom = 0 WHERE key = ?", (key,)
                )
                await db.commit()

                # Сбрасываем кэш
                cache_key = f"{key}:{lang}"
                cls._cache.pop(cache_key, None)

                logger.info(f"✅ Text template reset to default: {key}")
                return True
        except Exception as e:
            logger.error(f"❌ Error resetting text template {key}: {e}")
            return False

    @classmethod
    async def get_all(
        cls, category: str = None, lang: str = "ru", include_yaml: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """Получить все тексты (для админ-панели)

        Args:
            category: Фильтр по категории
            lang: Язык
            include_yaml: Включить тексты из YAML

        Returns:
            Dict[key, {'text': str, 'description': str, 'is_custom': bool}]
        """
        result = {}

        try:
            # Загружаем из БД
            async with aiosqlite.connect(DATABASE_PATH) as db:
                column = f"text_{lang}"

                if category:
                    query = f"SELECT key, {column}, description, is_custom FROM text_templates WHERE category = ?"
                    params = (category,)
                else:
                    query = f"SELECT key, {column}, description, is_custom FROM text_templates"
                    params = ()

                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        result[row[0]] = {
                            "text": row[1],
                            "description": row[2] or "",
                            "is_custom": bool(row[3]),
                            "source": "database",
                        }

            # Добавляем из YAML (если нет в БД)
            if include_yaml:
                if not cls._yaml_loaded:
                    cls._load_yaml()

                yaml_data = cls._yaml_translations.get(lang, {})

                # Флэтеним YAML данные в плоский dict
                def flatten_dict(d: Dict, parent_key: str = "") -> Dict:
                    items = []
                    for k, v in d.items():
                        new_key = f"{parent_key}.{k}" if parent_key else k
                        if isinstance(v, dict):
                            items.extend(flatten_dict(v, new_key).items())
                        else:
                            items.append((new_key, v))
                    return dict(items)

                flat_yaml = flatten_dict(yaml_data)

                for key, text in flat_yaml.items():
                    # Фильтр по категории
                    if category and not key.startswith(f"{category}."):
                        continue

                    # Добавляем только если нет в БД
                    if key not in result:
                        result[key] = {
                            "text": str(text),
                            "description": "",
                            "is_custom": False,
                            "source": "yaml",
                        }

            return result
        except Exception as e:
            logger.error(f"❌ Error loading all templates: {e}")
            return {}

    @classmethod
    def get_categories(cls) -> list[str]:
        """Получить список всех категорий

        Returns:
            Список категорий
        """
        if not cls._yaml_loaded:
            cls._load_yaml()

        # Извлекаем категории из YAML (верхний уровень)
        categories = set()
        for lang_data in cls._yaml_translations.values():
            categories.update(lang_data.keys())

        return sorted(categories)

    @classmethod
    def clear_cache(cls):
        """Очистить весь кэш (при массовых изменениях)"""
        cls._cache.clear()
        logger.info("✅ Text templates cache cleared")

    @classmethod
    def reload_yaml(cls):
        """Перезагрузить YAML файлы"""
        cls._yaml_loaded = False
        cls._yaml_translations.clear()
        cls._load_yaml()
        cls.clear_cache()
        logger.info("✅ YAML translations reloaded")


# Сокращенный alias для удобства
TextManager = HybridTextManager
_ = HybridTextManager.get  # Удобный alias: await _('booking.button')
