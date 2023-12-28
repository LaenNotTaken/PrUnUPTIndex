import os
import logging
import asyncio
from discord.ext import commands
from discord.errors import HTTPException
import discord
from fio_wrapper import FIO
import json
from collections import defaultdict
import traceback
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("TOKEN")

# Setup logging
logging.basicConfig(
    filename="../bot_errors.log",
    level=logging.ERROR,
    format="%(asctime)s:%(levelname)s:%(message)s",
)

# Initialize bot with intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.typing = True
bot = commands.Bot(command_prefix='!', intents=intents)


data_file = "Default.json"


fio = FIO()
last_known_values = {}
all_company_data = {}

async def scheduled_task():
    while True:
        try:
            # INSERT CHANNEL ID TO POST THE UPDATE
            channel = bot.get_channel(1187286797567406150)
            if channel:
                await pl(channel)
            await asyncio.sleep(3200)
        except Exception as e:
            print(f"An error occurred in scheduled_task: {str(e)}")

# Define the function to select companies from a list
def get_preselected_companies():
    # Returns a list of preselected company codes
    return [
        'KBI', 'BMEX', 'VAE',
        'AB', 'MEH', 'WYN',
        'PPH', 'MNDS', 'TSB',
        'COPI', 'ELD', 'UNIB',
        'LYME', 'M3L', 'DIRT',
        'UN', 'FEED', 'STOK',
        'INGA', 'CZAR', 'GIL',
        'ORT', 'ACS', 'PHX',
        'GAT', 'CGI', 'TRKS',
        'ARCL', 'AHIM', 'ESTO',
        'PROG', 'AMP', 'GGFI'
            ]  # Add your preselected companies here


# Define the function to load company from previous save
def load_company_data():
    try:
        with open(data_file, "r") as json_file:
            company_data_list = [json.loads(line) for line in json_file]
        return company_data_list
    except FileNotFoundError:
        return []


# Define the function to load previous known values for the company
def load_last_known_values(data_file):
    last_known_values = {}
    try:
        with open(data_file, "r") as json_file:
            for line in json_file:
                company_data = json.loads(line)
                company_code = company_data.get("company_code")
                last_fmv = company_data.get("last_fmv", {})
                last_cpv = company_data.get("last_cpv", {})
                last_avg_buys = company_data.get("averages_buys", {})
                last_avg_sells = company_data.get("averages_sells", {})

                # Store the last known values for each company
                last_known_values[company_code] = {
                    "last_fmv": last_fmv,
                    "last_cpv": last_cpv,
                    "last_avg_buys": last_avg_buys,
                    "last_avg_sells": last_avg_sells
                }
    except FileNotFoundError:
        print(f"File {data_file} not found. Starting with empty last known values.")
        traceback.print_exc()
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {data_file}: {e}")
        traceback.print_exc()
    return last_known_values


# Define the function to save previous known values for the company
def save_last_known_values(last_known_values, data_file):
    with open(data_file, "w") as json_file:
        for company_code, values in last_known_values.items():
            json.dump({"company_code": company_code, **values}, json_file)
            json_file.write("\n")

# Define the function to overwrite company data to be used next time.
def save_company_data(data_file, new_company_data):

    # Load existing data
    existing_data = {}
    try:
        with open(data_file, "r") as file:
            for line in file:
                data = json.loads(line)
                existing_data[data["company_code"]] = data
    except FileNotFoundError:
        print(f"File {data_file} not found. Creating new file.")
        traceback.print_exc()

    # Update with new data
    existing_data.update(new_company_data)

    # Write updated data back to file
    with open(data_file, "w") as file:
        for company_code, company_info in existing_data.items():
            json.dump({"company_code": company_code, **company_info}, file)
            file.write("\n")


# Define the function to save company data.
def write_data_to_file(data_file, company_data):
    with open(data_file, "a") as json_file:
        json.dump(company_data, json_file)
        json_file.write("\n")


# Define the function to map currencies to the right exchange
def map_currency(currency_code):
    mapping = {
        "IC1": "ICA",
        "NC1": "NCC",
        "NC2": "NC2",
        "AI1": "AIC",
        "CI1": "CIS",
        "CI2": "CIS",
    }
    return mapping.get(currency_code, currency_code)


# Define the function to Rate the total sum of companies locked liquidity
def categorize_currency(total_sum):
    if total_sum < 500000:
        return "F", 10000
    elif total_sum <= 1500000:
        return "E", 20000
    elif total_sum <= 2500000:
        return "D", 30000
    elif total_sum <= 5000000:
        return "C", 40000
    elif total_sum <= 49999999:
        return "B", 50000
    else:
        return "A", 100000


