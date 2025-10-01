import asyncio
import json
import os
import logging
import aiohttp
import re
from fastapi import FastAPI
from kaspa_crawler import main
from geolocation_db import GeolocationDB
from nodes_db import NodesDB

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


# Read multiple seed nodes from environment variables
def get_seed_nodes():
    seed_nodes = []

    # Read primary SEED_NODE
    primary_seed = os.getenv("SEED_NODE")
    if primary_seed:
        seed_nodes.append(primary_seed)

    # Read additional SEED_NODE_N
    i = 1
    while True:
        seed = os.getenv(f"SEED_NODE_{i}")
        if not seed:
            break
        seed_nodes.append(seed)
        i += 1

    return (
        seed_nodes if seed_nodes else ["kaspadns.kaspacalc.net:16111"]
    )  # Default fallback


seed_nodes = get_seed_nodes()
verbose = os.getenv("VERBOSE", 0)
ip_geolocation_token = os.getenv("IP_GEOLOCATION_TOKEN", 0)

logging.basicConfig(
    level=[logging.WARN, logging.INFO, logging.DEBUG][min(int(verbose), 2)]
)


NODE_OUTPUT_FILE = "data/nodes.db"


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


async def get_ip_info_with_session(session, ip):
    """
    Return string: "48.8000,12.3167"
    """
    if not ip:
        return None

    ip = ip.replace("ipv6:[::ffff:", "")
    url = f"https://api.findip.net/{ip}/?token={ip_geolocation_token}"
    async with session.get(url) as response:
        res = await response.text()
        res = json.loads(res)
        lat = res.get("location", {}).get("latitude")
        lon = res.get("location", {}).get("longitude")
        if lat and lon:
            print("found ip info", ip, f"{lat},{lon}")
            return f"{lat},{lon}"
        else:
            return None


@app.get("/")
async def read_root():
    # Read nodes from database, filtering out nodes older than 7 days
    with NodesDB(NODE_OUTPUT_FILE) as nodes_db:
        nodes = nodes_db.get_all_nodes(max_age_days=7)
        # Get the latest update timestamp
        updated_at = nodes_db.get_latest_update_time()

    # Build response in the same format as before
    with GeolocationDB() as geolocation_db:
        async with aiohttp.ClientSession() as session:
            for ip in nodes:
                if geolocation_db.get(ip):
                    nodes[ip]["loc"] = geolocation_db.get(ip)
                    continue
                try:
                    loc = await get_ip_info_with_session(session, extract_ip_address(ip))
                    if loc:
                        nodes[ip]["loc"] = loc
                        geolocation_db.set(ip, loc)
                except Exception as e:
                    logging.warning(f"Error processing IP {ip}: {str(e)}")

    # Return in the same format as the original JSON
    return {"nodes": nodes, "updated_at": updated_at}


@app.on_event("startup")
def init_data():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_nodes, "interval", minutes=30)
    scheduler.start()


async def update_nodes_async() -> None:
    logging.info(f"Starting crawler job with {len(seed_nodes)} seed nodes")

    # Convert all seed nodes to hostpair tuples
    hostpairs = []
    for seed in seed_nodes:
        if ":" in seed:
            host, port = seed.split(":", 1)
            hostpairs.append((host, port))
        else:
            hostpairs.append((seed, "16111"))

    logging.info(f"Seed nodes: {', '.join(seed_nodes)}")
    await main(hostpairs, "kaspa-mainnet", NODE_OUTPUT_FILE)


def update_nodes() -> None:
    max_runtime = 15 * 60  # 15 minutes
    try:
        asyncio.run(asyncio.wait_for(update_nodes_async(), timeout=max_runtime))
    except TimeoutError:
        logging.warning(f"Job exceeded max runtime of {max_runtime} seconds")
