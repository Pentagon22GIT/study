# bot.py
import os
import discord
from discord.ext import commands
import datetime

# keepalive サーバーの起動
import keepalive

keepalive.start()

# Bot の Intents 設定（VC参加やメンバー情報の取得のため）
intents = discord.Intents.default()
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# サーバごとにタイマー開始時刻を記録する辞書（シンプルな実装例）
voice_timers = {}

# 結果を送信するテキストチャンネルID（環境変数から取得）
DESIGNATED_CHANNEL_ID = int(
    os.environ.get("DESIGNATED_CHANNEL_ID", "123456789012345678")
)


@bot.command()
async def join(ctx):
    """
    VC に参加し、タイマーを開始するコマンド
    """
    if ctx.author.voice and ctx.author.voice.channel:
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            vc = await channel.connect()
            voice_timers[ctx.guild.id] = datetime.datetime.now()
            await ctx.send("VC に参加しました。タイマーを開始します。")
        else:
            await ctx.send("すでに VC に参加中です。")
    else:
        await ctx.send("まず VC に参加してからこのコマンドを実行してください。")


@bot.command()
async def leave(ctx):
    """
    VC から退出し、滞在時間を計測・報告するコマンド
    """
    if ctx.voice_client:
        start_time = voice_timers.pop(ctx.guild.id, None)
        elapsed = datetime.datetime.now() - start_time if start_time else None
        await ctx.voice_client.disconnect()
        if elapsed:
            elapsed_seconds = int(elapsed.total_seconds())
            message = f"VC 滞在時間: {elapsed_seconds}秒"
            designated_channel = bot.get_channel(DESIGNATED_CHANNEL_ID)
            if designated_channel:
                await designated_channel.send(message)
        await ctx.send("VC から退出しました。")
    else:
        await ctx.send("VC に参加していません。")


@bot.event
async def on_voice_state_update(member, before, after):
    """
    VC 内のメンバー変化を監視し、
    ボット以外のメンバーがいなくなった場合、自動退出するイベントハンドラー
    """
    vc = member.guild.voice_client
    if vc:
        # ボットのみの場合、自動退出
        if len(vc.channel.members) == 1:
            start_time = voice_timers.pop(member.guild.id, None)
            elapsed = datetime.datetime.now() - start_time if start_time else None
            await vc.disconnect()
            if elapsed:
                elapsed_seconds = int(elapsed.total_seconds())
                message = f"VC 滞在時間: {elapsed_seconds}秒（自動退出）"
                designated_channel = bot.get_channel(DESIGNATED_CHANNEL_ID)
                if designated_channel:
                    await designated_channel.send(message)


# googletrans を利用した翻訳コマンドの実装例
from googletrans import Translator


@bot.command()
async def translate(ctx, direction: str, *, text: str):
    """
    翻訳コマンド
    - direction: "en2jp" もしくは "jp2en"
    - text: 翻訳対象のテキスト
    """
    translator = Translator()
    if direction == "en2jp":
        result = translator.translate(text, src="en", dest="ja")
        await ctx.send(result.text)
    elif direction == "jp2en":
        result = translator.translate(text, src="ja", dest="en")
        await ctx.send(result.text)
    else:
        await ctx.send("direction は「en2jp」または「jp2en」を指定してください。")


# Bot トークンは環境変数から取得
TOKEN = os.environ.get("DISCORD_TOKEN")
bot.run(TOKEN)
