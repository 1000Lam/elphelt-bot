import discord
import os
import random
import asyncio
import json
import time
import threading
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta


load_dotenv() # Load the .env file
TOKEN = os.getenv("BOT_TOKEN") # PUT IT IN SO THE BOT CAN RUN
CATEGORY_ID = int(os.getenv("CATEGORY_ID")) # THE CATEGORY ID WHERE THE VC WILL BE CREATED
ALLOWED_SERVER_ID = int(os.getenv("ALLOWED_SERVER_ID")) # THE SERVER ID WHERE THE COMMANDS CAN BE USED FOR TEMP VC
ALLOWED_USERS = set(map(int, os.getenv("ALLOWED_USERS").split(","))) #THE !SAY COMMAND CAN BE USED BY THESE USERS

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True


bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
tree = bot.tree
#json hell
WALLET_FILE = "wallets.json"
BJSTATS_FILE = "blackjack_stats.json"
PERSISTENT_VC_NAME = "╰-₊˚ʚ-♡"
DATA_FILE = "temp_vc_data.json"
LASTCLAIM_FILE = "lastclaim.json"
STOCKS_FILE = "stocks.json"
PORTFOLIO_FILE = "portfolio.json"


# Define UTC+7 timezone
UTC_PLUS_7 = timezone(timedelta(hours=7))
wallet_lock = threading.Lock()
now = datetime.now(UTC_PLUS_7)

# Load stats from file if it exists
if os.path.exists(BJSTATS_FILE):
    with open(BJSTATS_FILE, "r") as f:
        blackjack_stats = json.load(f)
else:
    blackjack_stats = {}

card = {
    "A♠️": 11, "A♥️": 11, "A♦️": 11, "A♣️": 11,
    "2♠️": 2, "2♥️": 2, "2♦️": 2, "2♣️": 2,
    "3♠️": 3, "3♥️": 3, "3♦️": 3, "3♣️": 3,
    "4♠️": 4, "4♥️": 4, "4♦️": 4, "4♣️": 4,
    "5♠️": 5, "5♥️": 5, "5♦️": 5, "5♣️": 5,
    "6♠️": 6, "6♥️": 6, "6♦️": 6, "6♣️": 6,
    "7♠️": 7, "7♥️": 7, "7♦️": 7, "7♣️": 7,
    "8♠️": 8, "8♥️": 8, "8♦️": 8, "8♣️": 8,
    "9♠️": 9, "9♥️": 9, "9♦️": 9, "9♣️": 9,
    "10♠️": 10, "10♥️": 10, "10♦️": 10, "10♣️": 10,
    "J♠️": 10, "J♥️": 10, "J♦️": 10, "J♣️": 10,
    "Q♠️": 10, "Q♥️": 10, "Q♦️": 10, "Q♣️": 10,
    "K♠️": 10, "K♥️": 10, "K♦️": 10, "K♣️": 10
}


def load_wallets():
    try:
        with open(WALLET_FILE, "r") as f:
            wallets = json.load(f)
    except FileNotFoundError:
        wallets = {}

    # Ensure all users have both currency types
    for user_id in wallets:
        if "coins" not in wallets[user_id]:
            wallets[user_id]["coins"] = 2500  # Default coins
        if "dailes" not in wallets[user_id]:
            wallets[user_id]["dailes"] = 0  # Default Dailes

    return wallets


def save_wallets(wallets):
    with open(WALLET_FILE, "w") as f:
        json.dump(wallets, f, indent=4)

def get_balance(user_id):
    wallets = load_wallets()
    user_wallet = wallets.get(str(user_id), {"coins": 2500, "dailes": 0})
    return user_wallet["coins"], user_wallet["dailes"]

def update_balance(user_id, coins=0, dailes=0):
    user_id = str(user_id)  # Ensure it's a string

    with wallet_lock:  # Prevents issues when multiple updates happen at once
        wallets = load_wallets()

        # ✅ If the user doesn't exist, create them but DON'T overwrite existing users
        if user_id not in wallets:
            wallets[user_id] = {"coins": 2500, "dailes": 0}

        # ✅ Ensure values exist (in case of corrupted data)
        if "coins" not in wallets[user_id]:
            wallets[user_id]["coins"] = 2500
        if "dailes" not in wallets[user_id]:
            wallets[user_id]["dailes"] = 0

        # ✅ Prevent negative balance
        if wallets[user_id]["coins"] + coins < 0:
            return False  # Not enough funds, return failure

        # ✅ Update values
        wallets[user_id]["coins"] += coins
        wallets[user_id]["dailes"] += dailes

        save_wallets(wallets)  # Save changes
        return True  # Successfully updated

