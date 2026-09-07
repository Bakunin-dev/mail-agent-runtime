"""Stable public projection emitted by the deterministic mail connector.

This is not the rich Parser Core contract and not an AI result contract.
``mail_connector.parsing.contracts.ParsedMessage`` remains the parser-owned,
technical source of truth. The connector projects that ephemeral record into
these smaller transport models for upper layers. Server may consume this
projection, while Parser Core never imports Server, workflow, or API contracts.

Thread assembly is intentionally outside this message-level connector contract.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional


class SenderObject(BaseModel):
    name: Optional[str] = Field(None, description="Отображаемое имя контакта из MIME заголовка")
    email: str = Field(..., description="Валидный очищенный адрес электронной почты")


class RecipientsObject(BaseModel):
    to: List[SenderObject] = Field(default_factory=list, description="Список прямых адресатов")
    cc: List[SenderObject] = Field(default_factory=list, description="Список контактов в копии")


class AttachmentItem(BaseModel):
    name: str = Field(..., description="Полное имя файла с расширением")
    ext: str = Field(..., description="Расширение файла в нижнем регистре (без точки)")
    size_kb: float = Field(..., description="Точный размер в килобайтах")


class MessageSignals(BaseModel):
    is_forwarded: bool = Field(False, description="Признак пересланного сообщения")
    has_thread_markers: bool = Field(False, description="Признак наличия связанных писем")
    body_length: int = Field(..., description="Длина финального очищенного тела в символах")
    is_partial: bool = Field(False, description="Письмо обработано частично из-за ошибок парсинга")


class EmailPackage(BaseModel):
    subject: str = Field(..., description="Очищенная тема без Re/Fwd мусора")
    date_utc: str = Field(..., description="Дата отправки в ISO 8601 UTC")
    sender: SenderObject = Field(..., description="Объект отправителя")
    recipients: RecipientsObject = Field(..., description="Разделенные списки получателей")
    body: str = Field(..., description="Текущее смысловое тело письма (без таблиц)")
    original_context: Optional[str] = Field(None, description="Текст исходного пересланного письма")
    attachments: List[AttachmentItem] = Field(default_factory=list, description="Манифест вложений")
    extracted_tables: List[List[List[str]]] = Field(
        default_factory=list,
        description="Извлеченные таблицы: [таблица[строка[ячейка]]]",
    )
    is_partial: bool = Field(False, description="Письмо обработано частично из-за ошибок парсинга")
    parsing_errors: List[str] = Field(default_factory=list, description="Список ошибок при парсинге")


class ConnectorResult(BaseModel):
    """Главный объект контракта — то, что коннектор отдаёт, а AI-слой читает."""
    email: EmailPackage = Field(..., description="Пакет основного обрабатываемого письма")
    signals: MessageSignals = Field(..., description="Технические признаки сообщения")
