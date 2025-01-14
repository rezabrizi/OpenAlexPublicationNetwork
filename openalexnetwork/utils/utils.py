"""Utilities for the OpenAlex Crawler"""

import csv
import igraph as ig
import json
import logging
import os.path as osp
import requests
import time
from typing import Any, Dict, Optional
import urllib.parse

logger = logging.getLogger(__name__)


class _APIProfiler:
    def __init__(self):
        self._total_api_time = 0.0
        self._api_call_count = 0.0
        self._error_count = {}

    def reset(self):
        self._total_api_time = 0.0
        self._api_call_count = 0.0
        self._error_count.clear()

    def track(self, start, end):
        self._total_api_time += end - start
        self._api_call_count += 1

    def track(self, **kwargs):
        if "start_time" and "end_time" in kwargs:
            self._total_api_time += kwargs["end_time"] - kwargs["start_time"]
            self._api_call_count += 1
        elif "error" in kwargs:
            if kwargs["error"] not in self._error_count:
                self._error_count[kwargs["error"]] = 0
            self._error_count[kwargs["error"]] += 1
        else:
            raise NotImplementedError(
                "Only supporting time tracking and error tracking"
            )

    def get_summary(self):
        avg_time = (
            self._total_api_time / self._api_call_count
            if self._api_call_count > 0
            else 0
        )
        return {
            "total_time": self._total_api_time,
            "api_calls": self._api_call_count,
            "average_time": avg_time,
            "Errors": self._error_count,
        }


class OAAPI:
    def __init__(self):
        self._session: requests.Session = requests.Session()
        self.profiler: _APIProfiler = _APIProfiler()

    def makeOAAPICall(
        self,
        entityType,
        parameters,
        rateInterval=0.0,
    ) -> Dict[str, Any]:

        paramsEncoded = urllib.parse.urlencode(parameters)
        requestURL = f"https://api.openalex.org/{entityType}?{paramsEncoded}"
        response = self._makeOARawRequest(requestURL, rateInterval=rateInterval)

        if not response:
            raise Exception(f"Failed OpenAlex API call: {requestURL}")

        if "meta" not in response or "error" in response:
            if "error" in response and "message" in response:
                errorMessage = f'{response["error"]} -- {response["message"]}'
            else:
                errorMessage = f"Unknown Error\n Response: {response}"
            if "meta" not in response:
                self.profiler.track(error="NA_Meta_in_response")
            if "error" in response:
                self.profiler.track(error=response["error"])
            logger.error(f"OpenAlex API Error: {errorMessage}")
            raise Exception(
                f'Error in OpenAlex API call for "{entityType}":\nInput: {parameters}\n\tResponse: {errorMessage}'
            )
        return response

    def makeOASingleWorksCall(self, workID, mailto=None) -> Optional[Dict[str, Any]]:
        """Calls OpenAlex API for a single work and handles errors gracefully."""
        requestURL = f"https://api.openalex.org/works/{workID}"
        if mailto:
            requestURL = f"{requestURL}?mailto={mailto}"

        return self._makeOARawRequest(requestURL)

    def _makeOARawRequest(
        self, requestURL, retries=3, backoff=2.0, rateInterval=0.0
    ) -> Optional[Dict[str, Any]]:
        """Calls OpenAlex API for a single work and handles errors gracefully."""

        logger.debug(f"Making API request: {requestURL}")

        if rateInterval > 0.0:
            logger.debug(f"Sleeping for {rateInterval} seconds before API call...")
            time.sleep(rateInterval)

        if self._session is None:
            self._session = requests.Session()
        # Track each API call from when the first attempt is made
        start_time = time.time()
        for attempt in range(1, retries + 1):
            logger.debug(f"Individual Works OA API Attempt: {attempt} of {retries}")
            try:
                response = self._session.get(requestURL)

                # Check HTTP status before calling .json()
                if response.status_code == 200:
                    end_time = time.time()
                    self.profiler.track(start_time=start_time, end_time=end_time)

                    try:
                        return response.json()
                    except requests.exceptions.JSONDecodeError:
                        self.profiler.track(error="JSONDecodeError")
                        logger.error(
                            f"Failed to decode JSON from OpenAlex API. Response: {response.text}"
                        )
                        return None  # Prevent crashing

                elif response.status_code == 429:  # Rate Limit Exceeded
                    logger.warning(
                        f"Rate limit hit (HTTPS 429). Retrying in {backoff} seconds..."
                    )
                    self.profiler.track(error=response.status_code)
                    time.sleep(backoff)
                    backoff *= 2

                elif response.status_code >= 500:  # Server Errors
                    logger.error(f"Server error ({response.status_code}). Retrying...")
                    self.profiler.track(error=response.status_code)
                    time.sleep(backoff)

                else:
                    logger.error(
                        f"API request failed with status {response.status_code}: {response.text}"
                    )
                    self.profiler.track(error=response.status_code)
                    return None  # Return None to prevent further failures

            except requests.exceptions.RequestException as e:
                logger.error(f"HTTP Request failed: {e}")
                self.profiler.track(error=e)
                time.sleep(backoff)

        logger.error(f"Max retries reached for {requestURL}. Skipping this work.")
        return None


def save_citation_graph_to_csv(csv_handle: str, graph: ig.Graph) -> None:
    attributes_titles = graph.vs.attributes()

    with open(csv_handle, "w", newline="") as f:
        writer = csv.writer(f)

        header = ["pub", "references"] + attributes_titles
        writer.writerow(header)

        for v in graph.vs:
            node_idx = v.index
            children = [str(reference.index) for reference in v.successors()]

            children_str = ":".join(children) if children else ""
            attributes = [
                v[attr] if v[attr] is not None else "" for attr in attributes_titles
            ]

            writer.writerow([node_idx, children_str] + attributes)


def create_citation_graph_from_csv(csv_handler) -> ig.Graph:
    if not osp.exists(csv_handler):
        raise FileNotFoundError(f"File {csv_handler} does not exists")

    citationEdges = []
    nodeAttributes = {}
    nodes = set()

    with open(csv_handler, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "pub" not in row or "references" not in row:
                raise KeyError(
                    'The CSV must have the source node in the "pub" column and the references in the "references" column'
                )
            node_idx = int(row["pub"])
            nodes.add(node_idx)
            references = (
                [int(ref) for ref in row["references"].split(":")]
                if row["references"]
                else []
            )

            for reference in references:
                citationEdges.append((node_idx, reference))

            for k, v in row.items():
                if k == "pub" or k == "references":
                    continue
                if k not in nodeAttributes:
                    nodeAttributes[k] = []
                if k == "publication_year":
                    v = int(v)
                if k in {"authorships", "primary_topic", "abstract_inverted_index"}:
                    v = json.loads(v)
                nodeAttributes[k].append(v)

        g = ig.Graph(
            n=len(nodes),
            edges=citationEdges,
            directed=True,
            vertex_attrs=nodeAttributes,
        )
    return g


def timeit(func):
    """Decorator to log execution time of functions."""

    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"{func.__name__} executed in {end_time - start_time:.6f} seconds")
        return result

    return wrapper
