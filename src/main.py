import datetime
from datetime import timezone
import enum
import os
import zoneinfo
from typing import Optional, Final, List, Dict, Literal

import json
import discord
import psycopg2
import psycopg2.extras
from discord import app_commands
from discord.ext import commands, tasks

from .UtilityClasses_DiscordBot import command

DATABASE_URL = os.getenv('DATABASE_URL')
ZONE_TOKYO = zoneinfo.ZoneInfo('Asia/Tokyo')

COLORS: Final[Dict[str, discord.Color]] = {
    'red': discord.Color.red(),
    'orange': discord.Color.orange(),
    'yellow': discord.Color.yellow(),
    'brand green': discord.Color.brand_green(),
    'green': discord.Color.green(),
    'blue': discord.Color.blue(),
    'dark blue': discord.Color.dark_blue(),
    'purple': discord.Color.purple(),
    'black': discord.Color.default(),
    'grey': discord.Color.dark_theme(),
    'white': discord.Color.from_rgb(0, 0, 0)
}
COLORS_KEYS = tuple(COLORS.keys())


def generate_embed(title: str, description: Optional[str], image: Optional[str], thumbnail: Optional[str],
                   footer: Optional[str], footer_icon: Optional[str], color: discord.Color,
                   author: Optional[Literal['author']], user: discord.Member) -> discord.Embed:
    embed = discord.Embed(color=color, title=title, description=description)
    if image is not None:
        embed.set_image(url=image)
    if thumbnail is not None:
        embed.set_thumbnail(url=thumbnail)
    if footer is None:
        if footer_icon is None:
            pass
        else:
            embed.set_footer(icon_url=footer_icon)
    else:
        if footer_icon is None:
            embed.set_footer(text=footer)
        else:
            embed.set_footer(text=footer, icon_url=footer_icon)
    if author is not None:
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)

    return embed


