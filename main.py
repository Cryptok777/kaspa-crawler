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
ipinfo_token = os.getenv("IPINFO_TOKEN", 0)

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


@AsyncLRU(maxsize=4096)
async def get_ip_info(ip):
    url = f"https://ipinfo.io/{ip}?token={ipinfo_token}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            res = await response.json()
            return res.get("loc")


@app.get("/")
async def read_root():
    f = open(NODE_OUTPUT_FILE, "r")
    data = json.loads(f.read())
    for ip in data['nodes']:
        data['nodes'][ip]["loc"] = await get_ip_info(extract_ip_address(ip))
    return data


@app.on_event("startup")
def init_data():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_nodes, "interval", hours=1)
    scheduler.start()


def update_nodes() -> None:
    logging.info(f"Starting crawler job")
    hostpair = seed_node.split(":") if ":" in seed_node else (seed_node, "16111")
    asyncio.run(
        main([hostpair], "kaspa-mainnet", NODE_OUTPUT_FILE, ipinfo_token=ipinfo_token)
    )