# Define the function to Process each order for the company
def process_exchange_orders(exchange, currency_mapper):
    commodities_by_currency_buys = {}
    total_buys_by_currency = {}
    commodities_by_currency_sells = {}
    total_sells_by_currency = {}
    count_by_commodity = {}
    unique_currencies = set()

    for order in exchange:
        ticker = order.Ticker
        currency = ticker.split('.')[-1]
        commodity = ticker.split('.')[0]
         # obtain the currency code from the order
        unique_currencies.add(currency)
        currency_abbr = currency_mapper(currency)  # Map currency code to abbreviation

        # Ensure that each currency is initialized with 0 for total buys and sells
        if currency not in total_buys_by_currency:
            total_buys_by_currency[currency] = 0
        if currency not in total_sells_by_currency:
            total_sells_by_currency[currency] = 0

        # Initialize the commodities dictionaries if not already done
        if currency not in commodities_by_currency_buys:
            commodities_by_currency_buys[currency] = {}
        if currency not in commodities_by_currency_sells:
            commodities_by_currency_sells[currency] = {}

        for buy in order.Buys:
            total_buy_cost = buy.Count * buy.Cost
            commodities_by_currency_buys[currency][commodity] = commodities_by_currency_buys[currency].get(commodity, 0) + total_buy_cost
            total_buys_by_currency[currency] += total_buy_cost

        for sell in order.Sells:
            total_sell_cost = sell.Count * sell.Cost
            commodities_by_currency_sells[currency][commodity] = commodities_by_currency_sells[currency].get(commodity, 0) + total_sell_cost
            total_sells_by_currency[currency] += total_sell_cost

        # Update count for each commodity

        total_count = sum(buy.Count for buy in order.Buys) + sum(sell.Count for sell in order.Sells)
        count_by_commodity[commodity] = count_by_commodity.get(commodity, 0) + total_count

    return commodities_by_currency_buys, total_buys_by_currency, commodities_by_currency_sells, total_sells_by_currency, count_by_commodity, unique_currencies


# Define the function to start processing one by one I think...
def process_preselected_companies(preselected_companies, exchange_data, currency_mapper, data_file):

    company_blocks = []
    all_company_data = {}
    last_known_values = load_last_known_values(data_file)  # Assuming a function to load last known values



    for company_code in preselected_companies:

        # Fetch exchange data for the company
        exchange = exchange_data.get_orders(company_code, timeout=None)
        if not exchange:
            print(f"No data found for company code: {company_code}")
            continue

        # Process exchange orders
        commodities_buys, total_buys, commodities_sells, total_sells, count_commodity, unique_currencies = process_exchange_orders(
            exchange, currency_mapper)

        # Calculate averages
        averages_buys = calculate_averages(commodities_buys, total_buys, count_commodity)
        averages_sells = calculate_averages(commodities_sells, total_sells, count_commodity)

        # Calculate changes
        fmv_change, cpv_change = calculate_changes(averages_buys, averages_sells, last_known_values, company_code)

        # Format company message
        company_message = format_company_message(company_code, unique_currencies, averages_buys, averages_sells, fmv_change, cpv_change, currency_mapper)

        # Update all company data and last known values
        fmv_change, cpv_change = calculate_changes(averages_buys, averages_sells, last_known_values, company_code)
        all_company_data[company_code] = {
            "averages_buys": averages_buys,
            "averages_sells": averages_sells,
            "fmv_change": fmv_change,
            "cpv_change": cpv_change
        }
        last_known_values[company_code] = {
            "last_fmv": fmv_change,
            "last_cpv": cpv_change,
            "last_avg_buys": averages_buys,
            "last_avg_sells": averages_sells
        }


        # Append formatted message to company blocks
        company_blocks.append(company_message)


    # Save the updated last known values
    save_last_known_values(last_known_values, data_file)


    return company_blocks, last_known_values


# Define the function to calculate the FMV and CPV Averages
def calculate_averages(commodities_by_currency, total_sum_by_currency, count_by_commodity):

    averages_by_currency = defaultdict(float)  # Initialize with default values as float
    for currency, commodities in commodities_by_currency.items():
        total_commodities = sum(1 for commodity in commodities if commodities[commodity] > 0)
        if total_commodities == 0:
            continue

        total_sum = float(total_sum_by_currency.get(currency, 0))  # Convert to float here
        rank, divisor = categorize_currency(total_sum)
        average_sum = 0

        for commodity, total_cost in commodities.items():
            if total_cost > 0:
                count = count_by_commodity.get(commodity, 0)
                if count == 0:
                    continue

                try:
                    average_cost = (total_sum / count) / divisor
                    average_sum += average_cost
                except (ValueError, TypeError):
                    continue  # Skip if the division fails

        averages_by_currency[currency] = (rank, "{:.2f}".format(average_sum / total_commodities))

    return averages_by_currency