def save_blackjack_stats():
    """Save stats to a JSON file."""
    with open(BJSTATS_FILE, "w") as f:
        json.dump(blackjack_stats, f, indent=4)

def record_blackjack_stats(user_id, bet, result, profit):
    """Track wins, losses, money won/lost, and history."""
    if str(user_id) not in blackjack_stats:
        blackjack_stats[str(user_id)] = {'wins': 0, 'losses': 0, 'ties': 0, 'money_won': 0, 'money_lost': 0, 'history': []}

    stats = blackjack_stats[str(user_id)]

    if result == "win":
        stats['wins'] += 1
        stats['money_won'] += bet * 2
        stats['history'].append("W")
    elif result == "loss":
        stats['losses'] += 1
        stats['money_lost'] += bet
        stats['history'].append("L")
    elif result == "tie":
        stats['ties'] += 1
        stats['history'].append("T")

    if len(stats['history']) > 5:
        stats['history'].pop(0)

    save_blackjack_stats()

def fmt(num): return f"{num:,}"

def draw_card():
    return random.choice(list(card.items()))

# Load saved VC data
def load_vc_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

temp_vcs = load_vc_data()


# Load stock prices from the JSON file
def load_stock_prices():
    try:
        with open("stock_prices.json", "r") as f:
            stock_prices = json.load(f)
    except FileNotFoundError:
        stock_prices = {}

    # Set default prices and history if not available
    default_stocks = {
        "Valiant coins": {"price": 100, "previous_price": 100},
        "$ol badman": {"price": 900, "previous_price": 900},
        "19 inches of Venom": {"price": 2000, "previous_price": 2000},
        "Blessed tokens": {"price": 450, "previous_price": 450},
    }


    for stock, data in default_stocks.items():
        if stock not in stock_prices:
            stock_prices[stock] = data

    return stock_prices


def save_stock_prices(stock_prices):
    with open("stock_prices.json", "w") as f:
        json.dump(stock_prices, f, indent=4)



def update_stock_prices():
    stock_prices = load_stock_prices()

    for stock in stock_prices:
        previous_price = stock_prices[stock]["price"]
        trend = stock_prices[stock].get("trend", random.choice([-1, 1]))  # Assign a trend if none exists

        # Random fluctuation within a range, influenced by trend
        price_change = random.randint(-60, 70) * trend  # Slightly favoring positive growth

        # Momentum effect (slightly favor previous price movement)
        if stock_prices[stock].get("previous_change", 0) > 0:
            price_change += random.randint(0, 10)  # Boost upward trend
        elif stock_prices[stock].get("previous_change", 0) < 0:
            price_change -= random.randint(0, 10)  # Reinforce downward trend

        # Ensure the stock price doesn't drop below 1
        new_price = max(1, previous_price + price_change)

        # Store updated values
        stock_prices[stock]["previous_price"] = previous_price
        stock_prices[stock]["price"] = new_price
        stock_prices[stock]["previous_change"] = price_change  # Track the last change
        stock_prices[stock]["trend"] = trend if random.random() > 0.1 else -trend  # Occasionally reverse trend

    save_stock_prices(stock_prices)
    return stock_prices

# Load user portfolio data (how much of each stock they own)
def load_user_portfolio():
    try:
        with open("portfolio.json", "r") as f:
            user_portfolio = json.load(f)
    except FileNotFoundError:
        user_portfolio = {}

    return user_portfolio


# Save the updated user portfolio
def save_user_portfolio(user_portfolio):
    with open("portfolio.json", "w") as f:
        json.dump(user_portfolio, f, indent=4)


# Asynchronous function to update stock prices periodically
async def update_stock_prices_periodically():
    while True:
        await asyncio.sleep(60)  # Wait for 1 minute
        stock_prices = update_stock_prices()  # Update stock prices
        # print("Stock prices updated:", stock_prices)


