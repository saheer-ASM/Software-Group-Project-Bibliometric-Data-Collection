"""Thin, polite OpenAlex REST client.

OpenAlex is fully open (CC0), needs no API key, and imposes no cost -- the only
requirement is a `mailto` so you land in the polite pool.  Everything the sheet
asks for is available here: field/topic classification, works counts, citation
counts, h-index, and the works list needed to derive career age and
self-citation behaviour.
"""

import time

import requests

import config


class OpenAlexError(RuntimeError):
    pass


class BudgetExhausted(OpenAlexError):
    """The day's free OpenAlex budget is gone.

    The free tier is metered at 1,000 requests / $0.10 per day (see the
    X-RateLimit-* headers), resetting at midnight UTC.  Retrying is pointless,
    so this is raised immediately and the collectors stop cleanly on it --
    everything already gathered is on disk, and the next run resumes.
    """

    def __init__(self, message, reset_seconds=None):
        super().__init__(message)
        self.reset_seconds = reset_seconds

    @property
    def reset_text(self):
        if not self.reset_seconds:
            return "midnight UTC"
        hours, remainder = divmod(int(self.reset_seconds), 3600)
        return f"{hours}h {remainder // 60}m (midnight UTC)"


class OpenAlexClient:
    def __init__(self, mailto=config.OPENALEX_MAILTO,
                 api_key=config.OPENALEX_API_KEY):
        self.mailto = mailto
        self.api_key = api_key or None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})
        self.request_count = 0
        self.budget_remaining_usd = None
        self.requests_remaining = None

    def get(self, path, **params):
        """One GET against OpenAlex, with backoff on 429/5xx."""
        params["mailto"] = self.mailto
        if self.api_key:
            # A free key raises the daily allowance from $0.10 to $1.00.
            params["api_key"] = self.api_key
        url = config.OPENALEX_BASE + path
        delay = 1.0
        for attempt in range(config.MAX_RETRIES):
            time.sleep(config.REQUEST_DELAY_SECONDS)
            self.request_count += 1
            try:
                response = self.session.get(url, params=params,
                                            timeout=config.REQUEST_TIMEOUT)
            except requests.RequestException as exc:
                if attempt == config.MAX_RETRIES - 1:
                    raise OpenAlexError(f"{url}: {exc}") from exc
                time.sleep(delay)
                delay *= 2
                continue

            self._note_budget(response)

            if response.status_code == 200:
                return response.json()
            if response.status_code == 429 and self._is_budget_error(response):
                raise BudgetExhausted(
                    f"OpenAlex daily free budget exhausted "
                    f"({self.request_count} calls made this run)",
                    reset_seconds=response.headers.get("X-RateLimit-Reset"))
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay *= 2
                continue
            # 400s other than rate limiting are our bug, not a transient issue.
            raise OpenAlexError(
                f"{response.status_code} {url} :: {response.text[:300]}")
        raise OpenAlexError(f"gave up after {config.MAX_RETRIES} tries: {url}")

    def _note_budget(self, response):
        remaining = response.headers.get("X-RateLimit-Remaining-USD")
        if remaining is not None:
            try:
                self.budget_remaining_usd = float(remaining)
            except ValueError:
                pass
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            try:
                self.requests_remaining = int(remaining)
            except ValueError:
                pass

    @staticmethod
    def _is_budget_error(response):
        """A budget 429 is permanent for the day; a throughput 429 is not."""
        try:
            payload = response.json()
        except ValueError:
            return "insufficient budget" in response.text.lower()
        if payload.get("dailyRemainingUsd") == 0:
            return True
        return "insufficient budget" in str(payload.get("message", "")).lower()

    def paged(self, path, per_page=200, max_items=None, **params):
        """Cursor-paged iteration (the only way past OpenAlex's 10k page cap)."""
        cursor = "*"
        seen = 0
        while cursor:
            page = self.get(path, per_page=per_page, cursor=cursor, **params)
            for item in page.get("results", []):
                yield item
                seen += 1
                if max_items is not None and seen >= max_items:
                    return
            cursor = page.get("meta", {}).get("next_cursor")

    # ------------------------------------------------------------------ lookups
    AUTHOR_SELECT = ("id,display_name,orcid,works_count,cited_by_count,"
                     "summary_stats,affiliations,last_known_institutions,topics")

    def sample_authors(self, author_filter, size, seed):
        """Random sample of authors matching a filter (OpenAlex-side sampling)."""
        collected = []
        page_size = min(200, size)
        pages = (size + page_size - 1) // page_size
        for page_number in range(1, pages + 1):
            page = self.get("/authors", filter=author_filter, sample=size,
                            seed=seed, per_page=page_size, page=page_number,
                            select=self.AUTHOR_SELECT)
            results = page.get("results", [])
            collected.extend(results)
            if len(results) < page_size:
                break
        return collected

    def author_by_orcid(self, orcid):
        """Singleton lookup -- 1 credit, versus 10 for the equivalent filter."""
        try:
            return self.get(f"/authors/orcid:{orcid}", select=self.AUTHOR_SELECT)
        except BudgetExhausted:
            raise
        except OpenAlexError:
            return None      # 404 for an ORCID OpenAlex does not know

    def author_search(self, display_name):
        """Name fallback for laureates with no ORCID.

        This is a *search* request at $0.001 -- ten times a filter call -- so it
        is deliberately the last resort, tried only after the ORCID lookup.
        """
        page = self.get("/authors", search=display_name, per_page=5,
                        select=self.AUTHOR_SELECT)
        return page.get("results", [])

    def first_publication_year(self, author_id):
        page = self.get("/works", filter=f"authorships.author.id:{author_id}",
                        sort="publication_year:asc", per_page=1,
                        select="id,publication_year")
        results = page.get("results", [])
        if not results:
            return None
        return results[0].get("publication_year")

    def author_works(self, author_id, max_items, oldest_first=False):
        """Works by one author, with their reference lists."""
        order = "asc" if oldest_first else "desc"
        return list(self.paged("/works",
                               filter=f"authorships.author.id:{author_id}",
                               sort=f"publication_year:{order}",
                               per_page=min(200, max_items),
                               max_items=max_items,
                               select="id,publication_year,referenced_works"))


def short_id(openalex_url):
    """'https://openalex.org/A5062182194' -> 'A5062182194'."""
    if not openalex_url:
        return None
    return openalex_url.rstrip("/").split("/")[-1]
