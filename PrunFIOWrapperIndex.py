import logging
import asyncio
from discord.ext import commands
from discord.errors import HTTPException
import discord
from fio_wrapper import FIO
# Setup logging
logging.basicConfig(filename='../bot_errors.log', level=logging.ERROR, format='%(asctime)s:%(levelname)s:%(message)s')

# Initialize bot with intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.typing = True
bot = commands.Bot(command_prefix='!', intents=intents)

# async def scheduled_task():
    #while True:
        #try:
            ##Change the Channel ID for channel you want the bot to loop.
            #channel = bot.get_channel(ChannelID)
            #if channel:
                #await puptc(channel)
            #await asyncio.sleep(600)
        #except Exception as e:
            #print(f"An error occurred in scheduled_task: {str(e)}")

@bot.command()
async def poptc(ctx):
    try:
        #
        preselected_companies = ['VAE', 'BMEX', 'KBI', 'TSB', 'AB', 'WYN', 'UNIB', 'MNDS', 'PPH', 'ELD', 'COPI', 'ARCL', 'M3L', 'DIRT', 'HOT', 'LYME', 'BRFU']
        fio = FIO()
        company_blocks = []
        max_width = 0
        current_message = ""
        company_count = 0
        message_limit = 2000

        def map_currency(currency_code):
            mapping = {'IC1': 'ICA', 'NC1': 'NCC', 'NC2': 'NCC', 'AI1': 'AIC', 'CI1': 'CIS', 'CI2': 'CIS'}
            return mapping.get(currency_code, currency_code)

        def categorize_currency(total_sum):
            if total_sum < 500000:
                return 'F', 10000
            elif total_sum <= 1500000:
                return 'E', 20000
            elif total_sum <= 2500000:
                return 'D', 30000
            elif total_sum <= 5000000:
                return 'C', 40000
            elif total_sum <= 49999999:
                return 'B', 50000
            else:
                return 'A', 100000

        def calculate_averages(commodities_by_currency, total_sum_by_currency, count_by_commodity):
            averages_by_currency = {}
            for currency, commodities in commodities_by_currency.items():
                total_commodities = sum(1 for commodity in commodities if commodities[commodity] > 0)
                if total_commodities == 0:
                    continue

                total_sum = total_sum_by_currency.get(currency, 0)
                rank, divisor = categorize_currency(total_sum)
                average_sum = 0

                for commodity, total_cost in commodities.items():
                    if total_cost > 0:
                        count = count_by_commodity.get(commodity, 0)
                        if count == 0:
                            continue

                        average_cost = (total_sum / count) / divisor
                        average_sum += average_cost

                averages_by_currency[currency] = (rank, "{:.2f}".format(average_sum / total_commodities))
            return averages_by_currency

        def format_line(fmv_or_cpv, rank, avg, currency_abbr):
            sign = "+"
            if fmv_or_cpv == "CPV":
                sign = "-"
            formatted_avg = "{:.2f}".format(float(avg)) if avg != '-' else '-'
            return f"{sign}   {fmv_or_cpv} (Rating: {rank}) {formatted_avg:>10} {currency_abbr}"

        def transpose_blocks(company_blocks, n=3):
            transposed_lines = []
            for i in range(0, len(company_blocks), n):
                blocks = company_blocks[i:i + n]
                block_lines = [block.split('\n') for block in blocks]
                max_lines = max(len(bl) for bl in block_lines)

                for j in range(max_lines):
                    line = "   ".join(
                        block_lines[k][j] if j < len(block_lines[k]) else "".ljust(37) for k in range(len(blocks)))
                    transposed_lines.append(line)

            return transposed_lines

        for company_code in preselected_companies:
            exchange = fio.Exchange.get_orders(company_code, timeout=None)
            if not exchange:
                continue

            commodities_by_currency_buys = {}
            total_buys_by_currency = {}
            commodities_by_currency_sells = {}
            total_sells_by_currency = {}
            count_by_commodity = {}

            for order in exchange:
                ticker = order.Ticker
                currency = ticker.split('.')[-1]
                commodity = ticker.split('.')[0]

                if currency not in commodities_by_currency_buys:
                    commodities_by_currency_buys[currency] = {}
                    total_buys_by_currency[currency] = 0
                if currency not in commodities_by_currency_sells:
                    commodities_by_currency_sells[currency] = {}
                    total_sells_by_currency[currency] = 0

                for buy in order.Buys:
                    total_buy_cost = buy.Count * buy.Cost
                    commodities_by_currency_buys[currency][commodity] = commodities_by_currency_buys[currency].get(commodity, 0) + total_buy_cost
                    total_buys_by_currency[currency] += total_buy_cost

                for sell in order.Sells:
                    total_sell_cost = sell.Count * sell.Cost
                    commodities_by_currency_sells[currency][commodity] = commodities_by_currency_sells[currency].get(commodity, 0) + total_sell_cost
                    total_sells_by_currency[currency] += total_sell_cost

                count_by_commodity[commodity] = count_by_commodity.get(commodity, 0) + sum(buy.Count for buy in order.Buys) + sum(sell.Count for sell in order.Sells)
            # Get averages for each commodity currency pair
            averages_buys = calculate_averages(commodities_by_currency_buys, total_buys_by_currency, count_by_commodity)
            averages_sells = calculate_averages(commodities_by_currency_sells, total_sells_by_currency, count_by_commodity)

            company_message = [f"Company: {company_code}".ljust(37)]
            for currency in set(averages_buys.keys()).union(averages_sells.keys()):
                buy_rank, buy_avg = averages_buys.get(currency, ('-', '0.00'))
                sell_rank, sell_avg = averages_sells.get(currency, ('-', '0.00'))
                currency_abbr = map_currency(currency)

                buy_line = format_line("FMV", buy_rank, buy_avg, currency_abbr).ljust(37)
                sell_line = format_line("CPV", sell_rank, sell_avg, currency_abbr).ljust(37)
                company_message.extend([buy_line, sell_line])

            company_blocks.append("\n".join(company_message))
            # Adjusting the blocks to match max_width

        # Check if there are adjusted blocks to send
            # Transpose and send the blocks with diff formatting
        if company_blocks:
            transposed_lines = transpose_blocks(company_blocks)
            current_message = ""
            company_count = 0  # Initialize a counter for the number of "Company:" occurrences

            for line in transposed_lines:
                # Count the occurrences of "Company:" in the line
                company_count += line.count("Company:")

                # Check if adding this line exceeds the character limit or doesn't have three "Company:" occurrences
                if len(current_message) + len(line) <= message_limit and company_count <= 3:
                    current_message += line + "\n"
                else:
                    # Send the current message
                    await ctx.send(f"```diff\n{current_message}\n```")  # Send with diff formatting
                    current_message = line + "\n"
                    company_count = 1  # Reset the counter because a new message is started

            # Send any remaining message
            if current_message:
                await ctx.send(f"```diff\n{current_message}\n```")

        else:
            await ctx.send("No data available for the selected companies.")

    except Exception as e:
         await ctx.send(f"An error occurred: {str(e)}")

@bot.event
async def on_ready():

    try:
        #bot.loop.create_task(scheduled_task())
        print(f'Logged in as {bot.user.name} ({bot.user.id})')

    except Exception as e:
        logger.exception("Error occurred in on_ready")



bot.run(TOKEN)