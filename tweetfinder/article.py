from bs4 import BeautifulSoup
import readability
import re
import requests
import logging
import pycld2 as cld2

from . import mentions

logger = logging.getLogger(__name__)

# when we find a mention, we include this many characters of context before and after it
MENTIONS_CONTEXT_WINDOW_SIZE = 100

# how many seconds to wait when trying to load a webpage via GET
DEFAULT_TIMEOUT = 5


class UnsupportedLanguageException(BaseException):

    def __init__(self, language: str):
        self.language = language
        super().__init__("Finding mentions is only supported in English right now (not {})".format(self.language))


class Article:

    def __init__(self, url: str = None, html: str = None, mentions_list: list = None, timeout: int = None):
        if (url is None) and (html is None):
            raise ValueError('You must pass in either a url or html argument')
        self._url = url
        self._mentions_list = mentions_list or mentions.ALL
        self._download_timeout = timeout or DEFAULT_TIMEOUT
        if html is None:
            self._html = self._download_article()
        else:
            self._html = html
        self._process()

    def _download_article(self):
        url = self._url
        r = requests.get(url, self._download_timeout)
        return r.text.lower()

    def _process(self):
        self._html_soup = BeautifulSoup(self._html, "lxml")
        # remove HTML tags so we can search text-only content for mentions later
        doc = readability.Document(self._html)
        self._content = doc.summary()
        self._content_soup = BeautifulSoup(self._content, "lxml")
        self._content_no_tags = self._content_soup.get_text().strip()
        # lets parse it all here so we don't have to do it more than once
        self._embeds = self._find_embeds()
        self._mentions = self._find_mentions()

    def get_html(self):
        return self._html

    def get_content(self):
        return self._content

    def embeds_tweets(self):
        return len(self._embeds) > 0

    def mentions_tweets(self):
        return len(self._mentions) > 0

    def count_embedded_tweets(self):
        """Get the count of embedded tweets in the article."""
        return len(self._embeds)

    def count_mentioned_tweets(self):
        """Get the count of tweet mentions in the article."""
        return len(self._mentions)

    def list_embedded_tweets(self):
        """Get a list of tweets from the article."""
        return self._embeds

    def list_mentioned_tweets(self):
        """Get a list of starting positions for each of the twitter mentions in the text."""
        return self._mentions

    def _find_embeds(self):
        tweets = []
        # Twitter recommends embedding as block quotes
        blockquotes = self._html_soup.find_all('blockquote')
        for b in blockquotes:
            is_embedded_tweet = False
            # check the official way of doing it
            if b.has_attr('class') and ('twitter-tweet' in b['class']):  # this is an array of the CSS classes
                is_embedded_tweet = True
            # But we found some sites don't use that class, so check if there is a link to twitter in there.
            # In our experimentation this produces better results than just checking the class.
            links = b.find_all('a')
            twitter_url = None
            for link in links:
                if link.has_attr('href') and ('twitter.com' in link['href']):
                    is_embedded_tweet = True
                    twitter_url = link['href']
            if is_embedded_tweet:
                try:
                    info = tweet_status_url_pattern.match(twitter_url).groups()
                    tweet_info = dict(tweet_id=info[2], username=info[0], full_url=twitter_url,
                                      html_source='blockquote url pattern')
                except Exception:  # some other format
                    username_start_index = twitter_url.find('@')
                    username = twitter_url[username_start_index:-1]
                    tweet_id_start_index = twitter_url.find('/')
                    tweet_id = twitter_url[tweet_id_start_index:-1]
                    tweet_info = dict(tweet_id=tweet_id, username=username, full_url=twitter_url,
                                      html_source='blockquote url fallback')
                tweets.append(tweet_info)
        # some people do it differently, (CNN, others) embed with like this
        divs = self._html_soup.find_all('div', class_="embed-twitter")
        for d in divs:
            if d.has_attr('data-embed-id'):
                tweet_info = dict(tweet_id=d['data-embed-id'], html_source='div with data-embed-id')
                tweets.append(tweet_info)
        # check if we are looking at HTML already rendered by JS and transformed into an iframe of content
        divs = self._html_soup.find_all('div', class_="twitter-tweet-rendered")
        for d in divs:
            iframes = d.find_all('iframe')
            for iframe in iframes:
                if iframe.has_attr('data-tweet-id'):
                    tweet_info = dict(tweet_id=iframe['data-tweet-id'], html_source='rendered iframe')
                    tweets.append(tweet_info)
        return tweets

    def _validate_language(self):
        valid_languages = ['en']
        try:
            is_reliable, _, details = cld2.detect(self._content)
            detected_language = details[0][1]
            if is_reliable and (detected_language not in valid_languages):
                raise UnsupportedLanguageException(detected_language)
        except cld2.error:
            # if there was some weird unicode then assume it isn't english
            raise UnsupportedLanguageException("Undetectable")

    def _find_mentions(self):
        # self._validate_language()
        # find the first occurrence of the twitter phrase, then continue searching for the
        # next occurrence of the twitter phrase from the index of end of the current twitter phrase
        # instance until there are no more twitter phrases located
        mentions_dict_list = []
        article_text = self._content_no_tags
        for twitter_phrase in self._mentions_list:
            start_index = 0
            phrase_index = 0
            while phrase_index != -1:
                phrase_index = article_text.find(twitter_phrase, start_index)
                # this is the start index into the *content*, not the raw html
                start_index = phrase_index
                if phrase_index != -1:
                    context_start = max(0, phrase_index - MENTIONS_CONTEXT_WINDOW_SIZE)
                    context_end = min(len(article_text),
                                      phrase_index + len(twitter_phrase) + MENTIONS_CONTEXT_WINDOW_SIZE)
                    context = article_text[context_start:context_end]
                    mention_dict = {'phrase': twitter_phrase, 'context': context, 'content_start_index': start_index}
                    mentions_dict_list.append(mention_dict)
                    start_index = phrase_index + len(twitter_phrase)
        # returns a tuple of the twitter phrase count and a list of the starting indices of each of the
        # twitter phrases
        return mentions_dict_list

# modified from https://stackoverflow.com/questions/4138483/twitter-status-url-regex
tweet_status_url_pattern = re.compile('^https?:\/\/twitter\.com\/(?:#!\/)?(\w+)\/status(es)?\/(\d+).*', re.IGNORECASE)
