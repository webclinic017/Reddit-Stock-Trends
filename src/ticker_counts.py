import configparser
import json
import pandas as pd
import praw
import re
from collections import Counter
from functools import reduce
from operator import add
from typing import Set
import yfinance as yf
from tqdm import tqdm

#JB 02/07/2021 - Configparser introduced to scrape out some hardcode and allow removal of sensitive passwords

WEBSCRAPER_LIMIT = 2_000

config = configparser.ConfigParser()
config.read('config.ini')

CLIENT_ID = config['RedditApi']['ClientId']
CLIENT_SECRET = config['RedditApi']['ClientSecret']
USER_AGENT = config['RedditApi']['UserAgent']
stop_words = json.loads(config['FilteringOptions']['StopWords'])
block_words = json.loads(config['FilteringOptions']['StopWords'])


# Scrape subreddits `r/robinhoodpennystocks` and `r/pennystocks`
# Current it does fetch a lot of additional data like upvotes, comments, awards etc but not using anything apart from title for now
reddit = praw.Reddit(client_id=CLIENT_ID,
                     client_secret=CLIENT_SECRET,
                     user_agent=USER_AGENT)
subreddits = "+".join(json.loads(config['FilteringOptions']['Subreddits']))
new_bets = reddit.subreddit(subreddits).new(limit=WEBSCRAPER_LIMIT)

posts = [[post.id,
          post.title,
          post.score,
          post.num_comments,
          post.upvote_ratio,
          post.total_awards_received] for post in tqdm(new_bets, desc="Selecting relevant data from webscraper", total=WEBSCRAPER_LIMIT)]
posts = pd.DataFrame(posts, columns=["id",
                                     "title",
                                     "score",
                                     "comments",
                                     "upvote_ratio",
                                     "total_awards"])


def extract_ticker(body: str, re_string: str = "[$][A-Za-z]*|[A-Z][A-Z]{1,}") -> Set[str]:
    """Simple Regex to get tickers from text."""
    ticks = set(re.findall(re_string, str(body)))
    res = set()
    for item in ticks:
        if item not in block_words and item.lower() not in stop_words and item:
            try:
                tic = item.replace("$", "").upper()
                res.add(tic)
            except Exception as e:
                print(e)
    return res


# Extract tickers from all titles and create a new column
posts["Tickers"] = posts["title"].apply(extract_ticker)
ticker_sets = posts.Tickers.to_list()

# Count number of occurances of the Ticker and verify id the Ticker exists
counts = reduce(add, map(Counter, ticker_sets))

verified_tics = {}
for ticker, ticker_count in tqdm(counts.items(), desc="Filtering verified ticks"):
    if ticker_count > 3:  # If ticker is found more than 3 times
        try:
            _ = yf.Ticker(ticker).info
            verified_tics[ticker] = ticker_count
        except KeyError:  # Non-existant ticker
            pass

# Create Datable of just mentions
tick_df = pd.DataFrame(verified_tics.items(), columns=["Ticker", "Mentions"])
tick_df.sort_values(by=["Mentions"], inplace=True, ascending=False)
tick_df.reset_index(inplace=True, drop=True)

with open('./data/tick_df.csv', 'w+') as file:  # Use file to refer to the file object
    tick_df.to_csv("./data/tick_df.csv", index=False) # Save to file to load into yahoo analysis script
    print(tick_df.head())
