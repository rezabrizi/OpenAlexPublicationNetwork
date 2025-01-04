import urllib.parse
import requests
import urllib
import time
import math
from typing import Dict, Optional


def makeOAAPICall(entityType, parameters, session: requests.Session, rateInterval=0.0):
    paramsEncoded = urllib.parse.urlencode(parameters)
    requestURL = f"https://api.openalex.org/{entityType}?{paramsEncoded}"
    if rateInterval > 0.0:
        time.sleep(rateInterval)

    if session is None:
        raise Exception("session invalid in API call")

    response = session.get(requestURL).json()

    if "meta" not in response or "error" in response:
        errorMessage = response
        if "error" in response and "message" in response:
            errorMessage = f"{response["error"]} -- {response["message"]}"
        raise Exception(
            f'Error in OpenAlex API call for "{entityType}":\nInput: {parameters}\n\tURL: {requestURL}\n\tResponse: {errorMessage}'
        )

    return response


class OAApi:
    def __init__(self, email=None):
        self.email = email
        self.session = requests.Session()

    @classmethod
    def getFilterString(cls, filters):
        filtersList = []
        for filter, value in filters:
            filtersList.append(f"{filter}:{value}")
        return ",".join(filtersList)

    def getEntities(
        self,
        filter: Dict[Optional[str], Optional[str]] = {},
        search="",
        sort=[],
        maxEntities=10000,
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

        parametersFirstCall = {**parameters, "per-page": 200, "page": ""}
        firstResponse = makeOAAPICall(
            entityType="works", parameters=parametersFirstCall
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

        if totalEntries <= 10000:
            return  ## Need to return a page iterator

        else:
            return  ## Need to return a cursor iterator