@bot.tree.command(name="tempvc", description="Create a temporary voice channel🎤 with a user limit.")
@app_commands.describe(limit="Set the user limit for the VC (2-99)")
async def vc(interaction: discord.Interaction, limit: int):
    global temp_vcs

    # Ensure command is used in the correct server
    if interaction.guild.id != ALLOWED_SERVER_ID:
        await interaction.response.send_message("❌ This command can only be used in the allowed server.", ephemeral=True)
        return

    # Validate limit
    if limit < 2 or limit > 99:
        await interaction.response.send_message("❌ Please choose a valid limit between 2 and 99.", ephemeral=True)
        return

    # Determine VC name
    if limit <= 4:
        name = "︰🪑 | 𝐏𝐫𝐢𝐯𝐚𝐭𝐞"
    elif limit <= 10:
        name = "︰🎉 | 𝐏𝐚𝐫𝐭𝐲"
    else:
        name = "︰👔 | 𝐕𝐞𝐧𝐮𝐞"

    # Find category
    category = discord.utils.get(interaction.guild.categories, id=CATEGORY_ID)
    if not category:
        await interaction.response.send_message("❌ Category not found.", ephemeral=True)
        return

    # Delete old persistent VC before creating a new one
    for channel in category.voice_channels:
        if channel.name == PERSISTENT_VC_NAME:
            await channel.delete()
            break

    # Create temporary VC
    temp_vc = await interaction.guild.create_voice_channel(name, category=category, user_limit=limit)

    # Set permissions for `╰-₊˚ʚ-♡`
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(
            view_channel=True,  # Everyone can see it
            connect=False       # No one can join
        )
    }

    # Create new `╰-₊˚ʚ-♡` channel
    persistent_vc = await interaction.guild.create_voice_channel(
        PERSISTENT_VC_NAME, category=category, overwrites=overwrites
    )

    # Store VC creation time
    temp_vcs[str(temp_vc.id)] = {
        "created_at": now.isoformat(),
        "guild_id": interaction.guild.id
    }
    save_vc_data(temp_vcs)  # Save data to file

    await interaction.response.send_message(f"✅ Temporary VC created: {temp_vc.mention}", ephemeral=True)


# Save VC data
def save_vc_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

@tasks.loop(minutes=1)  # Runs every 1 minute
async def cleanup_task():
    now = datetime.now(UTC_PLUS_7)

    for vc_id, data in list(temp_vcs.items()):
        guild = bot.get_guild(data["guild_id"])
        if not guild:
            continue

        vc = guild.get_channel(int(vc_id))
        if vc and len(vc.members) == 0:
            created_at = datetime.fromisoformat(data["created_at"]).replace(tzinfo=UTC_PLUS_7)
            elapsed_time = (now - created_at).total_seconds()

            if elapsed_time > 300:  # 5 minutes
                await vc.delete()
                del temp_vcs[vc_id]
                save_vc_data(temp_vcs)


