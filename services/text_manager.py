"""Hybrid Text Manager для управления текстами бота

Приоритеты:
1. БД (text_templates) - кастомизация админом
2. YAML (locales/ru.yaml) - дефолтные тексты
3. Hardcoded fallback - на случай ошибок
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import aiosqlite
import yaml
from cachetools import TTLCache

from config import DATABASE_PATH
from utils.helpers import now_local


class HybridTextManager:
    """Гибридный менеджер текстов с поддержкой БД и YAML"""

    # Кэш на 5 минут (TTL)
    _cache: TTLCache = TTLCache(maxsize=1000, ttl=300)

    # YAML тексты (загружаются один раз при старте)
    _yaml_texts: Dict[str, Dict] = {}
    _yaml_loaded = False

    # Hardcoded fallback (на случай если БД и YAML недоступны)
    _fallbacks = {
        "common.back": "⬅️ Назад",
        "common.confirm": "✅ Подтвердить",
        "common.cancel": "❌ Отмена",
        "common.error": "❌ Произошла ошибка",
        "booking.button": "📅 Записаться",
        "booking.select_date": "📅 Выберите дату",
        "booking.select_time": "🕒 Выберите время",
    }

    @classmethod
    async def init(cls):
        """Инициализация - загрузка YAML текстов"""
        if not cls._yaml_loaded:
            await cls._load_yaml_texts()
            logging.info("✅ HybridTextManager initialized")

    @classmethod
    async def _load_yaml_texts(cls, lang: str = "ru"):
        """Загрузить тексты из YAML файла

        Args:
            lang: Язык (по умолчанию 'ru')
        """
        try:
            yaml_path = Path(f"locales/{lang}.yaml")

            if not yaml_path.exists():
                logging.warning(f"YAML file not found: {yaml_path}")
                return

            with open(yaml_path, "r", encoding="utf-8") as f:
                cls._yaml_texts[lang] = yaml.safe_load(f) or {}

            logging.info(f"✅ Loaded {len(cls._yaml_texts[lang])} YAML categories for '{lang}'")
            cls._yaml_loaded = True

        except Exception as e:
            logging.error(f"Error loading YAML texts: {e}", exc_info=True)

    @classmethod
    def _get_from_yaml(cls, key: str, lang: str = "ru") -> Optional[str]:
        """Получить текст из YAML

        Args:
            key: Ключ в формате 'category.subcategory.key'
            lang: Язык

        Returns:
            Текст или None
        """
        if not cls._yaml_loaded:
            return None

        # Разбираем ключ: "booking.success" -> ['booking', 'success']
        keys = key.split(".")

        # Навигация по вложенным dict
        value = cls._yaml_texts.get(lang, {})
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None

        return str(value) if value else None

    @classmethod
    async def _get_from_db(cls, key: str, lang: str = "ru") -> Optional[str]:
        """Получить текст из БД

        Args:
            key: Ключ текста
            lang: Язык

        Returns:
            Текст или None
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                column = f"text_{lang}"
                query = f"SELECT {column} FROM text_templates WHERE key = ?"

                async with db.execute(query, (key,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row and row[0] else None

        except Exception as e:
            logging.error(f"Error loading text from DB '{key}': {e}")
            return None

    @classmethod
    async def get(cls, key: str, lang: str = "ru", **kwargs) -> str:
        """Получить текст с приоритетами: БД > YAML > Fallback

        Args:
            key: Ключ текста (например, 'booking.success')
            lang: Язык ('ru' или 'en')
            **kwargs: Параметры для форматирования

        Returns:
            Отформатированный текст

        Example:
            >>> await TextManager.get('booking.success', date='10.02.2026', time='14:00')
            '✅ Вы успешно записаны!\n\n📅 Дата: 10.02.2026\n🕒 Время: 14:00'
        """
        # Инициализируем YAML если еще не загружен
        if not cls._yaml_loaded:
            await cls.init()

        # Проверяем кэш
        cache_key = f"{key}:{lang}"
        if cache_key in cls._cache:
            template = cls._cache[cache_key]
        else:
            # Приоритет 1: БД (кастомизация)
            template = await cls._get_from_db(key, lang)

            if not template:
                # Приоритет 2: YAML (дефолты)
                template = cls._get_from_yaml(key, lang)

            if not template:
                # Приоритет 3: Hardcoded fallback
                template = cls._fallbacks.get(key)

            if not template:
                # Ничего не найдено - возвращаем ключ
                logging.warning(f"⚠️ Text not found for key: {key}")
                return f"[{key}]"

            # Кэшируем
            cls._cache[cache_key] = template

        # Форматируем если есть параметры
        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                logging.error(f"Missing parameter {e} in template '{key}'")
                return template

        return template

    @classmethod
    async def update(
        cls, key: str, text: str, lang: str = "ru", admin_id: Optional[int] = None
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
                # Записываем старое значение в лог
                old_text = await cls._get_from_db(key, lang)

                if old_text:
                    await db.execute(
                        """INSERT INTO text_changes_log 
                        (key, old_value, new_value, changed_by) 
                        VALUES (?, ?, ?, ?)""",
                        (key, old_text, text, admin_id),
                    )

                # Обновляем или создаем
                column = f"text_{lang}"
                await db.execute(
                    f"""INSERT INTO text_templates (key, {column}, is_custom, updated_at, updated_by)
                    VALUES (?, ?, 1, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        {column} = excluded.{column},
                        is_custom = 1,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (key, text, now_local().isoformat(), admin_id),
                )

                await db.commit()

            # Сбрасываем кэш
            cache_key = f"{key}:{lang}"
            cls._cache.pop(cache_key, None)

            logging.info(f"✅ Text updated: {key} by admin {admin_id}")
            return True

        except Exception as e:
            logging.error(f"Error updating text '{key}': {e}", exc_info=True)
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
                await db.execute("DELETE FROM text_templates WHERE key = ?", (key,))
                await db.commit()

            # Сбрасываем кэш
            cache_key = f"{key}:{lang}"
            cls._cache.pop(cache_key, None)

            logging.info(f"✅ Text reset to default: {key}")
            return True

        except Exception as e:
            logging.error(f"Error resetting text '{key}': {e}", exc_info=True)
            return False

    @classmethod
    async def get_all(cls, category: Optional[str] = None) -> Dict[str, Tuple[str, bool]]:
        """Получить все тексты для админ-панели

        Args:
            category: Категория (необязательно)

        Returns:
            Dict[key, (text, is_custom)]
        """
        result = {}

        try:
            # Загружаем из БД
            async with aiosqlite.connect(DATABASE_PATH) as db:
                if category:
                    query = "SELECT key, text_ru, is_custom FROM text_templates WHERE category = ?"
                    params = (category,)
                else:
                    query = "SELECT key, text_ru, is_custom FROM text_templates"
                    params = ()

                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    for key, text, is_custom in rows:
                        result[key] = (text, bool(is_custom))

            # Добавляем из YAML (только если нет в БД)
            if cls._yaml_loaded and category:
                yaml_category = cls._yaml_texts.get("ru", {}).get(category, {})
                if isinstance(yaml_category, dict):
                    for subkey, value in yaml_category.items():
                        if isinstance(value, str):
                            full_key = f"{category}.{subkey}"
                            if full_key not in result:
                                result[full_key] = (value, False)

            return result

        except Exception as e:
            logging.error(f"Error getting all texts: {e}", exc_info=True)
            return {}

    @classmethod
    def clear_cache(cls):
        """Очистить весь кэш (при массовых изменениях)"""
        cls._cache.clear()
        logging.info("🧹 Text cache cleared")

    @classmethod
    async def reload_yaml(cls):
        """Перезагрузить YAML тексты (после редактирования)"""
        cls._yaml_loaded = False
        cls._yaml_texts.clear()
        await cls._load_yaml_texts()
        cls.clear_cache()
        logging.info("🔄 YAML texts reloaded")


# Alias для удобства
_ = HybridTextManager.get
