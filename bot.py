import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio
from supabase import create_client, Client

import keepalive

keepalive.start()

# SupabaseのURLとKEYを環境変数から取得してクライアント生成
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 必要な Intents を有効化
intents = discord.Intents.default()
intents.voice_states = True
intents.members = True


# Bot のサブクラス化（setup_hookでスラッシュコマンドを同期）
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()


bot = MyBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}.")
    await bot.change_presence(activity=discord.Game(name="開発中"))


#
# /start コマンド
# VCに参加し、勉強セッションの開始を記録する
#
@bot.tree.command(
    name="start",
    description="VCに参加して勉強セッションを開始します。タイトルを入力してください。",
)
@app_commands.describe(title="勉強セッションのタイトル")
async def start(interaction: discord.Interaction, title: str):
    if interaction.user.voice and interaction.user.voice.channel:
        channel = interaction.user.voice.channel
        if interaction.guild.voice_client is None:
            await channel.connect()

        # 現在時刻（UTC, timezone-aware）を記録
        current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        data = {"title": title, "start": current_time, "time": None}

        # 挿入実行
        response = supabase.table("study_sessions").insert(data).execute()

        await interaction.response.send_message(
            f"勉強セッション「{title}」を開始しました。", ephemeral=False
        )
    else:
        await interaction.response.send_message(
            "まずVCに参加してください。", ephemeral=True
        )


#
# /end コマンド
# VCから退出し、最新の勉強セッションの経過時間を計算して更新する
#
@bot.tree.command(name="end", description="VCから退出し、勉強セッションを終了します。")
async def end(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        vc = interaction.guild.voice_client
        await vc.disconnect()
        # timeが未設定（NULL）の最新セッションレコードを取得
        result = (
            supabase.table("study_sessions")
            .select("*")
            .is_("time", None)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )

        record = result.data[0]
        start_time = datetime.datetime.fromisoformat(record["start"])
        elapsed = (
            datetime.datetime.now(datetime.timezone.utc) - start_time
        ).total_seconds()

        # 経過時間でレコードを更新
        update_result = (
            supabase.table("study_sessions")
            .update({"time": elapsed})
            .eq("id", record["id"])
            .execute()
        )

        await interaction.response.send_message(
            f"勉強セッションを終了しました。経過時間: {elapsed:.0f}秒", ephemeral=False
        )
    else:
        await interaction.response.send_message(
            "VCに参加していません。", ephemeral=True
        )


#
# /records コマンド
# 過去10回分の勉強記録を表示する
#
@bot.tree.command(name="records", description="過去10回分の勉強記録を表示します。")
async def records(interaction: discord.Interaction):
    result = (
        supabase.table("study_sessions")
        .select("*")
        .order("id", desc=True)
        .limit(10)
        .execute()
    )

    records_data = result.data
    if not records_data:
        await interaction.response.send_message("記録がありません。", ephemeral=True)
        return

    msg = "過去の勉強記録:\n"
    for rec in records_data:
        title = rec["title"]
        start_time = rec["start"]
        elapsed = rec["time"]
        elapsed_str = "進行中" if elapsed is None else f"{int(elapsed)}秒"
        msg += f"タイトル: {title} | 開始: {start_time} | 経過: {elapsed_str}\n"

    await interaction.response.send_message(msg, ephemeral=False)


TOKEN = os.environ.get("DISCORD_TOKEN")
bot.run(TOKEN)
