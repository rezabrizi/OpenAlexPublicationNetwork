import requests


class OAApi:
    def __init__(self):
        self.session = requests.Session()

    @classmethod
    def getFilterString(cls, filters):
        filtersList = []
        for filter, value in filters:
            filtersList.append(f"{filter}:{value}")
        return ",".join(filtersList)

    def getEntities(
        self,
        filter={},
        search="",
        maxEntities=10000,
    ):
        parameters = {}
        if filter:
            parameters["filter"] = self.__class__.getFilterString(filter)