@bot.tree.command(name="blackjack", description="Play blackjack with me! 🎰")
async def blackjack(interaction: discord.Interaction, bet: int):
    user_id = interaction.user.id
    balance = get_balance(user_id)[0]

    if bet <= 0:
        await interaction.response.send_message("❌ Your bet must be greater than 0!", ephemeral=True)
        return
    if bet > balance:
        await interaction.response.send_message(f"❌ You don't have enough money! Your balance: {fmt(balance)}", ephemeral=True)
        return

    update_balance(user_id, -bet)  # Deduct bet from balance

    await interaction.response.defer()
    user_hand = [draw_card(), draw_card()]
    dealer_hand = [draw_card(), draw_card()]

    user_total = sum(card[1] for card in user_hand)
    dealer_total = sum(card[1] for card in dealer_hand)

    user_cards = " ".join(card[0] for card in user_hand)
    dealer_cards = f"{dealer_hand[0][0]} ❓"

    # **Check if the player or dealer has a Blackjack**
    user_blackjack = user_total == 21 and len(user_hand) == 2
    dealer_blackjack = dealer_total == 21 and len(dealer_hand) == 2

    if user_blackjack and not dealer_blackjack:  # **Player wins instantly**
        winnings = bet * 2.5  # **Blackjack pays 3:2**
        update_balance(user_id, winnings)
        record_blackjack_stats(user_id, bet, "blackjack", bet * 1.5)

        embed = discord.Embed(title="🎰 Blackjack 🎰", color=discord.Color.green())
        embed.add_field(name="Your Hand 🃏", value=f"{user_cards} → **{user_total}** (🎉 **Blackjack!**)", inline=False)
        embed.add_field(name="Dealer's Hand 🤵", value=f"{dealer_hand[0][0]} ❓", inline=False)
        embed.set_footer(text=f"Blackjack! You win {fmt(winnings - bet)} coins! 💰")
        await interaction.followup.send(embed=embed)
        return

    if dealer_blackjack and not user_blackjack:  # **Dealer wins instantly**
        embed = discord.Embed(title="🎰 Blackjack 🎰", color=discord.Color.red())
        embed.add_field(name="Your Hand 🃏", value=f"{user_cards} → **{user_total}**", inline=False)
        embed.add_field(name="Dealer's Hand 🤵", value=f"{' '.join(card[0] for card in dealer_hand)} → **{dealer_total}** (🔥 **Blackjack!**)", inline=False)
        embed.set_footer(text=f"Dealer got Blackjack! You lost {fmt(bet)} coins. 😭")
        record_blackjack_stats(user_id, bet, "loss", -bet)
        await interaction.followup.send(embed=embed)
        return

    # **Continue game if no one got Blackjack**
    embed = discord.Embed(title="🎰 Blackjack 🎰", color=discord.Color.gold())
    embed.add_field(name="Your Hand 🃏", value=f"{user_cards} → **{user_total}**", inline=False)
    embed.add_field(name="Dealer's Hand 🤵", value=f"{dealer_cards}", inline=False)
    embed.add_field(name="Bet Amount 💰", value=f"**{fmt(bet)}** coins", inline=False)
    embed.set_footer(text="React with 🃏 to Hit or ✋ to Stand.")

    message = await interaction.followup.send(embed=embed)
    await message.add_reaction("🃏")
    await message.add_reaction("✋")

    def check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in ["🃏", "✋"]

    while True:
        try:
            reaction, _ = await bot.wait_for("reaction_add", check=check, timeout=30)

            if str(reaction.emoji) == "🃏":  # HIT
                new_card = draw_card()
                user_hand.append(new_card)
                user_total += new_card[1]

                if user_total > 21:
                    for i, (card_name, value) in enumerate(user_hand):
                        if "A" in card_name and value == 11:
                            user_hand[i] = (card_name, 1)
                            user_total -= 10
                            break

                user_cards = " ".join(card[0] for card in user_hand)
                embed.set_field_at(0, name="Your Hand 🃏", value=f"{user_cards} → **{user_total}**", inline=False)
                await message.edit(embed=embed)

                if user_total > 21:  # **Player Busts**
                    embed.color = discord.Color.red()
                    embed.set_footer(text=f"You busted! 💥 Dealer wins.\nYour Balance: {fmt(balance - bet)} (-{fmt(bet)}) coins")
                    record_blackjack_stats(user_id, bet, "loss", -bet)
                    await message.edit(embed=embed)
                    await message.clear_reactions()
                    break

            elif str(reaction.emoji) == "✋":  # STAND
                while dealer_total < 17:
                    new_card = draw_card()
                    dealer_hand.append(new_card)
                    dealer_total += new_card[1]

                    if dealer_total > 21:
                        for i, (card_name, value) in enumerate(dealer_hand):
                            if "A" in card_name and value == 11:
                                dealer_hand[i] = (card_name, 1)
                                dealer_total -= 10
                                break

                dealer_cards = " ".join(card[0] for card in dealer_hand)
                embed.set_field_at(1, name="Dealer's Hand 🤵", value=f"{dealer_cards} → **{dealer_total}**", inline=False)

                if dealer_total > 21 or user_total > dealer_total:  # **Player Wins**
                    winnings = bet * 2
                    profit = bet
                    embed.color = discord.Color.green()
                    embed.set_footer(text=f"You win! 🎉\nYour Balance: {fmt(balance + winnings)} (+{fmt(profit)}) coins")
                    record_blackjack_stats(user_id, bet, "win", profit)

                elif user_total < dealer_total:  # **Dealer Wins**
                    embed.color = discord.Color.red()
                    embed.set_footer(text=f"Dealer wins. Better luck next time! 😜\nYour Balance: {fmt(balance - bet)} (-{fmt(bet)}) coins")
                    record_blackjack_stats(user_id, bet, "loss", -bet)

                else:  # **Tie**
                    winnings = bet
                    profit = 0
                    embed.color = discord.Color.blue()
                    embed.set_footer(text=f"It's a tie! 🤝\nYour Balance: {fmt(balance)} (Refunded)")
                    record_blackjack_stats(user_id, bet, "tie", profit)

                update_balance(user_id, winnings)
                embed.add_field(name="Your Balance 💳", value=f"**{fmt(balance + winnings)}**", inline=False)
                await message.edit(embed=embed)
                await message.clear_reactions()
                break

            await message.remove_reaction(reaction.emoji, interaction.user)

        except asyncio.TimeoutError:
            update_balance(user_id, bet)
            embed.color = discord.Color.red()
            embed.set_footer(text=f"Game timed out! ⏳ Your bet of {fmt(bet)} coins has been refunded.")
            await message.edit(embed=embed)
            await message.clear_reactions()
            break