class SendGroupCog(command.GroupCog, name='send'):
    def __init__(self, bot: commands.Bot, allow_duplicated: bool = False):
        super().__init__(bot=bot, allow_duplicated=allow_duplicated)
        self.database_connector = psycopg2.connect(DATABASE_URL)

    async def cog_load(self) -> None:
        if not self.sender.is_running():
            self.sender.start()
        with self.database_connector.cursor() as cur:
            cur.execute(
                'SELECT timestamp FROM scheduled_post'
            )
            results = cur.fetchall()
        times = [result.timetz() for result, in results] + self.sender.time
        print(times)
        self.sender.change_interval(time=times)
        print(self.sender.time)

    @app_commands.command(description='メッセージの予約投稿ができます。')
    @app_commands.describe(title='タイトル', description='詳細', image='大きく表示したい画像のurl',
                           thumbnail='小さく表示したい画像のurl', footer='下端に表示したい文章',
                           footer_icon='下端に表示したい画像のurl', color='色', author='作者情報を表示するか否か',
                           interval_days='繰り返しの間隔(日)',
                           interval_hours='繰り返しの間隔(時)', interval_minutes='繰り返しの間隔(分)')
    async def reserve(self, interaction: discord.Interaction, year: int, month: int, day: int, hour: int, minute: int,
                      title: str, description: Optional[str], image: Optional[str], thumbnail: Optional[str],
                      footer: Optional[str], footer_icon: Optional[str], author: Optional[Literal['author']],
                      color: Literal[COLORS_KEYS] = 'black', interval_days: int = 0, interval_hours: int = 0,
                      interval_minutes: int = 0):
        # エラー処理
        try:
            datetime_reserved = datetime.datetime(
                year=year, month=month, day=day, hour=hour, minute=minute, tzinfo=ZONE_TOKYO
            )
        except ValueError:
            embed = discord.Embed(
                title='エラー: 不正な時刻が指定されています。', description='以下の範囲で入力してください。', colour=discord.Colour.red()
            )
            embed.add_field(name='{0} <= year <= {1}'.format(datetime.MINYEAR, datetime.MAXYEAR))
            embed.add_field(name='1 <= month <= 12', value=' ')
            embed.add_field(name='1 <= day <= 28~31', value=' ')
            embed.add_field(name='0 <= hour <= 23', value=' ')
            embed.add_field(name='0 <= minute <= 59', value=' ')
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return
        try:
            interval = datetime.timedelta(days=interval_days, hours=interval_hours, minutes=interval_minutes)
        except OverflowError:
            embed = discord.Embed(
                title='エラー: 不正な時間が指定されています。', description='入力が大きすぎます。', colour=discord.Colour.red()
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
        if datetime_reserved < datetime.datetime.now(tz=ZONE_TOKYO) + datetime.timedelta(minutes=1):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title='エラー: 不正な時刻が指定されています。', description='現在時刻の1分後以降を指定してください。', colour=discord.Colour.red()),
                ephemeral=True
            )
            return
        embed = generate_embed(
            title=title, description=description, image=image, thumbnail=thumbnail,
            footer=footer, footer_icon=footer_icon, color=COLORS[color], author=author,
            user=interaction.user
        )

        # 予約処理
        if interval_days == 0 and interval_hours == 0 and interval_minutes == 0:
            with self.database_connector.cursor() as cur:
                cur.execute(
                    'INSERT INTO scheduled_post (channel_id, user_id, embed, timestamp, interval) VALUES (%s, %s, %s, %s, %s)',
                    (interaction.channel_id, interaction.user.id, json.dumps(embed.to_dict()), datetime_reserved, None)
                )
                self.database_connector.commit()
            times = [datetime_reserved.astimezone(tz=datetime.timezone.utc).timetz()] + self.sender.time
            self.sender.change_interval(time=times)
            self.sender.restart()

            await interaction.response.send_message(
                embeds=[discord.Embed(
                    title='予約されました。',
                    description='{}に以下のメッセージが送信されます。'.format(datetime_reserved.strftime('%Y年%m月%d日%H時%M分'))),
                        embed
                ], ephemeral=True
            )
        else:
            with self.database_connector.cursor() as cur:
                cur.execute(
                    'INSERT INTO scheduled_post (channel_id, user_id, embed, timestamp, interval) VALUES (%s, %s, %s, %s, %s)',
                    (interaction.channel_id, interaction.user.id, json.dumps(embed.to_dict()), datetime_reserved, interval)
                )
                self.database_connector.commit()
            times = [datetime_reserved.astimezone(tz=datetime.timezone.utc).timetz()] + self.sender.time
            self.sender.change_interval(time=times)
            self.sender.restart()

            await interaction.response.send_message(
                embeds=[discord.Embed(
                    title='予約されました。',
                    description='{0}に以下のメッセージが送信されます。以後{1}日{2}時{3}分間に1度繰り返し送信されます。'.format(
                        datetime_reserved.strftime('%Y年%m月%d日%H時%M分'),
                        interval_days, interval_hours, interval_minutes
                    )),
                    embed
                ], ephemeral=True
            )

    @app_commands.command(description='装飾されたメッセージを送信できます。')
    @app_commands.describe(title='タイトル', description='詳細', image='大きく表示したい画像のurl',
                           thumbnail='小さく表示したい画像のurl', footer='下端に表示したい文章',
                           footer_icon='下端に表示したい画像のurl', color='色', author='作者情報を表示するか否か')
    async def now(self, interaction: discord.Interaction, title: str, description: Optional[str],
                  image: Optional[str], thumbnail: Optional[str], footer: Optional[str], footer_icon: Optional[str],
                  author: Optional[Literal['author']], color: Optional[Literal[COLORS_KEYS]] = 'black'):
        await interaction.response.send_message(embed=generate_embed(
            title=title, description=description, image=image, thumbnail=thumbnail, footer=footer,
            footer_icon=footer_icon, color=COLORS[color], author=author, user=interaction.user
        ))

    @tasks.loop(time=[datetime.time(hour=0, minute=0, tzinfo=timezone.utc),
                      datetime.time(hour=22, minute=3, tzinfo=timezone.utc)])
    async def sender(self):
        now = datetime.datetime.now(tz=ZONE_TOKYO)
        with self.database_connector.cursor() as cur:
            cur.execute(
                'SELECT channel_id, user_id, embed, timestamp, interval FROM scheduled_post WHERE timestamp < %s',
                (now + datetime.timedelta(minutes=1),)
            )
            results = cur.fetchall()
        next_repetitions = []
        for channel_id, user_id, embed, timestamp, interval in results:
            print(embed)
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                continue
            else:
                if not isinstance(channel, discord.TextChannel):
                    continue
                if user_id not in [member.id for member in channel.members]:
                    continue

            if 'title' in embed:
                embed['title'] = embed['title'].format(
                    datetime=now.strftime('%Y年%m月%d日%H時%M分'),
                    date=now.strftime('%Y年%m月%d日'), time=now.strftime('%H時%M分'),
                    year=now.year, month=now.month, day=now.day, hour=now.hour, minute=now.minute, second=now.second
                )
            if 'description' in embed:
                embed['description'] = embed['description'].format(
                    datetime=now.strftime('%Y年%m月%d日%H時%M分'),
                    date=now.strftime('%Y年%m月%d日'), time=now.strftime('%H時%M分'),
                    year=now.year, month=now.month, day=now.day, hour=now.hour, minute=now.minute, second=now.second
                )
            if 'footer' in embed:
                embed['footer'] = embed['footer'].format(
                    datetime=now.strftime('%Y年%m月%d日%H時%M分'),
                    date=now.strftime('%Y年%m月%d日'), time=now.strftime('%H時%M分'),
                    year=now.year, month=now.month, day=now.day, hour=now.hour, minute=now.minute, second=now.second
                )

            await channel.send(embed=discord.Embed.from_dict(embed))
            if interval is not None:
                next_repetitions.append((channel_id, user_id, embed, timestamp + interval, interval))
        with self.database_connector.cursor() as cur:
            cur.execute(
                'DELETE FROM scheduled_post WHERE timestamp < %s', (now,)
            )
            self.database_connector.commit()
            for channel_id, user_id, embed, timestamp, interval in next_repetitions:
                cur.execute(
                    'INSERT INTO scheduled_post (channel_id, user_id, embed, timestamp, interval) VALUES (%s, %s, %s, %s, %s)',
                    (channel_id, user_id, json.dumps(embed), timestamp, interval)
                )
            self.database_connector.commit()
        times = [] + self.sender.time
        for next_repetition in next_repetitions:
            times.append(next_repetition[3].timetz())
        self.sender.change_interval(time=times)
        self.sender.restart()


class Essential(command.Command):
    def __init__(self, bot: discord.ext.commands.Bot):
        super().__init__(bot=bot)


async def setup(bot: discord.ext.commands.Bot):
    await bot.add_cog(SendGroupCog(bot=bot, allow_duplicated=True))
    await bot.add_cog(Essential(bot=bot))
