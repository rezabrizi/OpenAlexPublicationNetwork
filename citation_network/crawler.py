"""Crawling OpenAlex either via general search or citation BFS"""

from collections import deque
import math
from typing import Dict, Optional, List, Iterator, Union

from citation_network.utils import OAAPI, _pageIterator, _cursorIterator
from citation_network import log_context
import logging


logger = logging.getLogger(__name__)


class EntitiesCrawler:
    def __init__(self, email=None):
        self.email = email
        self._api = OAAPI()

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
    ) -> Union[_pageIterator, _cursorIterator]:
        self._api.profiler.reset()
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
        firstResponse = self._api.makeOAAPICall(
            entityType="works", parameters=parametersFirstCall
        )

        if not firstResponse:
            raise Exception("Error in getting a response from OpenAlex API")

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

        logger.debug("Finished first API call, returning iterator.")
        logger.info(
            f"Total entities found: {totalEntries}, Pages to fetch: {numberOfPages}"
        )
        if totalEntries <= 10000:
            return _pageIterator(
                self._api,
                "works",
                parameters,
                totalEntries,
                totalEntriesPerPage,
                numberOfPages,
                rateInterval,
            )

        else:
            return _cursorIterator(
                self._api,
                "works",
                parameters,
                totalEntries,
                totalEntriesPerPage,
                numberOfPages,
                rateInterval,
            )

    def citationBFS(
        self, root: List[str], maxLevels=10, maxNodes=10000
    ) -> Iterator[dict]:
        """Performs BFS on OpenAlex citations, up to a certain depth and node limit."""
        self._api.profiler.reset()
        queue = deque([(r, 0) for r in root])  # (publication_id, level)
        numNodesProcessed = 0  # Track number of processed nodes
        visited = set(root)

        while queue:
            if maxNodes is not None and numNodesProcessed >= maxNodes:
                break  # Stop if maxNodes limit is reached

            current_publication_id, level = queue.popleft()
            if level >= maxLevels:
                continue  # Stop expanding deeper
            with log_context({"WID": current_publication_id}):
                response = self._api.makeOASingleWorksCall(
                    current_publication_id, mailto=self.email
                )

            # TODO (reza): Add functionality to provide a report on the dataset such as
            #   WIDs that didn't return a response
            if not response:
                logger.error(
                    f"Error while getting works object for {current_publication_id}."
                )
                continue

            if "referenced_works" not in response:
                logger.error(
                    f"This work has no referenced works {current_publication_id}"
                )
                continue

            numNodesProcessed += 1

            for referenced_work in response["referenced_works"]:
                referenced_id = referenced_work.split("/")[-1]  # Extract ID
                if referenced_id not in visited:
                    visited.add(referenced_id)
                    queue.append((referenced_id, level + 1))
            yield response
