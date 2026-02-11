"""Сервис резервного копирования БД"""

import gzip
import logging
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


class BackupService:
    """
    Сервис для автоматического резервного копирования SQLite БД.

    Features:
    - Сжатие бэкапов через gzip
    - Ротация старых файлов
    - Восстановление из бэкапа
    - Логирование всех операций
    """

    def __init__(self, db_path: str, backup_dir: str, retention_days: int = 30):
        """
        Args:
            db_path: Путь к SQLite БД
            backup_dir: Директория для хранения бэкапов
            retention_days: Сколько дней хранить бэкапы
        """
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days

        # Создаём директорию если не существует
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        logging.info(f"✅ BackupService инициализирован: {self.backup_dir}")

    def create_backup(self) -> Optional[str]:
        """
        Создать резервную копию БД.

        Returns:
            Путь к созданному файлу или None при ошибке
        """
        try:
            if not self.db_path.exists():
                logging.error(f"❌ БД не найдена: {self.db_path}")
                return None

            # Генерируем имя файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}.sql.gz"
            backup_path = self.backup_dir / backup_filename

            # Создаём SQL-дамп со сжатием
            logging.info(f"💾 Создание бэкапа: {backup_filename}")

            conn = sqlite3.connect(str(self.db_path))

            with gzip.open(backup_path, "wt", encoding="utf-8") as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")

            conn.close()

            # Получаем размер файла
            file_size_mb = backup_path.stat().st_size / (1024 * 1024)

            logging.info(f"✅ Бэкап создан: {backup_filename} " f"({file_size_mb:.2f} MB)")

            # Очистка старых бэкапов
            self._cleanup_old_backups()

            return str(backup_path)

        except Exception as e:
            logging.error(f"❌ Ошибка при создании бэкапа: {e}", exc_info=True)
            return None

    def _cleanup_old_backups(self) -> int:
        """
        Удалить бэкапы старше retention_days.

        Returns:
            Количество удалённых файлов
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            deleted_count = 0

            for backup_file in self.backup_dir.glob("backup_*.sql.gz"):
                # Парсим дату из имени файла: backup_20260211_103045.sql.gz
                try:
                    date_str = backup_file.stem.split("_")[1]  # 20260211
                    time_str = backup_file.stem.split("_")[2]  # 103045
                    file_datetime = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")

                    if file_datetime < cutoff_date:
                        backup_file.unlink()
                        deleted_count += 1
                        logging.debug(f"🗑️ Удалён старый бэкап: {backup_file.name}")

                except (ValueError, IndexError):
                    # Некорректное имя файла - пропускаем
                    continue

            if deleted_count > 0:
                logging.info(f"🗑️ Удалено старых бэкапов: {deleted_count}")

            return deleted_count

        except Exception as e:
            logging.error(f"❌ Ошибка при очистке бэкапов: {e}")
            return 0

    def restore_backup(self, backup_file: str) -> bool:
        """
        Восстановить БД из бэкапа.

        Args:
            backup_file: Путь к файлу бэкапа

        Returns:
            True если успешно
        """
        try:
            backup_path = Path(backup_file)

            if not backup_path.exists():
                logging.error(f"❌ Файл бэкапа не найден: {backup_file}")
                return False

            # Создаём резервную копию текущей БД
            if self.db_path.exists():
                backup_current = self.db_path.with_suffix(".db.backup")
                shutil.copy2(self.db_path, backup_current)
                logging.info(f"💾 Создана резервная копия: {backup_current.name}")

            logging.info(f"🔄 Восстановление из: {backup_path.name}")

            # Удаляем текущую БД
            if self.db_path.exists():
                self.db_path.unlink()

            # Читаем сжатый SQL-дамп
            with gzip.open(backup_path, "rt", encoding="utf-8") as f:
                sql_dump = f.read()

            # Создаём новую БД и выполняем дамп
            conn = sqlite3.connect(str(self.db_path))
            conn.executescript(sql_dump)
            conn.commit()
            conn.close()

            logging.info(f"✅ БД успешно восстановлена из: {backup_path.name}")
            return True

        except Exception as e:
            logging.error(f"❌ Ошибка при восстановлении: {e}", exc_info=True)
            return False

    def list_backups(self) -> List[dict]:
        """
        Получить список всех бэкапов.

        Returns:
            Список словарей с информацией о бэкапах
        """
        backups = []

        for backup_file in sorted(self.backup_dir.glob("backup_*.sql.gz"), reverse=True):
            try:
                # Парсим информацию
                date_str = backup_file.stem.split("_")[1]
                time_str = backup_file.stem.split("_")[2]
                file_datetime = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")

                file_size_mb = backup_file.stat().st_size / (1024 * 1024)

                backups.append(
                    {
                        "filename": backup_file.name,
                        "path": str(backup_file),
                        "datetime": file_datetime,
                        "size_mb": round(file_size_mb, 2),
                        "age_days": (datetime.now() - file_datetime).days,
                    }
                )

            except (ValueError, IndexError):
                continue

        return backups

    def get_stats(self) -> dict:
        """
        Получить статистику бэкапов.

        Returns:
            Словарь со статистикой
        """
        backups = self.list_backups()

        total_size_mb = sum(b["size_mb"] for b in backups)

        return {
            "total_backups": len(backups),
            "total_size_mb": round(total_size_mb, 2),
            "oldest_backup": backups[-1]["datetime"] if backups else None,
            "newest_backup": backups[0]["datetime"] if backups else None,
            "backup_dir": str(self.backup_dir),
        }
