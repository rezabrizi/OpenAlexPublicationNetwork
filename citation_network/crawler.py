import requests
from collections import deque
import json
import igraph as ig
import math
from typing import Dict, Optional, Union, List, Iterator
from tqdm.auto import tqdm

from citation_network.utils import *
import logging


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def getIntegerIDFromOpenAlex(openAlexId: str):
    return int(openAlexId.split("/")[-1][1:])


class EntitiesCrawler:
    def __init__(self, email=None):
        self.email = email
        self.session = requests.Session()
        self._api = _OAAPI()

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
        self, root: List[str], maxLevels=100, maxNodes=None
    ) -> Iterator[dict]:
        """Performs BFS on OpenAlex citations, up to a certain depth and node limit."""
        queue = deque([(r, 0) for r in root])  # (publication_id, level)
        numNodesProcessed = 0  # Track number of processed nodes

        while queue:
            if maxNodes is not None and numNodesProcessed >= maxNodes:
                break  # Stop if maxNodes limit is reached

            current_publication_id, level = queue.popleft()
            print(level)
            if level >= maxLevels:
                continue  # Stop expanding deeper

            response = self._api.makeOASingleWorksCall(current_publication_id)

            numNodesProcessed += 1

            if not response or "referenced_works" not in response:
                logger.error(current_publication_id, " didn't return anything")
                continue
            for referenced_work in response["referenced_works"]:
                referenced_id = referenced_work.split("/")[-1]  # Extract ID
                queue.append((referenced_id, level + 1))
            yield response  # Return the current publication


########## CREATE NETWORK


# Attributes to keep
#   id
#   doi
#   title
#   publication_year
#   publication_date
#   language
#   is_oa
#   author(s)
#   primary_topic
#   abstract_inverted_index


def processPublicationAttributes(attributes):
    attributes_to_keep = set(["id", "doi", "title"])
    attributes = {k: v for k, v in attributes.items() if k in attributes_to_keep}
    for k, v in attributes.items():
        if not isinstance(v, (int, float, str)):
            attributes[k] = json.dumps(v)
    return attributes


# TODO: Finish building a citation network
def createCitationGraph(entities: Union[_pageIterator, _cursorIterator]):
    progress = tqdm(
        total=len(entities),
        desc="Creating the citation graph",
        leave=False,
        dynamic_ncols=True,
    )

    nodeAttributes = {}
    nodeReferences = []
    oaIntID2Index = {}
    index2oaIntID = []

    for work in entities:
        progress.update(1)

        oaIntegerID = getIntegerIDFromOpenAlex(work["id"])
        attributes = processPublicationAttributes(work)

        oaIntID2Index[oaIntegerID] = len(index2oaIntID)
        index2oaIntID.append(oaIntegerID)
        nodeReferences.append(
            [
                getIntegerIDFromOpenAlex(referenced_work)
                for referenced_work in work["referenced_works"]
            ]
        )

        for k, v in attributes.items():
            if k not in nodeAttributes:
                nodeAttributes[k] = []
            nodeAttributes[k].append(v)

    progress.close()

    citationEdges = []
    for pub_idx, references in enumerate(nodeReferences):
        for reference in references:
            if reference in oaIntID2Index:
                citationEdges.append((pub_idx, oaIntID2Index[reference]))
    g = ig.Graph(
        n=len(index2oaIntID),
        edges=citationEdges,
        directed=True,
        vertex_attrs=nodeAttributes,
    )

    return g
