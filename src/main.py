import datetime
import enum
import os
import zoneinfo
from typing import Optional, Final, List, Dict, Literal

import discord
import psycopg2
import psycopg2.extras
from discord import app_commands
from discord.ext import commands, tasks

from .UtilityClasses_DiscordBot import base

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


class Essential(base.Command):
    def __init__(self, bot: discord.ext.commands.Bot):
        super().__init__(bot=bot)

    @app_commands.command(description='装飾されたメッセージを送信できます。')
    @app_commands.describe(title='タイトル', description='詳細', image='大きく表示したい画像のurl',
                           thumbnail='小さく表示したい画像のurl', footer='下端に表示したい文章',
                           footer_icon='下端に表示したい画像のurl', color='色', is_author='作者情報を表示するか否か')
    async def embed(self, interaction: discord.Interaction, title: str, description: Optional[str],
                    image: Optional[str], thumbnail: Optional[str], footer: Optional[str], footer_icon: Optional[str],
                    color: Optional[Literal[COLORS_KEYS]], is_author: bool = True):
        embed = discord.Embed(
            title=title, description=description, color=COLORS[color]
        )
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
        if is_author:
            embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)


async def setup(bot: discord.ext.commands.Bot):
    await bot.add_cog(Essential(bot=bot))