@bot.tree.command(name="blackjackstats", description="View your blackjack statistics 📊")
async def blackjackstats(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    stats = blackjack_stats.get(user_id, {'wins': 0, 'losses': 0, 'ties': 0, 'money_won': 0, 'money_lost': 0, 'history': []})

    total_games = stats['wins'] + stats['losses'] + stats['ties']
    win_rate = round((stats['wins'] / total_games * 100), 2) if total_games > 0 else 0
    history = " ".join(stats['history']) if stats['history'] else "No games played"

    # Calculate profit
    profit = stats['money_won'] - stats['money_lost']

    embed = discord.Embed(title=f"📊 Blackjack Stats - {interaction.user.name}", color=discord.Color.blue())
    embed.add_field(name="🏆 Wins", value=f"{stats['wins']}", inline=True)
    embed.add_field(name="❌ Losses", value=f"{stats['losses']}", inline=True)
    embed.add_field(name="🤝 Ties", value=f"{stats['ties']}", inline=True)
    embed.add_field(name="💰 Money Won", value=f"{stats['money_won']:,} coins", inline=True)
    embed.add_field(name="💸 Money Lost", value=f"{stats['money_lost']:,} coins", inline=True)
    embed.add_field(name="📈 Win Rate", value=f"{win_rate}%", inline=True)
    embed.add_field(name="💵 Profit", value=f"{profit:,} coins", inline=True)
    embed.add_field(name="📜 Last 5 Games", value=history, inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="dnd", description="Get the D&D📜 document.")
async def dnd_command(interaction: discord.Interaction):
    disclaimer_text = """
**Disclaimer:**
This entire document is a collaborative effort by @The Fool, @กุ๊งกุ๊งกุ๊งกิ๊ง, GPT, and Quillbot (in some parts).
While there may be some flaws and errors, we can guarantee that this wall of text wasn't entirely generated by GPT.
It was primarily typed by the two people mentioned above, and then we used GPT to help fix any mistakes that resulted from our stream-of-consciousness writing.  

Feel free to use this for your next DnD session. We'll make sure to update everything to a more playable state as we go along.

📜 **Document Link:** [Click here](https://docs.google.com/document/d/1xqEmd_6WSMi-ACSHqSVGAskitR7MgCGPZbOT5C5t6K8/edit?usp=sharing)
    """

    await interaction.response.send_message(disclaimer_text, ephemeral=True)


# Function to load last claim times
def load_lastclaim():
    try:
        with open(LASTCLAIM_FILE, "r") as f:
            return json.load(f)  # Load as a dictionary
    except (FileNotFoundError, json.JSONDecodeError):
        return {}  # Return empty dictionary if file not found or invalid


# Function to save last claim times
def save_lastclaim(data):
    with open(LASTCLAIM_FILE, "w") as f:
        json.dump(data, f, indent=4)  # Save as JSON file


@bot.tree.command(name="daily", description="Claim your daily Dailes! ✨")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = time.time()

    coins, dailes = get_balance(user_id)  # Get current balance
    last_claim_data = load_lastclaim()  # Load last claim times
    last_claim = last_claim_data.get(user_id, 0)  # Get user's last claim time

    if now - last_claim < 86400:  # 24-hour cooldown
        remaining = 86400 - (now - last_claim)
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await interaction.response.send_message(
            f"❌ You have already claimed your daily reward! Try again in **{hours}h {minutes}m**.",
            ephemeral=True
        )
        return

    # Rewards
    daily_dailes = 1
    daily_coins = 1000
    update_balance(user_id, dailes=daily_dailes, coins=daily_coins)   # Update balance

    # Save new claim time
    last_claim_data[user_id] = now  # Store new timestamp
    save_lastclaim(last_claim_data)  # Save updated data

    # Re-fetch updated balance
    new_coins, new_dailes = get_balance(user_id)

    await interaction.response.send_message(
        f"🎁 **You received:**\n- 🪙 {daily_coins} Coins\n- 🎟️ {daily_dailes} Dailies\n\n"
        f"💰 **New balance:**\n- 🪙 Coins: {new_coins:,}\n- 🎟️ Dailies: {new_dailes:,}",
        ephemeral=False
    )


@bot.tree.command(name="balance", description="Check your current balance.💰")
async def balance(interaction: discord.Interaction):
    user_id = interaction.user.id
    coins, dailes = get_balance(user_id)

    await interaction.response.send_message(
        f"🪙 **Coins:** {fmt(coins)}\n🎟️ **Dailes:** {fmt(dailes)}",
        ephemeral=False
    )


@bot.tree.command(name="leaderboard", description="View the top 10 richest users.🤑")
async def leaderboard(interaction: discord.Interaction):
    wallets = load_wallets()
    top_10 = sorted(wallets.items(), key=lambda x: x[1]["coins"], reverse=True)[:10]

    embed = discord.Embed(title="💰 Leaderboard", color=discord.Color.gold())
    for i, (user_id, data) in enumerate(top_10, start=1):
        user = bot.get_user(int(user_id))
        if user:
            embed.add_field(name=f"{i}. {user.name}", value=f"🪙 `{fmt(data['coins'])}`", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=False)


@bot.tree.command(name="achievement", description="Claim your achievements! 🏆")
async def achievement(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # Defer the response to prevent expiration
    followup = interaction.followup  # Use followup for the final response
    guild = interaction.guild
    user = interaction.user
    user_id = str(user.id)

    # Load user stats and balance
    stats = blackjack_stats.get(user_id, {'wins': 0, 'losses': 0, 'ties': 0})
    wallets = load_wallets()
    balance = wallets.get(user_id, {"coins": 0})["coins"]

    total_games = stats['wins'] + stats['losses'] + stats['ties']

    # Achievement conditions
    game_roles = {
        "Gambler": (25, "Play 25 blackjack games."),
        "High Roller": (100, "Play 100 blackjack games."),
    }
    money_roles = {
        "Greenhorn": (250_000, "Earn 250,000 coins."),
        "Millionaire": (1_000_000, "Earn 1,000,000 coins."),
        "Billionaire": (1_000_000_000, "Earn 1,000,000,000 coins."),
        "Trillionaire": (1_000_000_000_000, "Earn 1,000,000,000,000 coins."),
    }
    top_roles = ["Top 1", "Top 2", "Top 3"]

    # Ensure all achievement roles exist
    async def get_or_create_role(role_name, color=discord.Color.gold()):
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            role = await guild.create_role(name=role_name, color=color)
        return role

    earned_achievements = []
    missing_achievements = []

    # Check game-based achievements
    for role_name, (games_required, condition) in game_roles.items():
        role = await get_or_create_role(role_name)
        if total_games >= games_required:
            earned_achievements.append(f"✅ **{role_name}** - {condition}")
            if role not in user.roles:
                await user.add_roles(role)
        else:
            missing_achievements.append(f"❌ **{role_name}** - {condition} ({total_games}/{games_required})")

    # Check money-based achievements
    for role_name, (balance_required, condition) in money_roles.items():
        role = await get_or_create_role(role_name)
        if balance >= balance_required:
            earned_achievements.append(f"✅ **{role_name}** - {condition}")
            if role not in user.roles:
                await user.add_roles(role)
        else:
            missing_achievements.append(f"❌ **{role_name}** - {condition} ({balance:,}/{balance_required:,})")

    # Assign leaderboard-based roles
    top_users = sorted(wallets.items(), key=lambda x: x[1]["coins"], reverse=True)[:3]
    for i, (top_user_id, _) in enumerate(top_users):
        role = await get_or_create_role(top_roles[i], color=discord.Color.blue())
        top_user = guild.get_member(int(top_user_id))
        if top_user:
            # Remove the role from all other members first
            for member in guild.members:
                if role in member.roles:
                    await member.remove_roles(role)
            # Assign the role to the top user
            if role not in top_user.roles:
                await top_user.add_roles(role)

    # Create response message
    response = "**🏆 Achievements Progress:**\n\n"
    if earned_achievements:
        response += "**✅ Earned Achievements:**\n" + "\n".join(earned_achievements) + "\n\n"
    if missing_achievements:
        response += "**❌ Locked Achievements:**\n" + "\n".join(missing_achievements)
    await followup.send(response, ephemeral=False)


@bot.event
async def on_message(message):
    if message.author.bot:
        return  # Ignore bot messages

    if message.content.startswith("!say"):
        if message.author.id in ALLOWED_USERS:
            say_message = message.content[len("!say "):].strip()

            if say_message:  # Prevent empty messages
                if message.channel.permissions_for(message.guild.me).manage_messages:
                    await message.delete()  # Delete the original message
                await message.channel.send(say_message)  # Bot sends the message
        else:
            await message.channel.send(f"{message.author.mention}, you are not allowed to use this command.", delete_after=5)

    # Ensure other commands still work, but exclude "!say" to prevent CommandNotFound errors
    if not message.content.startswith("!say"):
        await bot.process_commands(message)


# Slash command: /stocks
@bot.tree.command(name="stocks", description="View the current stock prices")
async def stocks_slash(interaction: discord.Interaction):
    stock_prices = load_stock_prices()  # Load stock prices from JSON file

    embed = discord.Embed(
        title="📈 **Stock Market** 📉", 
        description="Here are the current stock prices. Prices change every 3 minute.",
        color=discord.Color.gold()
    )

    for idx, (stock, data) in enumerate(stock_prices.items(), start=1):
        price = data["price"]
        previous_price = data["previous_price"]

        # Calculate the change
        price_change = price - previous_price
        if price_change > 0:
            change_emoji = f"📈 +{price_change} Coins"
        elif price_change < 0:
            change_emoji = f"📉 {abs(price_change)} Coins"
        else:
            change_emoji = "📊 No change"

        embed.add_field(
            name=f"`{idx}`. **{stock}**",
            value=f"🪙 {price} Coins\n{change_emoji}",
            inline=False
        )

    embed.set_footer(text="Use `!stockbuy <ID> <amount>` to buy, `!stocksell <ID> <amount>` to sell stocks, or `!stocks` to view prices.")
    await interaction.response.send_message(embed=embed)

# Text command: !stocks
@bot.command(name="stocks")
async def stocks(ctx):
    stock_prices = load_stock_prices()  # Load stock prices from JSON file

    embed = discord.Embed(
        title="📈 **Stock Market** 📉",
        description="Here are the current stock prices. Prices change every minute.",
        color=discord.Color.gold()
    )

    for idx, (stock, data) in enumerate(stock_prices.items(), start=1):
        price = data["price"]
        previous_price = data["previous_price"]

        # Calculate the change
        price_change = price - previous_price
        if price_change > 0:
            change_emoji = f"📈 +{price_change} Coins"
        elif price_change < 0:
            change_emoji = f"📉 {abs(price_change)} Coins"
        else:
            change_emoji = "📊 No change"

        embed.add_field(
            name=f"`{idx}`. **{stock}**",
            value=f"🪙 {price} Coins\n{change_emoji}",
            inline=False
        )

    embed.set_footer(text="Use `!stockbuy <ID or Name> <amount>` to buy, `!stocksell <ID or Name> <amount>` to sell stocks.")
    await ctx.send(embed=embed)


# Command to buy stocks
@bot.command(name="stockbuy", aliases=["sb"])
async def stockbuy(ctx, stock_id: str, amount: str):
    if not amount.isdigit() or int(amount) <= 0:
        await ctx.send("Invalid amount! Please enter a positive integer.")
        return
    amount = int(amount)

    stock_prices = load_stock_prices()  # Load stock prices from JSON file

    # Map stock IDs to names
    stock_id_map = {str(idx + 1): stock for idx, stock in enumerate(stock_prices.keys())}

    # Check if the stock ID is numeric and map it to the stock name
    if stock_id.isdigit():
        stock_id = stock_id_map.get(stock_id)
        if not stock_id:
            await ctx.send("Invalid stock ID!")
            return

    # Check if the stock exists by name
    if stock_id not in stock_prices:
        await ctx.send("Invalid stock ID!")
        return

    user_portfolio = load_user_portfolio()  # Load user portfolio

    # Check if the user has a portfolio entry
    if str(ctx.author.id) not in user_portfolio:
        user_portfolio[str(ctx.author.id)] = {}

    portfolio = user_portfolio[str(ctx.author.id)]

    # Calculate the total cost of the stock purchase
    stock_price = stock_prices[stock_id]["price"]
    total_cost = stock_price * amount

    # Fetch the user's actual balance using the get_balance function
    user_balance, _ = get_balance(ctx.author.id)  # Fetch coins and dailes

    # Check if the user can afford the stock
    if user_balance < total_cost:
        await ctx.send(f"You do not have enough coins to buy {amount} of {stock_id}.")
        return

    # Deduct the cost and update the user's portfolio
    if stock_id not in portfolio:
        portfolio[stock_id] = 0
    portfolio[stock_id] += amount

    update_balance(ctx.author.id, -total_cost)  # Deduct the cost from the user's balance
    save_user_portfolio(user_portfolio)  # Save the updated portfolio

    # Send confirmation
    await ctx.send(f"You bought {amount} of {stock_id} for {total_cost} coins.")
    print(f"{ctx.author} bought {amount} of {stock_id} for {total_cost} coins.")


# Command to sell stocks
@bot.command(name="stocksell", aliases=["ss"])
async def stocksell(ctx, stock_id: str, amount: str):
    if not amount.isdigit() or int(amount) <= 0:
        await ctx.send("Invalid amount! Please enter a positive integer.")
        return
    amount = int(amount)

    stock_prices = load_stock_prices()  # Load stock prices from JSON file

    # Map stock IDs to names
    stock_id_map = {str(idx + 1): stock for idx, stock in enumerate(stock_prices.keys())}

    # Check if the stock ID is numeric and map it to the stock name
    if stock_id.isdigit():
        stock_id = stock_id_map.get(stock_id)
        if not stock_id:
            await ctx.send("Invalid stock ID!")
            return

    # Check if the stock exists by name
    if stock_id not in stock_prices:
        await ctx.send("Invalid stock ID!")
        return

    user_portfolio = load_user_portfolio()  # Load user portfolio

    # Check if the user has a portfolio entry
    if str(ctx.author.id) not in user_portfolio:
        user_portfolio[str(ctx.author.id)] = {}

    portfolio = user_portfolio[str(ctx.author.id)]

    # Check if the user has enough of the stock
    if stock_id not in portfolio or portfolio[stock_id] < amount:
        await ctx.send(f"You do not have enough {stock_id} to sell.")
        return

    # Calculate the earnings from selling the stock
    stock_price = stock_prices[stock_id]["price"]
    total_earnings = stock_price * amount

    # Deduct the stock from the portfolio
    portfolio[stock_id] -= amount
    if portfolio[stock_id] == 0:
        del portfolio[stock_id]

    update_balance(ctx.author.id, total_earnings)  # Add the earnings to the user's balance
    save_user_portfolio(user_portfolio)  # Save the updated portfolio

    # Send confirmation
    await ctx.send(f"You sold {amount} of {stock_id} for {total_earnings} coins.")
    print(f"{ctx.author} sold {amount} of {stock_id} for {total_earnings} coins.")


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if not cleanup_task.is_running():  # Prevent multiple loops
        cleanup_task.start()
    await bot.tree.sync()
    print("✅ Slash commands synced")
    bot.loop.create_task(update_stock_prices_periodically())
    print("✅ Stock is stonking")
    activity = discord.Activity(type=discord.ActivityType.watching, name="GUILTY GEAR STRIVE: DUAL RULERS")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print("✅ Now Watching GUILTY GEAR STRIVE: DUAL RULERS")

bot.run(TOKEN)

# @bot.tree.command(name="shop", description="Buy items from the shop! 🛒")
# async def shop(interaction: discord.Interaction):
#     embed = discord.Embed(title="🛒 Shop", description="Use `/buy <item>` to purchase an item.", color=discord.Color.blurple())

#     # Coin-based items
#     embed.add_field(name="💰 Coin Shop", value="Spend your coins on cool items!", inline=False)
#     embed.add_field(name="🎟️ Dailies", value="Cost: **1000 Coins**\nEarn 1 Daile daily.", inline=False)
#     embed.add_field(name="🎲 Dice", value="Cost: **500 Coins**\nRoll a dice for a random reward.", inline=False)
#     embed.add_field(name="🎫 Lottery Ticket", value="Cost: **100 Coins**\nEnter the lottery for a chance to win big!", inline=False)

#     # Role Shop (Dailies-based)
#     embed.add_field(name="🛡️ Role Shop", value="Use your **Dailies** to unlock special roles!", inline=False)
#     embed.add_field(name="🟢 Green Role", value="Cost: **3 Dailies**", inline=True)
#     embed.add_field(name="🔵 Blue Role", value="Cost: **5 Dailies**", inline=True)
#     embed.add_field(name="🔴 Red Role", value="Cost: **7 Dailies**", inline=True)

#     # Color Purchases (Coin-based)
#     embed.add_field(name="🎨 Color Shop", value="Use coins to change your name color!", inline=False)
#     embed.add_field(name="🟡 Yellow Name", value="Cost: **1000 Coins**", inline=True)
#     embed.add_field(name="🟣 Purple Name", value="Cost: **2000 Coins**", inline=True)
#     embed.add_field(name="⚫ Black Name", value="Cost: **5000 Coins**", inline=True)

#     await interaction.response.send_message(embed=embed, ephemeral=True)