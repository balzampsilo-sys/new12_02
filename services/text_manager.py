"""Hybrid Text Manager - Гибридная система локализации

Приоритеты:
1. Текст из БД (is_customized=1) - кастомизация админом
2. Текст из YAML - дефолтные значения
3. Hardcoded fallback - на случай ошибки

Преимущества:
- ✅ Кэширование (TTL 5 мин)
- ✅ Hot reload без рестарта
- ✅ История изменений
- ✅ Поддержка параметров {date}, {time}, и т.д.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
import yaml
from cachetools import TTLCache

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


class TextManager:
    """Гибридный текстовый менеджер с приоритетами"""

    # Кэш на 5 минут (300с)
    _cache: TTLCache = TTLCache(maxsize=1000, ttl=300)

    # YAML трансляции (load once)
    _yaml_translations: Dict[str, Dict] = {}
    _yaml_loaded = False

    # Hardcoded fallbacks (на случай аварии)
    _fallbacks = {
        "common.back": "⬅️ Назад",
        "common.cancel": "❌ Отмена",
        "common.confirm": "✅ Подтвердить",
        "booking.button": "📅 Записаться",
        "booking.errors.slot_taken": "❌ Это время уже занято",
        "errors.generic": "❌ Произошла ошибка",
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
                    cls._yaml_translations[lang] = yaml.safe_load(f)
                logger.info(f"✅ Loaded YAML translations: {lang}")
            except Exception as e:
                logger.error(f"❌ Error loading {yaml_file}: {e}")

        cls._yaml_loaded = True

    @classmethod
    def _get_yaml_text(cls, key: str, lang: str = "ru") -> Optional[str]:
        """Получить текст из YAML

        Args:
            key: Ключ в формате "category.subcategory.key"
            lang: Язык (ru, en)

        Returns:
            Текст или None
        """
        if not cls._yaml_loaded:
            cls._load_yaml()

        if lang not in cls._yaml_translations:
            return None

        # Разбираем ключ: "booking.errors.slot_taken" -> ['booking', 'errors', 'slot_taken']
        keys = key.split(".")

        # Навигируемся по вложенным dict
        value = cls._yaml_translations[lang]
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None

        return str(value) if value is not None else None

    @classmethod
    async def _get_db_text(cls, key: str, lang: str = "ru") -> Optional[str]:
        """Получить текст из БД (только кастомизированные)

        Args:
            key: Ключ текста
            lang: Язык

        Returns:
            Текст или None
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                column = f"text_{lang}"
                query = f"SELECT {column} FROM text_templates WHERE key = ? AND is_customized = 1"

                async with db.execute(query, (key,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logger.error(f"Error loading text from DB {key}: {e}")
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
            '✅ Вы успешно записаны!\n\n📅 10.02.2026\n🕒 14:00'
        """
        cache_key = f"{key}:{lang}"

        # 1. Проверяем кэш
        if cache_key in cls._cache:
            template = cls._cache[cache_key]
        else:
            # 2. Проверяем БД (кастомизация)
            db_text = await cls._get_db_text(key, lang)
            if db_text:
                template = db_text
                cls._cache[cache_key] = template
                logger.debug(f"🟢 Text from DB: {key}")
            else:
                # 3. Проверяем YAML (дефолты)
                yaml_text = cls._get_yaml_text(key, lang)
                if yaml_text:
                    template = yaml_text
                    cls._cache[cache_key] = template
                    logger.debug(f"🟡 Text from YAML: {key}")
                else:
                    # 4. Fallback
                    template = cls._fallbacks.get(key, f"[{key}]")
                    logger.warning(f"⚠️ Text not found, using fallback: {key}")

        # Форматируем если есть параметры
        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing parameter {e} in template {key}")
                return template
        return template

    @classmethod
    async def update(
        cls, key: str, text: str, lang: str = "ru", admin_id: int = None
    ) -> Tuple[bool, str]:
        """Обновить текст в БД и сбросить кэш

        Args:
            key: Ключ текста
            text: Новый текст
            lang: Язык
            admin_id: ID админа

        Returns:
            Tuple[success: bool, message: str]
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                # Проверяем существует ли ключ
                async with db.execute(
                    "SELECT id, text_ru FROM text_templates WHERE key = ?", (key,)
                ) as cursor:
                    row = await cursor.fetchone()

                column = f"text_{lang}"

                if row:
                    # Обновляем существующую запись
                    old_text = row[1]
                    await db.execute(
                        f"""UPDATE text_templates
                        SET {column} = ?, is_customized = 1, updated_at = CURRENT_TIMESTAMP, updated_by = ?
                        WHERE key = ?""",
                        (text, admin_id, key),
                    )
                else:
                    # Создаём новую запись
                    old_text = None
                    await db.execute(
                        f"""INSERT INTO text_templates
                        (key, {column}, category, is_customized, updated_by)
                        VALUES (?, ?, 'custom', 1, ?)""",
                        (key, text, admin_id),
                    )

                # Записываем в историю
                await db.execute(
                    """INSERT INTO text_changes_log
                    (key, old_value, new_value, lang, changed_by)
                    VALUES (?, ?, ?, ?, ?)""",
                    (key, old_text, text, lang, admin_id),
                )

                await db.commit()

                # Сбрасываем кэш
                cache_key = f"{key}:{lang}"
                cls._cache.pop(cache_key, None)

                logger.info(f"✅ Text updated: {key} by admin {admin_id}")
                return True, "Текст успешно обновлён"

        except Exception as e:
            logger.error(f"❌ Error updating text {key}: {e}", exc_info=True)
            return False, f"Ошибка: {str(e)}"

    @classmethod
    async def reset_to_default(cls, key: str, lang: str = "ru") -> Tuple[bool, str]:
        """Сбросить текст к дефолтному значению из YAML

        Args:
            key: Ключ текста
            lang: Язык

        Returns:
            Tuple[success: bool, message: str]
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                # Устанавливаем is_customized = 0
                await db.execute(
                    "UPDATE text_templates SET is_customized = 0 WHERE key = ?", (key,)
                )
                await db.commit()

                # Сбрасываем кэш
                cache_key = f"{key}:{lang}"
                cls._cache.pop(cache_key, None)

                logger.info(f"✅ Text reset to default: {key}")
                return True, "Текст сброшен к дефолтному"

        except Exception as e:
            logger.error(f"❌ Error resetting text {key}: {e}")
            return False, f"Ошибка: {str(e)}"

    @classmethod
    async def get_all(cls, category: str = None, lang: str = "ru") -> Dict[str, Any]:
        """Получить все тексты (для админ-панели)

        Args:
            category: Категория фильтрации (booking, admin, common)
            lang: Язык

        Returns:
            Dict[key, {text, description, is_customized}]
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                column = f"text_{lang}"

                if category:
                    query = f"""SELECT key, {column}, description, is_customized, category
                               FROM text_templates WHERE category = ?
                               ORDER BY category, key"""
                    params = (category,)
                else:
                    query = f"""SELECT key, {column}, description, is_customized, category
                               FROM text_templates
                               ORDER BY category, key"""
                    params = ()

                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()

                    result = {}
                    for row in rows:
                        key, text, description, is_customized, cat = row
                        result[key] = {
                            "text": text,
                            "description": description,
                            "is_customized": bool(is_customized),
                            "category": cat,
                        }

                    return result

        except Exception as e:
            logger.error(f"Error loading all templates: {e}")
            return {}

    @classmethod
    async def get_categories(cls) -> List[str]:
        """Получить список всех категорий

        Returns:
            List[str]: Список категорий
        """
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.execute(
                    "SELECT DISTINCT category FROM text_templates ORDER BY category"
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error loading categories: {e}")
            return []

    @classmethod
    def clear_cache(cls):
        """Очистить весь кэш (при массовых изменениях)"""
        cls._cache.clear()
        logger.info("✅ Text templates cache cleared")

    @classmethod
    def reload_yaml(cls):
        """Перезагрузить YAML файлы (hot reload)"""
        cls._yaml_loaded = False
        cls._yaml_translations.clear()
        cls._load_yaml()
        cls.clear_cache()
        logger.info("✅ YAML translations reloaded")


# Сокращенный alias для удобства
_ = TextManager.get
