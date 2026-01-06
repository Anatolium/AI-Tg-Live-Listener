import datetime
import pytz
from typing import Optional, Sequence
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, select, update, func, delete
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
)
from sqlalchemy.orm import declarative_base
from pathlib import Path

# Локация БД
BASE_DIR = Path(__file__).parent.parent
DB_NAME = "tg_monitor.db"
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / DB_NAME}"

Base = declarative_base()


def msk_now():
    tz_msk = pytz.timezone('Europe/Moscow')
    msk_time = datetime.datetime.now(tz_msk)
    return msk_time.replace(tzinfo=None)  # <-- naive datetime (московское)


class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, unique=True, nullable=True)
    username = Column(String(255), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    is_monitored = Column(Boolean, default=False, nullable=False)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    msg_id = Column(Integer, nullable=False)
    chat_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    sender = Column(String(255))
    text = Column(Text, nullable=False)
    date = Column(DateTime, default=msk_now)  # <-- московское naive datetime
    is_summarized = Column(Boolean, default=False, nullable=False)


class Summary(Base):
    __tablename__ = "summaries"
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    created_at = Column(DateTime, default=msk_now)  # <-- московское naive datetime
    range_start = Column(DateTime)
    range_end = Column(DateTime)
    content = Column(Text, nullable=False)


class Database:
    def __init__(self, url: str = DATABASE_URL):
        self.engine = create_async_engine(url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def add_channel(self, username: str, title: str):
        async with self.session_factory() as session:
            new_channel = Channel(username=username, title=title)
            session.add(new_channel)
            await session.commit()

    async def get_all_channels(self) -> Sequence[Channel]:
        async with self.session_factory() as session:
            result = await session.execute(select(Channel).order_by(Channel.title))
            return result.scalars().all()

    async def get_channel_by_id(self, channel_id: int):
        async with self.session_factory() as session:
            result = await session.execute(select(Channel).where(Channel.id == channel_id))
            return result.scalar_one_or_none()

    async def set_channel_monitored(self, channel_id: int, monitored: bool):
        async with self.session_factory() as session:
            await session.execute(
                update(Channel).where(Channel.id == channel_id).values(is_monitored=monitored)
            )
            await session.commit()

    async def get_monitored_channels(self) -> Sequence[Channel]:
        async with self.session_factory() as session:
            result = await session.execute(select(Channel).where(Channel.is_monitored == True))
            return result.scalars().all()

    async def save_message(self, channel_id, msg_id, sender_id, text):
        async with self.session_factory() as session:
            new_msg = Message(
                msg_id=msg_id,
                chat_id=channel_id,
                sender=str(sender_id),
                text=text or "[Медиа или пустое сообщение]",
                date=datetime.datetime.now(),
                is_summarized=False
            )
            session.add(new_msg)
            await session.commit()

    async def get_stats(self):
        async with self.session_factory() as session:
            total = await session.execute(select(func.count(Message.id)))
            summarized = await session.execute(
                select(func.count(Message.id)).where(Message.is_summarized == True)
            )
            last_sum = await session.execute(
                select(Summary.created_at).order_by(Summary.created_at.desc()).limit(1)
            )

            last_summary = last_sum.scalar_one_or_none()
            if last_summary:
                tz_msk = pytz.timezone('Europe/Moscow')
                last_summary = last_summary.replace(tzinfo=pytz.utc).astimezone(tz_msk)

            return {
                "total": total.scalar() or 0,
                "analyzed": summarized.scalar() or 0,
                "last_summary": last_summary
            }

    async def save_summary(self, channel_id: int, content: str, start_dt: datetime.datetime, end_dt: datetime.datetime):
        async with self.session_factory() as session:
            new_summary = Summary(
                channel_id=channel_id,
                content=content,
                range_start=start_dt,
                range_end=end_dt
            )
            session.add(new_summary)
            await session.execute(
                update(Message)
                .where(Message.chat_id == channel_id)
                .where(Message.date.between(start_dt, end_dt))
                .values(is_summarized=True)
            )
            await session.commit()

    async def delete_channel(self, channel_id: int):
        async with self.session_factory() as session:
            await session.execute(
                update(Message).where(Message.chat_id == channel_id).values(is_summarized=False)
            )
            await session.execute(
                delete(Summary).where(Summary.channel_id == channel_id)
            )
            await session.execute(
                delete(Channel).where(Channel.id == channel_id)
            )
            await session.commit()
            return True
