import logging
from citation_network.utils.utils import OAAPI


logger = logging.getLogger()


class _pageIterator:
    def __init__(
        self,
        api: OAAPI,
        entityType,
        parameters,
        totalEntries,
        totalEntriesPerPage,
        totalPages,
        rateInterval,
    ):
        self._entityType = entityType
        self._api = api
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
            responsePage = self._api.makeOAAPICall(
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
        api: OAAPI,
        entityType,
        parameters,
        totalEntries,
        totalEntriesPerPage,
        totalPages,
        rateInterval,
    ):
        self._api = api
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
            response = self._api.makeOAAPICall(
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
