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

# X web app's public bearer token (same for all users, embedded in x.com's JS)
X_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

REMOVE_FOLLOWER_QID = "QpNfg0kpPRfjROQ_9eOLXA"
REMOVE_FOLLOWER_URL = f"https://x.com/i/api/graphql/{REMOVE_FOLLOWER_QID}/RemoveFollower"

FOLLOWERS_QID = "W16HbbxU_8PjA_nE2JCr9g"
FOLLOWERS_URL = f"https://x.com/i/api/graphql/{FOLLOWERS_QID}/Followers"

VIEWER_QID = "zWQLM9HIVahRSUvzUH4lDw"
VIEWER_URL = f"https://x.com/i/api/graphql/{VIEWER_QID}/Viewer"

VIEWER_FEATURES = {
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
}

FOLLOWERS_FEATURES = {
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": False,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_twitter_article_notes_tab_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "tweet_with_visibility_results_prefer_gql_media_interstitial_enabled": False,
}


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
    resp = session.get(VIEWER_URL, params=params)
    resp.raise_for_status()
    data = resp.json()
    user = data["data"]["viewer"]["user_results"]["result"]
    return int(user["rest_id"]), user["core"]["screen_name"]


def get_all_followers_graphql(session, user_id):
    """Fetch all followers via X's internal GraphQL Followers endpoint."""
    followers = []
    cursor = None

    while True:
        variables = {
            "userId": str(user_id),
            "count": 20,
            "includePromotedContent": False,
        }
        if cursor:
            variables["cursor"] = cursor

        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(FOLLOWERS_FEATURES),
        }
        resp = session.get(FOLLOWERS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        instructions = data["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
        entries = []
        for instr in instructions:
            if "entries" in instr:
                entries = instr["entries"]
                break

        next_cursor = None
        for entry in entries:
            eid = entry.get("entryId", "")
            if eid.startswith("user-"):
                try:
                    user = entry["content"]["itemContent"]["user_results"]["result"]
                    followers.append({
                        "id": int(user["rest_id"]),
                        "username": user["legacy"]["screen_name"],
                    })
                except (KeyError, TypeError):
                    continue
            elif eid.startswith("cursor-bottom-"):
                next_cursor = entry["content"]["value"]

        if not next_cursor:
            break
        cursor = next_cursor

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
    )
    resp.raise_for_status()
    log.info("Removed @%s (%s)", username, target_id)
    removal_logger.info(
        "%s\t@%s\t%s", time.strftime("%Y-%m-%d %H:%M:%S"), username, target_id
    )


def main():
    session = get_x_session()

    my_id, screen_name = get_my_user_id(session)
    log.info("Authenticated as @%s (ID: %s)", screen_name, my_id)
    log.info("Polling every %ds. Ctrl+C to stop.", POLL_INTERVAL)

    while True:
        try:
            followers = get_all_followers_graphql(session, my_id)

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
            if status == 429:
                log.warning("Rate limited on followers fetch. Waiting for next cycle.")
            elif status == 404 and e.response is not None and not e.response.text.strip():
                log.warning("Empty 404 — likely rate limited. Waiting for next cycle.")
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
