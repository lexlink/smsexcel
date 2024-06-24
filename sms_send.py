from database import get_database
import aiohttp
import asyncio
import requests
import re
import json


collection = get_database()

# Global Variables
api_key = "************"
smsno = "************"
urgent = "************"
url_send = "https://sender.ge/api/send.php"
url_callback = "https://sender.ge/api/callback.php"


headers = {"Content-Type": "application/xml"}


async def send_sms_sender(number: str, text: str, max_retries: int = 3):
    is_empty = True
    message_id = None
    retry_count = 0

    try:
        while is_empty and retry_count < max_retries:
            querystring = {
                "apikey": api_key,
                "destination": number,
                "content": text,
                "smsno": smsno,
                "urgent": urgent
            }
            response = requests.get(url_send, headers=headers, params=querystring)
            new_data = response.json()

            if response.status_code == 200:
                message_id = new_data['data'][0]['messageId']
                if message_id:
                    is_empty = False

                if message_id == '':
                    retry_count += 1
                    print(f"This is retry number {retry_count}")
                    await asyncio.sleep(1)  # Sleep for 1 second before the next retry
            else:
                # Handle the case when the response is not 200
                print(f"API request failed with status code {response.status_code}")

    except requests.exceptions.RequestException as e:
        # Handle exceptions when the URL is completely down
        print(f"API request failed with error: {e}")
        is_empty = True

    record = {
        "message_id": message_id or '',
        "sent_to": number,
        "sent_text": text,
        "delivered": not is_empty
    }
    collection.insert_one(record)
    return {"Text": text, "Number": number, "Delivered": not is_empty}


async def check_delivery_reports():
    empty_message_records = collection.find({"message_id": ''})
    for record in empty_message_records:
        sent_to = record['sent_to']
        sent_text = record['sent_text']

        querystring = {
            "apikey": api_key,
            "destination": sent_to,
            "content": sent_text,
            "smsno": smsno,
            "urgent": urgent
        }

        response = requests.get(url_send, params=querystring)
        new_data = response.json()
        message_id = new_data['data'][0]['messageId']

        if message_id:
            collection.update_one({"_id": record['_id']}, {"$set": {"message_id": message_id, "delivered": True}})


async def check_delivery_against_api():
    records = list(collection.find({}))  # Convert cursor to a list
    message_ids_to_update = []

    async def process_record(record):
        message_id = record["message_id"]
        status_id = record.get("status_id")
        timestamp = record.get("timestamp")

        if status_id != '1' or not re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", str(timestamp)):
            message_ids_to_update.append(message_id)
            print(f"Condition met for message_id: {message_id}")

    await asyncio.gather(*[process_record(record) for record in records])

    async with aiohttp.ClientSession() as session:
        async def send_request(message_id):
            params = {
                "apikey": api_key,
                "messageId": message_id
            }
            async with session.get(url_callback, params=params) as response:
                if response.status == 200:
                    response_text = await response.text()
                    try:
                        json_data = json.loads(response_text)
                        status_id = json_data["data"][0]["statusId"]
                        timestamp = json_data["data"][0]["timestamp"]

                        # Update the record in MongoDB with statusId and timestamp
                        collection.update_one(
                            {"message_id": message_id},
                            {"$set": {"status_id": status_id, "timestamp": timestamp}}
                        )
                    except json.JSONDecodeError:
                        # Handle the case when the response is not valid JSON
                        print(f"Invalid JSON response for message ID {message_id}")
                else:
                    # Handle the case when the API request fails
                    print(f"API request failed for message ID {message_id} with status code {response.status}")

        await asyncio.gather(*[send_request(message_id) for message_id in message_ids_to_update])
