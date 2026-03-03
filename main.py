import json
import os
import sys
import time
import logging

import requests
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

POLL_INTERVAL = 5  # seconds between polls
REQUEST_TIMEOUT = 15  # seconds per HTTP request
AUTH_ERROR_CODES = {401, 403}

# X web app's public bearer token (same for all users, embedded in x.com's JS)
X_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

REMOVE_FOLLOWER_QID = "QpNfg0kpPRfjROQ_9eOLXA"
REMOVE_FOLLOWER_URL = f"https://x.com/i/api/graphql/{REMOVE_FOLLOWER_QID}/RemoveFollower"

VIEWER_QID = "zWQLM9HIVahRSUvzUH4lDw"
VIEWER_URL = f"https://x.com/i/api/graphql/{VIEWER_QID}/Viewer"

VIEWER_FEATURES = {
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
}


def send_alert(subject, body):
    """Send an email alert via Postmark. Fails silently."""
    api_key = os.environ.get("POSTMARK_API_KEY")
    alert_email = os.environ.get("ALERT_EMAIL")
    if not api_key or not alert_email:
        return
    try:
        requests.post(
            "https://api.postmarkapp.com/email",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": api_key,
            },
            json={
                "From": alert_email,
                "To": alert_email,
                "Subject": subject,
                "TextBody": body,
            },
            timeout=10,
        )
        log.info("Alert email sent to %s", alert_email)
    except Exception as e:
        log.warning("Failed to send alert email: %s", e)


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
        "content-type": "application/json",
        "referer": "https://x.com/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    })
    session.cookies.update({
        "auth_token": os.environ["X_AUTH_TOKEN"],
        "ct0": ct0,
    })
    return session


def get_my_user_id(session):
    """Get the authenticated user's ID and screen name via the GraphQL Viewer endpoint."""
    params = {
        "variables": json.dumps({}),
        "features": json.dumps(VIEWER_FEATURES),
    }
    resp = session.get(VIEWER_URL, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    user = data["data"]["viewer"]["user_results"]["result"]
    return int(user["rest_id"]), user["core"]["screen_name"]


def get_all_followers(session, user_id):
    """Fetch all followers via the v1.1 REST API."""
    followers = []
    cursor = -1

    while cursor != 0:
        resp = session.get(
            "https://api.x.com/1.1/followers/list.json",
            params={
                "user_id": str(user_id),
                "count": 200,
                "cursor": str(cursor),
                "skip_status": "true",
                "include_user_entities": "false",
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        for user in data.get("users", []):
            followers.append({
                "id": user["id"],
                "username": user["screen_name"],
            })

        cursor = data.get("next_cursor", 0)

    return followers


def remove_follower(session, target_id, username):
    """Remove a follower via X's internal GraphQL API."""
    resp = session.post(
        REMOVE_FOLLOWER_URL,
        json={
            "queryId": REMOVE_FOLLOWER_QID,
            "variables": {"target_user_id": str(target_id)},
            "features": {},
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    log.info("Removed @%s (%s)", username, target_id)
    removal_logger.info(
        "%s\t@%s\t%s", time.strftime("%Y-%m-%d %H:%M:%S"), username, target_id
    )


def main():
    session = get_x_session()

    try:
        my_id, screen_name = get_my_user_id(session)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status in AUTH_ERROR_CODES:
            log.error("Session cookie expired or invalid (HTTP %s).", status)
            send_alert(
                "X Follower Remover: session cookie expired",
                "The daemon failed to authenticate. Your X session cookies "
                "have expired or been revoked.\n\n"
                "Grab fresh cookies from your browser and update the .env file, "
                "then restart the service:\n\n"
                "  sudo systemctl restart x-follower-remover",
            )
        raise

    log.info("Authenticated as @%s (ID: %s)", screen_name, my_id)
    log.info("Polling every %ds. Ctrl+C to stop.", POLL_INTERVAL)
    alerted = False

    while True:
        try:
            followers = get_all_followers(session, my_id)

            if not followers:
                log.info("No followers — nothing to do.")
            else:
                log.info("Found %d follower(s). Removing...", len(followers))
                removed = 0
                for f in followers:
                    try:
                        remove_follower(session, f["id"], f["username"])
                        removed += 1
                    except requests.HTTPError as e:
                        if e.response is not None and e.response.status_code == 429:
                            log.warning("Rate limited. Will retry next cycle.")
                            break
                        log.error("HTTP error removing @%s: %s", f["username"], e)
                    except Exception as e:
                        log.error("Failed to remove @%s: %s", f["username"], e)
                log.info("Removed %d/%d follower(s) this cycle.", removed, len(followers))

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status in AUTH_ERROR_CODES:
                log.error("Session cookie expired (HTTP %s).", status)
                if not alerted:
                    send_alert(
                        "X Follower Remover: session cookie expired",
                        "The daemon can no longer authenticate to X. Your session "
                        "cookies have expired or been revoked.\n\n"
                        "Grab fresh cookies from your browser and update the .env "
                        "file, then restart the service:\n\n"
                        "  sudo systemctl restart x-follower-remover",
                    )
                    alerted = True
            elif status == 429:
                log.warning("Rate limited on followers fetch. Waiting for next cycle.")
            else:
                log.error("HTTP error: %s", e)
        except Exception as e:
            log.error("Unexpected error: %s", e, exc_info=True)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Shutting down.")
