import asyncio
import json
import os
import logging
import aiohttp
import re

from fastapi import FastAPI
from kaspa_crawler import main

from dotenv import load_dotenv
from cache import AsyncLRU

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(override=True)
app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

seed_node = os.getenv("SEED_NODE", False)
verbose = os.getenv("VERBOSE", 0)
ip_geolocation_token = os.getenv("IP_GEOLOCATION_TOKEN", 0)

logging.basicConfig(
    level=[logging.WARN, logging.INFO, logging.DEBUG][min(int(verbose), 2)]
)


NODE_OUTPUT_FILE = "data/nodes.json"


def extract_ip_address(input_string):
    pattern = r"(?:ipv6:\[([:0-9a-fA-F]+)\]|(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}))"
    match = re.search(pattern, input_string)

    if match:
        ipv6_address = match.group(1)
        ipv4_address = match.group(2)

        if ipv6_address:
            return ipv6_address
        elif ipv4_address:
            return ipv4_address
        else:
            return None
    else:
        return None


@AsyncLRU(maxsize=8192)
async def get_ip_info(ip):
    """
    Return string: "48.8000,12.3167"
    """
    url = f"https://api.findip.net/{ip}/?token={ip_geolocation_token}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            res = await response.text()
            res = json.loads(res)
            lat = res.get("location", {}).get("latitude")
            lon = res.get("location", {}).get("longitude")
            if lat and lon:
                return f"{lat},{lon}"
            else:
                return None


@app.get("/")
async def read_root():
    f = open(NODE_OUTPUT_FILE, "r")
    data = json.loads(f.read())
    for ip in data["nodes"]:
        try:
            data["nodes"][ip]["loc"] = await get_ip_info(extract_ip_address(ip))
        except Exception as e:
            logging.warning(f"Error processing IP {ip}: {str(e)}")
    return data


@app.on_event("startup")
def init_data():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_nodes, "interval", minutes=60)
    scheduler.start()


async def update_nodes_async() -> None:
    logging.info(f"Starting crawler job")
    hostpair = seed_node.split(":") if ":" in seed_node else (seed_node, "16111")
    await main([hostpair], "kaspa-mainnet", NODE_OUTPUT_FILE)


def update_nodes() -> None:
    max_runtime = 15 * 60  # 15 minutes
    try:
        asyncio.run(asyncio.wait_for(update_nodes_async(), timeout=max_runtime))
    except TimeoutError:
        logging.warning(f"Job exceeded max runtime of {max_runtime} seconds")