# Define the function to calculate the difference from the current and the last known.
def calculate_changes(averages_buys, averages_sells, last_known_values, company_code):
    fmv_change = {}
    cpv_change = {}

    try:
        company_values = last_known_values.get(company_code, {})
        last_fmv = company_values.get("last_fmv", {}) if isinstance(company_values.get("last_fmv", {}), dict) else {}
        last_cpv = company_values.get("last_cpv", {}) if isinstance(company_values.get("last_cpv", {}), dict) else {}

        for currency, (rank, current_avg) in averages_buys.items():
            current_avg_float = float(current_avg if current_avg is not None else "0.00")
            previous_avg_float = float(last_fmv.get(currency, "0.00") if last_fmv.get(currency) is not None else "0.00")
            fmv_change[currency] = current_avg_float - previous_avg_float  # Direct subtraction

        for currency, (rank, current_avg) in averages_sells.items():
            current_avg_float = float(current_avg if current_avg is not None else "0.00")
            previous_avg_float = float(last_cpv.get(currency, "0.00") if last_cpv.get(currency) is not None else "0.00")
            cpv_change[currency] = current_avg_float - previous_avg_float  # Direct subtraction

        last_known_values[company_code]["last_fmv"] = fmv_change
        last_known_values[company_code]["last_cpv"] = cpv_change

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        traceback.print_exc()
        print(f"Error in calculate_changes for {company_code}: {e}")

    return fmv_change, cpv_change


# Define the function to format lines
def format_line(fmv_or_cpv, rank, avg, currency_abbr, change_value):
    # Define fixed widths for each component
    fmv_cpv_width = 4   # e.g., "FMV"
    rank_width = 3      # e.g., "(A)"
    avg_width = 9       # e.g., "123.45"
    currency_width = 4  # e.g., "ICA"
    change_width = 6   # e.g., "+123.45 (+100.00%)"

    # Calculate the percentage change
    percentage_change = (change_value / avg) * 100 if avg != 0 else 0

    # Create formatted strings with fixed widths
    fmv_cpv_str = fmv_or_cpv.ljust(fmv_cpv_width)
    rank_str = f"({rank})".ljust(rank_width)
    avg_str = f"{avg:.2f}".rjust(avg_width)
    currency_str = currency_abbr.ljust(currency_width)
    change_str = f"{change_value:+.2f} ({percentage_change:+.2f}%)".rjust(change_width)

    # Combine the strings
    final_line = f"{fmv_cpv_str} {rank_str} {avg_str} {currency_str} {change_str}"
    return final_line


# Define the function to format the company data to discord
def format_company_message(company_code, unique_currencies, averages_buys, averages_sells, fmv_change, cpv_change, currency_mapper):
    company_message = [f"Company: {company_code}".ljust(45)]

    for currency in unique_currencies:
        currency_abbr = currency_mapper(currency)

        # Get FMV and CPV averages
        buy_rank, buy_avg = averages_buys.get(currency, ('-', '0.00'))
        sell_rank, sell_avg = averages_sells.get(currency, ('-', '0.00'))

        # Get changes
        fmv_change_value = fmv_change.get(currency, 0)
        cpv_change_value = cpv_change.get(currency, 0)

        # Format lines and add to company message
        sell_line = format_line("- CPV", sell_rank, float(sell_avg), currency_abbr, cpv_change_value)
        buy_line = format_line("+ FMV", buy_rank, float(buy_avg), currency_abbr, fmv_change_value)
        company_message.append(sell_line.ljust(45))
        company_message.append(buy_line.ljust(45))

    return "\n".join(company_message)


# Define the function to Turn Blocky good looky messages
def transpose_blocks(company_blocks, n=3):
    transposed_lines = []
    for i in range(0, len(company_blocks), n):
        blocks = company_blocks[i: i + n]
        block_lines = [block.split("\n") for block in blocks]
        max_lines = max(len(bl) for bl in block_lines)

        for j in range(max_lines):
            line = "   ".join(
                block_lines[k][j] if j < len(block_lines[k]) else "".ljust(37)
                for k in range(len(blocks))
            )
            transposed_lines.append(line)

    return transposed_lines


# Define the function to sendorino
async def send_transposed_messages(ctx, transposed_lines, message_limit):
    current_message = ""
    company_count = 0
    max_companies_per_message = 3

    for line in transposed_lines:
        company_count += line.count("Company:")

        if len(current_message) + len(line) > message_limit or company_count > max_companies_per_message:
            await ctx.send(f"```diff\n{current_message}\n```")
            current_message = line + "\n"
            company_count = line.count("Company:")
        else:
            current_message += line + "\n"

    if current_message:
        await ctx.send(f"```diff\n{current_message}\n```")


# Define the function for activator.
@bot.command()
async def pl(ctx):
    try:
        preselected_companies = get_preselected_companies()
        #SELECT YOUR DATA FILE. INCASES WHERE YOU WANT TO RUN MULTIPLE DIFFERENT INDEXES AT ONCE.
        data_file = "BasicIndex.json"

        # Call the function to process companies
        company_blocks, last_known_values = process_preselected_companies(preselected_companies, fio.Exchange, map_currency, data_file)

        # Transpose and send company blocks as messages
        if company_blocks:
            transposed_lines = transpose_blocks(company_blocks)
            await send_transposed_messages(ctx, transposed_lines, message_limit=2000)
        else:
            await ctx.send("No data available for the selected companies.")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        traceback.print_exc()

@bot.event
async def on_ready():

    try:
        print(f'Logged in as {bot.user.name} ({bot.user.id})')
        bot.loop.create_task(scheduled_task())
    except Exception as e:
        logger.exception("Error occurred in on_ready")
        traceback.print_exc()


# IMPORT OR INSERT YOUR TOKEN HERE
bot.run(TOKEN)