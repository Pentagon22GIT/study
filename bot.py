# from dotenv import load_dotenv

# load_dotenv()

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

# 定数設定（以下のIDは実際のチャンネルIDに置き換えてください）
MONITORED_VC_ID = int(os.environ.get("MONITORED_VC_ID"))
DESIGNATED_TEXT_CHANNEL_ID = int(os.environ.get("DESIGNATED_TEXT_CHANNEL_ID"))

# 自動VCセッション管理用のグローバル変数（単一サーバー用）
auto_session = None


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
# テキストチャット上での勉強セッション開始コマンド
#
@bot.tree.command(
    name="start",
    description="テキストチャットで勉強セッションを開始します。タイトルを入力してください。",
)
@app_commands.describe(title="勉強セッションのタイトル")
async def start(interaction: discord.Interaction, title: str):
    now = datetime.datetime.now(datetime.timezone.utc)
    current_time_iso = now.isoformat()
    # 月日 時分秒の形式で表示
    current_time_formatted = now.strftime("%m月%d日 %H:%M:%S")
    data = {"title": title, "start": current_time_iso, "time": None}
    supabase.table("study_sessions").insert(data).execute()

    embed = discord.Embed(
        title="勉強開始",
        description=f"**{title}** を開始しました。",
        color=0x00FF00,  # 緑系の色
    )
    embed.set_footer(text=f"開始時刻: {current_time_formatted}")

    await interaction.response.send_message(embed=embed, ephemeral=False)


#
# テキストチャット上での勉強セッション終了コマンド
#
# テキストチャット上での勉強セッション終了コマンド
@bot.tree.command(
    name="end", description="テキストチャット上で勉強セッションを終了します。"
)
async def end(interaction: discord.Interaction):
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
    # 経過時間を整数秒で計算
    elapsed = int(
        (datetime.datetime.now(datetime.timezone.utc) - start_time).total_seconds()
    )
    supabase.table("study_sessions").update({"time": elapsed}).eq(
        "id", record["id"]
    ).execute()

    # 秒数を 時間・分・秒 に変換
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60
    elapsed_formatted = f"{hours}時間 {minutes}分 {seconds}秒"

    embed = discord.Embed(
        title="勉強終了",
        description=f"勉強時間: {elapsed_formatted}",
        color=0xFF4500,  # オレンジレッド系の色
    )
    embed.set_footer(text="勉強時間の計測を終了しました")

    await interaction.response.send_message(embed=embed, ephemeral=False)


#
# 自動VCタイマー機能
# VC の状態変化を監視し、対象VCに誰かが入ったら自動で参加・計測開始、
# VCから Bot 以外の全ユーザーが退出したら自動で退出し、結果を指定テキストチャンネルへ送信します。
#
# 自動VCタイマー機能（VCセッション終了時の処理）
@bot.event
async def on_voice_state_update(
    member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
):
    global auto_session

    # 監視対象のVCチャンネルを取得
    monitored_channel = bot.get_channel(MONITORED_VC_ID)
    if monitored_channel is None:
        return

    # Bot自身の更新は無視
    if member.bot:
        return

    # 対象VCにいるBot以外のメンバーを取得
    non_bot_members = [m for m in monitored_channel.members if not m.bot]

    if non_bot_members and auto_session is None:
        # 自動セッション開始：対象VCに人が入ったら（かつまだセッションが開始されていなければ）
        voice_client = discord.utils.get(
            bot.voice_clients, guild=monitored_channel.guild
        )
        if not voice_client or voice_client.channel.id != MONITORED_VC_ID:
            await monitored_channel.connect()

        now = datetime.datetime.now(datetime.timezone.utc)
        start_time_iso = now.isoformat()
        response = (
            supabase.table("vc_sessions")
            .insert({"start": start_time_iso, "time": None})
            .execute()
        )
        record_id = response.data[0]["id"]
        auto_session = {"start": start_time_iso, "record_id": record_id}
        print("自動VCセッションを開始しました。")

    elif not non_bot_members and auto_session is not None:
        # 自動セッション終了：対象VCから Bot以外の全ユーザーが退出した場合
        voice_client = discord.utils.get(
            bot.voice_clients, guild=monitored_channel.guild
        )
        if voice_client and voice_client.channel.id == MONITORED_VC_ID:
            await voice_client.disconnect()

        start_time_dt = datetime.datetime.fromisoformat(auto_session["start"])
        elapsed = int(
            (
                datetime.datetime.now(datetime.timezone.utc) - start_time_dt
            ).total_seconds()
        )
        supabase.table("vc_sessions").update({"time": elapsed}).eq(
            "id", auto_session["record_id"]
        ).execute()

        # 秒数を 時間・分・秒 に変換
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        elapsed_formatted = f"{hours}時間 {minutes}分 {seconds}秒"

        designated_channel = bot.get_channel(DESIGNATED_TEXT_CHANNEL_ID)
        if designated_channel:
            embed = discord.Embed(
                title="ストップウォッチ",
                description=f"勉強時間: {elapsed_formatted}",
                color=0x1E90FF,  # ドジャーブルー系の色
            )
            embed.set_footer(text="vc計測結果")
            await designated_channel.send(embed=embed)

        auto_session = None


TOKEN = os.environ.get("DISCORD_TOKEN")
bot.run(TOKEN)
