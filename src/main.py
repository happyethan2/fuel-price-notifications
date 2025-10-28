import pytz
import sys
import requests
import config
import json
import numpy as np
import csv
import os

from statistics import mean
from datetime import datetime
from openai import OpenAI

def main():
    notify_on = ["monday", "thursday", "saturday"]

    # set adelaide tz and dt variables
    local_tz = pytz.timezone('Australia/Adelaide')
    current_time = datetime.now(local_tz)
    current_day = (current_time.strftime("%A")).lower()

    formatted_date = current_time.strftime("%d/%m/%Y")
    formatted_time = current_time.strftime("%I:%M:%S %p")

    # print current time
    print(f"Current time is {current_day} {formatted_date} {formatted_time}")

    client = OpenAI(api_key=config.OPENAI_KEY) # init openai client
    MODEL = "gpt-5"

    def ask_model(system_content, user_content, max_tokens):
        print(f"\n[ask_model] model={MODEL} (Responses API)")
        print(f"[ask_model] prompt (200): {user_content[:200]!r}")

        resp = client.responses.create(
            model=MODEL,
            instructions=system_content,      # system/developer prompt
            input=user_content,               # user prompt
            max_output_tokens=max_tokens,     # GPT-5 uses this, not max_tokens
            reasoning={"effort": "minimal"},  # faster, low effort
            text={"verbosity": "low"},        # concise output
        )

        print(f"[ask_model] resp type: {type(resp)}")
        print(f"[ask_model] resp preview: {str(resp)[:300]}")

        # Preferred: unified text
        out = getattr(resp, "output_text", "") or ""

        # Fallback: aggregate structured output if unified text is empty
        if not out and getattr(resp, "output", None):
            parts = []
            for item in resp.output:
                for c in getattr(item, "content", []):
                    if getattr(c, "type", "") in ("output_text", "message") and hasattr(c, "text"):
                        parts.append(c.text)
            out = "\n".join(parts)

        out = (out or "").strip().lower()
        print(f"[ask_model] reply: {out!r}")
        return out


    def remove_outliers(prices):
        sorted_prices = sorted(prices)
        cleaned_prices = [sorted_prices[0]]

        for i in range(1, len(sorted_prices)):
            if sorted_prices[i] < 5000:
                cleaned_prices.append(sorted_prices[i])

        return cleaned_prices

    def calculate_statistics(prices, percentile):
        min_price = min(prices)
        avg_price = round(mean(prices), 2)
        percentile_price = np.percentile(prices, percentile)
        return min_price, avg_price, percentile_price


    def get_prices_by_id(fuel_id):
        url = "https://fppdirectapi-prod.safuelpricinginformation.com.au/Price/GetSitesPrices?countryId=21&geoRegionLevel=2&geoRegionId=189"
        headers = {
            "Authorization": f"FPDAPI SubscriberToken={config.FDPAPI_KEY}",
            "Content-type": "application/json"
        }
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = json.loads(response.text)
            prices = [site["Price"] for site in data["SitePrices"] if site["FuelId"] == fuel_id]
            if not prices:
                print(f"No prices found for Fuel ID {fuel_id}")
                return []
            return prices
        else:
            print(f"Error: Status Code: {response.status_code}")
            print(f"Response Text: {response.text}")
            return []


    def get_fuel_name(fuel_id):
        fuel_id_name_map = {
            2: "U91",
            3: "Diesel",
            4: "LPG",
            5: "U95",
            6: "ULSD",
            8: "U98",
            11: "LRP",
            12: "E10",
            13: "Premium e5",
            14: "Premium Diesel",
            16: "Bio-Diesel 20",
            19: "e85",
            21: "OPAL",
            22: "Compressed natural gas",
            23: "Liquefied natural gas",
            999: "e10/Unleaded",
            1000: "Diesel/Premium Diesel"
        }
        return fuel_id_name_map.get(fuel_id, "Unknown")

    # fetch 5th percentile price for fuel type
    def get_price(fuel_id):
        prices = get_prices_by_id(fuel_id)
        cleaned_prices = remove_outliers(prices)
        _, _, pctl_price = calculate_statistics(cleaned_prices, 5)
        return pctl_price

    # fuel preferences dict
    USERS_PATH = os.path.join(os.path.dirname(__file__), "users.json")
    with open(USERS_PATH) as f:
        users = json.load(f)

    # send push notification
    def send_push_notification(user_key, message, user_name):
        try:
            url = "https://api.pushover.net/1/messages.json"
            payload = {
                "token": config.PUSHOVER_TOKEN,
                "user": user_key,
                "message": message,
                "title": "Fuel Price Alert"
            }
            response = requests.post(url, data=payload)
            if response.status_code != 200:
                print(f"Error sending notification to {user_name}: {response.text}")
        except Exception as e:
            print(f"Error sending notification to {user_name}: {e}")


    def get_record(index=0):
        rows = read_csv()
        rows = sorted(rows, key=lambda x: int(x["id"]), reverse=True)
        if len(rows) < 2:
            return None
        return rows[index] if index < len(rows) else None

    CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "pricedata.csv")

    def read_csv():
        with open(CSV_PATH, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        return rows

    def write_csv(rows):
        with open(CSV_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "date", "u91", "u95", "u98", "diesel"])
            writer.writeheader()
            writer.writerows(rows)

    def insert_data():
        rows = read_csv()
        if not rows:
            next_id = 0
        else:
            next_id = max(int(r["id"]) for r in rows) + 1

        current_date = datetime.now().strftime("%d/%m/%Y")
        existing_dates = {r["date"] for r in rows}

        if current_date in existing_dates:
            print(f"Skipped upload: an entry for {current_date} already exists.")
            return

        u91_price = get_price(2)
        u95_price = get_price(5)
        u98_price = get_price(8)
        diesel_price = get_price(3)

        new_row = {
            "id": str(next_id),
            "date": current_date,
            "u91": str(u91_price),
            "u95": str(u95_price),
            "u98": str(u98_price),
            "diesel": str(diesel_price)
        }

        rows.append(new_row)
        write_csv(rows)
        print(f"Added record for {current_date} with ID {next_id}.")


    insert_data() # insert today's prices into table

    if current_day not in notify_on:
        print("Unsuitable day of the week, terminating program...")
        sys.exit()

    # daily pct change calculator
    def calc_pct_chng(rec0, rec1):
        pct_changes = {} # dict to store pct changes
        
        if rec0 is None:
            print("ERROR: Database contains < 2 rows")
        else:
            # calculate and store pct changes for each fuel type
            for fuel_type in ["u91", "u95", "u98", "diesel"]:
                try:
                    old_price = float(rec1[fuel_type])
                    new_price = float(rec0[fuel_type])
                    percent_change = ((new_price/old_price) - 1) * 100
                    pct_changes[fuel_type] = percent_change
                except KeyError:
                    print(f"WARNING: data for {fuel_type} not found in DB in pct-change calculation")

        return pct_changes


    def build_prompt(prices):
        """prices = list of floats oldest → newest (len≈90)."""

        # helper indexes
        today_idx = len(prices) - 1
        peak_idx  = int(np.argmax(prices))
        trough_idx= int(np.argmin(prices))

        def days_ago(idx):
            return today_idx - idx

        peak   = prices[peak_idx]
        trough = prices[trough_idx]

        # linear slopes (cents/L per day)
        def slope(days):
            y = prices[-days:]
            x = np.arange(days)
            m, _ = np.polyfit(x, y, 1)   # m = slope
            return round(m, 3)

        slope2  = slope(2)
        slope7  = slope(7)
        slope14 = slope(14)
        slope28 = slope(28)

        # comma-string of all prices for full fidelity
        series_txt = ", ".join(f"{p:.1f}" for p in prices)

        prompt = (
            "You are a fuel-price analyst who delivers super succinct push notifications with the daily pct-change.\n"
            "Daily 5th percentile U98 prices for Adelaide: "
            f"(cents/L), oldest-to-newest:\n\n{series_txt}\n\n"
            f"Last trough: {trough:.1f} ¢ ({days_ago(trough_idx)} days ago)\n"
            f"Last peak: {peak:.1f} ¢ ({days_ago(peak_idx)} days ago)\n"
            f"Slope 2-day: {slope2:+.3f} ¢/day\n"
            f"Slope 7-day: {slope7:+.3f} ¢/day\n" 
            f"Slope 14-day: {slope14:+.3f} ¢/day\n"
            f"Slope 28-day: {slope28:+.3f} ¢/day\n\n"
            "In less than 12 words, predict how Adelaide's cyclical trend is likely to move over the following week."
        )
        return prompt


    def get_advice(prompt):
        response = ask_model(
            system_content="You are an AI language model who creates concise fuel buying advice push notifications.",
            user_content=prompt,
            max_tokens=40
        )
        message = response.strip()
        print(f"AI Message: {message!r}")
        return message


    def get_records(limit=7):
        rows = read_csv()
        # sort by date descending (newest first)
        rows = sorted(rows, key=lambda x: datetime.strptime(x["date"], "%d/%m/%Y"), reverse=True)
        return rows[:limit]


    ### sending notifications loop

    last_quarter = get_records(90) # retrieve the last ~3mos of data
    records = list(reversed(last_quarter)) # last_quater returns newest date first (so reverse)
    u98_prices = [float(r["u98"]) / 10 for r in records] # 1779 -> 177.9

    prompt = build_prompt(u98_prices) # build prompt
    advice = get_advice(prompt)

    print(f"\n{prompt}\n")
    print(advice)

    # fetch two latest records
    last_record = get_record()
    second_last_record = get_record(1)

    pct_changes = calc_pct_chng(last_record, second_last_record)
    print(f"Percentage Changes: {pct_changes}")

    for user in users:
        percentile = 5
        prices = get_prices_by_id(user["preferred_fuel_id"])
        cleaned_prices = remove_outliers(prices)
        min_price, avg_price, pctl_price = calculate_statistics(cleaned_prices, percentile)

        fuel_name = get_fuel_name(user["preferred_fuel_id"])
        print(f"Fuel name for user {user['name']}: {fuel_name}")  # Debugging print statement

        if user["preferred_fuel_id"] == 3:
            price_to_use = avg_price # diesel
        else:
            price_to_use = pctl_price # not diesel

        price_to_use_moved = price_to_use / 10  # Move decimal three places to the left
        pct_chng = round(pct_changes.get(fuel_name.lower(), 'N/A'), 2)

        if pct_chng > 0:
            pct_chng = str("+" + str(pct_chng))
            notification_msg = f"{fuel_name} @{price_to_use_moved:.1f} ({pct_chng}%) {advice.lower()}"
        else:
            pct_chng = str(pct_chng)
            notification_msg = f"{fuel_name} @{price_to_use_moved:.1f} ({pct_chng}%) {advice.lower()}"


        print(f"User: {user['name']}, Notification Message: {notification_msg}")
        send_push_notification(user["user_key"], notification_msg, user['name']) # sending notification

        return {"statusCode": 200, "body": "done"}


if __name__ == "__main__":
    main()
