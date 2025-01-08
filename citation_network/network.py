"""Create a citation network based on an iterator on OpenAlex Work Objects"""

import json
import igraph as ig
from typing import Dict, Iterator, Union, List
from tqdm.auto import tqdm

from citation_network.utils import _pageIterator, _cursorIterator


def getIntegerIDFromOpenAlex(openAlexId: str):
    return int(openAlexId.split("/")[-1][1:])


def processPublicationAttributes(attributes, attributes_to_keep):
    attributes_to_keep = set(attributes_to_keep)
    attributes = {k: v for k, v in attributes.items() if k in attributes_to_keep}
    for k, v in attributes.items():
        if not isinstance(v, (int, float, str)):

            attributes[k] = json.dumps(v)
    return attributes


# TODO: Finish building a citation network
def createCitationGraph(
    entities: Union[_pageIterator, _cursorIterator, Iterator[Dict]],
    attributes_to_keep: List[str] = [
        "id",
        "doi",
        "title",
        "publication_year",
        "publication_date",
        "language",
        "is_oa",
        "authorships",
        "primary_topic",
        "abstract_inverted_index",
    ],
):
    progress = tqdm(
        total=len(entities) if hasattr(entities, "__len__") else None,
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
        attributes = processPublicationAttributes(work, attributes_to_keep)

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
