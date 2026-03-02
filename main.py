import os
import sys
import time
import logging

import tweepy
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("follower-remover")

POLL_INTERVAL = 60  # seconds between polls (rate limit: 15 req/15 min)


def get_client():
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


def get_all_followers(client, user_id):
    """Fetch all followers, handling pagination."""
    followers = []
    for resp in tweepy.Paginator(
        client.get_users_followers, user_id, max_results=1000, user_auth=True
    ):
        if resp.data:
            followers.extend(resp.data)
    return followers


def remove_follower(client, target_id, username):
    """Block then immediately unblock to remove a follower."""
    client.block(target_user_id=target_id, user_auth=True)
    client.unblock(target_user_id=target_id, user_auth=True)
    log.info("Removed @%s (%s)", username, target_id)


def main():
    client = get_client()

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
                log.info("Found %d follower(s). Removing...", len(followers))
                removed = 0
                for f in followers:
                    try:
                        remove_follower(client, f.id, f.username)
                        removed += 1
                    except tweepy.TooManyRequests:
                        # wait_on_rate_limit should handle this, but just in case
                        log.warning("Rate limited during removal. Will retry next cycle.")
                        break
                    except tweepy.TwitterServerError as e:
                        log.warning("Server error removing @%s: %s", f.username, e)
                    except Exception as e:
                        log.error("Failed to remove @%s: %s", f.username, e)
                log.info("Removed %d/%d follower(s) this cycle.", removed, len(followers))

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
