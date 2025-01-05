import urllib.parse
import requests
import urllib
import time
import math
from typing import Dict, Optional
import logging


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def timeit(func):
    """Decorator to log execution time of functions."""

    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"{func.__name__} executed in {end_time - start_time:.6f} seconds")
        return result

    return wrapper


@timeit
def makeOAAPICall(
    entityType, parameters, session: requests.Session = None, rateInterval=0.0
):
    paramsEncoded = urllib.parse.urlencode(parameters)
    requestURL = f"https://api.openalex.org/{entityType}?{paramsEncoded}"
    logger.debug(f"Making API request: {requestURL}")

    if rateInterval > 0.0:
        logger.debug(f"Sleeping for {rateInterval} seconds before API call...")
        time.sleep(rateInterval)

    if session is None:
        session = requests.Session()

    try:

        response = session.get(requestURL).json()

        if "meta" not in response or "error" in response:
            if "error" in response and "message" in response:
                errorMessage = f"{response["error"]} -- {response["message"]}"
            else:
                errorMessage = f"Unknown Error\n Response: {response}"

            logger.error(f"OpenAlex API Error: {errorMessage}")
            raise Exception(
                f'Error in OpenAlex API call for "{entityType}":\nInput: {parameters}\n\tURL: {requestURL}\n\tResponse: {errorMessage}'
            )
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Request failed: {e}")
        raise


class _pageIterator:
    def __init__(
        self,
        entityType,
        parameters,
        totalEntries,
        totalEntriesPerPage,
        totalPages,
        rateInterval,
    ):
        self._entityType = entityType
        self._parameters = parameters.copy()
        self._totalEntries = totalEntries
        self._totalEntriesPerPage = totalEntriesPerPage
        self._totalPages = totalPages
        self._rateInterval = rateInterval

    def __iter__(self):
        self._processedEntries = 0
        for page in range(1, self._totalPages + 1):
            logger.info(f"Fetching page {page}/{self._totalPages}")

            self._parameters["page"] = page
            self._parameters["per_page"] = self._totalEntriesPerPage
            responsePage = makeOAAPICall(
                self._entityType, self._parameters, rateInterval=self._rateInterval
            )
            shouldBreak = False
            for pageEntry in responsePage["results"]:
                if self._processedEntries < self._totalEntries:
                    self._processedEntries += 1
                    yield pageEntry
                else:
                    shouldBreak = True
                    break
            if shouldBreak:
                break

    def __len__(self):
        return self._totalEntries


class _cursorIterator:
    def __init__(
        self,
        entityType,
        parameters,
        totalEntries,
        totalEntriesPerPage,
        totalPages,
        rateInterval,
    ):
        self._entityType = entityType
        self._parameters = parameters
        self._totalEntries = totalEntries
        self._totalEntriesPerPage = totalEntriesPerPage
        self._totalPages = totalPages
        self._rateInterval = rateInterval
        self._parameters["cursor"] = "*"
        self._processedEntries = 0

    def __iter__(self):
        self._parameters["per_page"] = self._totalEntriesPerPage
        while True:
            response = makeOAAPICall(
                self._entityType, self._parameters, rateInterval=self._rateInterval
            )
            shouldBreak = False
            for pageEntry in response["results"]:
                self._processedEntries += 1
                if self._processedEntries > self._totalEntries:
                    shouldBreak = True
                    break
                yield pageEntry
            if (
                shouldBreak
                or "next_cursor" not in response["meta"]
                or not response["meta"]["next_cursor"]
            ):
                break
            self._parameters["cursor"] = response["meta"]["next_cursor"]

    def __len__(self):
        return self._totalEntries


class OAApi:
    def __init__(self, email=None):
        self.email = email
        self.session = requests.Session()

    @classmethod
    def getFilterString(cls, filters: Dict[str, str]):
        filtersList = []
        for filter, value in filters.items():
            filtersList.append(f"{filter}:{value}")
        return ",".join(filtersList)

    def getEntities(
        self,
        filter: Dict[Optional[str], Optional[str]] = {},
        search="",
        sort=[],
        maxEntities=10000,
        rateInterval=0.0,
    ):
        parameters = {}
        if filter:
            parameters["filter"] = self.__class__.getFilterString(filter)

        if search:
            parameters["search"] = search

        if sort:
            parameters["sort"] = ",".join(sort)

        if self.email:
            parameters["mailto"] = self.email

        parametersFirstCall = {**parameters, "per_page": 200, "page": ""}
        firstResponse = makeOAAPICall(
            entityType="works", parameters=parametersFirstCall, session=self.session
        )
        totalEntries = int(firstResponse["meta"]["count"])

        if totalEntries > maxEntities and maxEntities >= 0:
            import warnings

            warnings.warn(
                f"Number of entities ({totalEntries}) in OpenAlex is larger than the maximum allowed ({maxEntities}). Only the first {maxEntities} entities will be returned. You can set the maximum number of entities to be returned by setting maxEntities=yourNumber. To ignore this warning, set ignoreEntitiesLimitWarning=True.",
                stacklevel=2,
            )
            totalEntries = maxEntities
        totalEntriesPerPage = int(firstResponse["meta"]["per_page"])
        numberOfPages = math.ceil(totalEntries / totalEntriesPerPage)

        logger.info("Finished first API call, returning iterator.")
        logger.info(
            f"Total entities found: {totalEntries}, Pages to fetch: {numberOfPages}"
        )
        if totalEntries <= 10000:
            return _pageIterator(
                "works",
                parameters,
                totalEntries,
                totalEntriesPerPage,
                numberOfPages,
                rateInterval,
            )

        else:
            return _cursorIterator(
                "works",
                parameters,
                totalEntries,
                totalEntriesPerPage,
                numberOfPages,
                rateInterval,
            )
