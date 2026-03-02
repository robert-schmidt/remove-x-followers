import os
import sys
import time
import logging

import requests
import tweepy
from dotenv import load_dotenv

load_dotenv()

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
REMOVALS_LOG = os.path.join(LOG_DIR, "removals.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("follower-remover")

removal_logger = logging.getLogger("removals")
removal_logger.setLevel(logging.INFO)
removal_handler = logging.FileHandler(REMOVALS_LOG)
removal_handler.setFormatter(logging.Formatter("%(message)s"))
removal_logger.addHandler(removal_handler)

POLL_INTERVAL = 60  # seconds between polls (rate limit: 15 req/15 min)

# X web app's public bearer token (same for all users, embedded in x.com's JS)
X_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"


def get_tweepy_client():
    keys = ("API_KEY", "API_KEY_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET")
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        log.error("Missing env vars: %s", ", ".join(missing))
        sys.exit(1)

    return tweepy.Client(
        consumer_key=os.environ["API_KEY"],
        consumer_secret=os.environ["API_KEY_SECRET"],
        access_token=os.environ["ACCESS_TOKEN"],
        access_token_secret=os.environ["ACCESS_TOKEN_SECRET"],
        wait_on_rate_limit=True,
    )


def get_x_session():
    keys = ("X_AUTH_TOKEN", "X_CT0")
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        log.error("Missing env vars: %s", ", ".join(missing))
        sys.exit(1)

    ct0 = os.environ["X_CT0"]
    session = requests.Session()
    session.headers.update({
        "authorization": f"Bearer {X_BEARER}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://x.com/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    })
    session.cookies.update({
        "auth_token": os.environ["X_AUTH_TOKEN"],
        "ct0": ct0,
    })
    return session


def get_all_followers(client, user_id):
    """Fetch all followers, handling pagination."""
    followers = []
    for resp in tweepy.Paginator(
        client.get_users_followers, user_id, max_results=1000, user_auth=True
    ):
        if resp.data:
            followers.extend(resp.data)
    return followers


def block_user(session, target_id, username):
    """Block a user via X's internal API to remove them as a follower."""
    resp = session.post(
        "https://x.com/i/api/1.1/blocks/create.json",
        data={"user_id": str(target_id)},
    )
    resp.raise_for_status()
    log.info("Blocked @%s (%s)", username, target_id)
    removal_logger.info(
        "%s\t@%s\t%s", time.strftime("%Y-%m-%d %H:%M:%S"), username, target_id
    )


def main():
    client = get_tweepy_client()
    session = get_x_session()

    me = client.get_me(user_auth=True)
    if not me.data:
        log.error("Failed to authenticate — check your credentials.")
        sys.exit(1)

    my_id = me.data.id
    log.info("Authenticated as @%s (ID: %s)", me.data.username, my_id)
    log.info("Polling every %ds. Ctrl+C to stop.", POLL_INTERVAL)

    while True:
        try:
            followers = get_all_followers(client, my_id)

            if not followers:
                log.info("No followers — nothing to do.")
            else:
                log.info("Found %d follower(s). Blocking...", len(followers))
                removed = 0
                for f in followers:
                    try:
                        block_user(session, f.id, f.username)
                        removed += 1
                    except requests.HTTPError as e:
                        if e.response is not None and e.response.status_code == 429:
                            log.warning("Rate limited. Will retry next cycle.")
                            break
                        log.error("HTTP error blocking @%s: %s", f.username, e)
                    except Exception as e:
                        log.error("Failed to block @%s: %s", f.username, e)
                log.info("Blocked %d/%d follower(s) this cycle.", removed, len(followers))

        except tweepy.TooManyRequests:
            log.warning("Rate limited on followers fetch. Waiting for next cycle.")
        except tweepy.TwitterServerError as e:
            log.warning("Server error: %s. Retrying next cycle.", e)
        except Exception as e:
            log.error("Unexpected error: %s", e, exc_info=True)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Shutting down.")
