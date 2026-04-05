from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50))  # ynet, ynet_flash, reuters, nyt
    title: Mapped[str] = mapped_column(String(1000))
    url: Mapped[str] = mapped_column(String(2000), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    category: Mapped[str] = mapped_column(String(50), default="other")
    image_url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)


class TelegramChannel(Base):
    __tablename__ = "telegram_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_identifier: Mapped[str] = mapped_column(String(500), unique=True)
    display_name: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    messages: Mapped[list["TelegramMessage"]] = relationship(back_populates="channel")


class TelegramMessage(Base):
    __tablename__ = "telegram_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(Integer, ForeignKey("telegram_channels.id"))
    message_id: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)
    media_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # photo, video, document
    media_file: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  # filename in media dir
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_keywords: Mapped[str] = mapped_column(Text, default="[]")  # JSON array

    channel: Mapped[TelegramChannel] = relationship(back_populates="messages")

    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_channel_message"),
    )


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    period_hours: Mapped[int] = mapped_column(Integer, default=24)


class Config(Base):
    __tablename__ = "config"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="{}")  # JSON-encoded


class XAccount(Base):
    """A Twitter/X account being monitored."""
    __tablename__ = "x_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(200), unique=True)   # without @
    display_name: Mapped[str] = mapped_column(String(500), default="")
    x_user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Twitter numeric ID
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    posts: Mapped[list["XPost"]] = relationship(back_populates="account")


class XPost(Base):
    """A tweet fetched from a monitored X account."""
    __tablename__ = "x_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("x_accounts.id"))
    tweet_id: Mapped[str] = mapped_column(String(50), unique=True)
    text: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)
    media_urls: Mapped[str] = mapped_column(Text, default="[]")   # JSON list of image/video URLs
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    retweet_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    tweet_url: Mapped[str] = mapped_column(String(500), default="")
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_keywords: Mapped[str] = mapped_column(Text, default="[]")

    account: Mapped[XAccount] = relationship(back_populates="posts")
